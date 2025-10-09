import re
import json
from typing import Any, Dict, List
from pathlib import Path

import pymysql
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from datetime import datetime, timedelta, date
from sqlglot import exp, parse_one
from sqlglot.errors import ParseError


def create_medical_tools(
    *,
    db_host: str,
    db_user: str,
    db_password: str,
    db_name: str,
    db_port: int,
    session_contexts: Dict[str, Dict[str, Any]],
    current_session_id_ctx,
    llm_nontool,
) -> List[StructuredTool]:
    """Create local medical data tools.

    Args:
    - db_host/db_user/db_password/db_name/db_port: database connection configs
    - session_contexts: session context map keyed by session_id
    - current_session_id_ctx: contextvars.ContextVar for current session id
    - llm_nontool: reserved (no longer used)
    """

    def _fetch_allowed_tables() -> set:
        allowed = set()
        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = %s AND LOWER(COLUMN_NAME) = 'msid' GROUP BY TABLE_NAME",
                    (db_name,),
                )
                for row in cur.fetchall():
                    allowed.add(row["TABLE_NAME"])
        return allowed

    def _list_tables_with_current_msid() -> List[str]:
        """Return table names (having msid column) that contain rows for current msid."""
        session_id = current_session_id_ctx.get()
        ctx = session_contexts.get(session_id) or {}
        msid_value = ctx.get("msid")
        if msid_value is None:
            raise ValueError("Missing access scope, query denied.")

        all_allowed_tables = _fetch_allowed_tables()

        accessible_tables: List[str] = []
        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn:
            with conn.cursor() as cur:
                for table_name in all_allowed_tables:
                    try:
                        cur.execute(f"SELECT 1 FROM `{table_name}` WHERE msid = %s LIMIT 1", (msid_value,))
                        if cur.fetchone():
                            accessible_tables.append(table_name)
                    except Exception:
                        # 出错跳过该表
                        continue
        return sorted(accessible_tables)

    class MedicalQueryArgs(BaseModel):
        sql: str = Field(description="AI-generated SELECT/restricted SHOW statement. Access scope handled automatically by system.")

    def medical_query_impl(sql: str) -> Dict[str, Any]:
        session_id = current_session_id_ctx.get()
        ctx = session_contexts.get(session_id) or {}
        msid_value = ctx.get("msid")
        if msid_value is None:
            raise ValueError("Missing access scope, query denied.")

        # 直接使用 AI 生成的 SQL，智能追加访问限制（不再调用 LLM 重写）
        sql_stripped = str(sql or "").strip()
        sql_norm = re.sub(r"\s+", " ", sql_stripped).lower()

        if sql_norm.startswith("show tables"):
            tables_with_scope = _list_tables_with_current_msid()
            return {"ok": True, "tables": tables_with_scope}

        if not (
            sql_norm.startswith("select ")
            or sql_norm.startswith("show columns from ")
            or sql_norm.startswith("describe ")
        ):
            raise ValueError("Only SELECT and SHOW COLUMNS/DESCRIBE statements are allowed")

        allowed_tables = _fetch_allowed_tables()
        allowed_lookup = {t.lower() for t in allowed_tables}

        if sql_norm.startswith("show columns from ") or sql_norm.startswith("describe "):
            pattern = re.compile(r"(?:show columns from|describe)\s+([`\w\.]+)", re.IGNORECASE)
            match = pattern.search(sql_stripped)
            table_name = ""
            if match:
                table_name = match.group(1).strip('`')
            if not table_name:
                raise ValueError("SHOW/DESCRIBE must specify a supported table name")
            table_key = table_name.lower()
            matching_table = next((name for name in allowed_tables if name.lower() == table_key), None)
            if matching_table is None:
                raise ValueError("Table is not accessible or does not exist")
            table = matching_table
            conn = pymysql.connect(
                host=db_host,
                user=db_user,
                password=db_password,
                database=db_name,
                port=db_port,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
            )
            with conn:
                with conn.cursor() as cur:
                    cur.execute(f"DESCRIBE `{table}`")
                    rows = [r for r in cur.fetchall() if str(r.get('Field', '')).lower() != 'msid']
            return {"ok": True, "rows": rows}

        try:
            parsed_query = parse_one(sql_stripped, read="mysql")
        except ParseError as exc:
            raise ValueError(f"Invalid SQL syntax: {exc}") from exc

        referenced_tables = set()
        for table_expr in parsed_query.find_all(exp.Table):
            table_name = (table_expr.name or "").strip()
            if table_name:
                referenced_tables.add(table_name)
        if referenced_tables and any((name.lower() not in allowed_lookup) for name in referenced_tables):
            raise ValueError("Only supported tables can be accessed")

        parameters: List[Any] = []

        def _inject_scope_conditions(select_node: exp.Select):
            from_clause = select_node.args.get("from")
            if not from_clause:
                return

            table_nodes: List[exp.Table] = []

            primary = from_clause.this
            if isinstance(primary, exp.Table):
                table_nodes.append(primary)

            for join_expr in select_node.args.get("joins") or []:
                join_target = getattr(join_expr, "this", None)
                if isinstance(join_target, exp.Table):
                    table_nodes.append(join_target)

            # Deduplicate by alias (or table name when alias is absent)
            dedup_nodes: List[exp.Table] = []
            seen_aliases = set()
            for table_node in table_nodes:
                alias_or_name = table_node.alias_or_name or table_node.name
                if not alias_or_name:
                    continue
                key = alias_or_name.lower()
                if key in seen_aliases:
                    continue
                seen_aliases.add(key)
                dedup_nodes.append(table_node)

            scope_conditions: List[exp.Expression] = []
            for table_node in dedup_nodes:
                table_name = (table_node.name or "").lower()
                if table_name and table_name not in allowed_lookup:
                    raise ValueError("Only supported tables can be accessed")
                if not table_name:
                    continue
                scope_conditions.append(
                    exp.EQ(
                        this=exp.column("msid", table=table_node.alias_or_name or table_node.name),
                        expression=exp.Var(this="%s"),
                    )
                )
                parameters.append(msid_value)

            if not scope_conditions:
                return

            combined_condition = scope_conditions[0]
            for extra_condition in scope_conditions[1:]:
                combined_condition = exp.and_(combined_condition, extra_condition)

            existing_where = select_node.args.get("where")
            if existing_where:
                combined_condition = exp.and_(existing_where.this, combined_condition)
                existing_where.set("this", combined_condition)
            else:
                select_node.set("where", exp.Where(this=combined_condition))

        for select_expr in parsed_query.find_all(exp.Select):
            _inject_scope_conditions(select_expr)

        sql_final = parsed_query.sql(dialect="mysql")

        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql_final, parameters)
                rows = cur.fetchall()

        for row in rows:
            if 'msid' in row:
                del row['msid']
        return {"ok": True, "rows": rows}

    def show_tables_tool_impl() -> Dict[str, Any]:
        tables_with_scope = _list_tables_with_current_msid()
        
        # 加载表描述
        descriptions_path = Path(__file__).parent / "table_descriptions.json"
        table_descriptions = {}
        if descriptions_path.exists():
            try:
                with open(descriptions_path, 'r', encoding='utf-8') as f:
                    table_descriptions = json.load(f)
            except Exception:
                # 如果加载失败，使用空字典
                table_descriptions = {}
        
        # 构建带描述的表列表
        tables_with_descriptions = [
            {
                "name": table,
                "description": table_descriptions.get(table, "No description available")
            }
            for table in tables_with_scope
        ]
        
        return {"ok": True, "tables": tables_with_descriptions}

    class DescribeTableArgs(BaseModel):
        table_name: str = Field(description="Table name to examine")

    def descripttables_impl(table_name: str) -> Dict[str, Any]:
        table = str(table_name).strip('`')
        allowed = _fetch_allowed_tables()
        if table not in allowed:
            raise ValueError("Table is not accessible or does not exist")

        session_id = current_session_id_ctx.get()
        ctx_local = session_contexts.get(session_id) or {}
        effective_scope = ctx_local.get("msid")
        if effective_scope is None:
            raise ValueError("Missing access scope")

        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"DESCRIBE `{table}`")
                schema_rows = [r for r in cur.fetchall() if str(r.get('Field', '')).lower() != 'msid']

        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM `{table}` WHERE msid = %s ORDER BY RAND() LIMIT 4", (effective_scope,))
                sample_rows = cur.fetchall()
        for row in sample_rows:
            if 'msid' in row:
                del row['msid']

        return {"ok": True, "table": table, "schema": schema_rows, "sample_rows": sample_rows}

    # patient_info_by_id 工具已移除（通过 medical_query 可直接查询按 ID 的数据）

    def patient_count_stats_impl() -> Dict[str, Any]:
        """Summarize patient counts and distributions under current msid."""
        session_id = current_session_id_ctx.get()
        ctx = session_contexts.get(session_id) or {}
        scope_value = ctx.get("msid")
        if scope_value is None:
            raise ValueError("Missing access scope, query denied.")

        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
        
        try:
            with conn:
                with conn.cursor() as cur:
                    # 1. 统计总病人数
                    cur.execute(
                        "SELECT COUNT(DISTINCT usubjid) as total_patients FROM patient_adsl WHERE msid = %s",
                        (scope_value,)
                    )
                    total_result = cur.fetchone()
                    total_patients = total_result['total_patients'] if total_result else 0
                    
                    # 2. 性别分布统计
                    cur.execute(
                        "SELECT sex, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND sex IS NOT NULL GROUP BY sex ORDER BY count DESC",
                        (scope_value,)
                    )
                    sex_distribution = cur.fetchall()
                    
                    # 3. 年龄组分布统计
                    cur.execute(
                        "SELECT agegr1 as age_group, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND agegr1 IS NOT NULL GROUP BY agegr1 ORDER BY count DESC",
                        (scope_value,)
                    )
                    age_distribution = cur.fetchall()
                    
                    # 4. 治疗组分布统计
                    cur.execute(
                        "SELECT trt01p as treatment, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND trt01p IS NOT NULL GROUP BY trt01p ORDER BY count DESC",
                        (scope_value,)
                    )
                    treatment_distribution = cur.fetchall()
                    
                    # 5. 种族分布统计
                    cur.execute(
                        "SELECT race, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND race IS NOT NULL GROUP BY race ORDER BY count DESC",
                        (scope_value,)
                    )
                    race_distribution = cur.fetchall()
                    
                    # 6. 研究状态统计
                    cur.execute(
                        "SELECT eosstt as study_status, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND eosstt IS NOT NULL GROUP BY eosstt ORDER BY count DESC",
                        (scope_value,)
                    )
                    status_distribution = cur.fetchall()
                    
                    # 7. BMI分组统计
                    cur.execute(
                        "SELECT bmiblgr1 as bmi_group, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND bmiblgr1 IS NOT NULL GROUP BY bmiblgr1 ORDER BY count DESC",
                        (scope_value,)
                    )
                    bmi_distribution = cur.fetchall()
                    
                    # 8. 研究中心分布统计
                    cur.execute(
                        "SELECT siteid as site_id, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND siteid IS NOT NULL GROUP BY siteid ORDER BY count DESC",
                        (scope_value,)
                    )
                    site_distribution = cur.fetchall()
                    
                    # 9. 停药原因分布统计
                    cur.execute(
                        "SELECT dcsreas as discontinuation_reason, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND dcsreas IS NOT NULL GROUP BY dcsreas ORDER BY count DESC",
                        (scope_value,)
                    )
                    discontinuation_distribution = cur.fetchall()
                    
                    # 10. 地区分层因子统计（美国 vs 世界其他地区）
                    cur.execute(
                        "SELECT strat1g as region, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND strat1g IS NOT NULL GROUP BY strat1g ORDER BY count DESC",
                        (scope_value,)
                    )
                    region_distribution = cur.fetchall()
                    
                    # 11. ECOG评分基线统计
                    cur.execute(
                        "SELECT ecogbl as ecog_score, COUNT(DISTINCT usubjid) as count FROM patient_adsl WHERE msid = %s AND ecogbl IS NOT NULL GROUP BY ecogbl ORDER BY count DESC",
                        (scope_value,)
                    )
                    ecog_distribution = cur.fetchall()
                    
                    # 12. 基本年龄统计
                    cur.execute(
                        "SELECT AVG(age) as avg_age, MIN(age) as min_age, MAX(age) as max_age FROM patient_adsl WHERE msid = %s AND age IS NOT NULL",
                        (scope_value,)
                    )
                    age_stats = cur.fetchone()
                    
        except Exception as e:
            raise ValueError(f"查询病人统计信息时出错: {str(e)}")
        
        return {
            "ok": True,
            "total_patients": total_patients,
            "statistics": {
                "sex_distribution": list(sex_distribution) if sex_distribution else [],
                "age_group_distribution": list(age_distribution) if age_distribution else [],
                "treatment_distribution": list(treatment_distribution) if treatment_distribution else [],
                "race_distribution": list(race_distribution) if race_distribution else [],
                "study_status_distribution": list(status_distribution) if status_distribution else [],
                "bmi_distribution": list(bmi_distribution) if bmi_distribution else [],
                "site_distribution": list(site_distribution) if site_distribution else [],
                "discontinuation_distribution": list(discontinuation_distribution) if discontinuation_distribution else [],
                "region_distribution": list(region_distribution) if region_distribution else [],
                "ecog_distribution": list(ecog_distribution) if ecog_distribution else [],
                "age_stats": {
                    "average_age": round(float(age_stats['avg_age']), 1) if age_stats and age_stats['avg_age'] else None,
                    "min_age": age_stats['min_age'] if age_stats else None,
                    "max_age": age_stats['max_age'] if age_stats else None
                }
            }
        }


    class AdverseEventAnalysisArgs(BaseModel):
        ae_name: str = Field(description="Adverse event name to analyze (supports fuzzy match)")
        days_before: int = Field(default=3, description="Days window before AE onset to check medications (default 3)")

    def adverse_event_analysis_impl(ae_name: str, days_before: int = 3) -> Dict[str, Any]:
        """Analyze association between a specific adverse event and medications within given days before onset."""
        session_id = current_session_id_ctx.get()
        ctx = session_contexts.get(session_id) or {}
        scope_value = ctx.get("msid")
        if scope_value is None:
            raise ValueError("Missing access scope, query denied.")

        conn = pymysql.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name,
            port=db_port,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
        
        try:
            with conn:
                with conn.cursor() as cur:
                    # 1. 获取指定不良事件列表（支持模糊匹配）
                    cur.execute(
                        """
                        SELECT 
                            usubjid, aeterm, aedecod, aestdtc, aerel, aesev, aeout,
                            STR_TO_DATE(aestdtc, '%%Y-%%m-%%d') as ae_date
                        FROM patient_ae 
                        WHERE msid = %s AND aestdtc IS NOT NULL 
                        AND (aeterm LIKE %s OR aedecod LIKE %s)
                        ORDER BY aestdtc DESC
                        """,
                        (scope_value, f'%{ae_name}%', f'%{ae_name}%')
                    )
                    adverse_events = cur.fetchall()
                    
                    if not adverse_events:
                        return {
                            "ok": True,
                            "analysis_params": {"ae_name": ae_name, "days_before": days_before},
                            "events": 0,
                            "patients": 0,
                            "medication_counts": []
                        }
                    
                    # 按天粒度统计药物频次（day_offset: 1..days_before）
                    daily_counters: Dict[int, Dict[str, int]] = {d: {} for d in range(1, days_before + 1)}
                    distinct_patients = set()

                    def _parse_date_str(val):
                        if not val:
                            return None
                        try:
                            return datetime.strptime(str(val)[:10], '%Y-%m-%d').date()
                        except Exception:
                            return None

                    def _to_date(obj):
                        if isinstance(obj, datetime):
                            return obj.date()
                        if isinstance(obj, date):
                            return obj
                        return _parse_date_str(obj)
                    
                    for ae in adverse_events:
                        usubjid = ae['usubjid']
                        ae_date = ae['ae_date']
                        ae_term = ae['aeterm']
                        ae_decoded = ae['aedecod']
                        
                        if ae_date is None:
                            continue
                        distinct_patients.add(usubjid)
                            
                        # 计算查找用药的开始日期（不良事件前N天）
                        search_start_date = ae_date - timedelta(days=days_before)
                        
                        # 2. 查找该患者在不良事件前N天内的合并用药
                        cur.execute(
                            """
                            SELECT 
                                cmtrt as medication_name,
                                cmdecod as medication_decoded,
                                cmstdtc as start_date,
                                cmendtc as end_date,
                                cmindc as indication,
                                'Concomitant' as medication_type
                            FROM patient_cm 
                            WHERE msid = %s AND usubjid = %s 
                            AND cmstdtc IS NOT NULL
                            AND (
                                (STR_TO_DATE(cmstdtc, '%%Y-%%m-%%d') <= %s AND 
                                 (cmendtc IS NULL OR STR_TO_DATE(cmendtc, '%%Y-%%m-%%d') >= %s))
                                OR
                                (STR_TO_DATE(cmstdtc, '%%Y-%%m-%%d') BETWEEN %s AND %s)
                            )
                            """,
                            (scope_value, usubjid, ae_date, search_start_date, search_start_date, ae_date)
                        )
                        concomitant_meds = cur.fetchall()
                        
                        # 3. 查找该患者在不良事件前N天内的试验药物
                        cur.execute(
                            """
                            SELECT 
                                extrt as medication_name,
                                extrt as medication_decoded,
                                exstdtc as start_date,
                                exendtc as end_date,
                                'N/A' as indication,
                                'StudyDrug' as medication_type
                            FROM patient_ex 
                            WHERE msid = %s AND usubjid = %s 
                            AND exstdtc IS NOT NULL
                            AND (
                                (STR_TO_DATE(SUBSTR(exstdtc, 1, 10), '%%Y-%%m-%%d') <= %s AND 
                                 (exendtc IS NULL OR STR_TO_DATE(SUBSTR(exendtc, 1, 10), '%%Y-%%m-%%d') >= %s))
                                OR
                                (STR_TO_DATE(SUBSTR(exstdtc, 1, 10), '%%Y-%%m-%%d') BETWEEN %s AND %s)
                            )
                            """,
                            (scope_value, usubjid, ae_date, search_start_date, search_start_date, ae_date)
                        )
                        study_meds = cur.fetchall()
                        
                        # 合并所有用药记录并统计药物频次（按天）
                        for med in list(concomitant_meds) + list(study_meds):
                            med_name = med['medication_decoded'] or med['medication_name']
                            med_start = _parse_date_str(med.get('start_date'))
                            base_date = _to_date(ae_date)
                            med_end = _parse_date_str(med.get('end_date')) or base_date

                            # 针对窗口内每一天做覆盖判断
                            for d in range(1, days_before + 1):
                                day_date = base_date - timedelta(days=d)
                                if med_start and med_start <= day_date <= med_end:
                                    day_map = daily_counters[d]
                                    day_map[med_name] = day_map.get(med_name, 0) + 1
                        
                    
                    # 4. 生成药物统计摘要
                    # 将每日统计整理为排序后的列表
                    daily_medication_counts = []
                    for d in range(1, days_before + 1):
                        items = [
                            {"medication_name": name, "count": cnt}
                            for name, cnt in daily_counters[d].items()
                        ]
                        items.sort(key=lambda x: x["count"], reverse=True)
                        daily_medication_counts.append({
                            "day_offset": d,
                            "medications": items
                        })
                    
                    return {
                        "ok": True,
                        "analysis_params": {
                            "ae_name": ae_name,
                            "days_before": days_before
                        },
                        "events": len(adverse_events),
                        "patients": len(distinct_patients),
                        "daily_medication_counts": daily_medication_counts
                    }
                    
        except Exception as e:
            raise ValueError(f"分析不良反应与用药关联时出错: {str(e)}")

    medical_query_tool = StructuredTool.from_function(
        func=medical_query_impl,
        name="medical_query",
        description="Restricted SQL query: allows SELECT, SHOW COLUMNS, DESCRIBE, SHOW TABLES; automatic access control and structured results.",
        args_schema=MedicalQueryArgs,
    )

    showtables_tool = StructuredTool.from_function(
        func=show_tables_tool_impl,
        name="showtables",
        description="Returns list of available tables with descriptions for the current user's access scope . Each table entry includes the table name and a description of its contents and purpose.",
    )

    descripttables_tool = StructuredTool.from_function(
        func=descripttables_impl,
        name="descripttables",
        description="Describe table structure and return 4 random sample rows (automatic access control and field desensitization)",
        args_schema=DescribeTableArgs,
    )


    patient_count_stats_tool = StructuredTool.from_function(
        func=patient_count_stats_impl,
        name="patient_count_stats",
        description="Summarize patient counts and distributions under current access scope (msid): sex, age groups, treatment, race, study status, BMI groups, sites, discontinuation reasons, region stratification (US vs ROW), ECOG baseline.",
    )

    adverse_event_analysis_tool = StructuredTool.from_function(
        func=adverse_event_analysis_impl,
        name="adverse_event_analysis",
        description="Analyze association between a specific adverse event (fuzzy match) and medications used within N days (default 3) before onset; returns daily medication counts (concomitant and study drugs).",
        args_schema=AdverseEventAnalysisArgs,
    )

    return [
        medical_query_tool,
        showtables_tool,
        descripttables_tool,
        patient_count_stats_tool,
        adverse_event_analysis_tool,
    ]

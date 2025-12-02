"""
Doctor Agent 专属工具模块
为 DOCTOR_M (医学洞察) 和 DOCTOR_S (统计精度) 提供 PDF 阅读能力

通过 msid 关联到 ClinReview 平台的 pdf_upload 表，获取对应项目的 PDF 文件
"""

import os
import re
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

import pymysql
import pdfplumber
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


# PDF 文件存储根路径（与 ClinReview 平台一致）
PDF_UPLOAD_ROOT = "/home/ruoyi/uploadPath"


def _clean_text_keep_newlines(text: str) -> str:
    """保留换行的清洗：标准化换行，清理常见页眉/页脚片段"""
    if not text:
        return ""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    lines = text.split('\n')
    out: List[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            out.append("")
            continue
        # 跳过页码
        if re.match(r'^Page \d+\b', line):
            continue
        if re.match(r'^\d+\s*$', line):
            continue
        line = re.sub(r'[\t ]+', ' ', line)
        out.append(line)
    # 合并多余空行（最多一个）
    merged: List[str] = []
    empty = 0
    for ln in out:
        if ln == "":
            empty += 1
            if empty <= 1:
                merged.append("")
        else:
            empty = 0
            merged.append(ln)
    return '\n'.join(merged).strip()


def _extract_pdf_text(pdf_path: str, max_pages: int = 50) -> Dict[str, Any]:
    """提取 PDF 文本内容"""
    try:
        pages_content = []
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            pages_to_read = min(total_pages, max_pages)
            
            for i, page in enumerate(pdf.pages[:pages_to_read]):
                text = page.extract_text() or ""
                cleaned = _clean_text_keep_newlines(text)
                if cleaned:
                    pages_content.append({
                        "page": i + 1,
                        "content": cleaned
                    })
        
        return {
            "ok": True,
            "total_pages": total_pages,
            "pages_read": pages_to_read,
            "pages": pages_content
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"PDF读取失败: {str(e)}"
        }


def _extract_pdf_tables(pdf_path: str, max_pages: int = 50) -> Dict[str, Any]:
    """提取 PDF 中的表格数据"""
    try:
        all_tables = []
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            pages_to_read = min(total_pages, max_pages)
            
            for i, page in enumerate(pdf.pages[:pages_to_read]):
                tables = page.extract_tables()
                if tables:
                    for table_idx, table in enumerate(tables):
                        if table and len(table) > 0:
                            # 第一行作为表头
                            headers = table[0] if table[0] else []
                            rows = table[1:] if len(table) > 1 else []
                            all_tables.append({
                                "page": i + 1,
                                "table_index": table_idx + 1,
                                "headers": headers,
                                "rows": rows[:20],  # 限制行数
                                "total_rows": len(rows)
                            })
        
        return {
            "ok": True,
            "total_pages": total_pages,
            "tables_found": len(all_tables),
            "tables": all_tables
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"表格提取失败: {str(e)}"
        }


def create_doctor_tools(
    *,
    db_host: str,
    db_user: str,
    db_password: str,
    db_name: str,
    db_port: int,
    session_contexts: Dict[str, Dict[str, Any]],
    current_session_id_ctx,
    agent_type: str = "DOCTOR_M",  # DOCTOR_M 或 DOCTOR_S
) -> List[StructuredTool]:
    """
    创建 Doctor Agent 专属工具
    
    Args:
        db_host/db_user/db_password/db_name/db_port: 数据库连接配置
        session_contexts: 会话上下文映射
        current_session_id_ctx: 当前会话ID上下文变量
        agent_type: Agent 类型 (DOCTOR_M 或 DOCTOR_S)
    
    Returns:
        专属工具列表
    """
    
    def _get_current_msid() -> Optional[int]:
        """获取当前会话的 msid"""
        session_id = current_session_id_ctx.get()
        ctx = session_contexts.get(session_id) or {}
        return ctx.get("msid")
    
    def _get_pdf_list_by_msid(msid: int) -> List[Dict[str, Any]]:
        """从数据库获取 msid 对应的 PDF 文件列表"""
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
                    cur.execute("""
                        SELECT 
                            id,
                            name as pdf_name,
                            orginname as original_name,
                            path as pdf_path,
                            section,
                            title1 as title,
                            pdfDate as upload_date
                        FROM pdf_upload 
                        WHERE mystudyId = %s AND delFlag = '0'
                        ORDER BY section, title1, pdfDate DESC
                    """, (msid,))
                    return cur.fetchall()
        except Exception as e:
            print(f"⚠️ 查询 PDF 列表失败: {e}")
            return []
    
    def _resolve_pdf_path(db_path: str) -> str:
        """将数据库中的相对路径转换为绝对路径"""
        # 数据库存储的路径格式: /profile/uploadpdf/2025/05/27/xxx.pdf
        # 实际路径: /home/ruoyi/uploadPath/uploadpdf/2025/05/27/xxx.pdf
        if db_path.startswith('/profile/'):
            relative_path = db_path[len('/profile/'):]
            return os.path.join(PDF_UPLOAD_ROOT, relative_path)
        return db_path
    
    # ============= 工具实现 =============
    
    def list_project_pdfs_impl() -> Dict[str, Any]:
        """列出当前项目（msid）下的所有 PDF 文件"""
        msid = _get_current_msid()
        if msid is None:
            return {"ok": False, "error": "未关联项目，无法获取 PDF 列表"}
        
        pdf_list = _get_pdf_list_by_msid(msid)
        
        # 按 section 分组
        grouped = {}
        for pdf in pdf_list:
            section = pdf.get('section') or 'Other'
            if section not in grouped:
                grouped[section] = []
            grouped[section].append({
                "id": pdf['id'],
                "name": pdf['original_name'] or pdf['pdf_name'],
                "title": pdf.get('title', ''),
                "upload_date": str(pdf.get('upload_date', ''))[:10] if pdf.get('upload_date') else ''
            })
        
        return {
            "ok": True,
            "msid": msid,
            "total_pdfs": len(pdf_list),
            "sections": grouped
        }
    
    class ReadPdfArgs(BaseModel):
        pdf_id: int = Field(description="PDF文件ID（从 list_project_pdfs 获取）")
        max_pages: int = Field(default=30, description="最多读取的页数，默认30页")
    
    def read_pdf_content_impl(pdf_id: int, max_pages: int = 30) -> Dict[str, Any]:
        """读取指定 PDF 的文本内容"""
        msid = _get_current_msid()
        if msid is None:
            return {"ok": False, "error": "未关联项目，无法读取 PDF"}
        
        # 查询 PDF 信息
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
                    cur.execute("""
                        SELECT id, name, orginname, path, mystudyId
                        FROM pdf_upload 
                        WHERE id = %s AND mystudyId = %s AND delFlag = '0'
                    """, (pdf_id, msid))
                    pdf_info = cur.fetchone()
        except Exception as e:
            return {"ok": False, "error": f"查询PDF信息失败: {str(e)}"}
        
        if not pdf_info:
            return {"ok": False, "error": f"PDF不存在或无权访问 (id={pdf_id})"}
        
        # 解析实际路径
        pdf_path = _resolve_pdf_path(pdf_info['path'])
        if not os.path.exists(pdf_path):
            return {"ok": False, "error": f"PDF文件不存在: {pdf_info['orginname']}"}
        
        # 提取文本
        result = _extract_pdf_text(pdf_path, max_pages)
        result["pdf_name"] = pdf_info['orginname'] or pdf_info['name']
        result["pdf_id"] = pdf_id
        return result
    
    class ReadPdfTablesArgs(BaseModel):
        pdf_id: int = Field(description="PDF文件ID")
        max_pages: int = Field(default=50, description="最多扫描的页数，默认50页")
    
    def read_pdf_tables_impl(pdf_id: int, max_pages: int = 50) -> Dict[str, Any]:
        """提取指定 PDF 中的表格数据"""
        msid = _get_current_msid()
        if msid is None:
            return {"ok": False, "error": "未关联项目，无法读取 PDF"}
        
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
                    cur.execute("""
                        SELECT id, name, orginname, path, mystudyId
                        FROM pdf_upload 
                        WHERE id = %s AND mystudyId = %s AND delFlag = '0'
                    """, (pdf_id, msid))
                    pdf_info = cur.fetchone()
        except Exception as e:
            return {"ok": False, "error": f"查询PDF信息失败: {str(e)}"}
        
        if not pdf_info:
            return {"ok": False, "error": f"PDF不存在或无权访问 (id={pdf_id})"}
        
        pdf_path = _resolve_pdf_path(pdf_info['path'])
        if not os.path.exists(pdf_path):
            return {"ok": False, "error": f"PDF文件不存在: {pdf_info['orginname']}"}
        
        result = _extract_pdf_tables(pdf_path, max_pages)
        result["pdf_name"] = pdf_info['orginname'] or pdf_info['name']
        result["pdf_id"] = pdf_id
        return result
    
    class SearchPdfsArgs(BaseModel):
        keyword: str = Field(description="搜索关键词（匹配文件名或标题）")
    
    def search_project_pdfs_impl(keyword: str) -> Dict[str, Any]:
        """在当前项目中搜索 PDF 文件"""
        msid = _get_current_msid()
        if msid is None:
            return {"ok": False, "error": "未关联项目，无法搜索 PDF"}
        
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
                    cur.execute("""
                        SELECT 
                            id,
                            name as pdf_name,
                            orginname as original_name,
                            section,
                            title1 as title
                        FROM pdf_upload 
                        WHERE mystudyId = %s AND delFlag = '0'
                        AND (orginname LIKE %s OR title1 LIKE %s OR name LIKE %s)
                        ORDER BY section, title1
                        LIMIT 20
                    """, (msid, f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'))
                    results = cur.fetchall()
        except Exception as e:
            return {"ok": False, "error": f"搜索失败: {str(e)}"}
        
        return {
            "ok": True,
            "keyword": keyword,
            "results_count": len(results),
            "results": [
                {
                    "id": r['id'],
                    "name": r['original_name'] or r['pdf_name'],
                    "section": r.get('section', ''),
                    "title": r.get('title', '')
                }
                for r in results
            ]
        }
    
    class ReadMultiplePdfsArgs(BaseModel):
        pdf_ids: str = Field(description="PDF文件ID列表，逗号分隔，如 '123,456,789'")
        max_pages_per_pdf: int = Field(default=10, description="每个PDF最多读取的页数，默认10页")
    
    def read_multiple_pdfs_impl(pdf_ids: str, max_pages_per_pdf: int = 10) -> Dict[str, Any]:
        """批量读取多个 PDF 的内容（用于对比分析）"""
        msid = _get_current_msid()
        if msid is None:
            return {"ok": False, "error": "未关联项目，无法读取 PDF"}
        
        try:
            id_list = [int(x.strip()) for x in pdf_ids.split(',') if x.strip()]
        except ValueError:
            return {"ok": False, "error": "PDF ID格式错误，应为逗号分隔的数字"}
        
        if len(id_list) > 5:
            return {"ok": False, "error": "一次最多读取5个PDF"}
        
        results = []
        for pdf_id in id_list:
            result = read_pdf_content_impl(pdf_id, max_pages_per_pdf)
            results.append(result)
        
        return {
            "ok": True,
            "pdfs_count": len(results),
            "pdfs": results
        }
    
    # ============= 创建工具实例 =============
    
    list_pdfs_tool = StructuredTool.from_function(
        func=list_project_pdfs_impl,
        name="list_project_pdfs",
        description=f"[{agent_type}专属] 列出当前项目下的所有TFL PDF文件，按section分组返回，包含文件ID、名称、标题等信息。",
    )
    
    read_pdf_tool = StructuredTool.from_function(
        func=read_pdf_content_impl,
        name="read_pdf_content",
        description=f"[{agent_type}专属] 读取指定PDF的文本内容，需要提供pdf_id（从list_project_pdfs获取）。返回按页组织的文本内容。",
        args_schema=ReadPdfArgs,
    )
    
    read_tables_tool = StructuredTool.from_function(
        func=read_pdf_tables_impl,
        name="read_pdf_tables",
        description=f"[{agent_type}专属] 提取指定PDF中的表格数据，返回结构化的表头和行数据。适合分析统计表格。",
        args_schema=ReadPdfTablesArgs,
    )
    
    search_pdfs_tool = StructuredTool.from_function(
        func=search_project_pdfs_impl,
        name="search_project_pdfs",
        description=f"[{agent_type}专属] 在当前项目中按关键词搜索PDF文件（匹配文件名或标题）。",
        args_schema=SearchPdfsArgs,
    )
    
    read_multiple_tool = StructuredTool.from_function(
        func=read_multiple_pdfs_impl,
        name="read_multiple_pdfs",
        description=f"[{agent_type}专属] 批量读取多个PDF内容（最多5个），用于对比分析。pdf_ids格式: '123,456,789'",
        args_schema=ReadMultiplePdfsArgs,
    )
    
    return [
        list_pdfs_tool,
        read_pdf_tool,
        read_tables_tool,
        search_pdfs_tool,
        read_multiple_tool,
    ]


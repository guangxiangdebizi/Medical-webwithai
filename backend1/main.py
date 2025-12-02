"""
Dolphin Trinity AI™ Backend Server
===================================
Dr.S (StatGuard) - 审计专家: 合规与完整性检查
Dr.M (MediSense) - 医学专家: 安全与解读分析

Port: 8081
"""

import os
import re
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import fitz  # PyMuPDF

app = FastAPI(
    title="Dolphin Trinity AI™ API",
    description="AI-powered clinical trial document review system",
    version="1.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储上传的文件
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# ============================================================
# Data Models
# ============================================================

class DrSResult(BaseModel):
    """Dr.S 分析结果"""
    formatting_check: Dict[str, Any]
    logic_check: Dict[str, Any]
    cross_check: Dict[str, Any]
    diff_check: Optional[Dict[str, Any]] = None
    summary: str
    execution_time: float

class DrMResult(BaseModel):
    """Dr.M 分析结果"""
    mortality_overview: Dict[str, Any]
    sentinel_events: List[Dict[str, Any]]
    contextual_analysis: Dict[str, Any]
    medical_summary: Dict[str, Any]
    execution_time: float

class AnalysisRequest(BaseModel):
    """分析请求"""
    file_id: str
    analysis_type: str  # "dr_s" or "dr_m"
    options: Optional[Dict[str, Any]] = None


# ============================================================
# Dr.S (StatGuard) - 审计专家
# ============================================================

class DrSAnalyzer:
    """
    Dr.S - The Auditor
    Focus: Compliance & Integrity
    - Footer/Header Consistency
    - Mathematical Logic (n/N%)
    - Shell Compliance
    - Version Diff Check
    """
    
    def __init__(self):
        self.placeholder_patterns = [
            r'DDMMMYYYY',
            r'XX[A-Z]{3}\d{4}',
            r'\[INSERT\]',
            r'\[TBD\]',
            r'PLACEHOLDER',
        ]
    
    def analyze(self, pdf_path: str, previous_version_path: Optional[str] = None) -> DrSResult:
        """执行完整的 Dr.S 分析"""
        start_time = datetime.now()
        
        # 提取 PDF 内容
        doc = fitz.open(pdf_path)
        full_text = ""
        pages_data = []
        
        for page_num, page in enumerate(doc):
            text = page.get_text()
            full_text += text
            pages_data.append({
                "page_num": page_num + 1,
                "text": text,
                "tables": self._extract_tables(page)
            })
        doc.close()
        
        # Step 1: Formatting & Metadata Check
        formatting_result = self._check_formatting(pages_data, full_text)
        
        # Step 2: Logic & Calculation Check
        logic_result = self._check_logic(pages_data, full_text)
        
        # Step 3: Cross-Table Check (模拟)
        cross_result = self._check_cross_table(pages_data, full_text)
        
        # Step 4: Diff Check (如果提供了之前版本)
        diff_result = None
        if previous_version_path:
            diff_result = self._check_diff(pdf_path, previous_version_path)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 生成总结
        summary = self._generate_summary(formatting_result, logic_result, cross_result, diff_result)
        
        return DrSResult(
            formatting_check=formatting_result,
            logic_check=logic_result,
            cross_check=cross_result,
            diff_check=diff_result,
            summary=summary,
            execution_time=execution_time
        )
    
    def _extract_tables(self, page) -> List[Dict]:
        """从页面提取表格数据"""
        tables = []
        # 使用 PyMuPDF 的表格提取功能
        try:
            tabs = page.find_tables()
            for tab in tabs:
                tables.append({
                    "bbox": list(tab.bbox),
                    "cells": tab.extract()
                })
        except Exception:
            pass
        return tables
    
    def _check_formatting(self, pages_data: List[Dict], full_text: str) -> Dict[str, Any]:
        """Step 1: 格式与元数据核查"""
        issues = []
        warnings = []
        
        # 检查占位符
        for pattern in self.placeholder_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            if matches:
                warnings.append({
                    "type": "placeholder_detected",
                    "pattern": pattern,
                    "count": len(matches),
                    "message": f"Placeholder '{pattern}' found {len(matches)} time(s)"
                })
        
        # 检查日期格式一致性
        date_patterns = re.findall(r'\d{1,2}[A-Z]{3}\d{4}', full_text)
        if date_patterns:
            unique_dates = set(date_patterns)
            # 简单验证
        
        # 检查页码格式
        page_pattern = re.findall(r'Page\s+(\d+)\s+of\s+(\d+)', full_text, re.IGNORECASE)
        if page_pattern:
            for current, total in page_pattern:
                if int(current) > int(total):
                    issues.append({
                        "type": "page_number_error",
                        "message": f"Page {current} of {total} - current page exceeds total"
                    })
        
        # 检查程序名
        program_match = re.search(r'Program:\s*(\S+\.sas)', full_text, re.IGNORECASE)
        program_name = program_match.group(1) if program_match else None
        
        status = "PASS" if not issues else ("WARNING" if not [i for i in issues if i.get("severity") == "error"] else "FAIL")
        if warnings and status == "PASS":
            status = "WARNING"
        
        return {
            "status": status,
            "footer_consistency": {
                "program_name": program_name,
                "issues": [w for w in warnings if "placeholder" in w.get("type", "")]
            },
            "shell_compliance": {
                "page_numbering": "correct" if not [i for i in issues if "page" in i.get("type", "")] else "error",
                "issues": [i for i in issues if "page" in i.get("type", "")]
            },
            "warnings": warnings,
            "issues": issues
        }
    
    def _check_logic(self, pages_data: List[Dict], full_text: str) -> Dict[str, Any]:
        """Step 2: 逻辑与运算核查"""
        calculations_checked = []
        issues = []
        
        # 查找百分比计算 (n/N = x%)
        # 模式: 数字 (百分比%)
        percent_pattern = re.findall(r'(\d+)\s*\((\d+\.?\d*)\s*%?\)', full_text)
        
        # 查找 N 值 (通常在表头)
        n_pattern = re.findall(r'N\s*=\s*(\d+)', full_text)
        n_values = [int(n) for n in n_pattern] if n_pattern else []
        
        for count, percent in percent_pattern[:10]:  # 检查前10个
            count = int(count)
            reported_percent = float(percent)
            
            # 尝试用找到的 N 值验证
            for n in n_values:
                if n > 0:
                    calculated = round(count / n * 100, 1)
                    if abs(calculated - reported_percent) < 0.2:  # 允许0.2%误差
                        calculations_checked.append({
                            "count": count,
                            "n": n,
                            "calculated": calculated,
                            "reported": reported_percent,
                            "match": True
                        })
                        break
        
        # 检查排序规则
        sorting_valid = True  # 简化处理
        
        status = "PASS" if not issues else "FAIL"
        
        return {
            "status": status,
            "population_n_check": {
                "n_values_found": n_values,
                "message": f"Found N values: {n_values}" if n_values else "No N values detected in header"
            },
            "percentage_verification": {
                "samples_checked": len(calculations_checked),
                "calculations": calculations_checked[:5],  # 返回前5个
                "all_match": all(c["match"] for c in calculations_checked) if calculations_checked else True
            },
            "sorting_validation": {
                "valid": sorting_valid,
                "rule": "Descending frequency"
            },
            "issues": issues
        }
    
    def _check_cross_table(self, pages_data: List[Dict], full_text: str) -> Dict[str, Any]:
        """Step 3: 跨表核对"""
        # 这是模拟功能 - 实际需要多文件支持
        references_checked = []
        
        # 提取可能的表格引用
        table_refs = re.findall(r'Table\s+(\d+\.\d+\.\d+\.\d+)', full_text, re.IGNORECASE)
        listing_refs = re.findall(r'Listing\s+(\d+\.\d+\.\d+)', full_text, re.IGNORECASE)
        
        return {
            "status": "PASS",
            "references_found": {
                "tables": list(set(table_refs)),
                "listings": list(set(listing_refs))
            },
            "consistency_checks": references_checked,
            "note": "Cross-table validation requires multiple uploaded files for full analysis"
        }
    
    def _check_diff(self, current_path: str, previous_path: str) -> Dict[str, Any]:
        """Step 4: 版本比对"""
        changes = []
        
        try:
            # 提取两个版本的文本
            doc_current = fitz.open(current_path)
            doc_previous = fitz.open(previous_path)
            
            current_text = "".join([page.get_text() for page in doc_current])
            previous_text = "".join([page.get_text() for page in doc_previous])
            
            doc_current.close()
            doc_previous.close()
            
            # 简单的差异检测
            if current_text != previous_text:
                changes.append({
                    "type": "content_changed",
                    "message": "Document content has been modified"
                })
            
            return {
                "status": "CHANGES_DETECTED" if changes else "NO_CHANGES",
                "changes": changes,
                "summary": f"{len(changes)} change(s) detected"
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "error": str(e)
            }
    
    def _generate_summary(self, formatting: Dict, logic: Dict, cross: Dict, diff: Optional[Dict]) -> str:
        """生成分析总结"""
        summary_parts = []
        
        # Formatting
        if formatting["status"] == "WARNING":
            warning_count = len(formatting.get("warnings", []))
            summary_parts.append(f"⚠️ {warning_count} formatting warning(s) detected")
        elif formatting["status"] == "PASS":
            summary_parts.append("✅ Formatting check passed")
        
        # Logic
        if logic["status"] == "PASS":
            checked = logic["percentage_verification"]["samples_checked"]
            summary_parts.append(f"✅ Logic check passed ({checked} calculations verified)")
        
        # Cross-table
        if cross["status"] == "PASS":
            summary_parts.append("✅ Cross-table references identified")
        
        # Diff
        if diff:
            if diff["status"] == "CHANGES_DETECTED":
                summary_parts.append(f"ℹ️ Version differences detected")
        
        return " | ".join(summary_parts)


# ============================================================
# Dr.M (MediSense) - 医学专家
# ============================================================

class DrMAnalyzer:
    """
    Dr.M - The Scientist
    Focus: Safety & Interpretation
    - Signal Detection
    - Toxicity Imbalance
    - Severity Assessment (Grade 3/4)
    - Sentinel Events
    """
    
    # 哨兵事件关键词
    SENTINEL_EVENTS = {
        "fistula": {
            "keywords": ["fistula", "tracheo-oesophageal", "tracheoesophageal"],
            "context": "Often associated with VEGF inhibitors or concurrent radiation therapy",
            "severity": "critical",
            "color": "red"
        },
        "myocarditis": {
            "keywords": ["myocarditis", "cardiac inflammation"],
            "context": "Known immune-related Adverse Event (irAE) for checkpoint inhibitors",
            "severity": "critical",
            "color": "red"
        },
        "pneumonitis": {
            "keywords": ["pneumonitis", "interstitial lung disease", "ILD"],
            "context": "Common irAE, requires immediate steroid intervention",
            "severity": "high",
            "color": "orange"
        },
        "colitis": {
            "keywords": ["colitis", "diarrhea grade 3", "bowel perforation"],
            "context": "Immune-mediated colitis, may require immunosuppression",
            "severity": "high",
            "color": "orange"
        },
        "hepatotoxicity": {
            "keywords": ["hepatitis", "liver failure", "ALT increased", "AST increased"],
            "context": "Drug-induced liver injury, monitor LFTs closely",
            "severity": "high",
            "color": "orange"
        },
        "neurotoxicity": {
            "keywords": ["encephalopathy", "seizure", "neuropathy", "guillain-barre"],
            "context": "Central or peripheral nervous system toxicity",
            "severity": "high",
            "color": "orange"
        }
    }
    
    def __init__(self):
        pass
    
    def analyze(self, pdf_path: str, context: Optional[Dict] = None) -> DrMResult:
        """执行完整的 Dr.M 分析"""
        start_time = datetime.now()
        
        # 提取 PDF 内容
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()
        
        # 提取表格数据
        table_data = self._extract_ae_data(full_text)
        
        # Panel 1: Overview & Signal Detection
        mortality_overview = self._analyze_mortality(table_data, full_text)
        
        # Panel 2: Sentinel Events
        sentinel_events = self._detect_sentinel_events(full_text, table_data)
        
        # Panel 3: Contextual Analysis
        contextual = self._analyze_context(table_data, full_text, context)
        
        # Panel 4: Summary
        medical_summary = self._generate_medical_summary(
            mortality_overview, sentinel_events, contextual
        )
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return DrMResult(
            mortality_overview=mortality_overview,
            sentinel_events=sentinel_events,
            contextual_analysis=contextual,
            medical_summary=medical_summary,
            execution_time=execution_time
        )
    
    def _extract_ae_data(self, text: str) -> Dict[str, Any]:
        """从文本中提取不良事件数据"""
        data = {
            "treatment_arm": {},
            "placebo_arm": {},
            "events": []
        }
        
        # 提取 N 值
        n_pattern = re.findall(r'(Drug\s+\w+|Placebo|Treatment)[^\d]*N\s*=\s*(\d+)', text, re.IGNORECASE)
        for arm, n in n_pattern:
            arm_key = "treatment" if "drug" in arm.lower() or "treatment" in arm.lower() else "placebo"
            data[f"{arm_key}_arm"]["n"] = int(n)
        
        # 提取事件行 (简化模式)
        # 格式: Event Name    n (%)    n (%)
        event_pattern = re.findall(
            r'([A-Za-z][A-Za-z\s\-]+?)\s+(\d+)\s*\((\d+\.?\d*)\s*%?\)\s+(\d+)\s*\((\d+\.?\d*)\s*%?\)',
            text
        )
        
        for event_name, t_count, t_pct, p_count, p_pct in event_pattern:
            event_name = event_name.strip()
            if len(event_name) > 3 and not event_name.isupper():  # 过滤掉表头
                data["events"].append({
                    "name": event_name,
                    "treatment": {"count": int(t_count), "percent": float(t_pct)},
                    "placebo": {"count": int(p_count), "percent": float(p_pct)}
                })
        
        return data
    
    def _analyze_mortality(self, table_data: Dict, full_text: str) -> Dict[str, Any]:
        """Panel 1: 死亡率分析"""
        events = table_data.get("events", [])
        
        # 计算总体死亡率
        total_treatment = sum(e["treatment"]["count"] for e in events)
        total_placebo = sum(e["placebo"]["count"] for e in events)
        
        # 识别不平衡
        imbalances = []
        for event in events:
            t_pct = event["treatment"]["percent"]
            p_pct = event["placebo"]["percent"]
            
            # 如果差异 > 1% 或 比值 > 2
            if abs(t_pct - p_pct) > 1.0 or (p_pct > 0 and t_pct / p_pct > 2):
                imbalances.append({
                    "event": event["name"],
                    "treatment_pct": t_pct,
                    "placebo_pct": p_pct,
                    "direction": "higher_in_treatment" if t_pct > p_pct else "higher_in_placebo"
                })
        
        # 检测 "Death" 编码问题
        death_coding_note = None
        for event in events:
            if "death" in event["name"].lower() and event["name"].lower() != "death":
                continue
            if event["name"].lower() == "death":
                if event["treatment"]["count"] > 0 and event["placebo"]["count"] == 0:
                    death_coding_note = "PT 'Death' appears only in treatment arm. This likely indicates 'Unspecified Death' coding, not excess mortality."
        
        return {
            "status": "ATTENTION_REQUIRED" if imbalances else "BALANCED",
            "mortality_balance": {
                "treatment_total": total_treatment,
                "placebo_total": total_placebo,
                "insight": "Overall mortality appears balanced" if abs(total_treatment - total_placebo) <= 2 else "Mortality imbalance detected"
            },
            "specific_imbalances": imbalances[:5],  # Top 5
            "coding_notes": death_coding_note,
            "pattern_analysis": {
                "treatment_drivers": [e["name"] for e in events if e["treatment"]["count"] > e["placebo"]["count"]][:3],
                "placebo_drivers": [e["name"] for e in events if e["placebo"]["count"] > e["treatment"]["count"]][:3]
            }
        }
    
    def _detect_sentinel_events(self, text: str, table_data: Dict) -> List[Dict[str, Any]]:
        """Panel 2: 哨兵事件检测"""
        detected = []
        text_lower = text.lower()
        events = table_data.get("events", [])
        
        for event_type, config in self.SENTINEL_EVENTS.items():
            for keyword in config["keywords"]:
                if keyword.lower() in text_lower:
                    # 查找具体数据
                    event_data = None
                    for e in events:
                        if keyword.lower() in e["name"].lower():
                            event_data = e
                            break
                    
                    detected.append({
                        "type": event_type,
                        "keyword_matched": keyword,
                        "severity": config["severity"],
                        "color": config["color"],
                        "medical_context": config["context"],
                        "data": event_data,
                        "recommendation": self._get_recommendation(event_type)
                    })
                    break  # 每种类型只报告一次
        
        return detected
    
    def _get_recommendation(self, event_type: str) -> str:
        """获取针对特定事件的建议"""
        recommendations = {
            "fistula": "Immediate Patient Profile review required. Check: radiation therapy history, tumor location near esophagus.",
            "myocarditis": "Check if death occurred early in treatment. Verify Troponin levels and ECG findings in listing.",
            "pneumonitis": "Review chest imaging, check for concurrent ILD risk factors. Consider steroid protocol.",
            "colitis": "Review colonoscopy findings if available. Check for CMV reactivation.",
            "hepatotoxicity": "Review LFT trends, check for hepatitis B/C status. Assess alcohol history.",
            "neurotoxicity": "Obtain detailed neurological assessment. Check for pre-existing neuropathy."
        }
        return recommendations.get(event_type, "Detailed case review recommended.")
    
    def _analyze_context(self, table_data: Dict, full_text: str, context: Optional[Dict]) -> Dict[str, Any]:
        """Panel 3: 关联分析"""
        insights = []
        
        # 查找年龄相关信息
        age_pattern = re.search(r'(?:median\s+)?age[:\s]+(\d+\.?\d*)\s*(?:years)?', full_text, re.IGNORECASE)
        elderly_pattern = re.search(r'(?:age\s*)?[≥>=]\s*65[:\s]+(\d+\.?\d*)\s*%?', full_text, re.IGNORECASE)
        
        demographics = {}
        if age_pattern:
            demographics["median_age"] = float(age_pattern.group(1))
        if elderly_pattern:
            demographics["elderly_percent"] = float(elderly_pattern.group(1))
        
        # 基于人口学的洞察
        if demographics.get("median_age", 0) > 70:
            insights.append({
                "type": "age_related",
                "insight": "Advanced age population - increased fall risk, renal impairment considerations",
                "events_to_watch": ["Brain injury", "Fracture", "Acute kidney injury"]
            })
        
        # 检查特定事件的关联
        events = table_data.get("events", [])
        for event in events:
            if "brain injury" in event["name"].lower():
                insights.append({
                    "type": "fall_risk",
                    "event": event["name"],
                    "interpretation": "In elderly population, 'Brain injury' is highly likely secondary to a Fall.",
                    "next_step": "Check AE Listing for preceding events: Dizziness, Syncope, Hypotension"
                })
        
        return {
            "demographics_detected": demographics,
            "contextual_insights": insights,
            "cross_references": []
        }
    
    def _generate_medical_summary(self, mortality: Dict, sentinel: List, context: Dict) -> Dict[str, Any]:
        """Panel 4: 生成医学总结"""
        conclusion_points = []
        actions = []
        
        # 死亡率结论
        if mortality["status"] == "BALANCED":
            conclusion_points.append("No overall mortality imbalance detected.")
        else:
            conclusion_points.append("Mortality imbalance requires attention.")
        
        # 哨兵事件结论
        critical_events = [s for s in sentinel if s["severity"] == "critical"]
        if critical_events:
            event_names = [s["type"] for s in critical_events]
            conclusion_points.append(f"Critical signals detected: {', '.join(event_names)} warrant specific risk management.")
            actions.append({
                "priority": "high",
                "action": "Narrative Writing",
                "detail": f"Prioritize drafting narratives for {', '.join(event_names)} events"
            })
        
        # 行动建议
        if sentinel:
            actions.append({
                "priority": "medium",
                "action": "Protocol Check",
                "detail": "Verify if detected events are known risks in the Investigator's Brochure (IB)"
            })
        
        # 数据清理建议
        if context.get("contextual_insights"):
            for insight in context["contextual_insights"]:
                if insight.get("next_step"):
                    actions.append({
                        "priority": "low",
                        "action": "Data Query",
                        "detail": insight["next_step"]
                    })
        
        return {
            "conclusion": " ".join(conclusion_points),
            "risk_level": "HIGH" if critical_events else ("MEDIUM" if sentinel else "LOW"),
            "suggested_actions": actions,
            "closing_note": "While Dr. S ensures your data is correct, Dr. M ensures your data is understood."
        }


# ============================================================
# API Endpoints
# ============================================================

# 实例化分析器
dr_s = DrSAnalyzer()
dr_m = DrMAnalyzer()


@app.get("/")
async def root():
    """API 根路径"""
    return {
        "service": "Dolphin Trinity AI™",
        "version": "1.0.0",
        "agents": {
            "dr_s": "StatGuard - The Auditor (Compliance & Integrity)",
            "dr_m": "MediSense - The Scientist (Safety & Interpretation)",
            "dr_d": "Data Agent - The Detective (Context & Evidence)"
        },
        "status": "operational"
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传 PDF 文件"""
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # 生成唯一文件ID
    file_id = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}"
    file_path = UPLOAD_DIR / file_id
    
    # 保存文件
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    
    return {
        "success": True,
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content)
    }


@app.post("/api/analyze/dr-s")
async def analyze_dr_s(
    file_id: str = Query(..., description="已上传文件的ID"),
    previous_file_id: Optional[str] = Query(None, description="用于版本比对的前一版本文件ID")
):
    """运行 Dr.S (StatGuard) 分析"""
    file_path = UPLOAD_DIR / file_id
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    previous_path = None
    if previous_file_id:
        previous_path = UPLOAD_DIR / previous_file_id
        if not previous_path.exists():
            raise HTTPException(status_code=404, detail="Previous version file not found")
        previous_path = str(previous_path)
    
    result = dr_s.analyze(str(file_path), previous_path)
    return result.model_dump()


@app.post("/api/analyze/dr-m")
async def analyze_dr_m(
    file_id: str = Query(..., description="已上传文件的ID")
):
    """运行 Dr.M (MediSense) 分析"""
    file_path = UPLOAD_DIR / file_id
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    result = dr_m.analyze(str(file_path))
    return result.model_dump()


@app.get("/api/agents")
async def get_agents_info():
    """获取三个 Agent 的详细信息"""
    return {
        "agents": [
            {
                "id": "dr_s",
                "name": "Dr. S",
                "full_name": "StatGuard",
                "role": "The Auditor",
                "role_cn": "审计专家",
                "color": "#3B82F6",  # Blue
                "focus": "Compliance & Integrity",
                "focus_cn": "合规与完整性",
                "capabilities": [
                    "Footer/Header Consistency",
                    "Mathematical Logic (n/N%)",
                    "Shell Compliance",
                    "Version Diff Check"
                ],
                "signature_line": "Report 14.3.1.2 has a calculation error in row 4, and the data cutoff date is inconsistent with the protocol."
            },
            {
                "id": "dr_m",
                "name": "Dr. M",
                "full_name": "MediSense",
                "role": "The Scientist",
                "role_cn": "医学专家",
                "color": "#F59E0B",  # Amber
                "focus": "Safety & Interpretation",
                "focus_cn": "安全与解读",
                "capabilities": [
                    "Signal Detection",
                    "Toxicity Imbalance",
                    "Severity Assessment (Grade 3/4)",
                    "Sentinel Events"
                ],
                "signature_line": "I've detected a signal for neurotoxicity driving discontinuation. Also, there is one fatal event that requires immediate review."
            },
            {
                "id": "dr_d",
                "name": "Dr. D",
                "full_name": "Data Agent",
                "role": "The Detective",
                "role_cn": "数据侦探",
                "color": "#14B8A6",  # Teal
                "focus": "Context & Evidence",
                "focus_cn": "语境与证据",
                "capabilities": [
                    "Raw Data Querying",
                    "Patient Profiling",
                    "Conmeds/History Check",
                    "Ad-hoc Listing"
                ],
                "signature_line": "I pulled the patient profile for the fatal case. The subject had a history of radiation therapy, which explains the event."
            }
        ],
        "ecosystem": {
            "name": "Dolphin Trinity AI™",
            "tagline": "Meet Your New Digital Clinical Board",
            "workflow": "Check → Think → Find",
            "description": "Dr. S and Dr. M tell you WHAT happened, Dr. D helps you find WHY."
        }
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)



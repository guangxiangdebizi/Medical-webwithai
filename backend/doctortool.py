"""
Doctor Agent 专属工具模块 (简化版)
为 DOCTOR_M (医学洞察) 和 DOCTOR_S (统计精度) 提供 PDF 阅读能力

只有两个核心工具：
1. show_pdfs - 查看有哪些 PDF 可用
2. read_pdf - 读取 PDF 全部内容
"""

import os
import re
from typing import Any, Dict, List, Optional

import pymysql
import pdfplumber
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


# PDF 文件存储根路径（与 ClinReview 平台一致）
PDF_UPLOAD_ROOT = "/home/ruoyi/uploadPath"


def _clean_text(text: str) -> str:
    """清洗文本：标准化换行，去除页码等噪音"""
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
        # 跳过纯页码行
        if re.match(r'^Page\s*\d+\s*(of\s*\d+)?$', line, re.IGNORECASE):
            continue
        if re.match(r'^\d+\s*$', line):
            continue
        # 清理多余空格
        line = re.sub(r'[\t ]+', ' ', line)
        out.append(line)
    
    # 合并多余空行（最多保留一个）
    merged: List[str] = []
    empty_count = 0
    for ln in out:
        if ln == "":
            empty_count += 1
            if empty_count <= 1:
                merged.append("")
        else:
            empty_count = 0
            merged.append(ln)
    
    return '\n'.join(merged).strip()


def _extract_full_pdf_content(pdf_path: str) -> str:
    """提取 PDF 的全部文本内容，返回纯文本字符串"""
    try:
        all_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                cleaned = _clean_text(page_text)
                if cleaned:
                    all_text.append(f"--- Page {i+1} ---\n{cleaned}")
        
        return "\n\n".join(all_text) if all_text else "(PDF 内容为空)"
    except Exception as e:
        return f"(PDF 读取失败: {str(e)})"


def create_doctor_tools(
    *,
    db_host: str,
    db_user: str,
    db_password: str,
    db_name: str,
    db_port: int,
    session_contexts: Dict[str, Dict[str, Any]],
    current_session_id_ctx,
    agent_type: str = "DOCTOR_M",
) -> List[StructuredTool]:
    """
    创建 Doctor Agent 专属工具（简化版，只有2个工具）
    
    Args:
        db_host/db_user/db_password/db_name/db_port: 数据库连接配置
        session_contexts: 会话上下文映射
        current_session_id_ctx: 当前会话ID上下文变量
        agent_type: Agent 类型 (DOCTOR_M 或 DOCTOR_S)
    
    Returns:
        [show_pdfs, read_pdf] 两个工具
    """
    
    def _get_current_msid() -> Optional[int]:
        """获取当前会话的 msid"""
        session_id = current_session_id_ctx.get()
        ctx = session_contexts.get(session_id) or {}
        return ctx.get("msid")
    
    def _resolve_pdf_path(db_path: str) -> str:
        """将数据库中的相对路径转换为绝对路径"""
        if db_path.startswith('/profile/'):
            relative_path = db_path[len('/profile/'):]
            return os.path.join(PDF_UPLOAD_ROOT, relative_path)
        return db_path
    
    # ==================== 工具 1: show_pdfs ====================
    
    def show_pdfs_impl() -> str:
        """列出当前项目下所有可用的 PDF 文件"""
        msid = _get_current_msid()
        if msid is None:
            return "错误: 未关联项目，无法获取 PDF 列表"
        
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
                            orginname as name,
                            section,
                            title1 as title
                        FROM pdf_upload 
                        WHERE mystudyId = %s AND delFlag = '0'
                        ORDER BY section, title1
                    """, (msid,))
                    pdf_list = cur.fetchall()
        except Exception as e:
            return f"错误: 查询 PDF 列表失败 - {str(e)}"
        
        if not pdf_list:
            return "当前项目没有 PDF 文件"
        
        # 按 section 分组显示
        sections: Dict[str, List[str]] = {}
        for pdf in pdf_list:
            section = pdf.get('section') or 'Other'
            if section not in sections:
                sections[section] = []
            name = pdf.get('name') or f"PDF_{pdf['id']}"
            title = pdf.get('title') or ''
            display = f"  - ID: {pdf['id']} | {name}"
            if title:
                display += f" ({title})"
            sections[section].append(display)
        
        # 构建输出文本
        output_lines = [f"📂 项目共有 {len(pdf_list)} 个 PDF 文件:\n"]
        for section, items in sections.items():
            output_lines.append(f"【{section}】")
            output_lines.extend(items)
            output_lines.append("")
        
        return "\n".join(output_lines)
    
    # ==================== 工具 2: read_pdf ====================
    
    class ReadPdfArgs(BaseModel):
        pdf_id: int = Field(description="PDF 文件的 ID（从 show_pdfs 结果中获取）")
    
    def read_pdf_impl(pdf_id: int) -> str:
        """读取指定 PDF 的完整内容，返回纯文本"""
        msid = _get_current_msid()
        if msid is None:
            return "错误: 未关联项目，无法读取 PDF"
        
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
                        SELECT id, name, orginname, path
                        FROM pdf_upload 
                        WHERE id = %s AND mystudyId = %s AND delFlag = '0'
                    """, (pdf_id, msid))
                    pdf_info = cur.fetchone()
        except Exception as e:
            return f"错误: 查询 PDF 信息失败 - {str(e)}"
        
        if not pdf_info:
            return f"错误: PDF 不存在或无权访问 (ID: {pdf_id})"
        
        # 解析实际路径
        pdf_path = _resolve_pdf_path(pdf_info['path'])
        if not os.path.exists(pdf_path):
            return f"错误: PDF 文件不存在 - {pdf_info['orginname']}"
        
        # 提取全部内容
        pdf_name = pdf_info['orginname'] or pdf_info['name']
        content = _extract_full_pdf_content(pdf_path)
        
        return f"📄 文档: {pdf_name}\n{'='*50}\n\n{content}"
    
    # ==================== 创建工具实例 ====================
    
    show_pdfs_tool = StructuredTool.from_function(
        func=show_pdfs_impl,
        name="show_pdfs",
        description="列出当前项目所有可用的 PDF 文件，显示每个文件的 ID、名称和分类。调用后可获取 PDF 的 ID 用于读取。",
    )
    
    read_pdf_tool = StructuredTool.from_function(
        func=read_pdf_impl,
        name="read_pdf",
        description="读取指定 PDF 的完整内容。传入 pdf_id（从 show_pdfs 获取），返回 PDF 的全部文本内容。",
        args_schema=ReadPdfArgs,
    )
    
    return [show_pdfs_tool, read_pdf_tool]

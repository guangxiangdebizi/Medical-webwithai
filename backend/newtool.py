from typing import Any, Dict, List, Optional
from pathlib import Path
import re
import pdfplumber

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


ELMS_DIR = Path(__file__).parent / "eLMS"


def _ensure_elms_dir() -> Path:
    base = ELMS_DIR
    if not base.exists() or not base.is_dir():
        raise ValueError(f"eLMS 目录不存在: {base}")
    return base


def create_markdown_tools() -> List[StructuredTool]:
    """创建工具集合"""

    # -----------------------------
    # Show PDF files in eLMS
    # -----------------------------
    
    class ShowPdfArgs(BaseModel):
        pass

    def show_pdf_impl() -> Dict[str, Any]:
        base = _ensure_elms_dir()
        pdf_files = sorted(base.glob("*.pdf"))
        pdf_names = [p.name for p in pdf_files]
        return {
            "ok": True,
            "count": len(pdf_names),
            "pdf_files": pdf_names,
        }

    show_pdf_tool = StructuredTool.from_function(
        func=show_pdf_impl,
        name="show_pdf",
        description="列出 backend/eLMS 目录下所有 PDF 文件",
        args_schema=ShowPdfArgs,
    )

    # -----------------------------
    # PDF -> Markdown (single file)
    # -----------------------------

    class PdfToMdArgs(BaseModel):
        filename: str = Field(description="PDF 文件名（可含或不含 .pdf 扩展名），仅文件名即可")

    def _clean_text_keep_newlines(text: str) -> str:
        if not text:
            return ""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = text.split("\n")
        out: List[str] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                out.append("")
                continue
            if re.match(r"^Page \d+\b", line):
                continue
            if re.match(r"^\d+\s*$", line):
                continue
            line = re.sub(r"[\t ]+", " ", line)
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
        return "\n".join(merged).strip()

    def pdf_to_markdown_impl(filename: str) -> Dict[str, Any]:
        name = (filename or "").strip()
        if not name:
            raise ValueError("filename 不能为空")
        pdf_name = name if name.lower().endswith(".pdf") else f"{name}.pdf"

        # 优先 backend/eLMS，其次项目根的 eLMS
        base1 = Path(__file__).parent / "eLMS"
        base2 = Path(__file__).parent.parent / "eLMS"
        candidates = [base1 / pdf_name, base2 / pdf_name]
        pdf_path: Optional[Path] = None
        for p in candidates:
            if p.exists() and p.is_file():
                pdf_path = p
                break
        if pdf_path is None:
            raise ValueError(f"未找到 PDF 文件: {pdf_name}")

        pages: List[str] = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    cleaned = _clean_text_keep_newlines(text)
                    pages.append(cleaned)
        except Exception as e:
            raise RuntimeError(f"PDF 解析失败: {e}")

        md_lines: List[str] = [f"# {pdf_path.stem}", ""]
        for idx, pg in enumerate(pages, 1):
            md_lines.append(f"## 第 {idx} 页")
            md_lines.append("")
            md_lines.append(pg)
            md_lines.append("")
        markdown_text = "\n".join(md_lines).strip() if pages else f"# {pdf_path.stem}\n\n"

        return {"ok": True, "filename": pdf_path.stem, "markdown": markdown_text}

    pdf_to_markdown_tool = StructuredTool.from_function(
        func=pdf_to_markdown_impl,
        name="pdf_to_markdown",
        description=(
            "将 backend/eLMS 或 eLMS 下的指定 PDF 按页提取并清洗为一份完整 Markdown 文本。"
            "输入 filename（可含或不含 .pdf），返回 { ok, filename, markdown }。"
        ),
        args_schema=PdfToMdArgs,
    )

    return [
        show_pdf_tool,
        pdf_to_markdown_tool,
    ]


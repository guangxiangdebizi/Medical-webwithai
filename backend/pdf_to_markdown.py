import re
from pathlib import Path
from typing import List
import pdfplumber


def clean_text_keep_newlines(text: str) -> str:
    """保留换行的清洗：标准化换行，清理常见页眉/页脚片段，但不折叠整段为一行。"""
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


def extract_pages(pdf_path: Path) -> List[str]:
    """按页提取文本并清洗（保留换行）。"""
    pages: List[str] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                cleaned = clean_text_keep_newlines(text)
                pages.append(cleaned)
    except Exception as e:
        print(f"处理 {pdf_path} 时出错: {str(e)}")
        return []
    return pages


def save_combined_markdown(pdf_name: str, pages: List[str], out_root: Path) -> Path:
    """仅保存整本 Markdown（包含按页分节），不生成任何子文件。"""
    out_root.mkdir(parents=True, exist_ok=True)
    book_md = out_root / f"{pdf_name}.md"
    with open(book_md, 'w', encoding='utf-8') as f:
        f.write(f"# {pdf_name}\n\n")
        for idx, page_text in enumerate(pages, 1):
            f.write(f"## 第 {idx} 页\n\n{page_text}\n\n")
    return book_md


    # 删除了切片与向量化相关功能


def pdf_to_markdown(pdf_path, output_dir="markdown_output"):
    out_dir = Path(output_dir)
    out_dir.mkdir(exist_ok=True)
    pdf_name = Path(pdf_path).stem
    print(f"正在处理: {pdf_path}")
    pages = extract_pages(Path(pdf_path))
    if not pages:
        print(f"无法处理文件: {pdf_path}")
        return False
    book_md = save_combined_markdown(pdf_name, pages, out_dir)
    print(f"已转换: {book_md}")
    return True


def batch_convert_pdfs(input_dir=".", output_dir="markdown_output"):
    pdf_files = list(Path(input_dir).glob("*.pdf"))
    if not pdf_files:
        print("未找到PDF文件")
        return
    print(f"找到 {len(pdf_files)} 个PDF文件")
    success_count = 0
    for pdf_file in pdf_files:
        if pdf_to_markdown(pdf_file, output_dir=output_dir):
            success_count += 1
    print(f"\n转换完成！成功转换 {success_count}/{len(pdf_files)} 个文件")
    print(f"输出目录: {Path(output_dir).absolute()}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="批量将 PDF 转换为单一 Markdown（包含按页分节），不生成子文件")
    parser.add_argument("--input-dir", type=str, default=".", help="PDF 输入目录")
    parser.add_argument("--output-dir", type=str, default="markdown_output", help="Markdown 输出目录")
    args = parser.parse_args()
    batch_convert_pdfs(input_dir=args.input_dir, output_dir=args.output_dir)



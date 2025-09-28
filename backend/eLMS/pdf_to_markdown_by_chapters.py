import os
import pdfplumber
import re
from pathlib import Path

def clean_text(text):
    """清理提取的文本"""
    if not text:
        return ""
    
    # 先保留原始换行符
    # 移除页眉页脚常见模式
    text = re.sub(r'Page \d+.*?\n', '', text)
    text = re.sub(r'\d+\s*$', '', text, flags=re.MULTILINE)
    
    # 在数字章节标题前添加换行符，确保它们独立成行
    text = re.sub(r'(\S)\s+(\d+\.\s+[A-Z][A-Z\s]*)', r'\1\n\2', text)
    text = re.sub(r'(\S)\s+(\d+\.\d+\s+[A-Za-z])', r'\1\n\2', text)
    
    # 在特定关键词前添加换行符
    text = re.sub(r'(\S)\s+(PURPOSE|SCOPE|ABBREVIATIONS AND DEFINITIONS|RESPONSIBILITIES|INSTRUCTION|REFERENCES|APPENDICES)\s', r'\1\n\2 ', text)
    
    # 在Appendix前添加换行符
    text = re.sub(r'(\S)\s+(Appendix\s+\d+:)', r'\1\n\2', text)
    
    return text.strip()

def detect_chapter_titles(text):
    """检测章节标题"""
    lines = text.split('\n')
    chapter_titles = []
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # 检查各种章节模式
        is_chapter = False
        
        # 1. 数字开头的章节 (如: "1. PURPOSE", "2. SCOPE", "5.1 System Access")
        if re.match(r'^\d+\.\s+[A-Z][A-Z\s]*[A-Z]\s*$', line):
            is_chapter = True
        elif re.match(r'^\d+\.\d+\s+[A-Z][A-Za-z\s]*$', line):
            is_chapter = True
        elif re.match(r'^\d+\.\d+\.\d+\s+[A-Z][A-Za-z\s]*$', line):
            is_chapter = True
            
        # 2. 特定关键词开头的章节
        elif re.match(r'^(PURPOSE|SCOPE|ABBREVIATIONS AND DEFINITIONS|RESPONSIBILITIES|INSTRUCTION|REFERENCES|APPENDICES)\s*$', line, re.IGNORECASE):
            is_chapter = True
            
        # 3. Appendix 格式
        elif re.match(r'^Appendix\s+\d+:', line, re.IGNORECASE):
            is_chapter = True
            
        # 4. A1, A2 等格式的章节
        elif re.match(r'^A\d+\.\s+[A-Z][A-Z\s]*[A-Z]\s*$', line):
            is_chapter = True
            
        # 5. 中文章节
        elif re.match(r'^[一二三四五六七八九十]+[、．]\s*[^\n]*$', line):
            is_chapter = True
        elif re.match(r'^第[一二三四五六七八九十]+[章节]\s*[^\n]*$', line):
            is_chapter = True
            
        # 6. 数字加空格的格式 (如: "1 PURPOSE")
        elif re.match(r'^\d+\s+[A-Z][A-Z\s]*[A-Z]\s*$', line):
            is_chapter = True
            
        if is_chapter and len(line) < 150:  # 标题不应该太长
            # 避免重复添加相同的标题
            if not chapter_titles or chapter_titles[-1][1] != line:
                chapter_titles.append((i, line))
    
    return chapter_titles

def extract_text_by_chapters(pdf_path):
    """按章节提取PDF文本"""
    all_text = ""
    page_texts = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    # 保持原始格式，不过度清理
                    page_texts.append((page_num, text))
                    all_text += f"\n{text}\n"
    except Exception as e:
        print(f"处理 {pdf_path} 时出错: {str(e)}")
        return None
    
    # 使用更直接的方法检测章节
    chapters = extract_chapters_from_text(all_text)
    
    if not chapters:
        # 如果没有检测到章节，回退到按页面组织
        print(f"未检测到章节结构，使用页面分割模式")
        content = []
        for page_num, text in page_texts:
            cleaned_text = clean_text(text)
            content.append(f"\n## 第 {page_num} 页\n\n{cleaned_text}\n")
        return "\n".join(content)
    
    # 按章节组织内容
    print(f"检测到 {len(chapters)} 个章节")
    
    markdown_chapters = []
    for title, content in chapters:
        # 根据标题级别确定Markdown标题级别
        if re.match(r'^\d+\.\s+', title):  # 主章节
            markdown_title = f"# {title}"
        elif re.match(r'^\d+\.\d+\s+', title):  # 二级章节
            markdown_title = f"## {title}"
        elif re.match(r'^\d+\.\d+\.\d+\s+', title):  # 三级章节
            markdown_title = f"### {title}"
        else:
            markdown_title = f"## {title}"
        
        # 清理内容
        cleaned_content = clean_text(content)
        
        if cleaned_content:
            markdown_chapters.append(f"{markdown_title}\n\n{cleaned_content}\n")
    
    return "\n".join(markdown_chapters)

def extract_chapters_from_text(text):
    """从文本中提取章节"""
    chapters = []
    
    # 使用正则表达式查找章节标题和内容
    # 匹配 "数字. 标题" 格式的章节
    chapter_pattern = r'(\d+\.\s+[A-Z][A-Z\s]+)'
    
    # 分割文本
    parts = re.split(chapter_pattern, text)
    
    current_title = None
    current_content = ""
    
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
            
        # 检查是否是章节标题
        if re.match(r'^\d+\.\s+[A-Z][A-Z\s]+$', part):
            # 保存前一个章节
            if current_title and current_content:
                chapters.append((current_title, current_content))
            
            current_title = part
            current_content = ""
        else:
            # 这是章节内容
            if current_title:
                current_content += part + "\n"
    
    # 保存最后一个章节
    if current_title and current_content:
        chapters.append((current_title, current_content))
    
    # 如果没有找到标准格式的章节，尝试其他模式
    if not chapters:
        # 尝试匹配更宽松的模式
        looser_pattern = r'(\d+\.\s+[A-Z][A-Za-z\s]+)(?=\s|\n|$)'
        matches = list(re.finditer(looser_pattern, text))
        
        for i, match in enumerate(matches):
            title = match.group(1).strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start_pos:end_pos].strip()
            
            if content:
                chapters.append((title, content))
    
    return chapters

def pdf_to_markdown_by_chapters(pdf_path, output_dir="markdown_chapters"):
    """将PDF按章节转换为Markdown"""
    # 创建输出目录
    Path(output_dir).mkdir(exist_ok=True)
    
    # 获取PDF文件名（不含扩展名）
    pdf_name = Path(pdf_path).stem
    
    # 按章节提取文本
    print(f"正在处理: {pdf_path}")
    content = extract_text_by_chapters(pdf_path)
    
    if content is None:
        print(f"无法处理文件: {pdf_path}")
        return False
    
    # 创建Markdown内容
    markdown_content = f"# {pdf_name}\n\n{content}"
    
    # 保存为Markdown文件
    output_path = Path(output_dir) / f"{pdf_name}.md"
    
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        print(f"已转换: {output_path}")
        return True
    except Exception as e:
        print(f"保存文件时出错: {str(e)}")
        return False

def batch_convert_pdfs_by_chapters(input_dir=".", output_dir="markdown_chapters"):
    """批量按章节转换目录中的所有PDF文件"""
    pdf_files = list(Path(input_dir).glob("*.pdf"))
    
    if not pdf_files:
        print("未找到PDF文件")
        return
    
    print(f"找到 {len(pdf_files)} 个PDF文件")
    
    success_count = 0
    for pdf_file in pdf_files:
        if pdf_to_markdown_by_chapters(pdf_file, output_dir):
            success_count += 1
    
    print(f"\n转换完成！成功转换 {success_count}/{len(pdf_files)} 个文件")
    print(f"输出目录: {Path(output_dir).absolute()}")

if __name__ == "__main__":
    # 批量按章节转换当前目录下的所有PDF文件
    batch_convert_pdfs_by_chapters()
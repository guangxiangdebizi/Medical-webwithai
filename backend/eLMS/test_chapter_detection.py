import pdfplumber
import re
from pathlib import Path

def clean_text(text):
    """清理提取的文本"""
    if not text:
        return ""
    
    # 移除多余的空白字符
    text = re.sub(r'\s+', ' ', text)
    # 移除页眉页脚常见模式
    text = re.sub(r'Page \d+.*?\n', '', text)
    text = re.sub(r'\d+\s*$', '', text, flags=re.MULTILINE)
    
    return text.strip()

def detect_chapter_titles(text):
    """检测章节标题"""
    lines = text.split('\n')
    chapter_titles = []
    
    print(f"总共有 {len(lines)} 行文本")
    print("前20行内容:")
    for i, line in enumerate(lines[:20]):
        print(f"{i:3d}: '{line.strip()}'")
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # 检查各种章节模式
        is_chapter = False
        matched_pattern = ""
        
        # 1. 数字开头的章节 (如: "1. PURPOSE", "2. SCOPE", "5.1 System Access")
        if re.match(r'^\d+\.\s+[A-Z][A-Z\s]*[A-Z]\s*$', line):
            is_chapter = True
            matched_pattern = "数字点格式(全大写)"
        elif re.match(r'^\d+\.\s+[A-Za-z][A-Za-z\s]*$', line):
            is_chapter = True
            matched_pattern = "数字点格式(混合大小写)"
        elif re.match(r'^\d+\.\d+\s+[A-Z][A-Za-z\s]*$', line):
            is_chapter = True
            matched_pattern = "数字点数字格式"
        elif re.match(r'^\d+\.\d+\.\d+\s+[A-Z][A-Za-z\s]*$', line):
            is_chapter = True
            matched_pattern = "三级数字格式"
            
        # 2. 特定关键词开头的章节
        elif re.match(r'^(PURPOSE|SCOPE|ABBREVIATIONS AND DEFINITIONS|RESPONSIBILITIES|INSTRUCTION|REFERENCES|APPENDICES)\s*$', line, re.IGNORECASE):
            is_chapter = True
            matched_pattern = "关键词格式"
            
        # 3. Appendix 格式
        elif re.match(r'^Appendix\s+\d+:', line, re.IGNORECASE):
            is_chapter = True
            matched_pattern = "Appendix格式"
            
        # 4. A1, A2 等格式的章节
        elif re.match(r'^A\d+\.\s+[A-Z][A-Z\s]*[A-Z]\s*$', line):
            is_chapter = True
            matched_pattern = "A数字格式"
            
        # 5. 中文章节
        elif re.match(r'^[一二三四五六七八九十]+[、．]\s*[^\n]*$', line):
            is_chapter = True
            matched_pattern = "中文数字格式"
        elif re.match(r'^第[一二三四五六七八九十]+[章节]\s*[^\n]*$', line):
            is_chapter = True
            matched_pattern = "第X章格式"
            
        # 6. 数字加空格的格式 (如: "1 PURPOSE")
        elif re.match(r'^\d+\s+[A-Z][A-Z\s]*[A-Z]\s*$', line):
            is_chapter = True
            matched_pattern = "数字空格格式"
            
        if is_chapter and len(line) < 150:  # 标题不应该太长
            # 避免重复添加相同的标题
            if not chapter_titles or chapter_titles[-1][1] != line:
                chapter_titles.append((i, line))
                print(f"找到章节 (行{i}): '{line}' - 匹配模式: {matched_pattern}")
    
    return chapter_titles

def test_pdf_chapter_detection(pdf_path):
    """测试PDF章节检测"""
    print(f"\n测试文件: {pdf_path}")
    print("=" * 50)
    
    all_text = ""
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    cleaned_text = clean_text(text)
                    if cleaned_text:
                        all_text += f"\n{cleaned_text}\n"
                        
                # 只处理前3页进行测试
                if page_num >= 3:
                    break
                    
    except Exception as e:
        print(f"处理 {pdf_path} 时出错: {str(e)}")
        return
    
    # 检测章节标题
    chapter_titles = detect_chapter_titles(all_text)
    
    print(f"\n检测结果: 找到 {len(chapter_titles)} 个章节标题")
    for i, (line_idx, title) in enumerate(chapter_titles):
        print(f"{i+1}. {title}")

if __name__ == "__main__":
    # 测试一个具体的PDF文件
    test_file = "Statistical Programming.pdf"
    if Path(test_file).exists():
        test_pdf_chapter_detection(test_file)
    else:
        print(f"文件 {test_file} 不存在")
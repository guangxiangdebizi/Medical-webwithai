from __future__ import annotations

from pathlib import Path
import argparse
import json
import re
from typing import Dict, Iterable, List, Optional, Tuple


MD_DIR = Path(__file__).parent / "markdown_chapters"
OUT_JSONL = Path(__file__).parent / "processed_corpus.jsonl"
STRUCTURED_JSONL = Path(__file__).parent / "structured_corpus.jsonl"


def ensure_md_dir() -> Path:
    base = MD_DIR
    if not base.exists() or not base.is_dir():
        raise ValueError(f"markdown_chapters 不存在: {base}")
    return base


def list_md_files() -> List[Path]:
    base = ensure_md_dir()
    return sorted(base.glob("*.md"))


def read_text(path: Path) -> str:
    with open(path, "r", encoding="utf-8", errors="strict") as f:
        return f.read()


def _noise_patterns(mode: str) -> List[Tuple[str, re.Pattern]]:
    # 保守模式：仅移除带有明显系统页眉/编号/生效信息的行
    conservative: List[Tuple[str, re.Pattern]] = [
        ("retrieved_notice", re.compile(r"^This copy of the document was retrieved", re.IGNORECASE)),
        ("confidential", re.compile(r"^Company Confidential Document No\.", re.IGNORECASE)),
        ("vv_qdoc_number", re.compile(r"^Number:\s*VV-QDOC-", re.IGNORECASE)),
        ("status_effective", re.compile(r"^\s*Status:\s*Effective", re.IGNORECASE)),
        ("effective_date", re.compile(r"^\s*Effective Date:\s*", re.IGNORECASE)),
    ]
    # 激进模式：在保守基础上，额外移除孤立的版式残片（可能来自页眉分行）
    aggressive_extra: List[Tuple[str, re.Pattern]] = [
        ("orphan_WORK", re.compile(r"^\s*WORK\s*$", re.IGNORECASE)),
        ("orphan_INSTRUCTION", re.compile(r"^\s*INSTRUCTION\s*$", re.IGNORECASE)),
        ("orphan_SOP", re.compile(r"^\s*STANDARD OPERATING PROCEDURE\s*$", re.IGNORECASE)),
    ]
    return conservative + (aggressive_extra if mode == "aggressive" else [])


def clean_text(text: str, mode: str = "conservative") -> Tuple[str, Dict[str, int]]:
    # 移除通用页眉/页脚噪音（可选：保守/激进），并统计移除计数
    lines = text.splitlines()
    cleaned: List[str] = []
    patterns = _noise_patterns(mode)
    removed_counts: Dict[str, int] = {k: 0 for k, _ in patterns}

    for raw in lines:
        line = raw.strip()
        if not line:
            cleaned.append("")
            continue
        matched = False
        for key, pat in patterns:
            if pat.search(line):
                removed_counts[key] += 1
                matched = True
                break
        if matched:
            continue
        cleaned.append(raw)

    # 合并多余空行（最多保留一个）
    merged: List[str] = []
    empty_streak = 0
    for raw in cleaned:
        if raw.strip() == "":
            empty_streak += 1
            if empty_streak <= 1:
                merged.append("")
        else:
            empty_streak = 0
            merged.append(raw.rstrip())
    return "\n".join(merged).strip(), removed_counts


def detect_chapters(text: str) -> List[Tuple[str, int, int]]:
    lines = text.splitlines()
    chapter_lines: List[Tuple[int, str]] = []
    pat_list = [
        re.compile(r"^#\s*\d+\.?\s+.+"),  # 标题行形式的 1., 1.1 等
        re.compile(r"^\d+\.\s+.+"),
        re.compile(r"^\d+\.\d+\s+.+"),
        re.compile(r"^\d+\.\d+\.\d+\s+.+"),
        re.compile(r"^Appendix\s+\d+:.*", re.IGNORECASE),
        re.compile(r"^(PURPOSE|SCOPE|ABBREVIATIONS AND DEFINITIONS|RESPONSIBILITIES|INSTRUCTION|PROCEDURE|REFERENCES|APPENDICES)\s*$", re.IGNORECASE),
        re.compile(r"^[一二三四五六七八九十]+[、．]\s*.*"),
        re.compile(r"^第[一二三四五六七八九十]+[章节]\s*.*"),
    ]
    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line or len(line) > 150:
            continue
        for pat in pat_list:
            if pat.match(line):
                if not chapter_lines or chapter_lines[-1][0] != idx:
                    chapter_lines.append((idx, line))
                break
    chapters: List[Tuple[str, int, int]] = []
    if not chapter_lines:
        return chapters
    for i, (line_no, title) in enumerate(chapter_lines):
        start = line_no
        end = chapter_lines[i + 1][0] if i + 1 < len(chapter_lines) else len(lines)
        chapters.append((title, start, end))
    return chapters


# -----------------------
# Structured extraction
# -----------------------

def extract_metadata_from_raw(raw: str) -> Dict[str, Optional[str]]:
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    title = None
    for ln in lines[:10]:
        m = re.match(r"^#\s+(.+)$", ln)
        if m:
            title = m.group(1).strip()
            break
    if title is None and lines:
        title = lines[0]

    def find_one(pat: str) -> Optional[str]:
        r = re.compile(pat, re.IGNORECASE)
        for ln in lines[:80]:
            m = r.search(ln)
            if m:
                return m.group(1).strip()
        return None

    number = find_one(r"Number:\s*([A-Za-z0-9\-]+)")
    version = find_one(r"Version:\s*([0-9.]+)")
    status = find_one(r"Status:\s*([A-Za-z]+)")
    eff_date = find_one(r"Effective Date:\s*([0-9A-Za-z\s/]+)")

    upper = raw.upper()
    if re.search(r"\bSTANDARD OPERATING PROCEDURE\b", upper) or re.search(r"\bSOP\b", upper):
        doc_type = "SOP"
    elif re.search(r"\bWORK\s*INSTRUCTION\b", upper) or re.search(r"\bWI\b", upper):
        doc_type = "WI"
    else:
        doc_type = "DOC"

    return {
        "title": title,
        "number": number,
        "version": version,
        "status": status,
        "effective_date": eff_date,
        "doc_type": doc_type,
    }


def parse_outline(text: str) -> List[Dict[str, object]]:
    lines = text.splitlines()
    headings: List[Tuple[int, str, int]] = []  # (level, title, line_index)
    for idx, raw in enumerate(lines):
        ln = raw.strip()
        if not ln or len(ln) > 200:
            continue
        m = re.match(r"^(#+)\s+(.+)$", ln)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            headings.append((level, title, idx))
            continue
        m = re.match(r"^(\d+(?:\.\d+){0,3})\s+(.+)$", ln)
        if m:
            level = m.group(1).count(".") + 1
            title = f"{m.group(1)} {m.group(2).strip()}"
            headings.append((level, title, idx))
            continue
        if re.match(r"^(PURPOSE|SCOPE|ABBREVIATIONS AND DEFINITIONS|RESPONSIBILITIES|INSTRUCTION|PROCEDURE|REFERENCES|APPENDICES)\s*$", ln, re.IGNORECASE):
            title = ln
            level = 1
            headings.append((level, title, idx))
            continue

    if not headings:
        return []

    # Compute end lines
    enriched: List[Dict[str, object]] = []
    for i, (level, title, start) in enumerate(headings):
        end = headings[i + 1][2] if i + 1 < len(headings) else len(lines)
        enriched.append({
            "level": level,
            "title": title,
            "start": start,
            "end": end,
            "content": "\n".join(lines[start:end]).strip(),
        })
    return enriched


def extract_abbreviations(section_text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for raw in section_text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        m = re.match(r"^(?:\d+(?:\.\d+)*\s*)?([A-Za-z][A-Za-z0-9\-/]{1,15})\s*:\s*(.+)$", ln)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip()
            if 1 < len(key) <= 15 and len(val) > 0:
                out[key] = val
    return out


def extract_responsibilities(section_text: str) -> Dict[str, List[str]]:
    roles: Dict[str, List[str]] = {}
    current_role: Optional[str] = None
    for raw in section_text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        m_role = re.match(r"^\d+\.\d+\s+(.+)$", ln)
        if m_role:
            current_role = m_role.group(1).strip()
            roles.setdefault(current_role, [])
            continue
        m_item = re.match(r"^\d+\.\d+\.\d+\s+(.+)$", ln)
        if m_item and current_role:
            roles[current_role].append(m_item.group(1).strip())
            continue
        # bullet style
        if current_role and re.match(r"^[-•]\s+", ln):
            roles[current_role].append(re.sub(r"^[-•]\s+", "", ln))
    return roles


def extract_procedure(section_text: str) -> List[Dict[str, object]]:
    # Build nested steps from numbering like 5.1, 5.1.1
    steps: List[Dict[str, object]] = []
    stack: List[Tuple[List[Dict[str, object]], int]] = [(steps, 0)]
    for raw in section_text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        m = re.match(r"^(\d+(?:\.\d+){0,4})\s+(.+)$", ln)
        if not m:
            continue
        ident = m.group(1)
        text = m.group(2).strip()
        level = ident.count(".") + 1
        node = {"id": ident, "text": text, "children": []}
        while stack and stack[-1][1] >= level:
            stack.pop()
        stack[-1][0].append(node)
        stack.append((node["children"], level))
    return steps


def extract_references(section_text: str) -> List[str]:
    refs: List[str] = []
    for raw in section_text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if re.match(r"^[-•]\s+", ln) or re.match(r"^\d+\.\s+", ln):
            refs.append(re.sub(r"^([-•]|\d+\.)\s+", "", ln))
    return refs


def build_structured_document(md_path: Path, mode: str = "conservative") -> Dict[str, object]:
    raw = read_text(md_path)
    meta = extract_metadata_from_raw(raw)
    cleaned, _ = clean_text(raw, mode=mode)
    outline = parse_outline(cleaned)

    # Section lookup (case-insensitive contains)
    def find_section(names: List[str]) -> Optional[str]:
        for node in outline:
            title = str(node.get("title", ""))
            for nm in names:
                if re.search(rf"\b{re.escape(nm)}\b", title, re.IGNORECASE):
                    return str(node.get("content", ""))
        return None

    sec_abbr = find_section(["ABBREVIATIONS AND DEFINITIONS", "ABBREVIATIONS", "DEFINITIONS"])
    sec_resp = find_section(["RESPONSIBILITIES"]) 
    sec_proc = find_section(["INSTRUCTION", "PROCEDURE"]) 
    sec_refs = find_section(["REFERENCES"]) 

    abbreviations = extract_abbreviations(sec_abbr) if sec_abbr else {}
    responsibilities = extract_responsibilities(sec_resp) if sec_resp else {}
    procedure = extract_procedure(sec_proc) if sec_proc else []
    references = extract_references(sec_refs) if sec_refs else []

    return {
        "filename": md_path.stem,
        "metadata": meta,
        "chapter_titles": [n["title"] for n in outline] if outline else ["FULL_TEXT"],
        "outline": outline,
        "abbreviations": abbreviations,
        "responsibilities": responsibilities,
        "procedure": procedure,
        "references": references,
    }


def iter_records(md_path: Path, mode: str = "conservative") -> Iterable[Dict[str, str]]:
    raw = read_text(md_path)
    text, _ = clean_text(raw, mode=mode)
    lines = text.splitlines()
    chapters = detect_chapters(text)

    if not chapters:
        yield {
            "filename": md_path.stem,
            "chapter_title": "FULL_TEXT",
            "content": text,
        }
        return

    for title, start, end in chapters:
        content = "\n".join(lines[start:end]).strip()
        if not content:
            continue
        yield {
            "filename": md_path.stem,
            "chapter_title": title,
            "content": content,
        }


def export_jsonl(out_path: Path = OUT_JSONL, mode: str = "conservative", report_path: Optional[Path] = None) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    report: Dict[str, Dict[str, object]] = {}
    with open(out_path, "w", encoding="utf-8") as f:
        for md_file in list_md_files():
            raw = read_text(md_file)
            cleaned, removed = clean_text(raw, mode=mode)
            chapters = detect_chapters(cleaned)
            before_len = len(raw)
            after_len = len(cleaned)
            report[md_file.name] = {
                "mode": mode,
                "removed_counts": removed,
                "before_chars": before_len,
                "after_chars": after_len,
                "num_chapters": len(chapters) if chapters else 1,
                "chapter_titles": [t for (t, _, _) in chapters] if chapters else ["FULL_TEXT"],
            }
            for rec in iter_records(md_file, mode=mode):
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                count += 1
    if report_path is not None:
        with open(report_path, "w", encoding="utf-8") as rf:
            json.dump(report, rf, ensure_ascii=False, indent=2)
    print(f"exported {count} records to {out_path}")
    if report_path is not None:
        print(f"wrote report to {report_path}")
    return out_path


def export_structured_jsonl(out_path: Path = STRUCTURED_JSONL, mode: str = "conservative") -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for md_file in list_md_files():
            doc = build_structured_document(md_file, mode=mode)
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            count += 1
    print(f"exported {count} structured documents to {out_path}")
    return out_path


def _preview_one(md_file: Path, mode: str = "conservative", max_lines: int = 80) -> None:
    raw = read_text(md_file)
    cleaned, removed = clean_text(raw, mode=mode)
    chapters = detect_chapters(cleaned)
    print(f"Preview: {md_file.name} (mode={mode})")
    print("Removed counts:", json.dumps(removed, ensure_ascii=False))
    print("Chapters:", [t for (t, _, _) in chapters] if chapters else ["FULL_TEXT"]) 
    print("--- BEFORE (head) ---")
    for line in raw.splitlines()[:max_lines]:
        print(line)
    print("--- AFTER (head) ---")
    for line in cleaned.splitlines()[:max_lines]:
        print(line)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process SAS Markdown corpus for RAG.")
    parser.add_argument("--mode", choices=["conservative", "aggressive"], default="conservative", help="Cleaning strictness")
    parser.add_argument("--out", type=str, default=str(OUT_JSONL), help="Output JSONL path")
    parser.add_argument("--report", type=str, default=None, help="Write a cleaning report (JSON)")
    parser.add_argument("--preview", type=str, default=None, help="Preview a single Markdown file (path)")
    parser.add_argument("--structured-out", type=str, default=None, help="Write structured JSONL per document")
    parser.add_argument("--preview-structure", type=str, default=None, help="Preview structured extraction for a single file (path)")
    args = parser.parse_args()

    mode = args.mode
    out_path = Path(args.out)
    report_path = Path(args.report) if args.report else None
    if args.preview:
        md_file = Path(args.preview)
        if not md_file.exists():
            # 允许仅输入文件名，自动在目录下匹配
            candidate = MD_DIR / md_file
            if candidate.exists():
                md_file = candidate
        if not md_file.exists():
            raise FileNotFoundError(f"Preview file not found: {args.preview}")
        _preview_one(md_file, mode=mode)
        return
    if args.preview_structure:
        md_file = Path(args.preview_structure)
        if not md_file.exists():
            candidate = MD_DIR / md_file
            if candidate.exists():
                md_file = candidate
        if not md_file.exists():
            raise FileNotFoundError(f"Preview file not found: {args.preview_structure}")
        doc = build_structured_document(md_file, mode=mode)
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return

    export_jsonl(out_path=out_path, mode=mode, report_path=report_path)
    if args.structured_out:
        export_structured_jsonl(out_path=Path(args.structured_out), mode=mode)


if __name__ == "__main__":
    main()



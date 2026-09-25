"""
Task 3 — Chuẩn hóa dữ liệu sang Markdown.

Cấu trúc giữ nguyên hai nhánh:
    data/landing/legal/*.pdf   -> data/standardized/legal/*.md
    data/landing/news/*.json   -> data/standardized/news/*.md

Vì sao không chỉ gọi MarkItDown rồi ghi ra file:
    1. MarkItDown trả về plain text, 0 heading, 0 bảng — nó rút text khỏi PDF
       chứ không dựng lại cấu trúc Markdown.
    2. Text trích từ PDF dính khoảng trắng đôi (PDF canh lề đều) và bị ngắt dòng
       giữa câu theo layout trang giấy. Không xử lý thì chunker ở task 4 sẽ cắt
       giữa câu và retrieval trả về mảnh cụt.
    3. Văn bản pháp quy có sẵn cấu trúc Chương/Điều (6 file này: 222 "Điều N",
       18 "CHƯƠNG"). Khôi phục thành heading Markdown để task 4 chunk theo đúng
       ranh giới Điều, và task 8 (PageIndex) có cây mục lục để duyệt.
    4. Metadata phải nhúng vào file .md: task 4 load_documents() chỉ đọc
       standardized/, không đọc landing/. Không nhúng thì mất url và doc_type
       mà docs/MODULE_CONTRACTS.md yêu cầu.

Dùng YAML frontmatter cho cả hai nhánh để task 4 chỉ cần một parser.
"""

import json
import re
from pathlib import Path

from markitdown import MarkItDown

from src.task1_collect_legal_docs import SOURCES


LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"

# "Điều 5. Đăng ký học phần" / "Điều 12."
DIEU_PATTERN = re.compile(r"^(Điều\s+\d+\s*\.?)\s*(.*)$")
# "CHƯƠNG II" / "Chương II. QUY ĐỊNH CHUNG"
CHUONG_PATTERN = re.compile(r"^(CHƯƠNG|Chương)\s+([IVXLC]+)\s*\.?\s*(.*)$")
# Dòng mục lục: "Điều 3. Môn học ................ 4" — trùng nội dung với thân bài,
# biến thành heading sẽ tạo chunk rỗng và làm nhiễu PageIndex.
TOC_PATTERN = re.compile(r"\.{4,}")


# Một số PDF dùng font ánh xạ sai "ư" thành "ƣ" (U+01A3), ký tự không dùng trong
# tiếng Việt hiện đại. Văn bản 196/QĐ-ĐHCNTT dính 151 lần, khiến "đƣợc" không khớp
# "được" ở cả embedding lẫn BM25. Chỉ map hai ký tự chắc chắn sai, không đụng tới
# những ký tự hợp lệ như "õ" hay "ĩ".
BROKEN_CHARS = {"ừ": "ừ", "ƣ": "ư", "Ƣ": "Ư"}


def normalize_text(text: str) -> str:
    """Gộp khoảng trắng thừa và nối lại những câu bị PDF ngắt giữa chừng."""
    for broken, fixed in BROKEN_CHARS.items():
        text = text.replace(broken, fixed)

    lines = [re.sub(r"[ \t]{2,}", " ", line).strip() for line in text.splitlines()]

    merged: list[str] = []
    for line in lines:
        if not line:
            merged.append("")
            continue
        previous = merged[-1] if merged else ""
        # Nối khi dòng trước chưa kết thúc câu và dòng này viết thường
        # -> gần như chắc chắn là một câu bị layout trang giấy cắt đôi.
        if (
            previous
            and not previous.endswith((".", ":", ";", "!", "?", "-"))
            and line[:1].islower()
        ):
            merged[-1] = f"{previous} {line}"
        else:
            merged.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(merged)).strip()


def restore_headings(text: str) -> str:
    """Đưa Chương/Điều về heading Markdown để chunker và PageIndex bám vào được."""
    output: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()

        if TOC_PATTERN.search(stripped):
            continue

        chuong = CHUONG_PATTERN.match(stripped)
        if chuong and len(stripped) < 120:
            prefix, numeral, rest = chuong.groups()
            heading = f"{prefix} {numeral}" + (f". {rest}" if rest else "")
            output.append(f"\n# {heading}")
            continue

        dieu = DIEU_PATTERN.match(stripped)
        if dieu and len(stripped) < 200:
            number, rest = dieu.groups()
            heading = f"{number} {rest}".strip()
            output.append(f"\n## {heading}")
            continue

        output.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(output)).strip()


def build_frontmatter(
    source: str, title: str, doc_type: str, url: str | None, **extra: str
) -> str:
    """YAML frontmatter theo schema metadata của docs/MODULE_CONTRACTS.md."""
    fields = {
        "source": source,
        "title": title,
        "doc_type": doc_type,
        "url": url or "",
        **extra,
    }
    body = "".join(
        f'{key}: "{str(value).replace(chr(34), chr(39))}"\n'
        for key, value in fields.items()
    )
    return f"---\n{body}---\n\n"


def convert_legal_docs() -> None:
    """PDF/DOCX -> standardized/legal/*.md, có frontmatter và heading Chương/Điều."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    converter = MarkItDown()
    for path in sorted(legal_dir.iterdir()):
        if path.suffix.lower() not in {".pdf", ".doc", ".docx"}:
            continue

        text = converter.convert(str(path)).text_content
        body = restore_headings(normalize_text(text))
        if len(body) < 200:
            print(f"Skip (nội dung quá ngắn, nhiều khả năng là bản scan): {path.name}")
            continue

        # Tên văn bản và URL lấy từ SOURCES ở task 1 — PDF không tự mang metadata này.
        info = SOURCES.get(path.name, {})
        title = info.get("title") or path.stem.replace("-", " ")
        header = build_frontmatter(path.name, title, "legal", info.get("url"))

        (output_dir / f"{path.stem}.md").write_text(header + body, encoding="utf-8")
        print(f"legal: {path.stem}.md ({len(body)} ký tự)")


def convert_news_articles() -> None:
    """JSON -> standardized/news/*.md, giữ nguyên metadata đã crawl."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(news_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        body = data["content_markdown"].strip()
        if len(body) < 200:
            print(f"Skip (nội dung quá ngắn): {path.name}")
            continue

        header = build_frontmatter(
            path.name,
            data["title"],
            "news",
            data["url"],
            date_crawled=data["date_crawled"],
        )

        (output_dir / f"{path.stem}.md").write_text(header + body, encoding="utf-8")
        print(f"news:  {path.stem}.md ({len(body)} ký tự)")


def convert_all() -> None:
    """Convert toàn bộ dữ liệu landing."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    convert_legal_docs()
    convert_news_articles()
    print(f"Saved Markdown to: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()

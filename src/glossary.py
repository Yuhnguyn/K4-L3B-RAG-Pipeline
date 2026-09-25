"""
Glossary viết tắt cho corpus quy chế UIT.

Cơ sở: Recommendation #1 trong group_project/evaluation/RESULT.md. Văn bản
159/QĐ-ĐHCNTT dùng "KLTN" 113 lần nhưng chỉ viết đầy đủ 11 lần ("khóa luận tốt
nghiệp"), "CBPB" 25 lần so với 2 lần. Câu hỏi của người dùng viết đầy đủ nên cả
dense lẫn BM25 đều khớp nhầm sang văn bản 790 (viết đầy đủ) và bỏ sót văn bản
159 (chứa câu trả lời) — case có context_recall = 0.000.

Khắc phục: đọc bảng viết tắt ngay trong văn bản rồi, lúc index, chèn dạng đầy
đủ vào chunk. Vì chunk `content` là nguồn chung của cả dense (embedding) và BM25
(token), một lần chèn có tác dụng cho cả hai retriever.

Nguồn bảng viết tắt trong corpus:
    - 159/QĐ-ĐHCNTT — Điều 2, mỗi dòng dạng "▪ KLTN: Khóa luận tốt nghiệp".
    - 1032/QĐ-ĐHCNTT — "DANH MỤC TỪ VIẾT TẮT" dạng bảng Markdown.
    - 956/QĐ-ĐHCNTT — câu nội tuyến "(sau đây viết tắt là CTC)".
    - 790/QĐ-ĐHCNTT — "DANH MỤC TỪ VIẾT TẮT", nhưng PDF tách rời khối viết tắt
      và khối định nghĩa nên không còn ghép cặp 1-1 được; các mục của 790 nằm
      trong MANUAL, ghi rõ nguồn.

Vì sao phải thêm dòng chú thích ở cuối chunk thay vì sửa thẳng trong câu: phần
thân văn bản được giữ nguyên văn để trích dẫn đối chiếu được với PDF gốc — đây
là yêu cầu xuyên suốt của báo cáo nhóm.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


STANDARDIZED_LEGAL_DIR = (
    Path(__file__).parent.parent / "data" / "standardized" / "legal"
)

# Một key chỉ được coi là viết tắt khi toàn bộ ký tự nằm trong nhóm in hoa, số
# và ký hiệu mã văn bản. Nhờ đó "Khoa", "Hội đồng", "Môn học cốt lõi" trong bảng
# thuật ngữ bị loại — nếu không, mọi chunk chứa chữ "Khoa" đều nhận chú thích.
ABBREV_PATTERN = re.compile(r"^[A-ZĐ][A-ZĐ0-9.&/\-]{1,11}$")

# Bỏ qua viết tắt 2 ký tự như SV, TV, CH: chúng có mặt ở gần như mọi chunk nên
# thêm chú thích vào mọi chunk chỉ làm loãng embedding mà không cải thiện truy
# vấn nào. Các viết tắt mục tiêu (KLTN, CBHD, CBPB, CTĐT, ĐTBHK...) đều >= 3.
MIN_ABBREV_LEN = 3
MAX_ABBREV_LEN = 12

# Chặn footer phình to ở chunk chứa quá nhiều viết tắt.
MAX_TERMS_PER_CHUNK = 12

# Dừng lấy "DANH MỤC TỪ VIẾT TẮT" khi gặp đầu chương, footer trang, hoặc số trang.
_SECTION_STOP = re.compile(r"(?m)^\s*(#\s*)?(CHƯƠNG|Chương|Trang|\d+\s*$)")

# "▪ KLTN: Khóa luận tốt nghiệp" (▪ là U+FF0D trong PDF gốc).
_COLON_ENTRY = re.compile(r"^[\uf02d\-\u2013•]\s*([^:]{1,16}?)\s*:\s*(.+?)\s*$")

# "| CTTN | | Chương trình Tài năng |"
_TABLE_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*\|\s*([^|]+?)\s*\|\s*$")

# "VPCTĐB Văn phòng các chương trình đặc biệt" — dòng bảng bị vỡ, mất dấu "|".
_PLAIN_PAIR = re.compile(r"^([A-ZĐ][A-ZĐ0-9.&/\-]{1,11})\s+(\S.*)$")

# "chương trình chuẩn (sau đây viết tắt là CTC)". Loại cả ':' và ';' khỏi vế
# mở rộng để không hút cụm dẫn như "bao gồm:" vào định nghĩa.
_INLINE_ENTRY = re.compile(
    r"([^,():;\n]+?)\s*\(sau đây viết tắt là ([A-ZĐ][A-ZĐ0-9]{1,11})\)"
)


# 790/QĐ-ĐHCNTT, "DANH MỤC TỪ VIẾT TẮT" — PDF tách khối viết tắt (dòng 51-69)
# khỏi khối định nghĩa (dòng 71-99) nên không ghép cặp tự động được. Dựng lại
# thủ công từ đúng hai khối đó. Vài mục của 956 cũng chép tay vì câu nội tuyến
# có thể bị PDF ngắt dòng giữa "viết tắt là".
MANUAL: dict[str, str] = {
    "TCHP": "Tín chỉ học phí",
    "TCHPHL": "Tín chỉ học phí học lại",
    "TCHPCT": "Tín chỉ học phí học cải thiện",
    "TCHPHM": "Tín chỉ học phí học mới",
    "HPHK": "Học phí học kỳ",
    "CSĐT": "Cơ sở đào tạo",
    "ĐTBHK": "Điểm trung bình học kỳ",
    "ĐTBC": "Điểm trung bình chung",
    "ĐTBCTL": "Điểm trung bình chung tích lũy",
    "ĐKHP": "Đăng ký học phần",
    "CTC": "chương trình chuẩn",
    "CTA": "chương trình dạy và học bằng tiếng Anh",
    "CTTT": "chương trình tiên tiến",
    "VB2": "chương trình văn bằng hai",
    "NNCM": "môn học Ngoại ngữ chuyên môn",
}

_SECTION_MARKERS = ("DANH MỤC TỪ VIẾT TẮT", "Một số thuật ngữ, chữ viết tắt")

_GLOSSARY_CACHE: dict[str, str] | None = None


def _is_abbreviation(key: str) -> bool:
    """Key có phải viết tắt thật (không phải một cụm từ thường)."""
    key = key.strip()
    if not (MIN_ABBREV_LEN <= len(key) <= MAX_ABBREV_LEN):
        return False
    if not ABBREV_PATTERN.match(key):
        return False
    # "Đ." hay "P" không đủ phân biệt; cần ít nhất hai ký tự in hoa.
    return sum(character.isupper() for character in key) >= 2


def _add(target: dict[str, str], key: str, expansion: str) -> None:
    key = key.strip()
    expansion = " ".join(expansion.split()).strip(" .;:–-")
    if expansion and _is_abbreviation(key) and key not in target:
        target[key] = expansion


def _glossary_sections(text: str) -> list[str]:
    """Các đoạn văn bản nằm trong mục từ viết tắt."""
    sections: list[str] = []
    for marker in _SECTION_MARKERS:
        start = text.find(marker)
        if start == -1:
            continue
        tail = text[start + len(marker):]
        stop = _SECTION_STOP.search(tail)
        sections.append(tail[: stop.start()] if stop else tail)
    return sections


def parse_glossary_text(text: str) -> dict[str, str]:
    """Trích mọi cặp viết tắt -> định nghĩa từ một văn bản Markdown."""
    found: dict[str, str] = {}

    for line in text.splitlines():
        match = _COLON_ENTRY.match(line)
        if match:
            _add(found, match.group(1), match.group(2))

    for section in _glossary_sections(text):
        for line in section.splitlines():
            table = _TABLE_ROW.match(line)
            if table:
                _add(found, table.group(1), table.group(2))
                continue
            broken = _PLAIN_PAIR.match(line)
            if broken:
                _add(found, broken.group(1), broken.group(2))

    for expansion, abbreviation in _INLINE_ENTRY.findall(text):
        _add(found, abbreviation, expansion)

    return found


def load_glossary(directory: Path | str | None = None) -> dict[str, str]:
    """Gộp bảng viết tắt của mọi văn bản legal, rồi phủ MANUAL lên trên.

    Kết quả được cache vì ``expand_for_indexing`` gọi một lần cho mỗi chunk
    (hàng trăm lần mỗi lần index).
    """
    global _GLOSSARY_CACHE

    if directory is None and _GLOSSARY_CACHE is not None:
        return _GLOSSARY_CACHE

    base = Path(directory) if directory else STANDARDIZED_LEGAL_DIR
    glossary: dict[str, str] = {}
    if base.is_dir():
        for path in sorted(base.glob("*.md")):
            parsed = parse_glossary_text(path.read_text(encoding="utf-8"))
            # Giữ mục gặp trước: bảng của 1032 có "Chương trình Tài năng" còn câu
            # nội tuyến của 956 viết thường cùng viết tắt; bản đầu thường chuẩn hơn.
            for abbreviation, expansion in parsed.items():
                glossary.setdefault(abbreviation, expansion)
    # MANUAL thắng: sửa những mục parser không lấy được hoặc lấy sai.
    glossary.update(MANUAL)

    if directory is None:
        _GLOSSARY_CACHE = glossary
    return glossary


def expand_for_indexing(text: str, glossary: dict[str, str] | None = None) -> str:
    """Nối dòng chú thích viết tắt vào cuối chunk, giữ nguyên văn phần thân.

    Chỉ thêm khi chunk thực sự chứa viết tắt, và chỉ thêm một lần (idempotent).
    """
    if not text or not text.strip():
        return text
    if "[Từ viết tắt:" in text:
        return text
    # Cờ để đo A/B: đặt GLOSSARY_EXPANSION=0 thì giữ nguyên chunk, dùng lại đúng
    # code cho lượt baseline thay vì sửa file rồi revert.
    if os.getenv("GLOSSARY_EXPANSION", "1").strip().lower() in {
        "0", "false", "no", "off",
    }:
        return text

    glossary = glossary if glossary is not None else load_glossary()

    terms: list[tuple[str, str]] = []
    for abbreviation, expansion in glossary.items():
        # Biên từ: "ĐTĐH" không được khớp bên trong "P.ĐTĐH".
        if re.search(
            rf"(?<![\w.]){re.escape(abbreviation)}(?![\w])", text
        ):
            terms.append((abbreviation, expansion))

    if not terms:
        return text

    terms.sort()
    note = "; ".join(
        f"{abbreviation} = {expansion}"
        for abbreviation, expansion in terms[:MAX_TERMS_PER_CHUNK]
    )
    return f"{text.rstrip()}\n\n[Từ viết tắt: {note}]"


if __name__ == "__main__":
    entries = load_glossary()
    print(f"{len(entries)} viết tắt:")
    for abbreviation, expansion in sorted(entries.items()):
        print(f"  {abbreviation:<12} {expansion}")

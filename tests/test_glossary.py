import pytest

from src.glossary import (
    expand_for_indexing,
    load_glossary,
    parse_glossary_text,
)


def test_parse_colon_format():
    text = (
        "\uf02d KLTN: Khóa luận tốt nghiệp\n"
        "\uf02d CBPB: Cán bộ phản biện\n"
        "\uf02d Khoa: Khoa quản lý SV\n"  # cụm từ thường, phải bị loại
    )
    glossary = parse_glossary_text(text)
    assert glossary["KLTN"] == "Khóa luận tốt nghiệp"
    assert glossary["CBPB"] == "Cán bộ phản biện"
    assert "Khoa" not in glossary


def test_parse_markdown_table_and_broken_row():
    text = (
        "DANH MỤC TỪ VIẾT TẮT\n\n"
        "| CTTN | | Chương trình Tài năng |\n"
        "| ---------- | --- | --------------------- |\n"
        "VPCTĐB Văn phòng các chương trình đặc biệt\n"
        "| CTĐT | | Chương trình đào tạo |\n\n"
        "Chương 1. NHỮNG QUY ĐỊNH CHUNG\n"
        "| KHONGCO | | Không được lấy vì ngoài mục |\n"
    )
    glossary = parse_glossary_text(text)
    assert glossary["CTTN"] == "Chương trình Tài năng"
    assert glossary["VPCTĐB"] == "Văn phòng các chương trình đặc biệt"
    assert glossary["CTĐT"] == "Chương trình đào tạo"
    assert "KHONGCO" not in glossary


def test_parse_inline_format():
    text = (
        "bao gồm: chương trình chuẩn (sau đây viết tắt là CTC), "
        "chương trình tài năng (sau đây viết tắt là CTTN)."
    )
    glossary = parse_glossary_text(text)
    assert glossary["CTC"] == "chương trình chuẩn"
    assert glossary["CTTN"] == "chương trình tài năng"


def test_load_glossary_covers_entries_from_several_documents():
    glossary = load_glossary()
    assert glossary["KLTN"] == "Khóa luận tốt nghiệp"      # 159, Điều 2
    assert glossary["CBPB"] == "Cán bộ phản biện"           # 159, Điều 2
    assert glossary["CTTN"] == "Chương trình Tài năng"      # 1032, bảng
    assert glossary["ĐTBHK"] == "Điểm trung bình học kỳ"    # 790, MANUAL
    assert glossary["CTC"] == "chương trình chuẩn"          # 956, nội tuyến


def test_glossary_excludes_prose_and_short_abbreviations():
    glossary = load_glossary()
    assert "Khoa" not in glossary
    assert "Hội đồng" not in glossary
    assert "SV" not in glossary  # 2 ký tự: bị MIN_ABBREV_LEN loại


def test_expand_appends_footer_and_keeps_body_verbatim():
    text = "Sinh viên làm KLTN phải có CBHD và CBPB."
    expanded = expand_for_indexing(text)
    assert expanded.startswith(text)  # phần thân nguyên vẹn
    assert "KLTN = Khóa luận tốt nghiệp" in expanded
    assert "CBHD = Cán bộ hướng dẫn" in expanded
    assert "CBPB = Cán bộ phản biện" in expanded


def test_expand_is_noop_without_abbreviation():
    text = "Sinh viên phải hoàn thành nghĩa vụ học phí đúng quy định."
    assert expand_for_indexing(text) == text


def test_expand_ignores_short_abbreviations():
    assert "[Từ viết tắt:" not in expand_for_indexing("SV nộp hồ sơ cho Khoa.")


def test_expand_is_idempotent():
    text = "Điều kiện làm KLTN."
    once = expand_for_indexing(text)
    assert expand_for_indexing(once) == once


def test_expand_can_be_disabled_by_env(monkeypatch):
    monkeypatch.setenv("GLOSSARY_EXPANSION", "0")
    text = "Điều kiện làm KLTN."
    assert expand_for_indexing(text) == text


@pytest.mark.parametrize("text", ["", "   \n  "])
def test_expand_handles_empty_text(text):
    assert expand_for_indexing(text) == text

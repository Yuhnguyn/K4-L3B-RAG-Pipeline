"""
Task 1 — Thu thập tài liệu chính sách/quy định.

Chủ đề nhóm: Quy chế & quy định dành cho sinh viên hệ đại học chính quy
             Trường Đại học Công nghệ Thông tin (UIT), ĐHQG-HCM.

Nguồn công khai (kiểm chứng được):
    - Cổng thông tin đào tạo UIT: https://student.uit.edu.vn/qui-che-qui-dinh-qui-trinh
    - Phòng Công tác Sinh viên UIT: https://ctsv.uit.edu.vn/bai-viet/quy-dinh-lien-quan-den-hoc-bong-sinh-vien

robots.txt của uit.edu.vn cho phép crawl (Allow: /), không cần vượt WAF.
Lưu ý đã kiểm chứng: nhiều PDF trên cổng UIT/ĐHQG/Bộ GDĐT là bản scan hoặc OCR
bằng font không Unicode (VNI/TCVN3) -> trích xuất ra ký tự rác, không dùng được.
6 file dưới đây đã được test bằng pypdf: có text Unicode, tỉ lệ ký tự tiếng Việt > 14%.
"""

from pathlib import Path

import requests


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"

# filename -> thông tin nguồn (url tải, trang công khai để đối chiếu, tên văn bản)
SOURCES: dict[str, dict[str, str]] = {
    "790-2022-quy-che-dao-tao-tin-chi.pdf": {
        "url": "https://student.uit.edu.vn/sites/daa/files/202309/790-qd-dhcntt_28-9-22_quy_che_dao_tao.pdf",
        "page": "https://student.uit.edu.vn/01-quyet-dinh-ve-viec-ban-hanh-quy-che-dao-tao-theo-hoc-che-tin-chi",
        "title": "Quy chế đào tạo theo học chế tín chỉ cho hệ đại học chính quy (790/QĐ-ĐHCNTT, 28/9/2022)",
    },
    "1139-2022-to-chuc-thi-tap-trung.pdf": {
        "url": "https://student.uit.edu.vn/sites/daa/files/202309/1139_qd-dhcntt_20-12-2022_to_chuc_thi_cac_mon_hoc_he_dai_hoc_chinh_quy.pdf",
        "page": "https://student.uit.edu.vn/07-quyet-dinh-ve-viec-ban-hanh-quy-dinh-chuc-thi-tap-trung-cac-mon-hoc-he-dhcq",
        "title": "Quy định tổ chức thi tập trung các môn học hệ đại học chính quy (1139/QĐ-ĐHCNTT, 20/12/2022)",
    },
    "956-2026-quy-che-dao-tao-ngoai-ngu.pdf": {
        "url": "https://student.uit.edu.vn/sites/daa/files/202608/956-qd-dhcntt_10-8-2026_quy_che_dao_tao_ngoai_ngu_tu_khoa_2026_0.pdf",
        "page": "https://student.uit.edu.vn/05-quy-dinh-dao-tao-ngoai-ngu-doi-voi-he-dai-hoc-chinh-quy-cua-truong-dhcntt",
        "title": "Quy chế đào tạo ngoại ngữ áp dụng từ khóa 2026 (956/QĐ-ĐHCNTT, 10/8/2026)",
    },
    "159-2024-quy-dinh-khoa-luan-tot-nghiep.pdf": {
        "url": "https://student.uit.edu.vn/sites/daa/files/202410/159-qd-dhcntt_05-03-2024_ban_hanh_quy_dinh_kltn.pdf",
        "page": "https://student.uit.edu.vn/06-quyet-dinh-ve-viec-ban-hanh-quy-dinh-ve-khoa-luan-tot-nghiep-cho-sv-he-cq",
        "title": "Quy định về Khóa luận tốt nghiệp cho bậc đại học hệ chính quy (159/QĐ-ĐHCNTT, 5/3/2024)",
    },
    "1032-2025-quy-dinh-chuong-trinh-tai-nang.pdf": {
        "url": "https://student.uit.edu.vn/sites/daa/files/202512/1032-qd-dhcntt_3-9-2025_quy_dinh_dao_tao_chuong_trinh_tai_nang.pdf",
        "page": "https://student.uit.edu.vn/04-quyet-dinh-ve-viec-ban-hanh-quy-dinh-ve-he-tai-nang",
        "title": "Quy định đào tạo chương trình tài năng (1032/QĐ-ĐHCNTT, 3/9/2025)",
    },
    "196-2023-day-hoc-truc-tuyen-ket-hop.pdf": {
        "url": "https://student.uit.edu.vn/sites/daa/files/202309/196-qd-dhcntt_16-3-2023_quy_dinh_day_va_hoc_theo_phuong_thuc_truc_tuyen_va_phuong_thuc_ket_hop.pdf",
        "page": "https://student.uit.edu.vn/thongbao/24-quyet-dinh-ve-viec-ban-hanh-quy-dinh-day-va-hoc-theo-phuong-thuc-truc-tuyen-va-phuong",
        "title": "Quy định dạy và học theo phương thức trực tuyến và phương thức kết hợp (196/QĐ-ĐHCNTT, 16/3/2023)",
    },
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; UIT-RAG-lab/1.0)"}


def setup_directory() -> None:
    """Tạo thư mục lưu tài liệu gốc."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Ready: {DATA_DIR}")


def download_documents() -> None:
    """Tải các PDF quy chế/quy định từ nguồn công khai của UIT."""
    for filename, info in SOURCES.items():
        url = info["url"]
        target = DATA_DIR / filename
        if target.exists() and target.stat().st_size > 1024:
            print(f"Skip (đã có): {filename}")
            continue
        response = requests.get(url, headers=HEADERS, timeout=60)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower():
            raise RuntimeError(f"{url} không trả về PDF (Content-Type={content_type})")
        target.write_bytes(response.content)
        print(f"Saved: {filename} ({len(response.content) // 1024} KB)")


if __name__ == "__main__":
    setup_directory()
    download_documents()

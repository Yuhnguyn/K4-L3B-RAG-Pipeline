"""
Task 2 — Crawl bài viết/thông báo.

Chủ đề: Quy chế & quy định dành cho sinh viên UIT (xem src/task1_collect_legal_docs.py).
Mỗi URL dưới đây bám sát một văn bản đã thu thập ở task 1, để corpus legal và news
bổ trợ nhau: quy chế cho biết "luật là gì", thông báo cho biết "kỳ này áp dụng ra sao".

Lưu ý đã kiểm chứng khi khảo sát nguồn:
    - www.uit.edu.vn là React SPA: nội dung render bằng JS, requests/curl crawl ra rỗng.
      Bắt buộc dùng trình duyệt thật -> Crawl4AI + `python -m playwright install chromium`.
    - student.uit.edu.vn và ctsv.uit.edu.vn là Drupal server-rendered, crawl dễ hơn,
      nhưng phần lớn trang thông báo chỉ là stub đính kèm PDF -> đã loại, chỉ giữ
      những trang có nội dung thật.
    - Sidebar ctsv.uit.edu.vn đang bị chèn link SEO rác -> lọc ở remove_boilerplate().
    - Không lấy trang có danh sách sinh viên (MSSV, họ tên) để tránh dữ liệu cá nhân.

robots.txt của uit.edu.vn cho phép crawl (Allow: /).

Cài browser trước khi chạy:
    python -m playwright install chromium
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator


DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

ARTICLE_URLS = [
    # Kế hoạch ĐKHP <-> Quy chế đào tạo tín chỉ (790/QĐ-ĐHCNTT)
    "https://www.uit.edu.vn/bai-viet/chinh-thuc-cong-bo-ke-hoach-dang-ky-hoc-phan-hoc-ky-i-nam-hoc-20262027",
    # Nhập học lại, bảo lưu, thôi học <-> Quy chế đào tạo tín chỉ (790/QĐ-ĐHCNTT)
    "https://www.uit.edu.vn/bai-viet/thong-bao-nhan-don-nhap-hoc-lai-bao-luu-chuyen-nganh-song-nganh-va-thoi-hoc-hoc-ky-i-nam-hoc-20262027",
    # Tuyển sinh hệ tài năng <-> Quy định chương trình tài năng (1032/QĐ-ĐHCNTT)
    "https://www.uit.edu.vn/bai-viet/tuyen-sinh-sinh-vien-tai-nang-nam-2026",
    # Kế hoạch xét tốt nghiệp <-> Quy định khóa luận tốt nghiệp (159/QĐ-ĐHCNTT)
    "https://www.uit.edu.vn/bai-viet/ke-hoach-xet-tot-nghiep-dot-02-nam-2026",
    # Học bổng khuyến khích học tập
    "https://www.uit.edu.vn/bai-viet/huong-dan-ve-quy-dinh-hoc-bong-khuyen-khich-hoc-tap-uit-tu-hoc-ky-i-nam-hoc-2026-2027",
    # Xét miễn Anh văn <-> Quy chế đào tạo ngoại ngữ (956/QĐ-ĐHCNTT)
    # (đã loại trang student.uit.edu.vn/content/huong-dan-sinh-vien-...-chuan-qua-trinh:
    #  sidebar nằm trong #main-content và nội dung thật là bảng ~123 link PDF, chunk ra rác)
    "https://www.uit.edu.vn/bai-viet/thong-bao-mien-xet-anh-van-1-2-3-dot-2-trong-hk2-nam-hoc-2025-2026",
    # Lịch trình tân sinh viên (nguồn Drupal, dự phòng nếu bài React bị ngắn)
    "https://ctsv.uit.edu.vn/bai-viet/lich-trinh-chi-tiet-danh-cho-tan-sinh-vien-khoa-2026",
]

MIN_CONTENT_CHARS = 300

# Link SEO rác bị chèn vào sidebar ctsv.uit.edu.vn, không liên quan nội dung.
SPAM_DOMAINS = ("mobile24h.com.vn", "thuexechatluong.net")

# Link trợ năng và menu còn sót của theme Drupal.
BOILERPLATE_PATTERNS = (
    re.compile(r"^\s*\[Skip to [^\]]+\]\([^)]*\)\s*$", re.I),
    re.compile(r"^\s*\[?(Đăng nhập|Sơ đồ website|Webmail|Trang chủ)\]?\s*\|?\s*$", re.I),
)

# student.uit.edu.vn và ctsv.uit.edu.vn dùng chung theme Drupal có #main-content.
# Không khoanh vùng thì menu và sidebar lọt hết vào markdown.
DRUPAL_CONTENT_SELECTOR = "#main-content"
DRUPAL_HOSTS = ("student.uit.edu.vn", "ctsv.uit.edu.vn")


def build_config(url: str) -> CrawlerRunConfig:
    """Cấu hình crawl; site Drupal cần khoanh vùng nội dung, site React thì không."""
    host = urlparse(url).netloc
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        wait_until="networkidle",     # chờ React render xong
        page_timeout=60000,
        excluded_tags=["nav", "header", "footer", "aside", "form", "script", "style"],
        exclude_external_links=True,
        word_count_threshold=10,
        # target_elements chỉ khoanh vùng lúc sinh markdown, vẫn giữ <head> để lấy title;
        # css_selector thì cắt luôn <head> nên mất metadata.
        target_elements=[DRUPAL_CONTENT_SELECTOR] if host in DRUPAL_HOSTS else None,
        markdown_generator=DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.45, threshold_type="dynamic")
        ),
    )


def slugify(url: str) -> str:
    """Tên file ổn định theo URL: chạy lại crawl ghi đè đúng file, không sinh bản sao."""
    slug = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    slug = re.sub(r"[^a-z0-9-]+", "-", slug.lower()).strip("-")
    return slug[:80] or "article"


def remove_boilerplate(markdown: str) -> str:
    """Bỏ link spam và dòng rỗng thừa còn sót sau bộ lọc của Crawl4AI."""
    lines = [
        line for line in markdown.splitlines()
        if not any(domain in line for domain in SPAM_DOMAINS)
        and not any(pattern.match(line) for pattern in BOILERPLATE_PATTERNS)
    ]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


async def crawl_article(url: str, crawler: AsyncWebCrawler | None = None) -> dict:
    """Crawl 1 URL -> dict đủ 4 field bắt buộc: url, title, date_crawled, content_markdown."""
    if crawler is None:
        async with AsyncWebCrawler(verbose=False) as own_crawler:
            return await crawl_article(url, own_crawler)

    result = await crawler.arun(url=url, config=build_config(url))
    if not result.success:
        raise RuntimeError(f"Crawl thất bại: {result.error_message}")

    markdown = result.markdown
    # fit_markdown đã bỏ menu/boilerplate; raw_markdown là bản dự phòng nếu lọc quá tay.
    content = getattr(markdown, "fit_markdown", "") or ""
    if len(content.strip()) < MIN_CONTENT_CHARS:
        content = getattr(markdown, "raw_markdown", None) or str(markdown)
    content = remove_boilerplate(content)

    if len(content) < MIN_CONTENT_CHARS:
        raise RuntimeError(f"Nội dung quá ngắn ({len(content)} ký tự) — nhiều khả năng là trang stub")

    title = (result.metadata or {}).get("title", "").strip()
    if not title:
        raise RuntimeError("Không lấy được title")

    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now().isoformat(),
        "content_markdown": content,
    }


async def crawl_all() -> None:
    """Crawl và lưu từng bài thành một file JSON."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    saved = 0
    # Dùng chung một browser cho mọi URL thay vì mở lại từng lần.
    async with AsyncWebCrawler(verbose=False) as crawler:
        for url in ARTICLE_URLS:
            try:
                article = await crawl_article(url, crawler)
                output = DATA_DIR / f"{slugify(url)}.json"
                output.write_text(
                    json.dumps(article, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                saved += 1
                print(f"Saved: {output.name} ({len(article['content_markdown'])} ký tự)")
            except Exception as error:
                print(f"Failed: {url} — {error}")

    print(f"\nĐã lưu {saved}/{len(ARTICLE_URLS)} bài (yêu cầu tối thiểu: 5)")


if __name__ == "__main__":
    asyncio.run(crawl_all())

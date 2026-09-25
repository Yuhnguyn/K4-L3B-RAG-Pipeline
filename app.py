import base64
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.task10_generation import (
    LLM_PROVIDER,
    generate_with_citation,
    reorder_for_llm,
    resolve_model,
)
from src.task9_retrieval_pipeline import SCORE_THRESHOLD


load_dotenv()

st.set_page_config(
    page_title="Hỏi đáp quy chế UIT",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Bảng màu và hình khối lấy từ uit.edu.vn: xanh #1D4ED8 chủ đạo, cam #F27A2A nhấn,
# nền sáng, bo tròn 0.5–1.5rem, nhiều khoảng trắng.
UIT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap');

:root {
    --blue: #1D4ED8;
    --blue-2: #2563EB;
    --blue-deep: #1E3A8A;
    --orange: #F27A2A;
    --orange-2: #EE583A;
    --tint: #EFF6FF;
    --tint-2: #DBEAFE;
    --ink: #1E293B;
    --muted: #64748B;
    --line: #E3EBF7;
}

/* KHÔNG dùng selector [class*="st-"] ở đây.
   Streamlit gán font icon (Material Symbols Rounded) qua class emotion sinh lúc
   chạy, dạng st-emotion-cache-xxxx. Selector [class*="st-"] khớp đúng những class
   đó và đè lên font icon, khiến icon hiện ra thành chữ: "gavel" thành "gave",
   "arrow_right", "keyboard_double_arrow_left".
   Đặt font ở gốc rồi để kế thừa xuống: phần tử nào đã có font-family riêng —
   đúng là các span icon — sẽ tự giữ font của nó. */
html, body, .stApp, button, input, textarea, [data-testid="stSidebar"] {
    font-family: 'Be Vietnam Pro', system-ui, sans-serif;
}

/* Lớp bảo hiểm: nếu phiên bản Streamlit sau đổi cách gán class, vẫn ép đúng
   font ligature cho các phần tử icon. */
[data-testid="stIconMaterial"],
span.material-symbols-rounded,
.material-icons, .material-icons-outlined, .material-symbols-outlined {
    font-family: 'Material Symbols Rounded' !important;
    font-feature-settings: 'liga' !important;
}

/* Chỉ ẩn thanh công cụ góc phải (Deploy, menu). KHÔNG ẩn cả <header> vì nút bung
   lại sidebar nằm trong header — ẩn đi thì thu sidebar xong không mở ra được nữa.
   Streamlit 1.64 đặt tên testid là stAppToolbar, không phải stToolbar. */
/* Tắt scroll anchoring. Trình duyệt tự bù vị trí cuộn khi nội dung phía trên đổi
   chiều cao (ảnh logo tải xong, expander bung ra, font web nạp muộn). Với trang
   chat dài, cơ chế này làm cuộn lên bị khựng rồi giật ngược xuống dưới. */
html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMainBlockContainer"], .block-container {
    overflow-anchor: none;
}

#MainMenu, footer {visibility: hidden;}
[data-testid="stAppToolbar"] {visibility: hidden;}
[data-testid="stDecoration"] {display: none;}
[data-testid="stHeader"] {background: transparent;}

/* Luôn giữ nút thu/bung sidebar bấm được, kể cả khi sidebar đang đóng. */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] * {
    visibility: visible !important;
    opacity: 1 !important;
}
[data-testid="stSidebarCollapseButton"] button {color: var(--blue) !important;}
.block-container {padding-top: 1.5rem; padding-bottom: 5rem; max-width: 1180px;}
.stApp {background: #FFFFFF;}

/* ---------- Hero ----------
   Mô phỏng nền hero của uit.edu.vn: dải gradient xanh nhạt sang trắng, rải các
   khối vuông bo góc màu cam và xanh ở hai mép, một số khối tràn ra ngoài khung. */
.hero {
    background: linear-gradient(170deg, #EDF3FF 0%, #FFFFFF 38%, #FFFFFF 62%, #E9F0FF 100%);
    border-radius: 1.5rem;
    padding: 34px 56px 36px 56px;
    position: relative;
    overflow: hidden;
    border: 1px solid var(--line);
    min-height: 300px;
}
.hero .inner {position: relative; z-index: 2; text-align: center;}
.hero-logo {height: 38px; width: auto; display: block; margin: 0 auto 24px auto;}

/* !important vì Streamlit đã có style riêng cho h1 trong markdown. */
.hero h1 {
    color: var(--blue) !important;
    font-size: 3.1rem; font-weight: 700; line-height: 1.14;
    margin: 0 auto; letter-spacing: -1.2px;
    text-shadow: 0 3px 22px rgba(29, 78, 216, 0.15);
}
.hero h1::after {
    content: ""; display: block;
    width: 92px; height: 5px; border-radius: 3px;
    background: var(--orange);
    margin: 22px auto;
}
.hero p {
    color: #47566B; font-size: 1.02rem; line-height: 1.7;
    margin: 0 auto; max-width: 720px; text-align: center;
}

.deco {
    position: absolute;
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    z-index: 1;
    opacity: 0.28;          /* hoạ tiết chỉ làm nền, không tranh chỗ với chữ */
}
.deco svg {width: 58%; height: 58%; opacity: 0.85;}
/* mép trái */
.d1 {left: -46px;  top: -30px;   width: 132px; height: 132px; background: #F2932F;}
.d2 {left: 6px;    top: 128px;   width: 92px;  height: 92px;  background: #F3A04A;}
.d3 {left: -38px;  bottom: -44px; width: 104px; height: 104px; background: #4A7BF7;}
/* mép phải */
.d4 {right: -40px; top: -26px;   width: 124px; height: 124px; background: #4A7BF7;}
.d5 {right: 14px;  top: 120px;   width: 88px;  height: 88px;  background: #F2932F;}
.d6 {right: -34px; bottom: -40px; width: 112px; height: 112px; background: #6C97FA;}
.d7 {right: 122px; bottom: 16px;  width: 54px;  height: 54px;  background: #DCE7FD;}

/* ---------- Dải lưu ý ---------- */
.notice {
    display: flex; gap: 12px; align-items: flex-start;
    background: #FFF7ED;
    border: 1px solid #FFE0BF;
    border-radius: 0.75rem;
    padding: 13px 18px;
    margin: 16px 0 26px 0;
    color: #8A4B12; font-size: 0.85rem; line-height: 1.6;
}
.notice .bar {
    flex: 0 0 4px; align-self: stretch;
    background: var(--orange); border-radius: 3px;
}

/* ---------- Gợi ý câu hỏi ---------- */
.sec-title {
    color: var(--blue-deep); font-size: 0.78rem; font-weight: 600;
    letter-spacing: 1.2px; text-transform: uppercase;
    margin: 6px 0 12px 0;
}
div[data-testid="stHorizontalBlock"] button {
    border-radius: 0.75rem !important;
    border: 1px solid var(--line) !important;
    background: #FFFFFF !important;
    color: var(--ink) !important;
    font-size: 0.86rem !important; font-weight: 500 !important;
    padding: 14px 16px !important; text-align: left !important;
    box-shadow: 0 1px 2px rgba(16,40,80,0.05);
    transition: all .16s ease;
}
div[data-testid="stHorizontalBlock"] button:hover {
    border-color: var(--blue-2) !important;
    background: var(--tint) !important;
    color: var(--blue) !important;
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(29,78,216,0.13);
}

/* ---------- Chat ---------- */
[data-testid="stChatMessage"] {background: transparent; padding: 6px 0;}
[data-testid="stChatMessageContent"] {font-size: 0.98rem; line-height: 1.72;}
[data-testid="stChatMessageAvatarUser"] {
    background: var(--blue-2) !important;
}

/* ---------- Nhãn phương pháp ---------- */
.method {
    display: inline-flex; align-items: center; gap: 7px;
    background: var(--tint-2); color: var(--blue-deep);
    font-size: 0.76rem; font-weight: 600;
    padding: 6px 14px; border-radius: 999px;
    margin: 18px 0 10px 0;
}
.method .dot {width: 7px; height: 7px; border-radius: 50%; background: var(--blue-2);}
.method.fallback {background: #FFEDD5; color: #9A3412;}
.method.fallback .dot {background: var(--orange);}
.method.none {background: #F1F5F9; color: var(--muted);}
.method.none .dot {background: #94A3B8;}
.count {color: var(--muted); font-size: 0.8rem; margin-left: 10px;}

/* ---------- Thẻ nguồn ---------- */
[data-testid="stExpander"] {
    border: 1px solid var(--line) !important;
    border-radius: 0.75rem !important;
    margin-bottom: 9px;
    background: #FFFFFF;
    box-shadow: 0 1px 2px rgba(16,40,80,0.04);
    overflow: hidden;
}
[data-testid="stExpander"]:hover {border-color: #BFD4F5 !important;}
[data-testid="stExpander"] summary {
    font-size: 0.88rem; font-weight: 500; color: var(--ink);
    padding: 4px 2px;
}
[data-testid="stExpander"] summary:hover {color: var(--blue);}

.meta {font-size: 0.83rem; color: var(--muted); line-height: 1.85;}
.meta b {color: var(--blue-deep); font-weight: 600;}
.snippet {
    background: var(--tint); border: 1px solid var(--line);
    border-radius: 0.5rem; padding: 14px 16px;
    font-size: 0.86rem; line-height: 1.65; color: #2C3E58;
    white-space: pre-wrap; max-height: 320px; overflow-y: auto; margin-top: 10px;
    overscroll-behavior: contain;   /* cuộn hết đoạn thì dừng, không đẩy sang trang */
}

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] {
    background: #FBFCFF;
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] .side-brand {
    color: var(--blue); font-size: 1.15rem; font-weight: 700;
    line-height: 1.3; margin-bottom: 4px;
}
[data-testid="stSidebar"] .side-sub {
    color: var(--muted); font-size: 0.82rem; line-height: 1.55;
    padding-bottom: 14px; border-bottom: 3px solid var(--orange);
    margin-bottom: 4px;
}
[data-testid="stSidebar"] .side-sec {
    color: var(--blue-deep); font-size: 0.72rem; font-weight: 600;
    letter-spacing: 1.2px; text-transform: uppercase;
    margin: 22px 0 8px 0;
}
[data-testid="stSidebar"] .side-row {
    display: flex; justify-content: space-between; align-items: center;
    font-size: 0.83rem; color: var(--muted); padding: 5px 0;
    border-bottom: 1px dashed var(--line);
}
[data-testid="stSidebar"] .side-row b {
    color: var(--blue-deep); font-weight: 600; font-size: 0.8rem;
}
[data-testid="stSidebar"] button {
    border-radius: 0.75rem !important;
    border: 1px solid var(--line) !important;
    color: var(--ink) !important; font-size: 0.85rem !important;
}
[data-testid="stSidebar"] button:hover {
    border-color: var(--orange) !important; color: var(--orange-2) !important;
}

/* ---------- Ô nhập ---------- */
[data-testid="stChatInput"] {border-radius: 1rem;}
[data-testid="stChatInput"] textarea {font-size: 0.95rem;}
</style>
"""

# Mở app với ?nocss=1 để tắt toàn bộ CSS tuỳ biến. Dùng để khoanh vùng: nếu lỗi
# vẫn còn khi tắt thì nguyên nhân nằm ở Streamlit, không phải CSS của nhóm.
if st.query_params.get("nocss") != "1":
    st.markdown(UIT_CSS, unsafe_allow_html=True)

ASSETS = Path(__file__).parent / "assets"
AVATAR_BOT = str(ASSETS / "uit-avatar.png")   # biểu tượng UIT, tải từ uit.edu.vn
AVATAR_USER = "🎓"


@st.cache_data
def _logo_data_uri() -> str:
    """Nhúng logo dạng base64 để đặt được vào HTML của hero.

    st.image không chèn được vào giữa một khối markdown HTML, còn trỏ đường dẫn
    file cục bộ thì trình duyệt không đọc được vì không nằm trong thư mục static.
    """
    raw = (ASSETS / "uit-logo-full.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode()


LOGO_DATA_URI = _logo_data_uri()

# Hoạ tiết line-art trong các khối vuông, vẽ lại theo mô-típ của uit.edu.vn.
ICON_TARGET = (
    '<svg viewBox="0 0 48 48" fill="none" stroke="#FFFFFF" stroke-width="3">'
    '<circle cx="24" cy="26" r="16"/><circle cx="24" cy="26" r="8"/>'
    '<circle cx="24" cy="26" r="1.5" fill="#FFFFFF"/>'
    '<path d="M28 22 L42 8 M36 8 h6 v6"/></svg>'
)
ICON_DIAMOND = (
    '<svg viewBox="0 0 48 48" fill="none" stroke="#FFFFFF" stroke-width="3">'
    '<path d="M10 20 L24 8 L38 20 L24 40 Z"/><path d="M10 20 h28 M24 8 L18 20 '
    'M24 8 L30 20 M18 20 L24 40 M30 20 L24 40"/></svg>'
)

METHOD_LABELS = {
    "hybrid": ("Hybrid — dense + BM25 + RRF", ""),
    "pageindex": ("Vectorless — duyệt cây Chương/Điều", "fallback"),
    "dense": ("Dense — tìm theo ngữ nghĩa", ""),
    "bm25": ("BM25 — tìm theo từ khóa", ""),
    "none": ("Không truy xuất được nguồn", "none"),
}

# Icon Material cho từng loại văn bản, phân biệt quy chế với bài viết/thông báo.
DOC_ICONS = {
    "legal": ":material/gavel:",
    "news": ":material/campaign:",
}

SAMPLE_QUESTIONS = [
    "Một tín chỉ học tập bằng bao nhiêu tiết lý thuyết?",
    "Sinh viên bị buộc thôi học trong trường hợp nào?",
    "Điều kiện để được làm khóa luận tốt nghiệp?",
    "Thủ tục phúc khảo bài thi như thế nào?",
]


def citation_numbers(sources: list[dict]) -> dict[str, int]:
    """Map id -> số [Document N] mà LLM đã thấy trong context.

    Cần thiết vì sources được sắp theo score giảm dần (contract yêu cầu), còn
    context lại được reorder_for_llm() xếp xen kẽ để chống lost-in-the-middle.
    Hai thứ tự khác nhau, nên [Document 4] trong câu trả lời KHÔNG phải
    sources[3]. Dựng lại đúng thứ tự context để citation truy ngược được.
    """
    return {
        chunk["id"]: index
        for index, chunk in enumerate(reorder_for_llm(sources), 1)
    }


def render_sources(sources: list[dict], retrieval_source: str) -> None:
    """Hiển thị nguồn thật đã đưa vào context, kèm score và đường dẫn gốc."""
    label, variant = METHOD_LABELS.get(retrieval_source, (retrieval_source, ""))

    if not sources:
        st.markdown(
            f'<div><span class="method none"><span class="dot"></span>{label}</span>'
            '<span class="count">Câu trả lời này không dựa trên tài liệu nào trong '
            "corpus.</span></div>",
            unsafe_allow_html=True,
        )
        return

    numbers = citation_numbers(sources)
    st.markdown(
        f'<div><span class="method {variant}"><span class="dot"></span>{label}</span>'
        f'<span class="count">{len(sources)} nguồn trong ngữ cảnh</span></div>',
        unsafe_allow_html=True,
    )

    for chunk in sources:
        metadata = chunk["metadata"]
        number = numbers.get(chunk["id"], "?")
        icon = DOC_ICONS.get(metadata.get("doc_type", ""), ":material/description:")
        with st.expander(
            f"Document {number}   ·   {metadata['title']}   ·   score {chunk['score']:.4f}",
            icon=icon,
        ):
            st.markdown(
                f'<div class="meta">'
                f'<b>Tệp gốc</b> &nbsp; {metadata["source"]}<br>'
                f'<b>Định danh chunk</b> &nbsp; {chunk["id"]}<br>'
                f'<b>Vị trí</b> &nbsp; chunk_index {metadata["chunk_index"]}'
                f' &nbsp;&nbsp;·&nbsp;&nbsp; <b>Phương pháp</b> &nbsp; '
                f'{chunk["retrieval_method"]}'
                f"</div>",
                unsafe_allow_html=True,
            )
            if metadata.get("url"):
                st.link_button(
                    "Mở văn bản gốc trên cổng thông tin UIT",
                    metadata["url"],
                    icon=":material/open_in_new:",
                )
            st.markdown(
                f'<div class="snippet">{chunk["content"]}</div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown('<div class="side-brand">Trợ lý quy chế</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="side-sub">Trường Đại học Công nghệ Thông tin<br>ĐHQG-HCM</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="side-sec">Tham số truy xuất</div>', unsafe_allow_html=True)
    top_k = st.slider("Số đoạn văn bản đưa vào ngữ cảnh", 3, 10, 5)

    st.markdown('<div class="side-sec">Cấu hình hệ thống</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="side-row"><span>Mô hình sinh</span><b>{resolve_model()}</b></div>'
        f'<div class="side-row"><span>Embedding</span><b>bge-m3</b></div>'
        f'<div class="side-row"><span>Ngưỡng fallback</span><b>{SCORE_THRESHOLD}</b></div>'
        f'<div class="side-row"><span>Kích thước chunk</span><b>800 / 120</b></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="side-sec">Phạm vi dữ liệu</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="side-row"><span>Quy chế, quy định</span><b>6</b></div>'
        '<div class="side-row"><span>Bài viết, thông báo</span><b>7</b></div>'
        '<div class="side-row"><span>Đoạn đã lập chỉ mục</span><b>396</b></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="side-sec">Phiên làm việc</div>', unsafe_allow_html=True)
    if st.button("Xóa lịch sử hội thoại", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# ---------------------------------------------------------------- hero
st.markdown(
    '<div class="hero">'
    f'<div class="deco d1">{ICON_TARGET}</div>'
    '<div class="deco d2"></div>'
    '<div class="deco d3"></div>'
    f'<div class="deco d4">{ICON_TARGET}</div>'
    f'<div class="deco d5">{ICON_DIAMOND}</div>'
    '<div class="deco d6"></div>'
    '<div class="deco d7"></div>'
    '<div class="inner">'
    f'<img class="hero-logo" src="{LOGO_DATA_URI}" width="362" height="38" alt="Logo Trường ĐH Công nghệ Thông tin">'
    "<h1>Hỏi đáp quy chế<br>và quy định đào tạo</h1>"
    "<p>Mọi câu trả lời đều trích dẫn kèm tên văn bản, số hiệu Điều và liên kết tới "
    "tệp gốc trên cổng thông tin của Trường. Câu hỏi nằm ngoài phạm vi dữ liệu sẽ "
    "được từ chối thay vì trả lời phỏng đoán.</p>"
    "</div></div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="notice"><div class="bar"></div><div>'
    "Đây là sản phẩm bài tập môn học do sinh viên xây dựng, "
    "<b>không phải dịch vụ chính thức của Trường ĐH Công nghệ Thông tin</b>. "
    "Vui lòng đối chiếu văn bản gốc trước khi sử dụng cho mục đích chính thức."
    "</div></div>",
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []

# Gợi ý câu hỏi, chỉ hiện khi chưa có hội thoại
if not st.session_state.messages:
    st.markdown('<div class="sec-title">Bắt đầu với một câu hỏi</div>', unsafe_allow_html=True)
    columns = st.columns(len(SAMPLE_QUESTIONS), gap="small")
    for column, sample in zip(columns, SAMPLE_QUESTIONS):
        if column.button(sample, use_container_width=True):
            st.session_state.pending = sample
            st.rerun()

# Lịch sử phải lưu đủ sources và retrieval_source để render lại được nguồn
# của những câu trả lời trước, không chỉ riêng phần text.
for message in st.session_state.messages:
    avatar = AVATAR_BOT if message["role"] == "assistant" else AVATAR_USER
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(
                message.get("sources", []),
                message.get("retrieval_source", "none"),
            )

query = st.chat_input("Nhập câu hỏi về quy chế, quy định của Trường...")
if not query and "pending" in st.session_state:
    query = st.session_state.pop("pending")

if query:
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user", avatar=AVATAR_USER):
        st.markdown(query)

    with st.chat_message("assistant", avatar=AVATAR_BOT):
        with st.spinner("Đang truy xuất văn bản và tạo câu trả lời..."):
            try:
                result = generate_with_citation(query, top_k=top_k)
            except Exception as error:
                # Giao diện không được crash vì lỗi backend.
                result = {
                    "answer": (
                        "Hệ thống gặp lỗi khi xử lý câu hỏi này "
                        f"({type(error).__name__}). Vui lòng thử lại."
                    ),
                    "sources": [],
                    "retrieval_source": "none",
                }

        st.markdown(result["answer"])
        render_sources(result["sources"], result["retrieval_source"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
            "retrieval_source": result["retrieval_source"],
        }
    )

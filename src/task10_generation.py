"""
Task 10 — Generation có citation.

Luồng: retrieve -> reorder -> format context -> gọi LLM -> GenerationResult.

Vì sao tầng này phải tự từ chối được:
    Checkpoint trước đã đo và ghi nhận rằng vectorless fallback KHÔNG phân biệt
    được truy vấn trong hay ngoài chủ đề (điểm thô của hai nhóm chồng lên nhau).
    Câu hỏi "Cách nấu phở bò" vẫn nhận về "Điều 24. Cách quản lý điểm" vì khớp
    chữ "cách". Nếu tầng này trả lời vô điều kiện trên context nhận được thì hệ
    thống sẽ dùng quy chế đào tạo để trả lời câu hỏi nấu ăn — đúng kiểu ảo giác
    nguy hiểm nhất vì nó trông như có căn cứ. Đây là chốt chặn cuối cùng.
"""

import os

from dotenv import load_dotenv

from .task9_retrieval_pipeline import retrieve


load_dotenv()

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3
MAX_TOKENS = 1024
REQUEST_TIMEOUT = 60

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL = os.getenv("LLM_MODEL", "")

# Pin phiên bản cụ thể, không dùng alias kiểu "gemini-flash-latest": alias tự đổi
# model bên dưới, làm số liệu trong RESULT.md không tái lập được.
# Kiểm tra model còn khả dụng bằng: python -m src.list_gemini_models
DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.5-flash",
    "anthropic": "claude-haiku-4-5-20251001",
}

# LLM được yêu cầu trả về đúng chuỗi này khi context không chứa câu trả lời,
# để pipeline nhận ra và không đính kèm nguồn không liên quan.
REFUSAL_MARKER = "KHONG_DU_EVIDENCE"
REFUSAL_ANSWER = "Tôi không thể xác minh thông tin này từ nguồn hiện có."

# Đây là prompt v1. Nhóm đã thử một bản v2 nới lỏng hơn (yêu cầu câu trả lời tự
# đứng vững, liệt kê đầy đủ, chấp nhận trả lời một phần, hiểu câu nêu ý định) và
# đo lại bằng RAGAS trên cùng 15 golden case: faithfulness tụt 1.0000 -> 0.8889 ở
# Config A, answer relevance cũng tụt 0.4426 -> 0.4072. Nguyên nhân là yêu cầu
# "nhắc lại chủ thể" khiến mô hình đưa tên văn bản vào văn xuôi, tạo ra những mệnh
# đề về xuất xứ mà RAGAS không kiểm chứng được từ context. Chi tiết trong
# group_project/evaluation/RESULT.md, mục "Xác minh recommendation #2".
SYSTEM_PROMPT = f"""Bạn trả lời câu hỏi về quy chế và quy định của Trường Đại học
Công nghệ Thông tin (UIT), chỉ dựa trên context được cung cấp.

Quy tắc:
1. Chỉ dùng thông tin có trong context. Tuyệt đối không dùng kiến thức bên ngoài.
2. Mỗi khẳng định phải kèm citation dạng [Document N].
3. Trích dẫn chính xác số hiệu Điều và tên văn bản khi context có.
4. Nếu context không chứa thông tin trả lời được câu hỏi, chỉ trả lời đúng một
   dòng: {REFUSAL_MARKER}
   Không suy đoán, không trả lời một phần, không xin lỗi dài dòng.

Câu hỏi nằm ngoài phạm vi quy chế UIT luôn rơi vào trường hợp 4, kể cả khi
context có chứa vài từ trùng với câu hỏi."""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Đưa chunks quan trọng về đầu và cuối context.

    LLM đọc context không đều: phần đầu và phần cuối được nhớ rõ hơn phần giữa
    (lost-in-the-middle). Retrieval trả về theo score giảm dần nên chunk mạnh
    thứ hai, thứ ba lại rơi đúng vào vùng mù. Xếp xen kẽ để chunk mạnh nhất ở
    đầu, mạnh nhì ở cuối, yếu nhất bị đẩy vào giữa.

    Không sửa list đầu vào: Task 9 và báo cáo còn đọc lại thứ tự gốc theo score.
    """
    if len(chunks) <= 2:
        return list(chunks)
    front = chunks[::2]
    back = chunks[1::2]
    return front + back[::-1]


def format_context(chunks: list[dict]) -> str:
    """Tạo context có title và source label.

    Nhãn là thứ cho phép LLM trích dẫn kiểm chứng được: từ câu trả lời người
    đọc thấy số hiệu văn bản, tra ngược được file landing và URL công khai.
    """
    parts = []
    for index, chunk in enumerate(chunks, 1):
        metadata = chunk["metadata"]
        header = (
            f"[Document {index} | Title: {metadata['title']} | "
            f"Source: {metadata['source']}]"
        )
        parts.append(f"{header}\n{chunk['content']}")
    return "\n\n---\n\n".join(parts)


def resolve_model() -> str:
    """LLM_MODEL trong .env, hoặc mặc định theo provider."""
    if LLM_MODEL.strip():
        return LLM_MODEL.strip()
    try:
        return DEFAULT_MODELS[LLM_PROVIDER]
    except KeyError:
        raise ValueError(f"LLM_PROVIDER={LLM_PROVIDER} không được hỗ trợ") from None


def _require_key(name: str) -> str:
    key = os.getenv(name, "").strip()
    if not key:
        raise RuntimeError(f"{name} chưa được đặt trong .env")
    return key


def openai_client_kwargs() -> dict:
    """Tham số khởi tạo ``OpenAI`` client, có hỗ trợ endpoint tùy biến.

    ``OPENAI_BASE_URL`` cho phép trỏ sang endpoint OpenAI-compatible khác, ví dụ
    Command Code Provider API (``https://api.commandcode.ai/provider/v1``). Bỏ
    trống thì dùng ``api.openai.com`` mặc định.
    """
    kwargs: dict = {
        "api_key": _require_key("OPENAI_API_KEY"),
        "timeout": REQUEST_TIMEOUT,
    }
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    if base_url:
        kwargs["base_url"] = base_url
    return kwargs


def call_llm(system_prompt: str, user_message: str) -> str:
    """Gọi OpenAI, Gemini hoặc Anthropic theo cấu hình. Trả về text thuần."""
    model = resolve_model()

    if LLM_PROVIDER == "openai":
        from openai import OpenAI

        client = OpenAI(**openai_client_kwargs())
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
            top_p=TOP_P,
            max_tokens=MAX_TOKENS,
        )
        return (response.choices[0].message.content or "").strip()

    if LLM_PROVIDER == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=_require_key("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model=model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=TEMPERATURE,
                top_p=TOP_P,
                max_output_tokens=MAX_TOKENS,
            ),
        )
        return (response.text or "").strip()

    if LLM_PROVIDER == "anthropic":
        import anthropic

        client = anthropic.Anthropic(
            api_key=_require_key("ANTHROPIC_API_KEY"), timeout=REQUEST_TIMEOUT
        )
        response = client.messages.create(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=TEMPERATURE,
            top_p=TOP_P,
            max_tokens=MAX_TOKENS,
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        ).strip()

    raise ValueError(f"LLM_PROVIDER={LLM_PROVIDER} không được hỗ trợ")


def _refusal() -> dict:
    """GenerationResult an toàn khi không đủ evidence hoặc provider lỗi."""
    return {
        "answer": REFUSAL_ANSWER,
        "sources": [],
        "retrieval_source": "none",
    }


def _retrieval_source(chunks: list[dict]) -> str:
    """Map retrieval_method sang RetrievalSource của contract.

    retrieval_method có 4 giá trị (dense/bm25/hybrid/pageindex) nhưng
    retrieval_source chỉ nhận 3 (hybrid/pageindex/none). Nhánh dense-only của
    Config A trả về method "dense", nên phải map chứ không gán thẳng.
    """
    method = chunks[0]["retrieval_method"]
    return "pageindex" if method == "pageindex" else "hybrid"


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Trả về GenerationResult."""
    if not query.strip():
        return _refusal()

    chunks = retrieve(query, top_k=top_k)
    if not chunks:
        return _refusal()

    context = format_context(reorder_for_llm(chunks))
    user_message = f"Context:\n{context}\n\nCâu hỏi: {query}"

    try:
        answer = call_llm(SYSTEM_PROMPT, user_message)
    except Exception as error:
        print(f"LLM lỗi ({type(error).__name__}: {error}) — trả safe refusal")
        return _refusal()

    # LLM tự xác định context không đủ: không đính kèm nguồn không liên quan.
    if not answer or REFUSAL_MARKER in answer:
        return _refusal()

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": _retrieval_source(chunks),
    }


if __name__ == "__main__":
    probes = [
        "Một tín chỉ học tập bằng bao nhiêu tiết lý thuyết?",
        "Sinh viên bị buộc thôi học trong trường hợp nào?",
        "Cách nấu phở bò ngon tại nhà",
    ]
    print(f"provider={LLM_PROVIDER} model={resolve_model()}\n")
    for probe in probes:
        result = generate_with_citation(probe, top_k=5)
        print(f"=== {probe}")
        print(f"    retrieval_source: {result['retrieval_source']}, "
              f"{len(result['sources'])} nguồn")
        print(f"    {result['answer'][:400]}")
        for source in result["sources"][:3]:
            print(f"      - {source['metadata']['source']} :: chunk {source['metadata']['chunk_index']}")
        print()

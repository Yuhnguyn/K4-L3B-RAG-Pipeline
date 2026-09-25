"""
Conversation memory — chuẩn hoá câu hỏi nối tiếp thành câu hỏi độc lập.

Rubric bonus: "Conversation memory cho follow-up question". Cách làm: dùng LLM
viết lại câu hỏi nối tiếp dựa trên lịch sử hội thoại, rồi mới đưa câu đã viết
lại vào pipeline retrieval. Ví dụ:

    Lượt 1: "Điều kiện để làm khóa luận tốt nghiệp là gì?"
    Lượt 2: "Thế còn thời gian thực hiện?"   <- mơ hồ nếu tách khỏi lượt 1
    -> condense: "Thời gian thực hiện khóa luận tốt nghiệp là bao lâu?"

Vì sao không đổi chữ ký ``generate_with_citation``: contract test
``test_public_function_signatures_are_stable`` yêu cầu đúng tham số
``["query", "top_k"]``. Conversation memory là một bước tiền xử lý ở tầng UI,
không phải một nhánh retrieval.

Mọi lỗi ở tầng này phải quy về câu hỏi gốc. Viết lại câu hỏi là tiện ích phụ:
LLM hết quota hay timeout không được làm hỏng cả câu trả lời.
"""

from __future__ import annotations

from dotenv import load_dotenv

from .task10_generation import call_llm


load_dotenv()

# Giới hạn lịch sử đưa vào prompt: đủ để nối tham chiếu, không làm loãng.
MAX_TURNS = 4
MAX_MESSAGE_CHARS = 400

CONDENSE_SYSTEM_PROMPT = """Bạn viết lại câu hỏi mới nhất của người dùng thành một câu hỏi
độc lập, đủ nghĩa khi tách khỏi đoạn hội thoại, để dùng cho bước tra cứu tài liệu.

Quy tắc:
1. Nếu câu hỏi mới đã độc lập và đầy đủ, giữ nguyên, không sửa gì.
2. Nếu câu hỏi mới dựa vào ngữ cảnh trước (đại từ, từ thay thế, câu tiếp nối),
   thay chúng bằng nội dung cụ thể đã có trong hội thoại.
3. Giữ đúng ý định và ngôn ngữ của người dùng; không thêm câu hỏi mới.
4. Chỉ trả về đúng một câu hỏi, không giải thích, không đặt trong dấu ngoặc kép,
   không trả lời câu hỏi."""


def format_history(
    history: list[dict], max_turns: int = MAX_TURNS
) -> str:
    """Diễn giải ``max_turns`` lượt gần nhất thành văn bản cho prompt."""
    turns = [
        message
        for message in (history or [])
        if str(message.get("content", "")).strip()
    ][-(max_turns * 2):]

    lines = []
    for message in turns:
        role = "Người dùng" if message.get("role") == "user" else "Trợ lý"
        content = " ".join(str(message["content"]).split())[:MAX_MESSAGE_CHARS]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def condense_question(history: list[dict], question: str) -> str:
    """Viết lại câu hỏi nối tiếp thành câu hỏi độc lập.

    Trả về câu hỏi gốc khi không có lịch sử, câu hỏi rỗng, hoặc LLM lỗi.
    """
    if not question or not question.strip():
        return question

    has_prior = any(
        str(message.get("content", "")).strip() for message in (history or [])
    )
    if not has_prior:
        return question

    user_message = (
        "Lịch sử hội thoại:\n"
        f"{format_history(history)}\n\n"
        f"Câu hỏi mới của người dùng: {question}\n\n"
        "Viết lại câu hỏi mới thành một câu hỏi độc lập:"
    )

    try:
        rewritten = call_llm(CONDENSE_SYSTEM_PROMPT, user_message)
    except Exception as error:
        print(
            f"condense_question lỗi ({type(error).__name__}: {error}) "
            "— dùng câu hỏi gốc"
        )
        return question

    rewritten = (rewritten or "").strip()
    # LLM đôi khi trả về thêm dòng giải thích; lấy dòng không rỗng đầu tiên, rồi
    # mới bỏ dấu ngoặc kép còn sót ở cuối câu.
    first_line = next(
        (line.strip() for line in rewritten.splitlines() if line.strip()), ""
    )
    return first_line.strip().strip('"').strip() or question


if __name__ == "__main__":
    demo_history = [
        {"role": "user", "content": "Điều kiện để làm khóa luận tốt nghiệp là gì?"},
        {
            "role": "assistant",
            "content": "Sinh viên phải đăng ký KLTN và đáp ứng các yêu cầu ...",
        },
    ]
    for probe in (
        "Thế còn thời gian thực hiện?",
        "Điều kiện để làm khóa luận tốt nghiệp là gì?",
    ):
        print(f"{probe}\n  -> {condense_question(demo_history, probe)}\n")

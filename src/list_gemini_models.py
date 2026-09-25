"""
Liệt kê các model Gemini mà GEMINI_API_KEY trong .env truy cập được.

Chạy:
    python -m src.list_gemini_models

Dùng để chọn giá trị điền vào LLM_MODEL thay vì đoán tên model.
"""

import os

from dotenv import load_dotenv


load_dotenv()


def main() -> None:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit("GEMINI_API_KEY chưa được đặt trong .env")

    from google import genai

    client = genai.Client(api_key=key)

    rows = []
    for model in client.models.list():
        actions = getattr(model, "supported_actions", None) or []
        if "generateContent" not in actions:
            continue
        name = model.name.removeprefix("models/")
        limit = getattr(model, "input_token_limit", None)
        rows.append((name, limit, getattr(model, "display_name", "") or ""))

    rows.sort()
    print(f"{len(rows)} model hỗ trợ generateContent:\n")
    print(f"{'LLM_MODEL':<38}{'input tokens':>14}   Tên hiển thị")
    for name, limit, display in rows:
        print(f"{name:<38}{str(limit or '-'):>14}   {display[:40]}")

    print("\nChép tên ở cột LLM_MODEL vào .env, ví dụ:  LLM_MODEL=gemini-2.0-flash")


if __name__ == "__main__":
    main()

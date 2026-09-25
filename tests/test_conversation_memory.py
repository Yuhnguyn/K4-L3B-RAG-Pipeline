import src.conversation_memory as memory


def test_without_history_returns_question_and_skips_llm(monkeypatch):
    calls = {"count": 0}

    def fake_call_llm(system_prompt, user_message):
        calls["count"] += 1
        return "không được gọi"

    monkeypatch.setattr(memory, "call_llm", fake_call_llm)
    question = "Một tín chỉ bằng bao nhiêu tiết?"
    assert memory.condense_question([], question) == question
    assert calls["count"] == 0


def test_with_history_rewrites_follow_up(monkeypatch):
    seen = {}

    def fake_call_llm(system_prompt, user_message):
        seen["system"] = system_prompt
        seen["user"] = user_message
        return "Thời gian thực hiện khóa luận tốt nghiệp là bao lâu?"

    monkeypatch.setattr(memory, "call_llm", fake_call_llm)
    history = [
        {"role": "user", "content": "Điều kiện để làm khóa luận tốt nghiệp là gì?"},
        {"role": "assistant", "content": "Sinh viên phải đăng ký KLTN ..."},
    ]

    output = memory.condense_question(history, "Thế còn thời gian thực hiện?")

    assert output == "Thời gian thực hiện khóa luận tốt nghiệp là bao lâu?"
    assert "Điều kiện để làm khóa luận tốt nghiệp" in seen["user"]
    assert "Thế còn thời gian thực hiện?" in seen["user"]


def test_history_entries_without_content_are_ignored(monkeypatch):
    calls = {"count": 0}

    def fake_call_llm(system_prompt, user_message):
        calls["count"] += 1
        return "x"

    monkeypatch.setattr(memory, "call_llm", fake_call_llm)
    question = "Câu hỏi?"
    assert memory.condense_question([{"role": "user", "content": "  "}], question) == question
    assert calls["count"] == 0


def test_llm_error_falls_back_to_original(monkeypatch):
    def unavailable(system_prompt, user_message):
        raise RuntimeError("hết quota")

    monkeypatch.setattr(memory, "call_llm", unavailable)
    question = "Thế còn thời gian?"
    history = [{"role": "user", "content": "Điều kiện làm KLTN?"}]
    assert memory.condense_question(history, question) == question


def test_empty_rewrite_falls_back_to_original(monkeypatch):
    monkeypatch.setattr(memory, "call_llm", lambda system_prompt, user_message: "   ")
    question = "Thế còn?"
    history = [{"role": "user", "content": "x"}]
    assert memory.condense_question(history, question) == question


def test_rewrite_strips_quotes_and_extra_lines(monkeypatch):
    def fake_call_llm(system_prompt, user_message):
        return '"Thời gian thực hiện KLTN là bao lâu?"\nGiải thích thêm...'

    monkeypatch.setattr(memory, "call_llm", fake_call_llm)
    history = [{"role": "user", "content": "Điều kiện làm KLTN?"}]
    assert (
        memory.condense_question(history, "Thế còn thời gian?")
        == "Thời gian thực hiện KLTN là bao lâu?"
    )


def test_format_history_limits_turns():
    history = [
        {"role": "user", "content": f"câu {index}"} for index in range(20)
    ]
    text = memory.format_history(history, max_turns=2)
    assert text.count("Người dùng:") == 4

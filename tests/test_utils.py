from ai import Context, Model, Options, Tool, UserMessage
from ai.utils.context_window import detect_context_overflow
from ai.utils.schema_validation import validate_tool_arguments
from ai.utils.unicode import sanitize_unicode


MODEL = Model(
    id="openai:gpt-5",
    provider="openai",
    inputPrice=1.25,
    outputPrice=10.0,
    contextWindow=64,
    maxOutputTokens=16,
)


def test_validate_tool_arguments_accepts_valid_payload() -> None:
    tool = Tool(
        name="lookup_spec",
        inputSchema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    )

    result = validate_tool_arguments(tool, {"query": "llm"})

    assert result is True


def test_detect_context_overflow_reports_when_budget_exceeded() -> None:
    context = Context(
        systemPrompt="你是测试助手。",
        messages=[UserMessage(content="x" * 200)],
        tools=[],
    )

    overflow = detect_context_overflow(MODEL, context, Options(maxTokens=8))

    assert overflow.is_overflow is True
    assert overflow.estimated_tokens > MODEL.contextWindow - 8


def test_sanitize_unicode_removes_zero_width_characters() -> None:
    cleaned = sanitize_unicode("A\u200bB\u200dC")

    assert cleaned == "ABC"

from ai import AssistantMessage, Model, StreamEvent, ToolCall


def test_stream_event_done_can_hold_final_result() -> None:
    model = Model(
        id="openai:gpt-5",
        provider="openai",
        inputPrice=1.25,
        outputPrice=10.0,
        contextWindow=272000,
        maxOutputTokens=8192,
    )
    message = AssistantMessage(
        content="final answer",
        thinking="analysis",
        toolCalls=[ToolCall(id="call_1", name="lookup", arguments='{"q":"x"}')],
    )

    event = StreamEvent(
        type="done",
        model=model,
        provider=model.provider,
        assistantMessage=message,
    )

    assert event.type == "done"
    assert event.model == model
    assert event.assistantMessage is message
    assert event.assistantMessage.toolCalls[0].id == "call_1"


def test_assistant_message_supports_text_thinking_and_toolcalls() -> None:
    message = AssistantMessage(
        content="hello",
        thinking="reasoning",
        toolCalls=[ToolCall(id="call_1", name="lookup", arguments="{}")],
    )

    assert message.content == "hello"
    assert message.thinking == "reasoning"
    assert message.toolCalls[0].name == "lookup"

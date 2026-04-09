from __future__ import annotations

import inspect
from collections.abc import AsyncIterator

import pytest

from ai import AssistantMessage, Model, StreamEvent, UserMessage
from ai.options import Options
from ai.providers.base import Provider
from ai.registry import ProviderRegistry
from ai.session import StreamSession
from agent_core import (
    Agent,
    AgentContext,
    AgentEvent,
    AgentLoopConfig,
    AgentOptions,
    AgentState,
    AgentTool,
    AfterToolCallContext,
    BeforeToolCallContext,
)
from agent_core import agent_loop as agent_loop_module


class EchoProvider(Provider):
    name = "stub"

    def supports(self, model: Model) -> bool:
        return model.provider == self.name

    async def stream(self, model: Model, context, options: Options) -> AsyncIterator[StreamEvent]:
        latest_user = next(
            (message.content for message in reversed(context.messages) if getattr(message, "role", "") == "user"),
            "hello",
        )
        yield StreamEvent(type="start", provider=model.provider, model=model)
        yield StreamEvent(type="text_start", provider=model.provider, model=model)
        yield StreamEvent(type="text_delta", provider=model.provider, model=model, text=f"echo:{latest_user}")
        yield StreamEvent(
            type="done",
            provider=model.provider,
            model=model,
            assistantMessage=AssistantMessage(content=f"echo:{latest_user}"),
        )


@pytest.fixture
def stub_model() -> Model:
    return Model(
        id="stub:test-model",
        provider="stub",
        inputPrice=0.1,
        outputPrice=0.2,
        contextWindow=128000,
        maxOutputTokens=4096,
    )


async def collect_events(session: StreamSession[AgentEvent]) -> list[AgentEvent]:
    events: list[AgentEvent] = []
    async for event in session.consume():
        events.append(event)
    return events


def make_loop(stub_model: Model) -> AgentLoopConfig:
    registry = ProviderRegistry([EchoProvider()])

    async def custom_stream(model, context, thinking, registry=None):
        return await agent_loop_module.streamSimple(
            model,
            {"systemPrompt": context.systemPrompt, "messages": context.history, "tools": context.tools},
            reasoning=thinking,
            registry=registry,
        )

    return AgentLoopConfig(model=stub_model, stream=custom_stream, registry=registry)


@pytest.mark.asyncio
async def test_agent_options_can_construct_agent(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    assert agent.state.model == stub_model


@pytest.mark.asyncio
async def test_agent_prompt_runs_and_accumulates_state(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))

    first_session = await agent.prompt(UserMessage(content="first"))
    first_run = await collect_events(first_session)
    second_session = await agent.prompt(UserMessage(content="second"))
    second_run = await collect_events(second_session)

    assert first_run[-1].state.history[-1].content == "echo:first"
    assert second_run[-1].state.history[-1].content == "echo:second"
    assert [message.content for message in second_run[-1].state.history if hasattr(message, "content")] == [
        "first",
        "echo:first",
        "second",
        "echo:second",
    ]


@pytest.mark.asyncio
async def test_agent_continue_conversation_uses_current_state(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    await collect_events(await agent.prompt(UserMessage(content="hello")))
    agent.updateState(history=agent.state.history + [UserMessage(content="resume")])

    session = await agent.continueConversation()
    events = await collect_events(session)

    assert isinstance(session, StreamSession)
    assert events[-1].state.history[-1].content == "echo:resume"


@pytest.mark.asyncio
async def test_agent_continue_conversation_consumes_queued_messages_from_assistant_tail(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    await collect_events(await agent.prompt(UserMessage(content="hello")))
    agent.enqueueSteering(UserMessage(content="queued-steer"))

    session = await agent.continueConversation()
    events = await collect_events(session)

    assert events[-1].state.history[-2].content == "queued-steer"
    assert events[-1].state.history[-1].content == "echo:queued-steer"


@pytest.mark.asyncio
async def test_agent_run_uses_queue_when_pending_messages_exist(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    agent.enqueue(UserMessage(content="queued"))

    session = await agent.run()
    events = await collect_events(session)

    assert events[-1].state.history[-1].content == "echo:queued"


@pytest.mark.asyncio
async def test_agent_subscribe_and_unsubscribe_work(stub_model: Model) -> None:
    seen: list[str] = []

    def listener(event: AgentEvent) -> None:
        seen.append(event.type)

    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    agent.subscribe(listener)
    await collect_events(await agent.prompt(UserMessage(content="hello")))
    agent.unsubscribe(listener)
    await collect_events(await agent.prompt(UserMessage(content="world")))

    assert "agent_start" in seen
    assert seen.count("agent_start") == 1


@pytest.mark.asyncio
async def test_listener_errors_do_not_break_main_flow(stub_model: Model) -> None:
    def broken_listener(event: AgentEvent) -> None:
        raise RuntimeError("listener failed")

    agent = Agent(AgentOptions(loop=make_loop(stub_model), listeners=[broken_listener]))
    events = await collect_events(await agent.prompt(UserMessage(content="hello")))

    assert events[-1].type == "agent_end"
    assert agent.state.error == "listener failed"


@pytest.mark.asyncio
async def test_queue_operations_work(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    agent.enqueue(UserMessage(content="a"))
    agent.enqueue([UserMessage(content="b")])

    assert agent.queueSize() == 2
    drained = agent.dequeueAll()
    assert [message.content for message in drained] == ["a", "b"]
    assert agent.queueSize() == 0

    agent.enqueue(UserMessage(content="c"))
    agent.clearQueue()
    assert agent.queueSize() == 0


def test_high_level_message_queues_are_explicitly_separated(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    agent.enqueue(UserMessage(content="normal"))
    agent.enqueueSteering(UserMessage(content="steer"))
    agent.enqueueFollowUp(UserMessage(content="follow"))

    assert agent.queueSize() == 1
    assert agent.steeringQueueSize() == 1
    assert agent.followUpQueueSize() == 1
    assert [message.content for message in agent.pendingMessages] == ["normal"]
    assert [message.content for message in agent.steeringMessages] == ["steer"]
    assert [message.content for message in agent.followUpMessages] == ["follow"]

    assert [message.content for message in agent.dequeueSteeringAll()] == ["steer"]
    assert [message.content for message in agent.dequeueFollowUpAll()] == ["follow"]
    assert agent.steeringQueueSize() == 0
    assert agent.followUpQueueSize() == 0


@pytest.mark.asyncio
async def test_agent_steering_and_follow_up_queues_drive_loop(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    agent.enqueue(UserMessage(content="first"))
    agent.enqueueSteering(UserMessage(content="second"))
    agent.enqueueFollowUp(UserMessage(content="third"))

    events = await collect_events(await agent.run())

    assert events[-1].type == "agent_end"
    history_contents = [message.content for message in events[-1].state.history if hasattr(message, "content")]
    assert "first" in history_contents
    assert "second" in history_contents
    assert "third" in history_contents
    assert "echo:third" in history_contents
    assert agent.steeringQueueSize() == 0
    assert agent.followUpQueueSize() == 0


@pytest.mark.asyncio
async def test_agent_cancel_and_wait_control_current_session(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    session = await agent.prompt(UserMessage(content="hello"))

    assert agent.currentSession is session
    assert agent.currentTask is not None
    agent.cancel()
    await agent.wait()

    assert agent.isRunning is False


@pytest.mark.asyncio
async def test_agent_is_running_changes_during_run(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    agent.enqueue(UserMessage(content="hello"))

    session = await agent.run()
    assert agent.isRunning is True

    observed_running = []
    async for event in session.consume():
        observed_running.append(agent.isRunning)
        if event.type == "message_update":
            assert event.state.isStreaming is True

    await session.wait_closed()
    assert observed_running
    assert all(observed_running)
    assert agent.isRunning is False
    assert agent.state.isStreaming is False


@pytest.mark.asyncio
async def test_agent_reset_clears_runtime_state(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    await collect_events(await agent.prompt(UserMessage(content="hello")))

    agent.reset()

    assert agent.state.history == []
    assert agent.state.currentMessage is None
    assert agent.state.runningToolCall is None
    assert agent.lastMessage is None
    assert agent.currentSession is None
    assert agent.currentTask is None
    assert agent.queueSize() == 0
    assert agent.steeringQueueSize() == 0
    assert agent.followUpQueueSize() == 0


def test_getters_and_state_setters_work(stub_model: Model) -> None:
    agent = Agent(AgentOptions(loop=make_loop(stub_model)))
    snapshot = agent.getState()
    snapshot.error = "changed"
    assert agent.state.error is None

    replacement = AgentState(
        systemPrompt="new",
        model=stub_model,
        thinking="high",
        tools=[],
        history=[],
        isStreaming=False,
        currentMessage=None,
        runningToolCall=None,
        error=None,
    )
    agent.setState(replacement)
    agent.setSystemPrompt("changed")
    agent.setThinking("medium")
    agent.setModel(stub_model)
    agent.setTools([])
    agent.updateState(error="oops")

    assert agent.state.systemPrompt == "changed"
    assert agent.state.thinking == "medium"
    assert agent.state.error == "oops"


def test_types_module_exposes_only_new_core_shapes() -> None:
    import agent_core.types as types_module

    assert hasattr(types_module, "AgentLoopConfig")
    assert hasattr(types_module, "AgentContext")
    assert not hasattr(types_module, "AgentConfig")
    assert not hasattr(types_module, "AgentHooks")
    assert not hasattr(types_module, "ToolHooks")


def test_public_classes_and_methods_have_chinese_docstrings() -> None:
    public_objects = [
        Agent,
        AgentOptions,
        AgentContext,
        AgentEvent,
        AgentLoopConfig,
        AgentState,
        AgentTool,
        BeforeToolCallContext,
        AfterToolCallContext,
    ]

    for obj in public_objects:
        doc = inspect.getdoc(obj)
        assert doc
        assert any("\u4e00" <= char <= "\u9fff" for char in doc)

    for method_name in [
        "__init__",
        "enqueue",
        "send",
        "prompt",
        "continueConversation",
        "run",
        "cancel",
        "wait",
        "reset",
    ]:
        doc = inspect.getdoc(getattr(Agent, method_name))
        assert doc
        assert any("\u4e00" <= char <= "\u9fff" for char in doc)

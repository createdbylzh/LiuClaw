from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path

import pytest

from ai import AssistantMessage, Model, StreamEvent, ToolCall, UserMessage
from coding_agent.cli import parse_args
from coding_agent.config.paths import build_agent_paths, find_project_settings_file
from coding_agent.core.agent_session import AgentSession
from coding_agent.core.compaction import SessionCompactor
from coding_agent.core.model_registry import ModelRegistry
from coding_agent.core.resource_loader import ResourceLoader
from coding_agent.core.session_manager import SessionManager
from coding_agent.core.settings_manager import SettingsManager
from coding_agent.core.tools import build_default_tools
from coding_agent.core.types import CodingAgentSettings, ToolPolicy
from coding_agent.modes.interactive.controller import InteractiveController
from coding_agent.modes.interactive.renderer import InteractiveRenderer
from coding_agent.modes.interactive.state import InteractiveState

main_module = importlib.import_module("coding_agent.main")


class FakeSession:
    def __init__(self, events: list[StreamEvent]) -> None:
        self._events = events

    async def consume(self):
        for event in self._events:
            yield event

    async def close(self) -> None:
        return None


@pytest.fixture
def stub_model() -> Model:
    return Model(
        id="stub:test",
        provider="stub",
        inputPrice=0.1,
        outputPrice=0.2,
        contextWindow=10000,
        maxOutputTokens=1000,
    )


def test_paths_and_settings_merge(tmp_path: Path) -> None:
    paths = build_agent_paths(tmp_path)
    paths.ensure_exists()
    workspace = tmp_path / "workspace"
    project_dir = workspace / ".LiuClaw"
    project_dir.mkdir(parents=True)
    project_file = find_project_settings_file(workspace)
    paths.settings_file.write_text(
        json.dumps({"default_model": "openai:gpt-5", "tool_policy": {"allow_bash": False}}),
        encoding="utf-8",
    )
    project_file.write_text(json.dumps({"default_thinking": "high", "theme": "sunrise"}), encoding="utf-8")

    settings = SettingsManager(paths.settings_file, project_file).load()

    assert settings.default_model == "openai:gpt-5"
    assert settings.default_thinking == "high"
    assert settings.theme == "sunrise"
    assert settings.tool_policy.allow_bash is False


def test_resource_loader_and_conflict_detection(tmp_path: Path) -> None:
    root = tmp_path / "root"
    paths = build_agent_paths(root)
    paths.ensure_exists()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (paths.skills_dir / "demo").mkdir(parents=True)
    (paths.skills_dir / "demo" / "SKILL.md").write_text("# Skill\nbody", encoding="utf-8")
    (paths.prompts_dir / "SYSTEM.md").write_text("custom prompt", encoding="utf-8")
    (workspace / "AGENTS.md").write_text("project context", encoding="utf-8")

    bundle = ResourceLoader(
        skills_dir=paths.skills_dir,
        prompts_dir=paths.prompts_dir,
        themes_dir=paths.themes_dir,
        extensions_dir=paths.extensions_dir,
        workspace_root=workspace,
    ).load()

    assert bundle.skills[0].name == "demo"
    assert bundle.prompts["SYSTEM"].content == "custom prompt"
    assert bundle.agents_context == "project context"

    (paths.prompts_dir / "demo.md").write_text("conflict", encoding="utf-8")
    with pytest.raises(ValueError, match="Resource name conflict"):
        ResourceLoader(
            skills_dir=paths.skills_dir,
            prompts_dir=paths.prompts_dir,
            themes_dir=paths.themes_dir,
            extensions_dir=paths.extensions_dir,
            workspace_root=workspace,
        ).load()


def test_session_manager_and_compaction(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path / "sessions")
    snapshot = manager.create_session(cwd=tmp_path, model_id="openai:gpt-5")
    parent_id = None
    for index in range(4):
        user = manager.append_message(
            snapshot.session_id,
            message=UserMessage(content=f"user-{index}"),
            branch_id=snapshot.branch_id,
            parent_id=parent_id,
        )
        parent_id = user.id
        assistant = manager.append_message(
            snapshot.session_id,
            message=AssistantMessage(content=f"assistant-{index}"),
            branch_id=snapshot.branch_id,
            parent_id=parent_id,
        )
        parent_id = assistant.id

    result = SessionCompactor(manager, keep_turns=1).compact_session(snapshot.session_id)
    messages = manager.build_context_messages(snapshot.session_id)

    assert result.compacted_count == 6
    assert messages[0].metadata["summary"] is True
    contents = [message.content for message in messages]
    assert "user-0" not in contents
    assert "assistant-3" in contents


@pytest.mark.asyncio
async def test_tools_and_agent_session_flow(tmp_path: Path, stub_model: Model) -> None:
    settings = CodingAgentSettings(default_model=stub_model.id, tool_policy=ToolPolicy(max_read_chars=1000))
    tools = {tool.name: tool for tool in build_default_tools(tmp_path, settings)}
    await tools["write"].execute(json.dumps({"path": "a.txt", "content": "hello"}), None)
    assert await tools["read"].execute(json.dumps({"path": "a.txt"}), None) == "hello"
    await tools["edit"].execute(json.dumps({"path": "a.txt", "old": "hello", "new": "world"}), None)
    assert await tools["read"].execute(json.dumps({"path": "a.txt"}), None) == "world"
    assert "a.txt" in await tools["find"].execute(json.dumps({"pattern": "a.txt"}), None)
    assert "a.txt" in await tools["ls"].execute(json.dumps({"path": "."}), None)
    assert "a.txt:1:world" in await tools["grep"].execute(json.dumps({"pattern": "world", "path": "."}), None)
    bash_output = await tools["bash"].execute(json.dumps({"command": "printf world"}), None)
    assert "exit_code: 0" in bash_output

    home_root = tmp_path / "home"
    paths = build_agent_paths(home_root)
    paths.ensure_exists()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    resource_loader = ResourceLoader(
        skills_dir=paths.skills_dir,
        prompts_dir=paths.prompts_dir,
        themes_dir=paths.themes_dir,
        extensions_dir=paths.extensions_dir,
        workspace_root=workspace,
    )
    session_manager = SessionManager(paths.sessions_dir)

    async def fake_stream(model, context, thinking, registry=None):
        latest_user = next(message.content for message in reversed(context.history) if getattr(message, "role", "") == "user")
        return FakeSession(
            [
                StreamEvent(type="start", provider="stub", model=stub_model),
                StreamEvent(type="text_delta", provider="stub", model=stub_model, text="echo:"),
                StreamEvent(
                    type="done",
                    provider="stub",
                    model=stub_model,
                    assistantMessage=AssistantMessage(content=f"echo:{latest_user}"),
                ),
            ]
        )

    agent_session = AgentSession(
        workspace_root=workspace,
        cwd=workspace,
        model=stub_model,
        thinking="medium",
        settings=settings,
        session_manager=session_manager,
        resource_loader=resource_loader,
        stream_fn=fake_stream,
    )
    agent_session.send_user_message("hello")
    events = [event async for event in agent_session.run_turn()]
    restored = session_manager.build_context_messages(agent_session.session_id)

    assert any(event.type == "message_delta" for event in events)
    assert restored[-1].content == "echo:hello"


@pytest.mark.asyncio
async def test_agent_session_uses_steering_and_follow_up(tmp_path: Path, stub_model: Model) -> None:
    settings = CodingAgentSettings(default_model=stub_model.id)
    home_root = tmp_path / "home"
    paths = build_agent_paths(home_root)
    paths.ensure_exists()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    resource_loader = ResourceLoader(
        skills_dir=paths.skills_dir,
        prompts_dir=paths.prompts_dir,
        themes_dir=paths.themes_dir,
        extensions_dir=paths.extensions_dir,
        workspace_root=workspace,
    )
    session_manager = SessionManager(paths.sessions_dir)

    async def fake_stream(model, context, thinking, registry=None):
        if any(getattr(message, "metadata", {}).get("follow_up") for message in context.history if getattr(message, "role", "") == "user"):
            return FakeSession(
                [
                    StreamEvent(type="start", provider="stub", model=stub_model),
                    StreamEvent(
                        type="done",
                        provider="stub",
                        model=stub_model,
                        assistantMessage=AssistantMessage(content="final answer"),
                    ),
                ]
            )
        if any(getattr(message, "role", "") == "tool" for message in context.history):
            return FakeSession(
                [
                    StreamEvent(type="start", provider="stub", model=stub_model),
                    StreamEvent(
                        type="done",
                        provider="stub",
                        model=stub_model,
                        assistantMessage=AssistantMessage(content="draft answer"),
                    ),
                ]
            )
        return FakeSession(
            [
                StreamEvent(type="start", provider="stub", model=stub_model),
                StreamEvent(
                    type="done",
                    provider="stub",
                    model=stub_model,
                    assistantMessage=AssistantMessage(
                        content="need tool",
                        toolCalls=[ToolCall(id="call_1", name="ls", arguments='{"path":"."}')],
                    ),
                ),
            ]
        )

    agent_session = AgentSession(
        workspace_root=workspace,
        cwd=workspace,
        model=stub_model,
        thinking="medium",
        settings=settings,
        session_manager=session_manager,
        resource_loader=resource_loader,
        stream_fn=fake_stream,
    )
    agent_session.send_user_message("inspect workspace")
    events = [event async for event in agent_session.run_turn()]
    restored = session_manager.build_context_messages(agent_session.session_id)

    status_sources = [event.payload.get("source") for event in events if event.type == "status"]
    restored_control_messages = [
        message for message in restored if getattr(message, "role", "") == "user" and getattr(message, "metadata", {})
    ]

    assert "steering" in status_sources
    assert "follow_up" in status_sources
    assert events[-1].message == "final answer"
    assert any(message.metadata.get("steering") for message in restored_control_messages)
    assert any(message.metadata.get("follow_up") for message in restored_control_messages)


@pytest.mark.asyncio
async def test_session_manager_lists_recent_sessions(tmp_path: Path) -> None:
    manager = SessionManager(tmp_path / "sessions")
    first = manager.create_session(cwd=tmp_path / "a", model_id="openai:gpt-5", title="first")
    second = manager.create_session(cwd=tmp_path / "b", model_id="openai:gpt-5", title="second")
    manager.append_message(second.session_id, message=UserMessage(content="hello second"), branch_id="main", parent_id=None)
    recent = manager.list_recent_sessions(limit=10)

    assert recent[0]["session_id"] == second.session_id
    assert any(item["session_id"] == first.session_id for item in recent)


@pytest.mark.asyncio
async def test_interactive_controller_commands(tmp_path: Path, stub_model: Model) -> None:
    settings = CodingAgentSettings(default_model=stub_model.id)
    home_root = tmp_path / "home"
    paths = build_agent_paths(home_root)
    paths.ensure_exists()
    paths.models_file.write_text(
        json.dumps(
            [
                {
                    "id": "stub:test",
                    "provider": "stub",
                    "inputPrice": 0.1,
                    "outputPrice": 0.2,
                    "contextWindow": 10000,
                    "maxOutputTokens": 1000,
                }
            ]
        ),
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    resource_loader = ResourceLoader(
        skills_dir=paths.skills_dir,
        prompts_dir=paths.prompts_dir,
        themes_dir=paths.themes_dir,
        extensions_dir=paths.extensions_dir,
        workspace_root=workspace,
    )
    session_manager = SessionManager(paths.sessions_dir)
    registry = ModelRegistry(paths.models_file)

    async def fake_stream(model, context, thinking, registry=None):
        latest_user = next(message.content for message in reversed(context.history) if getattr(message, "role", "") == "user")
        return FakeSession(
            [
                StreamEvent(type="start", provider="stub", model=stub_model),
                StreamEvent(type="text_delta", provider="stub", model=stub_model, text="ok:"),
                StreamEvent(type="done", provider="stub", model=stub_model, assistantMessage=AssistantMessage(content=f"ok:{latest_user}")),
            ]
        )

    session = AgentSession(
        workspace_root=workspace,
        cwd=workspace,
        model=stub_model,
        thinking="medium",
        settings=settings,
        session_manager=session_manager,
        resource_loader=resource_loader,
        stream_fn=fake_stream,
    )
    state = InteractiveState.from_session(session)
    renderer = type(
        "RendererStub",
        (),
        {
            "__init__": lambda self: setattr(self, "input_buffer", type("BufferStub", (), {"text": "", "completer": None, "history": None})()) or setattr(self, "application", None),
            "invalidate": lambda self: None,
        },
    )()
    controller = InteractiveController(session, registry, renderer, state)

    await controller.handle_command("/model stub:test")
    await controller.handle_command("/thinking high")
    await controller.handle_command("/theme default")
    await controller.handle_command("/pwd")
    await controller.handle_text("hello")
    await controller.handle_command("/retry")
    await controller.handle_command("/sessions")

    assert controller.session.model.id == "stub:test"
    assert state.thinking == "high"
    assert state.theme == "default"
    assert any("workspace" in item for item in state.status_timeline)
    assert any(card.body == "ok:hello" for card in state.output_cards)
    assert any("stub:test" in item for item in state.status_timeline)
    await controller.handle_command("/clear")
    assert not state.output_cards


def test_renderer_keeps_full_history_and_scroll_api() -> None:
    state = InteractiveState(
        session_id="s1",
        model_id="stub:test",
        thinking="medium",
        cwd=Path("/tmp"),
        theme="default",
    )
    for index in range(30):
        state.output_cards.append(type("Card", (), {"title": f"Assistant {index}", "body": f"body-{index}", "style": "assistant"})())
    renderer = InteractiveRenderer(state)
    fragments = renderer._render_main_panel()

    assert any("body-0" in text for _, text in fragments)
    assert any("body-29" in text for _, text in fragments)
    renderer.scroll_main(3)
    assert renderer.main_window.vertical_scroll == 3


def test_model_registry_cli_and_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home_root = tmp_path / "home"
    paths = build_agent_paths(home_root)
    paths.ensure_exists()
    paths.models_file.write_text(
        json.dumps(
            [
                {
                    "id": "stub:test",
                    "provider": "stub",
                    "inputPrice": 0.1,
                    "outputPrice": 0.2,
                    "contextWindow": 10000,
                    "maxOutputTokens": 1000,
                }
            ]
        ),
        encoding="utf-8",
    )
    registry = ModelRegistry(paths.models_file)
    assert registry.get("stub:test").provider == "stub"

    args = parse_args(["--model", "stub:test", "--thinking", "low", "--cwd", str(tmp_path)])
    assert args.model == "stub:test"
    assert args.thinking == "low"

    run_state: dict[str, object] = {}

    async def fake_run(self) -> int:
        run_state["model"] = self.session.model.id
        run_state["thinking"] = self.session.thinking
        return 0

    monkeypatch.setattr(main_module, "build_agent_paths", lambda: paths)
    monkeypatch.setattr("coding_agent.modes.interactive.app.InteractiveApp.run", fake_run)

    exit_code = main_module.main(["--model", "stub:test", "--thinking", "low", "--cwd", str(tmp_path)])

    assert exit_code == 0
    assert run_state == {"model": "stub:test", "thinking": "low"}

from __future__ import annotations

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.styles import Style

from .state import InteractiveState


class InteractiveRenderer:
    """负责把交互状态渲染成 prompt_toolkit 界面。"""

    def __init__(self, state: InteractiveState) -> None:
        """初始化渲染器并保存状态对象。"""

        self.state = state
        self.application: Application | None = None
        self.input_buffer = Buffer(multiline=True)
        self.main_window = Window(FormattedTextControl(self._render_main_panel), wrap_lines=True)
        self.sidebar_window = Window(FormattedTextControl(self._render_sidebar), width=Dimension(preferred=36), wrap_lines=True)
        self.input_window = Window(BufferControl(buffer=self.input_buffer), height=Dimension(min=3, preferred=5), wrap_lines=True)

    def build_application(self, controller) -> Application:
        """创建完整的 prompt_toolkit Application。"""

        key_bindings = self._build_key_bindings(controller)
        body = VSplit(
            [
                self.main_window,
                Window(width=1, char="|"),
                self.sidebar_window,
            ]
        )
        root = HSplit(
            [
                body,
                Window(height=1, char="-"),
                Window(FormattedTextControl(self._render_input_hint), height=1),
                self.input_window,
                Window(height=1, char="-"),
                Window(FormattedTextControl(self._render_status_bar), height=1),
            ]
        )
        application = Application(
            layout=Layout(root, focused_element=self.input_window),
            key_bindings=key_bindings,
            full_screen=True,
            mouse_support=False,
            style=self._build_style(),
            refresh_interval=0.1,
        )
        self.application = application
        return application

    def invalidate(self) -> None:
        """请求界面刷新。"""

        if self.application is not None:
            self.application.invalidate()

    def _build_style(self) -> Style:
        """根据当前主题生成界面样式。"""

        return Style.from_dict(
            {
                "assistant": "ansicyan",
                "thinking": "ansiblue",
                "tool_running": "ansiyellow",
                "tool_success": "ansigreen",
                "tool_error": "ansired",
                "status": "ansiwhite",
                "error": "ansired bold",
                "status_bar": "reverse",
                "input_prompt": "ansimagenta",
            }
        )

    def _build_key_bindings(self, controller) -> KeyBindings:
        """构造交互层使用的快捷键集合。"""

        kb = KeyBindings()

        @kb.add("enter", filter=Condition(lambda: self.state.submit_on_enter and not self.state.is_running))
        def _(event) -> None:
            controller.submit_current_buffer()

        @kb.add("escape", "enter")
        def _(event) -> None:
            self.input_buffer.insert_text("\n")

        @kb.add("c-c")
        def _(event) -> None:
            controller.cancel_current()

        @kb.add("c-l")
        def _(event) -> None:
            controller.clear_output()

        @kb.add("tab")
        def _(event) -> None:
            controller.autocomplete_buffer()

        @kb.add("c-r")
        def _(event) -> None:
            controller.show_help("历史搜索可使用上下方向键浏览输入历史。")

        @kb.add("pageup")
        def _(event) -> None:
            controller.scroll_main_page_up()

        @kb.add("pagedown")
        def _(event) -> None:
            controller.scroll_main_page_down()

        @kb.add("escape", "up")
        def _(event) -> None:
            controller.scroll_main_up()

        @kb.add("escape", "down")
        def _(event) -> None:
            controller.scroll_main_down()

        @kb.add("f6")
        def _(event) -> None:
            controller.toggle_focus()

        return kb

    def _render_main_panel(self):
        """渲染主输出区。"""

        fragments: list[tuple[str, str]] = []
        for card in self.state.output_cards:
            fragments.append(("class:assistant", f"[{card.title}]\n"))
            fragments.append((f"class:{card.style}", f"{card.body}\n\n"))
        for thinking_card in self.state.thinking_cards:
            fragments.append(("class:thinking", f"[{thinking_card.title}]\n"))
            fragments.append(("class:thinking", f"{thinking_card.body}\n\n"))
        for tool in self.state.tool_cards:
            tool_style = "tool_error" if tool.status == "error" else ("tool_success" if tool.status == "success" else "tool_running")
            fragments.append((f"class:{tool_style}", f"[Tool:{tool.tool_name}] {tool.status}\n"))
            if tool.arguments:
                fragments.append((f"class:{tool_style}", f"args: {tool.arguments}\n"))
            if tool.output_preview:
                fragments.append((f"class:{tool_style}", f"{tool.output_preview}\n"))
            fragments.append((f"class:{tool_style}", "\n"))
        if not fragments:
            fragments.append(("class:status", "No output yet.\n"))
        return fragments

    def _render_sidebar(self):
        """渲染侧边状态栏。"""

        lines = [
            ("class:status", f"Session: {self.state.session_id}\n"),
            ("class:status", f"Model: {self.state.model_id}\n"),
            ("class:status", f"Thinking: {self.state.thinking or 'default'}\n"),
            ("class:status", f"CWD: {self.state.cwd}\n"),
            ("class:status", f"Running: {'yes' if self.state.is_running else 'no'}\n"),
            ("class:status", f"Theme: {self.state.theme}\n"),
            ("class:status", f"Current Tool: {self.state.current_tool or '-'}\n"),
            ("class:status", "\nRecent Sessions:\n"),
        ]
        for item in self.state.recent_sessions[:5]:
            lines.append(("class:status", f"- {item.get('session_id')} {item.get('title', '')}\n"))
        lines.append(("class:status", "\nStatus Timeline:\n"))
        for item in self.state.status_timeline[-8:]:
            lines.append(("class:status", f"- {item}\n"))
        return lines

    def _render_input_hint(self):
        """渲染输入区说明。"""

        mode = "Enter send / Alt-Enter newline" if self.state.submit_on_enter else "Alt-Enter send / Enter newline"
        return [("class:input_prompt", f"Input: {mode}")]

    def _render_status_bar(self):
        """渲染底部状态栏。"""

        error = f" | Error: {self.state.last_error}" if self.state.last_error else ""
        running = "RUNNING" if self.state.is_running else "IDLE"
        return [("class:status_bar", f" Ctrl-C cancel | Ctrl-L clear | PgUp/PgDn scroll | Esc+Up/Down line scroll | F6 focus | Tab complete | {running}{error}")]

    def scroll_main(self, delta: int) -> None:
        """按行滚动主输出区。"""

        self.main_window.vertical_scroll = max(0, self.main_window.vertical_scroll + delta)
        self.invalidate()

    def scroll_main_page(self, delta_pages: int) -> None:
        """按页滚动主输出区。"""

        page = max(5, self._window_height(self.main_window) - 2)
        self.scroll_main(delta_pages * page)

    def focus_main(self) -> None:
        """把焦点切换到主输出区。"""

        if self.application is not None:
            self.application.layout.focus(self.main_window)

    def focus_input(self) -> None:
        """把焦点切换回输入区。"""

        if self.application is not None:
            self.application.layout.focus(self.input_window)

    def focused_on_input(self) -> bool:
        """判断当前焦点是否位于输入区。"""

        if self.application is None:
            return True
        return self.application.layout.current_window is self.input_window

    @staticmethod
    def _window_height(window: Window) -> int:
        """读取窗口当前渲染高度，取不到时返回保守默认值。"""

        render_info = window.render_info
        if render_info is None:
            return 12
        return max(1, render_info.window_height)

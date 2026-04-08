from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .types import ChatEvent


@dataclass(slots=True)
class EventRecord:
    name: str
    data: dict[str, Any]


class EventsWatcher:
    def __init__(self, events_dir: Path, dispatch) -> None:
        self.events_dir = events_dir
        self.dispatch = dispatch
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def scan_once(self) -> None:
        self.events_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(self.events_dir.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            event = self._build_chat_event(path, payload)
            if event is None:
                continue
            await self.dispatch(event)
            if payload.get("type") in {"immediate", "one-shot"}:
                path.unlink(missing_ok=True)

    def _build_chat_event(self, path: Path, payload: dict[str, Any]) -> ChatEvent | None:
        event_type = payload.get("type")
        if event_type not in {"immediate", "one-shot", "periodic"}:
            return None
        if event_type == "one-shot":
            at_value = payload.get("at")
            if not at_value:
                return None
            at = datetime.fromisoformat(str(at_value).replace("Z", "+00:00"))
            if at > datetime.now(timezone.utc):
                return None
        if event_type == "periodic":
            interval = int(payload.get("interval_seconds", 0) or 0)
            last_run = payload.get("last_run")
            if interval <= 0:
                return None
            if last_run:
                last_dt = datetime.fromisoformat(str(last_run).replace("Z", "+00:00"))
                elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
                if elapsed < interval:
                    return None
            payload["last_run"] = datetime.now(timezone.utc).isoformat()
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return ChatEvent(
            platform="feishu",
            chat_id=str(payload["channelId"]),
            message_id=f"event:{path.stem}",
            sender_id="system",
            sender_name="system",
            text=str(payload["text"]),
            is_direct=False,
            is_trigger=True,
            metadata={"synthetic": True, "event_type": event_type, "event_file": path.name},
        )

    async def run(self, interval_seconds: float = 1.0) -> None:
        while not self._stop.is_set():
            await self.scan_once()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval_seconds)
            except asyncio.TimeoutError:
                continue

    def start(self, interval_seconds: float = 1.0) -> asyncio.Task:
        self._stop.clear()
        self._task = asyncio.create_task(self.run(interval_seconds=interval_seconds))
        return self._task

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class DummyResponse:
    def __init__(self, payload=None, *, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class DummyStreamResponse:
    def __init__(self, lines: list[str], *, status_code: int = 200):
        self._lines = lines
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class DummyStreamContext:
    def __init__(self, response: DummyStreamResponse):
        self.response = response

    async def __aenter__(self) -> DummyStreamResponse:
        return self.response

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

"""Per-stage latency measurement.

Every pipeline stage is wrapped in ``log.stage("name")``. Each stage produces one
record ``{run_id, stage, ms, ...meta}`` that is optionally appended to a JSONL file,
so the eval scripts can compute p50/p95 per stage later.
"""
from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class LatencyLog:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records: list[dict[str, Any]] = []
        self.run_id = self.new_run()

    def new_run(self) -> str:
        """Start a new run (one utterance going through the pipeline)."""
        self.run_id = uuid.uuid4().hex[:8]
        self._run_start = time.perf_counter()
        return self.run_id

    @contextmanager
    def stage(self, name: str, **meta: Any) -> Iterator[dict[str, Any]]:
        """Time a block. Callers may add fields to the yielded dict (e.g. results)."""
        extra: dict[str, Any] = {}
        t0 = time.perf_counter()
        try:
            yield extra
        finally:
            ms = (time.perf_counter() - t0) * 1000
            self._write({"stage": name, "ms": round(ms, 2), **meta, **extra})

    def mark(self, name: str, **meta: Any) -> float:
        """Record an event as time since run start (e.g. first LLM token, first audio)."""
        ms = (time.perf_counter() - self._run_start) * 1000
        self._write({"stage": name, "ms": round(ms, 2), "since_run_start": True, **meta})
        return ms

    def _write(self, rec: dict[str, Any]) -> None:
        rec = {"run_id": self.run_id, "ts": time.time(), **rec}
        self.records.append(rec)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def last(self, stage: str) -> dict[str, Any] | None:
        for rec in reversed(self.records):
            if rec["stage"] == stage and rec["run_id"] == self.run_id:
                return rec
        return None

"""Shop-floor tools the LLM can call, with JSON schemas.

The data is a mock MES snapshot (``data/shopfloor.json``) loaded into memory;
``create_ticket`` mutates the in-memory copy only, so every process starts from
the same state (reproducible evals).

Tools never raise on bad input from the LLM. They return ``{"error": ...}`` so
the model can correct itself or tell the user, instead of crashing the turn.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

DATA_PATH = Path(__file__).parent / "data" / "shopfloor.json"

SEVERITIES = ("info", "warning", "critical")
PRIORITIES = ("low", "medium", "high")

# Neutral schema format: {name, description, parameters (JSON Schema)}.
# Converters below adapt it to the OpenAI/Ollama and Anthropic tool formats.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "get_line_status",
        "description": (
            "Get the current status of one production line: running/degraded/stopped/"
            "maintenance, output vs. target per hour, OEE, and the status of each machine."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer", "minimum": 1, "maximum": 5, "description": "Line number 1-5"},
            },
            "required": ["line_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_alarms",
        "description": (
            "List currently active alarms, newest first. Optionally filter by line and/or "
            "severity. Without filters, returns all active alarms."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "line_id": {"type": "integer", "minimum": 1, "maximum": 5, "description": "Only alarms on this line"},
                "severity": {
                    "type": "string",
                    "enum": list(SEVERITIES),
                    "description": "Only alarms with exactly this severity",
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_ticket",
        "description": (
            "Create a maintenance ticket for a machine. Changes data: the assistant must "
            "confirm with the user before calling it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "machine_id": {"type": "integer", "minimum": 1, "maximum": 12, "description": "Machine number 1-12"},
                "description": {"type": "string", "minLength": 3, "description": "What is wrong, in the user's words"},
                "priority": {"type": "string", "enum": list(PRIORITIES), "description": "Default: medium"},
            },
            "required": ["machine_id", "description"],
            "additionalProperties": False,
        },
    },
]


def openai_tools() -> list[dict[str, Any]]:
    """Schemas in the OpenAI / Ollama ``tools=[...]`` format."""
    return [{"type": "function", "function": s} for s in TOOL_SCHEMAS]


def anthropic_tools() -> list[dict[str, Any]]:
    """Schemas in the Anthropic Messages API format."""
    return [
        {"name": s["name"], "description": s["description"], "input_schema": s["parameters"]}
        for s in TOOL_SCHEMAS
    ]


class ToolError(ValueError):
    pass


def _int(args: dict, key: str, lo: int, hi: int, required: bool = True) -> int | None:
    val = args.get(key)
    if val is None:
        if required:
            raise ToolError(f"missing required argument '{key}'")
        return None
    # LLMs sometimes send numbers as strings ("2") or floats (2.0)
    try:
        num = float(val)
    except (TypeError, ValueError):
        raise ToolError(f"'{key}' must be an integer, got {val!r}") from None
    if not num.is_integer():
        raise ToolError(f"'{key}' must be an integer, got {val!r}")
    num = int(num)
    if not lo <= num <= hi:
        raise ToolError(f"'{key}' must be between {lo} and {hi}, got {num}")
    return num


def _enum(args: dict, key: str, allowed: tuple[str, ...], default: str | None = None) -> str | None:
    val = args.get(key)
    if val is None:
        return default
    val = str(val).strip().lower()
    if val not in allowed:
        raise ToolError(f"'{key}' must be one of {list(allowed)}, got {val!r}")
    return val


class ShopFloor:
    def __init__(self, data: dict[str, Any] | None = None, now: Callable[[], datetime] = datetime.now) -> None:
        if data is None:
            data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
        self.data = copy.deepcopy(data)
        self._now = now
        self.tools: dict[str, Callable[..., dict[str, Any]]] = {
            "get_line_status": self.get_line_status,
            "list_alarms": self.list_alarms,
            "create_ticket": self.create_ticket,
        }

    # --- lookups -----------------------------------------------------------
    def _machine(self, machine_id: int) -> dict[str, Any]:
        for m in self.data["machines"]:
            if m["id"] == machine_id:
                return m
        raise ToolError(f"machine {machine_id} does not exist")

    def _line(self, line_id: int) -> dict[str, Any]:
        for line in self.data["lines"]:
            if line["id"] == line_id:
                return line
        raise ToolError(f"line {line_id} does not exist")

    # --- tools -------------------------------------------------------------
    def get_line_status(self, line_id: Any = None) -> dict[str, Any]:
        line = self._line(_int({"line_id": line_id}, "line_id", 1, 5))
        active = [a for a in self.data["alarms"] if a["active"] and a["line_id"] == line["id"]]
        return {
            "line_id": line["id"],
            "name": line["name"],
            "status": line["status"],
            "output_per_hour": line["output_per_hour"],
            "target_per_hour": line["target_per_hour"],
            "oee": line["oee"],
            "machines": [
                {"id": m["id"], "name": m["name"], "status": m["status"]}
                for m in map(self._machine, line["machines"])
            ],
            "active_alarms": len(active),
        }

    def list_alarms(self, line_id: Any = None, severity: Any = None) -> dict[str, Any]:
        args = {"line_id": line_id, "severity": severity}
        lid = _int(args, "line_id", 1, 5, required=False)
        sev = _enum(args, "severity", SEVERITIES)
        alarms = [
            a for a in self.data["alarms"]
            if a["active"] and (lid is None or a["line_id"] == lid) and (sev is None or a["severity"] == sev)
        ]
        alarms.sort(key=lambda a: a["raised_at"], reverse=True)
        return {
            "filters": {"line_id": lid, "severity": sev},
            "count": len(alarms),
            "alarms": [
                {k: a[k] for k in ("id", "code", "machine_id", "line_id", "severity", "message_de", "message_en", "raised_at")}
                for a in alarms
            ],
        }

    def create_ticket(self, machine_id: Any = None, description: Any = None, priority: Any = None) -> dict[str, Any]:
        args = {"machine_id": machine_id, "priority": priority}
        machine = self._machine(_int(args, "machine_id", 1, 12))
        desc = (description or "").strip() if isinstance(description, str) else ""
        if len(desc) < 3:
            raise ToolError("'description' must be a short text describing the problem")
        prio = _enum(args, "priority", PRIORITIES, default="medium")

        tickets = self.data["tickets"]
        next_no = max((int(t["id"].split("-")[1]) for t in tickets), default=0) + 1
        ticket = {
            "id": f"T-{next_no:04d}",
            "machine_id": machine["id"],
            "description": desc,
            "priority": prio,
            "status": "open",
            "created_at": self._now().isoformat(timespec="seconds"),
        }
        tickets.append(ticket)
        return {"created": True, "ticket": ticket, "machine_name": machine["name"]}

    # --- dispatch ----------------------------------------------------------
    def call(self, name: str, arguments: dict[str, Any] | str | None = None) -> dict[str, Any]:
        """Run a tool by name. Arguments may be a dict or a JSON string (as LLMs return them)."""
        fn = self.tools.get(name)
        if fn is None:
            return {"error": f"unknown tool '{name}'", "available": list(self.tools)}
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except json.JSONDecodeError as e:
                return {"error": f"arguments are not valid JSON: {e.msg}"}
        arguments = arguments or {}
        if not isinstance(arguments, dict):
            return {"error": "arguments must be a JSON object"}

        allowed = set(next(s for s in TOOL_SCHEMAS if s["name"] == name)["parameters"]["properties"])
        unknown = set(arguments) - allowed
        if unknown:
            return {"error": f"unknown argument(s) {sorted(unknown)} for '{name}'", "allowed": sorted(allowed)}
        try:
            return fn(**arguments)
        except ToolError as e:
            return {"error": str(e)}

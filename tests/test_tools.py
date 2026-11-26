from datetime import datetime

import pytest

from functions.tools import TOOL_SCHEMAS, ShopFloor, anthropic_tools, openai_tools


@pytest.fixture
def shop():
    return ShopFloor(now=lambda: datetime(2026, 11, 26, 9, 30))


# --- schemas ---------------------------------------------------------------
def test_every_schema_has_a_tool_and_vice_versa(shop):
    assert {s["name"] for s in TOOL_SCHEMAS} == set(shop.tools)


def test_schema_formats():
    for t in openai_tools():
        assert t["type"] == "function" and t["function"]["parameters"]["type"] == "object"
    for t in anthropic_tools():
        assert set(t) == {"name", "description", "input_schema"}


def test_required_args_exist_in_properties():
    for s in TOOL_SCHEMAS:
        params = s["parameters"]
        assert set(params["required"]) <= set(params["properties"])


# --- get_line_status -------------------------------------------------------
def test_line_status(shop):
    r = shop.call("get_line_status", {"line_id": 2})
    assert r["status"] == "degraded"
    assert [m["id"] for m in r["machines"]] == [3, 4, 5]
    assert r["active_alarms"] == 2


@pytest.mark.parametrize("raw", ["3", 3.0, '{"line_id": "3"}'])
def test_line_status_coerces_llm_style_numbers(shop, raw):
    args = raw if isinstance(raw, str) and raw.startswith("{") else {"line_id": raw}
    assert shop.call("get_line_status", args)["line_id"] == 3


@pytest.mark.parametrize("bad", [0, 6, 2.5, "zwei", None])
def test_line_status_rejects_bad_ids(shop, bad):
    assert "error" in shop.call("get_line_status", {"line_id": bad})


# --- list_alarms -----------------------------------------------------------
def test_list_alarms_all_active_newest_first(shop):
    r = shop.call("list_alarms", {})
    assert r["count"] == 7  # A-1007 is inactive
    times = [a["raised_at"] for a in r["alarms"]]
    assert times == sorted(times, reverse=True)


def test_list_alarms_filters(shop):
    assert {a["id"] for a in shop.call("list_alarms", {"line_id": 3})["alarms"]} == {"A-1003", "A-1004", "A-1005"}
    crit = shop.call("list_alarms", {"severity": "CRITICAL"})
    assert crit["count"] == 3 and all(a["severity"] == "critical" for a in crit["alarms"])
    both = shop.call("list_alarms", {"line_id": 3, "severity": "warning"})
    assert [a["code"] for a in both["alarms"]] == ["W-301"]
    assert shop.call("list_alarms", {"line_id": 1})["count"] == 0


def test_list_alarms_rejects_unknown_severity(shop):
    assert "error" in shop.call("list_alarms", {"severity": "urgent"})


# --- create_ticket ---------------------------------------------------------
def test_create_ticket(shop):
    r = shop.call("create_ticket", {"machine_id": 7, "description": "Spindel überhitzt", "priority": "high"})
    assert r["created"] and r["ticket"]["id"] == "T-0043"
    assert r["ticket"]["created_at"] == "2026-11-26T09:30:00"
    assert r["machine_name"] == "Schweißroboter S-420"
    assert shop.call("create_ticket", {"machine_id": 1, "description": "leak"})["ticket"]["id"] == "T-0044"


def test_create_ticket_defaults_priority(shop):
    assert shop.call("create_ticket", {"machine_id": 3, "description": "noise"})["ticket"]["priority"] == "medium"


@pytest.mark.parametrize(
    "args",
    [
        {"machine_id": 13, "description": "x broken"},
        {"description": "no machine"},
        {"machine_id": 3, "description": "  "},
        {"machine_id": 3, "description": "ok text", "priority": "asap"},
    ],
)
def test_create_ticket_rejects_bad_input(shop, args):
    before = len(shop.data["tickets"])
    assert "error" in shop.call("create_ticket", args)
    assert len(shop.data["tickets"]) == before


def test_instances_do_not_share_state():
    a, b = ShopFloor(), ShopFloor()
    a.call("create_ticket", {"machine_id": 2, "description": "test ticket"})
    assert len(b.data["tickets"]) == len(a.data["tickets"]) - 1


# --- dispatch --------------------------------------------------------------
def test_dispatch_errors(shop):
    assert "error" in shop.call("reboot_plant", {})
    assert "error" in shop.call("get_line_status", "{not json")
    assert "error" in shop.call("get_line_status", {"line_id": 1, "verbose": True})
    assert "error" in shop.call("get_line_status", "[1]")

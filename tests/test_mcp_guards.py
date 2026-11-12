import asyncio

import pytest

from processpilot.mcp_server import uipath_mcp as m


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    monkeypatch.setattr(m.audit, "log", lambda *a, **k: None)
    monkeypatch.setattr(m.audit, "count_since", lambda *a, **k: 0)
    monkeypatch.delenv("PP_ALLOW_SIMULATION", raising=False)


def test_rejects_malformed_invoice_id():
    assert m.submit_request("INV-204; DROP TABLE", "r1")["ok"] is False


def test_rejects_malformed_request_id():
    assert m.submit_request("INV-204", "a b")["ok"] is False


def test_simulation_is_refused_by_default():
    r = m.submit_request("INV-204", "r1", "app_timeout")
    assert r["ok"] is False and "simulation" in r["error"]


def test_rate_limit_refuses(monkeypatch):
    monkeypatch.setattr(m.audit, "count_since", lambda *a, **k: 99)
    r = m.submit_request("INV-204", "r1")
    assert r["ok"] is False and "rate limit" in r["error"]


def test_valid_submit_starts_the_agent_once(monkeypatch):
    calls = []

    def fake_start(request, simulate, request_id):
        calls.append(request_id)
        return {"thread_id": request_id, "stage": "AWAITING_APPROVAL", "invoice_id": "INV-204",
                "pending": {"kind": "INVOICE", "invoice_id": "INV-204", "vendor": "x", "total": 1,
                            "required_role": "Finance Manager", "summary": "ok"}}

    monkeypatch.setattr(m.service, "start_request", fake_start)
    r = m.submit_request("INV-204", "r1")
    assert r["ok"] and r["stage"] == "AWAITING_APPROVAL" and calls == ["mcp-r1"]
    assert "A person must approve" in r["human_next_step"]


def test_status_is_scoped_to_mcp_created_threads(monkeypatch):
    seen = []
    monkeypatch.setattr(m.service, "get_status", lambda tid: seen.append(tid) or {"thread_id": tid, "stage": "NOT_FOUND"})
    m.get_request_status("abc")
    assert seen == ["mcp-abc"]


def test_no_approval_tool_is_exposed():
    names = [t.name for t in asyncio.run(m.mcp.list_tools())]
    assert not any("approv" in n or "decision" in n for n in names)
    assert len(names) == 6
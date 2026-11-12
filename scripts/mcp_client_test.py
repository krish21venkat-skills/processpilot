"""Stage 7 A2: exercise the MCP server as a client would (stdio), then play the human approver."""
import asyncio
import json
import sys
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from processpilot import service


def out(res) -> dict:
    text = next((c.text for c in res.content if hasattr(c, "text")), "")
    try:
        return json.loads(text)
    except ValueError:
        return {"ok": False, "error": text[:200]}


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["-m", "processpilot.mcp_server.uipath_mcp"],
                                   env={"PP_CLIENT_ID": "test-client"})
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()

        async def call(name: str, **args) -> dict:
            return out(await s.call_tool(name, args))

        names = [t.name for t in (await s.list_tools()).tools]
        print("tools:", names)
        print("approval tool exposed?", any("approv" in n for n in names))
        print("\nsearch_policy:", [h["citation"] for h in (await call("search_policy", query="retry after timeout", k=2))["results"]])
        print("check_invoice INV-203:", [f["code"] for f in (await call("check_invoice", invoice_id="INV-203"))["findings"]])

        print("\n-- guards (all must be refused) --")
        for label, name, args in [
            ("malformed invoice id", "submit_request", dict(invoice_id="INV-204; DROP", request_id="x1")),
            ("malformed request id", "submit_request", dict(invoice_id="INV-204", request_id="a b")),
            ("simulation disabled", "submit_request", dict(invoice_id="INV-204", request_id="x2", simulate_failure="app_timeout")),
            ("unknown invoice", "submit_request", dict(invoice_id="INV-999", request_id="x3")),
            ("unknown request", "get_request_status", dict(request_id="nope")),
        ]:
            res = await call(name, **args)
            print(f"{label:22} ok={res['ok']}  {res.get('error', '')[:70]}")

        print("\n-- live run through the agent --")
        rid = "t-" + uuid.uuid4().hex[:8]
        a = await call("submit_request", invoice_id="INV-204", request_id=rid)
        print("submit:", a["stage"], "| pending role:", a["pending"]["required_role"])
        print("next  :", a["human_next_step"])
        b = await call("submit_request", invoice_id="INV-204", request_id=rid)
        print("repeat with the same id -> duplicate_request =", b["duplicate_request"])

        print("\n(playing the human approver: r.kumar, Finance Manager; the bot now runs...)")
        service.submit_decision("mcp-" + rid, "r.kumar", "Finance Manager", True)

        st = await call("get_request_status", request_id=rid)
        print("\nstatus:", st["stage"], st["outcome"], "|", st.get("answer", "")[-90:])
        logs = await call("get_job_logs", request_id=rid)
        print("logs (untrusted_data=%s):" % logs.get("untrusted_data"))
        print("\n".join("   " + x for x in logs.get("lines", [])[-4:]))
        print("\naudit (last 5):")
        for e in (await call("get_audit_trail", invoice_id="INV-204"))["events"][-5:]:
            print("  ", e["ts"][11:19], e["event"])


asyncio.run(main())
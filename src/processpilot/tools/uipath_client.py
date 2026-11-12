"""Minimal UiPath Orchestrator client: OAuth client credentials, queue items only (no destructive calls)."""
import time

import requests
import re
from datetime import datetime, timedelta

from processpilot import config

TOKEN_URL = "https://cloud.uipath.com/identity_/connect/token"
BASE = f"https://cloud.uipath.com/{config.UIPATH_ORG}/{config.UIPATH_TENANT}/orchestrator_/"

_token = {"value": "", "expires": 0.0}


def _auth() -> dict:
    """Fetch (and cache) an access token; build the headers for an Orchestrator call."""
    if time.time() > _token["expires"] - 60:
        r = requests.post(TOKEN_URL, timeout=30, data={
            "grant_type": "client_credentials",
            "client_id": config.UIPATH_CLIENT_ID,
            "client_secret": config.UIPATH_CLIENT_SECRET,
            "scope": config.UIPATH_SCOPES,
        })
        if not r.ok:
            raise RuntimeError(f"Token request failed {r.status_code}: {r.text[:300]}")
        body = r.json()
        _token.update(value=body["access_token"], expires=time.time() + body["expires_in"])
    return {"Authorization": f"Bearer {_token['value']}", "X-UIPATH-FolderPath": config.UIPATH_FOLDER}


def _call(method: str, path: str, **kw) -> dict:
    r = requests.request(method, BASE + path, headers=_auth(), timeout=30, **kw)
    if not r.ok:
        raise RuntimeError(f"Orchestrator {r.status_code} on {path}: {r.text[:300]}")
    return r.json() if r.text else {}


def add_queue_item(invoice: dict, simulate_failure: str = "none") -> int:
    """Push one invoice to the queue. Returns the queue item id."""
    body = {"itemData": {
        "Name": config.UIPATH_QUEUE,
        "Priority": "Normal",
        "Reference": invoice["invoice_id"],
        "SpecificContent": {
            "invoice_id": invoice["invoice_id"],
            "vendor_id": invoice["vendor_id"],
            "invoice_number": invoice["invoice_number"],
            "invoice_date": invoice["invoice_date"],
            "total": str(invoice["total"]),
            "po_number": invoice.get("po_number") or "",
            "simulate_failure": simulate_failure,  # none | bad_date | missing_field | duplicate | app_timeout
        },
    }}
    return _call("POST", "odata/Queues/UiPathODataSvc.AddQueueItem", json=body)["Id"]


def get_queue_item_status(item_id: int) -> dict:
    d = _call("GET", f"odata/QueueItems({item_id})")
    return {"id": d["Id"], "status": d["Status"], "reference": d.get("Reference"),
            "retries": d.get("RetryNumber"), "output": d.get("OutputData"),
            "exception": d.get("ProcessingException"),
            "started": d.get("StartProcessing"), "ended": d.get("EndProcessing")}

def _ts(s: str) -> datetime:
    return datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")


def get_job_logs(started: str | None, ended: str | None, limit: int = 12) -> list[str]:
    """Robot log lines written while the bot processed one queue item (one robot, so the window is unambiguous)."""
    if not started:
        return []
    lo = _ts(started) - timedelta(seconds=1)
    hi = _ts(ended or started) + timedelta(seconds=3)
    d = _call("GET", "odata/RobotLogs", params={"$top": 200, "$orderby": "TimeStamp desc"})
    rows = sorted((r for r in d.get("value", []) if lo <= _ts(r["TimeStamp"]) <= hi),
                  key=lambda r: r["TimeStamp"])
    return [f"{r['TimeStamp'][11:19]} {r['Level']}: {' '.join(str(r['Message']).split())[:200]}"
            for r in rows][-limit:]
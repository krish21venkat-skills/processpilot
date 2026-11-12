"""Stage 5 probe: find which RobotLogs query returns the bot's log lines."""
from processpilot.tools.uipath_client import _call


def show(label: str, params: dict) -> None:
    try:
        rows = _call("GET", "odata/RobotLogs", params=params).get("value", [])
        print(f"{label}: {len(rows)} rows")
        for r in rows[:3]:
            print("   ", r.get("TimeStamp"), r.get("Level"), str(r.get("Message"))[:100])
    except Exception as e:
        print(f"{label}: ERROR {str(e)[:200]}")


show("newest 5, no filter", {"$top": 5, "$orderby": "TimeStamp desc"})
show("Message contains INV-204", {"$filter": "contains(Message,'INV-204')", "$top": 5, "$orderby": "TimeStamp desc"})
show("Message contains [PP]", {"$filter": "contains(Message,'[PP]')", "$top": 5, "$orderby": "TimeStamp desc"})
show("Level is Error", {"$filter": "Level eq 'Error'", "$top": 5, "$orderby": "TimeStamp desc"})
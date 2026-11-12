"""Collects the evidence the exception agent reasons over: queue item outcome plus robot log lines."""
from dataclasses import dataclass, field

from processpilot.tools.uipath_client import get_job_logs, get_queue_item_status


@dataclass
class FailureReport:
    invoice_id: str
    queue_item_id: int
    status: str
    exc_type: str | None
    reason: str | None
    attempts: int = 0                      # retries already made by the agent
    logs: list[str] = field(default_factory=list)


def gather(invoice_id: str, queue_item_id: int, attempts: int = 0) -> FailureReport:
    s = get_queue_item_status(queue_item_id)
    exc = s.get("exception") or {}
    try:
        logs = get_job_logs(s.get("started"), s.get("ended"))
    except Exception as e:  # logs are supporting evidence; the reason text alone can still drive the decision
        logs = [f"(robot logs unavailable: {str(e)[:120]})"]
    return FailureReport(
        invoice_id=invoice_id,
        queue_item_id=queue_item_id,
        status=s["status"],
        exc_type=exc.get("Type"),
        reason=exc.get("Reason"),
        attempts=attempts,
        logs=logs,
    )
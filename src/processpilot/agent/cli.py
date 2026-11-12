"""Two-step CLI over the service layer: `run` starts a request and pauses for approval; `approve` resumes it."""
import argparse

from processpilot import bedrock, service
from processpilot.tools.checks import ROLES


def _show(s: dict) -> None:
    if s["stage"].startswith("AWAITING"):
        p, tid = s["pending"], s["thread_id"]
        base = f"python -m processpilot.agent.cli approve {tid} --by <user> --role \"{p['required_role']}\""
        print(f"PAUSED - {p['kind']} approval needed (thread {tid})")
        print(f"  {p['invoice_id']} | {p['vendor']} | INR {p['total']:,.0f} | required: {p['required_role']}")
        print(f"  {p['summary']}")
        print(f"  approve: {base}")
        print(f"  reject : {base} --reject --reason \"...\"")
    elif s["stage"] == "COMPLETED":
        print(s["answer"])
    else:
        print(f"{s['stage']} (thread {s['thread_id']})")
    print(f"[tokens in/out={bedrock.USAGE['in']}/{bedrock.USAGE['out']}]")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("request")
    r.add_argument("--simulate", default="none", choices=service.SIMULATE)
    r.add_argument("--request-id", default=None)
    a = sub.add_parser("approve")
    a.add_argument("thread")
    a.add_argument("--by", required=True)
    a.add_argument("--role", required=True, choices=ROLES)
    a.add_argument("--reject", action="store_true")
    a.add_argument("--reason", default="")
    args = ap.parse_args()

    if args.cmd == "run":
        _show(service.start_request(args.request, args.simulate, args.request_id))
    else:
        _show(service.submit_decision(args.thread, args.by, args.role, not args.reject, args.reason))


if __name__ == "__main__":
    main()
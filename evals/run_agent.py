"""Run the deployable research agent on eval cases (multi-turn, checkpointer)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_case(case_id: str) -> dict:
    ds = json.loads((ROOT / "evals" / "dataset.json").read_text())
    for case in ds["cases"]:
        if case["id"] == case_id:
            return case
    raise SystemExit(f"unknown case: {case_id}")


def _all_case_ids() -> list[str]:
    ds = json.loads((ROOT / "evals" / "dataset.json").read_text())
    return [case["id"] for case in ds["cases"]]


def run_one(case_id: str, out_dir: Path, *, as_of: date) -> Path:
    from langgraph.checkpoint.memory import InMemorySaver

    from freight_second_brain.agent.research import (
        MAX_RECURSION,
        _message_text,
        _tool_names_from_messages,
        build_research_agent,
    )
    from freight_second_brain.config import get_settings

    case = _load_case(case_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{case_id}.json"
    settings = get_settings()
    started = datetime.now(timezone.utc).isoformat()
    checkpointer = InMemorySaver()
    agent = build_research_agent(
        settings=settings,
        checkpointer=checkpointer,
        as_of=as_of,
    )
    thread = {
        "configurable": {"thread_id": f"eval-{case_id}"},
        "recursion_limit": MAX_RECURSION,
    }
    seen = 0
    turns_out: list[dict] = []
    error: str | None = None
    try:
        for turn in case["conversation"]:
            print(f"{case_id} turn {turn['turn']} start", flush=True)
            result = agent.invoke(
                {"messages": [{"role": "user", "content": turn["user"]}]},
                config=thread,
            )
            messages = list(result.get("messages") or [])
            new = messages[seen:]
            seen = len(messages)
            answer = _message_text(messages[-1]) if messages else ""
            tools = _tool_names_from_messages(new)
            print(
                f"{case_id} turn {turn['turn']} done tools={tools} chars={len(answer)}",
                flush=True,
            )
            turns_out.append(
                {
                    "turn": turn["turn"],
                    "user": turn["user"],
                    "answer": answer,
                    "tools_used": tools,
                }
            )
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        print(f"{case_id} FAILED {error}", flush=True)

    payload = {
        "case_id": case_id,
        "candidate_id": settings.openrouter_model,
        "as_of": as_of.isoformat(),
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "ok": error is None and len(turns_out) == len(case["conversation"]),
        "error": error,
        "n_gold_turns": len(case["conversation"]),
        "turns": turns_out,
    }
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"wrote {dest} ok={payload['ok']}", flush=True)
    return dest


def _worker_cmd(case_id: str, out_dir: Path, as_of: str) -> list[str]:
    return [
        sys.executable,
        str(Path(__file__).resolve()),
        "--case",
        case_id,
        "--out-dir",
        str(out_dir),
        "--as-of",
        as_of,
    ]


def run_many(case_ids: list[str], out_dir: Path, *, as_of: date, workers: int, force: bool) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    pending = []
    for case_id in case_ids:
        dest = out_dir / f"{case_id}.json"
        if dest.exists() and not force:
            try:
                existing = json.loads(dest.read_text())
            except json.JSONDecodeError:
                existing = {}
            if existing.get("ok"):
                print(f"skip {case_id} (already ok)", flush=True)
                continue
        pending.append(case_id)

    if not pending:
        print("nothing to run", flush=True)
        return 0

    as_of_s = as_of.isoformat()
    procs: list[subprocess.Popen] = []
    queue = list(pending)
    failures = 0
    while queue or procs:
        while queue and len(procs) < workers:
            case_id = queue.pop(0)
            print(f"spawn {case_id}", flush=True)
            proc = subprocess.Popen(_worker_cmd(case_id, out_dir, as_of_s))
            procs.append(proc)
        still: list[subprocess.Popen] = []
        for proc in procs:
            code = proc.poll()
            if code is None:
                still.append(proc)
            elif code != 0:
                failures += 1
        procs = still
        if procs:
            procs[0].wait()
            code = procs[0].poll()
            if code not in (0, None):
                failures += 1
            procs = procs[1:]
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--as-of", default="2026-09-09")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    as_of = date.fromisoformat(args.as_of)
    out_dir = args.out_dir if args.out_dir.is_absolute() else (ROOT / args.out_dir)

    if args.case:
        dest = run_one(args.case, out_dir, as_of=as_of)
        payload = json.loads(dest.read_text())
        sys.exit(0 if payload.get("ok") else 1)

    if not args.all:
        parser.error("pass --case ID or --all")
    ids = _all_case_ids()
    failures = run_many(ids, out_dir, as_of=as_of, workers=args.workers, force=args.force)
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run the frozen Plainwise A/B/C benchmark with Codex CLI.

No model is called in --dry-run mode. Outputs are saved with condition labels
for later blinded presentation. Run with a connected, authenticated Codex CLI.

Optional Windows setup:
  set PLAINWISE_CODEX_CMD_JSON=["C:\\path\\to\\node.exe","C:\\path\\to\\codex.js"]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

COMMON = (
    "日本語のですます調で、初めて聞く人にも納得できる説明をしてください。"
    "150〜350字程度。未確認の事実を捏造せず、外部ツールを使わず回答してください。"
)
GENERIC = (
    "聞き手が思わず『なるほど！』と思える説明にしてください。"
    "単なる理由の羅列を避け、主張の盲点や混同を一つ見つけ、"
    "身近な一問や意外でも正確な対比を示して、"
    "最後に別の場面でも使える判断基準を残してください。"
    "標準語で自然に語りかけ、架空の常識や無理な逆説を作らないでください。"
)
CONDITIONS = ("baseline", "strong_general_instruction", "plainwise_candidate")


def cli_prefix() -> list[str]:
    raw = os.environ.get("PLAINWISE_CODEX_CMD_JSON")
    if raw:
        prefix = json.loads(raw)
        if not isinstance(prefix, list) or not prefix or not all(isinstance(x, str) and x for x in prefix):
            raise ValueError("PLAINWISE_CODEX_CMD_JSON must be an argv JSON array.")
        return prefix
    return ["codex"]


def build_prompt(condition: str, question: str, skill: str) -> str:
    common = COMMON + "\n\n質問：" + question
    if condition == "baseline":
        return common
    if condition == "strong_general_instruction":
        return GENERIC + "\n\n" + common
    if condition == "plainwise_candidate":
        return (
            "次のAgent Skillの指示を適用し、スキル名や手順には触れず、"
            "回答本文だけを書いてください。\n\n"
            + skill + "\n\n" + common
        )
    raise ValueError("Unknown condition: " + condition)


def run_codex(command: list[str], prompt: str, timeout_seconds: int) -> dict:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command + [prompt],
            text=True, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout_seconds, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"exit_code": -1, "answer": "", "error": repr(exc),
                "seconds": round(time.monotonic() - started, 2)}
    events = []
    for line in proc.stdout.splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    messages = [
        event["item"].get("text", "")
        for event in events
        if event.get("type") == "item.completed"
        and event.get("item", {}).get("type") == "agent_message"
    ]
    tools = [
        event.get("item", {}).get("type")
        for event in events
        if event.get("type") in ("item.started", "item.completed")
        and event.get("item", {}).get("type") not in ("agent_message", "reasoning")
    ]
    errors = [event for event in events if event.get("type") in ("error", "turn.failed")]
    return {
        "exit_code": proc.returncode,
        "answer": messages[-1] if messages else "",
        "characters": len(messages[-1]) if messages else 0,
        "tool_events": tools,
        "seconds": round(time.monotonic() - started, 2),
        "error": str(errors)[:600] if errors else (proc.stderr[-600:] if proc.returncode else ""),
    }


def save_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill", type=Path, default=Path("SKILL.md"))
    parser.add_argument("--cases", type=Path, default=Path("evaluation/aha_holdout_v1.json"))
    parser.add_argument("--out", type=Path, default=Path("evaluation/results/aha_v1_raw.json"))
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=150)
    parser.add_argument("--seed", type=int, default=20261111)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.repetitions < 1:
        parser.error("--repetitions must be >= 1")
    skill = args.skill.read_text(encoding="utf-8")
    benchmark = json.loads(args.cases.read_text(encoding="utf-8"))
    questions = benchmark["cases"]
    fingerprints = {
        "skill_sha256": hashlib.sha256(skill.encode("utf-8")).hexdigest(),
        "cases_sha256": hashlib.sha256(args.cases.read_bytes()).hexdigest(),
        "generic_sha256": hashlib.sha256(GENERIC.encode("utf-8")).hexdigest(),
        "common_sha256": hashlib.sha256(COMMON.encode("utf-8")).hexdigest(),
    }
    if len({x["id"] for x in questions}) != len(questions):
        raise ValueError("Duplicate question IDs")
    planned = [(q, rep, condition)
               for q in questions
               for rep in range(1, args.repetitions + 1)
               for condition in CONDITIONS]
    random.Random(args.seed).shuffle(planned)
    print(f"{len(questions)} questions × {args.repetitions} repetitions × 3 conditions = {len(planned)} answers")
    if args.dry_run:
        print("Model:", args.model, "Effort:", args.reasoning_effort)
        print("CLI prefix:", json.dumps(cli_prefix(), ensure_ascii=False))
        print("Planned first five:", [(q["id"], rep, condition) for q, rep, condition in planned[:5]])
        return

    if args.out.exists():
        output = json.loads(args.out.read_text(encoding="utf-8"))
        meta = output.get("meta", {})
        expected = {"model": args.model, "effort": args.reasoning_effort,
                    "seed": args.seed, "skill": str(args.skill),
                    "repetitions": args.repetitions, **fingerprints}
        if any(meta.get(key) != value for key, value in expected.items()):
            raise ValueError("Existing results are from different settings; choose another output path.")
    else:
        output = {
            "meta": {"model": args.model, "effort": args.reasoning_effort,
                     "seed": args.seed, "skill": str(args.skill),
                     "repetitions": args.repetitions, **fingerprints,
                     "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                     "note": "Generated responses only; not a human comprehension study."},
            "responses": [],
        }
    prefix = cli_prefix()
    command = prefix + [
        "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
        "--skip-git-repo-check", "--sandbox", "read-only",
        "--model", args.model, "-c",
        f'model_reasoning_effort="{args.reasoning_effort}"', "--json"
    ]
    for q, rep, condition in planned:
        if any(x["id"] == q["id"] and x["repetition"] == rep
               and x["condition"] == condition for x in output["responses"]):
            continue
        response = run_codex(command, build_prompt(condition, q["question"], skill),
                             args.timeout_seconds)
        output["responses"].append({
            "id": q["id"], "repetition": rep, "condition": condition,
            "question": q["question"], "accuracy_guard": q["accuracy_guard"],
            **response
        })
        save_atomic(args.out, output)
        print(f"{q['id']} repetition {rep} {condition}: "
              f"exit={response['exit_code']} chars={response.get('characters', 0)}", flush=True)
        if response["exit_code"] != 0 or not response["answer"] or response["tool_events"]:
            print("ERROR: execution failed or tool was invoked; inspect output.", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()

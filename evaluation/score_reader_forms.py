#!/usr/bin/env python3
"""Summarize blinded reader ratings; never imply that AI grading equals human evidence."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

CONDITIONS = ("baseline", "strong_general_instruction", "plainwise_candidate")
CHOICES = ("A", "B", "tie", "neither")
YES = {"yes", "true", "1", "y", "あり"}


def parse_score(value: str, field: str) -> int:
    if value.strip() not in {"0", "1", "2", "3", "4"}:
        raise ValueError(f"{field}: expected score 0..4, got {value!r}")
    return int(value)


def read_reviews(answer_key: dict, paths: list[Path]) -> list[dict]:
    lookup = {(x["form_id"], x["id"], str(x["repetition"])): x
              for x in answer_key["key"]}
    if len(lookup) != len(answer_key["key"]):
        raise ValueError("Duplicate answer key entries")
    records: list[dict] = []
    for path in paths:
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if not set(("form_id", "id", "repetition", "choice",
                        "aha_A", "aha_B", "factual_error_A",
                        "factual_error_B", "insight")).issubset(reader.fieldnames or ()):
                raise ValueError(f"{path}: missing required columns")
            seen = set()
            for line, row in enumerate(reader, start=2):
                key = row["form_id"], row["id"], row["repetition"]
                if key not in lookup or key in seen:
                    raise ValueError(f"{path}:{line}: unknown/duplicate id {key}")
                seen.add(key)
                if not row["choice"] and not row["aha_A"] and not row["aha_B"]:
                    continue  # an unfilled response template is not an evaluation
                if row["choice"] not in CHOICES:
                    raise ValueError(f"{path}:{line}: invalid preference")
                score_a = parse_score(row["aha_A"], f"{path}:{line} aha_A")
                score_b = parse_score(row["aha_B"], f"{path}:{line} aha_B")
                labels = lookup[key]
                factual_a = (row["factual_error_A"] or "").strip().lower() in YES
                factual_b = (row["factual_error_B"] or "").strip().lower() in YES
                records.append({
                    "form_id": row["form_id"], "id": row["id"],
                    "repetition": row["repetition"],
                    "conditions": {"A": labels["A"], "B": labels["B"]},
                    "choice": row["choice"],
                    "scores": {"A": score_a, "B": score_b},
                    "factual_error": {"A": factual_a, "B": factual_b},
                    "insight": (row["insight"] or "").strip(),
                    "file": path.name,
                })
    return records


def summarize(records: list[dict]) -> dict:
    counts = {c: {"n": 0, "score_sum": 0, "factual_flags": 0} for c in CONDITIONS}
    pairs: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"n": 0, "wins": defaultdict(int), "tie": 0, "neither": 0}
    )
    for row in records:
        a, b = row["conditions"]["A"], row["conditions"]["B"]
        if a == b or a not in counts or b not in counts:
            raise ValueError("Invalid label mapping")
        for label, condition in (("A", a), ("B", b)):
            entry = counts[condition]
            entry["n"] += 1
            faulty = row["factual_error"][label]
            entry["factual_flags"] += int(faulty)
            entry["score_sum"] += 0 if faulty else row["scores"][label]
        pair = pairs[tuple(sorted((a, b)))]
        pair["n"] += 1
        choice = row["choice"]
        if choice == "tie":
            pair["tie"] += 1
        elif choice == "neither":
            pair["neither"] += 1
        else:
            chosen_condition = row["conditions"][choice]
            if row["factual_error"][choice]:
                # A compelling but factually wrong explanation is not a win.
                pair["neither"] += 1
            else:
                pair["wins"][chosen_condition] += 1
    return {
        "answered_comparisons": len(records),
        "files_received": len({r["file"] for r in records}),
        "questions_covered": len({r["id"] for r in records}),
        "scores": {
            name: {
                "n": val["n"],
                "mean_aha_with_factual_failures_as_zero": (
                    round(val["score_sum"] / val["n"], 3) if val["n"] else None
                ),
                "factual_flags": val["factual_flags"],
            } for name, val in counts.items()
        },
        "pairwise": [
            {"conditions": list(pair), "n": val["n"],
             "wins": dict(val["wins"]), "tie": val["tie"],
             "neither_or_invalid": val["neither"]}
            for pair, val in sorted(pairs.items())
        ],
        "caution": (
            "Observational descriptive data only; file count is not independent reader count. "
            "No p-value or proof of superiority, and free-text insights require manual checking."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--answer-key", type=Path,
                        default=Path("evaluation/results/reader_forms/answer-key.json"))
    parser.add_argument("--response-files", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path,
                        default=Path("evaluation/results/reader_summary.json"))
    args = parser.parse_args()
    key = json.loads(args.answer_key.read_text(encoding="utf-8"))
    records = read_reviews(key, args.response_files)
    result = summarize(records)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{result['answered_comparisons']} answered comparisons; "
          f"{result['questions_covered']} distinct questions.")
    print(json.dumps(result["pairwise"], ensure_ascii=False, indent=2))
    print("These counts cannot replace independent human validation.")


if __name__ == "__main__":
    main()

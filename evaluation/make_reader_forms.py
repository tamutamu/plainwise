#!/usr/bin/env python3
"""Create short, balanced, source-blind A/B review forms from complete model runs."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

CONDITIONS = ("baseline", "strong_general_instruction", "plainwise_candidate")
PAIRS = (
    ("baseline", "strong_general_instruction"),
    ("strong_general_instruction", "plainwise_candidate"),
    ("baseline", "plainwise_candidate"),
)


def load_groups(raw: dict) -> dict[tuple[str, int], dict[str, dict]]:
    groups: dict[tuple[str, int], dict[str, dict]] = {}
    for entry in raw["responses"]:
        key = entry["id"], entry["repetition"]
        condition = entry["condition"]
        group = groups.setdefault(key, {})
        if condition not in CONDITIONS or condition in group:
            raise ValueError(f"Unexpected or duplicate condition: {key} {condition}")
        if entry.get("exit_code") != 0 or not entry.get("answer") or entry.get("tool_events"):
            raise ValueError(f"Failed or tool-using generation: {key} {condition}")
        group[condition] = entry
    for key, group in groups.items():
        if set(group) != set(CONDITIONS):
            raise ValueError(f"Incomplete set: {key}")
        if len({x["question"] for x in group.values()}) != 1:
            raise ValueError(f"Different questions for {key}")
    return groups


def make_forms(raw: dict, forms: int, seed: int) -> tuple[list[tuple[str, str]], list[dict]]:
    if not 1 <= forms <= 3:
        raise ValueError("forms must be 1..3")
    groups = load_groups(raw)
    qids = sorted({key[0] for key in groups})
    if not qids:
        raise ValueError("No complete questions")

    results: list[tuple[str, str]] = []
    answer_key: list[dict] = []
    for form_idx in range(forms):
        form_id = f"F{form_idx + 1}"
        lines = [
            f"# Plainwise 読み比べ — {form_id}",
            "",
            "回答の出所は伏せられています。読みやすさだけでなく、",
            "説明を聞く前と後で、何の見方が変わったかを評価してください。",
            "文章の長さや比喩・疑問文の数では判断しないでください。",
            "実際に誤りがあれば、その説明には加点しないでください。",
            "",
        ]
        for index, qid in enumerate(qids):
            repetition = form_idx + 1
            group = groups.get((qid, repetition))
            if group is None:
                raise ValueError(f"Missing set: {qid} repetition {repetition}")
            pair = list(PAIRS[(index + form_idx) % len(PAIRS)])
            random.Random(f"{seed}:{form_idx}:{qid}").shuffle(pair)
            lines.extend([
                f"## {qid}（{index + 1}/{len(qids)}）",
                "",
                "**質問**：" + group[pair[0]]["question"],
                "",
                "### 回答A",
                "",
                group[pair[0]]["answer"],
                "",
                "### 回答B",
                "",
                group[pair[1]]["answer"],
                "",
                "**回答者の評価**",
                "",
                "- 新しい気づきが大きかった：A / B / 同じ / どちらもなし",
                "- 「なるほど」と感じた強さ（0＝なし〜4＝強い）：A __ / B __",
                "- 事実・計算・論理上の重大な誤り：Aあり / Bあり / なし",
                "- **何の見方が変わりましたか？ なければ「なし」**：",
                "",
                "---",
                "",
            ])
            answer_key.append({
                "form_id": form_id, "id": qid, "repetition": repetition,
                "A": pair[0], "B": pair[1]
            })
        content = "\n".join(lines)
        if any(cond in content for cond in CONDITIONS):
            raise ValueError("Answer label leaked into reviewer form")
        results.append((f"{form_id}.md", content))
    return results, answer_key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("evaluation/results/aha_v1_raw.json"))
    parser.add_argument("--out-dir", type=Path, default=Path("evaluation/results/reader_forms"))
    parser.add_argument("--forms", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261112)
    args = parser.parse_args()

    pages, answer_key = make_forms(
        json.loads(args.input.read_text(encoding="utf-8")), args.forms, args.seed
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in pages:
        (args.out_dir / filename).write_text(content, encoding="utf-8")
    (args.out_dir / "answer-key.json").write_text(
        json.dumps({"seed": args.seed, "key": answer_key}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print(f"Created {len(pages)} blind A/B forms. Keep answer-key.json separate.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Turn generated outputs into blinded A/B/C material plus a separate answer key."""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

CONDITIONS = {"baseline", "strong_general_instruction", "plainwise_candidate"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path,
                        default=Path("evaluation/results/aha_v1_raw.json"))
    parser.add_argument("--blind-output", type=Path,
                        default=Path("evaluation/results/aha_v1_blind.md"))
    parser.add_argument("--key-output", type=Path,
                        default=Path("evaluation/results/aha_v1_answer_key.json"))
    parser.add_argument("--seed", type=int, default=1701)
    args = parser.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    groups: dict[tuple[str, int], list[dict]] = {}
    for response in raw["responses"]:
        key = response["id"], response["repetition"]
        groups.setdefault(key, []).append(response)

    lines = [
        "# Plainwise：出所を伏せた説明比較",
        "",
        "**比較の目的**：理解しやすかったかだけでなく、",
        "説明の前後で何の見方が変わったか、具体的に書けるかを確かめます。",
        "",
        "回答の出所は伏せています。文章の長さ・疑問文や例えの数では評価しないでください。",
        "",
        "採点：正確性（0〜4）、予想外だが納得できた発見（0〜4）、",
        "その発見を自分の言葉で説明できるか（0〜4）、",
        "別の場面への応用可能性（0〜4）。誤りがある回答は必ず指摘します。",
        "",
    ]
    key_data = []
    for (qid, repetition), responses in sorted(groups.items()):
        if {r["condition"] for r in responses} != CONDITIONS:
            raise ValueError(f"{qid} repetition {repetition}: incomplete comparison")
        if any(r["exit_code"] != 0 or not r["answer"] or r.get("tool_events")
               for r in responses):
            raise ValueError(f"{qid} repetition {repetition}: failed/tool-using response")

        # Shuffle independently for each comparison, never sort by condition name.
        rng = random.Random(f"{args.seed}:{qid}:{repetition}")
        ordered = list(responses)
        rng.shuffle(ordered)
        lines.extend([
            f"## {qid} — 実行 {repetition}",
            "",
            f"**質問**：{ordered[0]['question']}",
            ""
        ])
        mapping = {}
        for label, response in zip("ABC", ordered):
            mapping[label] = response["condition"]
            lines.extend([f"### 回答 {label}", "", response["answer"], ""])
        lines.extend([
            "**評価欄**",
            "",
            "| 評価観点 | A | B | C |",
            "| --- | --- | --- | --- |",
            "| 正確性（0–4） | | | |",
            "| 新しい気づき（0–4） | | | |",
            "| 自分の言葉で説明できた（0–4） | | | |",
            "| 別の場面へ応用できる（0–4） | | | |",
            "",
            "どの前提・物差しが変わりましたか？（変わらなければ「なし」）",
            "",
            "**評価者の記述**：",
            "",
            "誤り・飛躍はありましたか？",
            "",
            "**指摘**：",
            "",
        ])
        key_data.append({"id": qid, "repetition": repetition, "labels": mapping})

    args.blind_output.parent.mkdir(parents=True, exist_ok=True)
    args.key_output.parent.mkdir(parents=True, exist_ok=True)
    args.blind_output.write_text("\n".join(lines), encoding="utf-8")
    args.key_output.write_text(
        json.dumps({"seed": args.seed, "key": key_data}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )
    print(f"{len(key_data)} completed comparisons written.")
    print("Keep the answer key separate from the evaluation forms.")


if __name__ == "__main__":
    main()

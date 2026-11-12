#!/usr/bin/env python3
"""Tests for source-blind human A/B comparison aggregation."""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from evaluation import make_reader_forms as forms
from evaluation import score_reader_forms as score


def synthetic():
    responses = []
    for q in ("Q01", "Q02", "Q03"):
        for rep in (1, 2, 3):
            for cond in forms.CONDITIONS:
                responses.append({
                    "id": q, "repetition": rep, "condition": cond,
                    "question": "質問" + q, "answer": "説明" + q,
                    "exit_code": 0, "tool_events": []
                })
    return {"responses": responses}


class ScoreFormsTests(unittest.TestCase):
    def test_blind_result_scoring(self):
        pages, mapping = forms.make_forms(synthetic(), 3, 8)
        self.assertEqual(len(pages), 3)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            completed_files = []
            for form_id in ("F1", "F2", "F3"):
                path = root / (form_id + ".csv")
                with path.open("w", encoding="utf-8", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=[
                        "form_id", "id", "repetition", "choice", "aha_A", "aha_B",
                        "factual_error_A", "factual_error_B", "insight"
                    ])
                    writer.writeheader()
                    for key in mapping:
                        if key["form_id"] != form_id:
                            continue
                        a, b = key["A"], key["B"]
                        scores = {"plainwise_candidate": "4",
                                  "strong_general_instruction": "1", "baseline": "2"}
                        winner = "A" if a == "plainwise_candidate" else (
                            "B" if b == "plainwise_candidate" else "A"
                        )
                        writer.writerow({
                            "form_id": form_id, "id": key["id"], "repetition": key["repetition"],
                            "choice": winner, "aha_A": scores[a], "aha_B": scores[b],
                            "factual_error_A": "0", "factual_error_B": "0",
                            "insight": "見るべき指標が変わった"
                        })
                completed_files.append(path)

            rows = score.read_reviews({"key": mapping}, completed_files)
            self.assertEqual(len(rows), 9)
            summary = score.summarize(rows)
            self.assertEqual(summary["answered_comparisons"], 9)
            self.assertEqual(summary["files_received"], 3)
            self.assertEqual(summary["questions_covered"], 3)
            self.assertEqual(
                summary["scores"]["plainwise_candidate"]["mean_aha_with_factual_failures_as_zero"], 4
            )
            self.assertEqual(len(summary["pairwise"]), 3)
            cand_pairs = [x for x in summary["pairwise"] if "plainwise_candidate" in x["conditions"]]
            self.assertTrue(all(x["wins"].get("plainwise_candidate") == 3 for x in cand_pairs))

    def test_factual_failure_cannot_count_as_win(self):
        row = {
            "id": "Q01", "file": "form.csv",
            "conditions": {"A": "plainwise_candidate", "B": "baseline"},
            "scores": {"A": 4, "B": 2},
            "factual_error": {"A": True, "B": False},
            "choice": "A",
        }
        report = score.summarize([row])
        self.assertEqual(report["scores"]["plainwise_candidate"]["factual_flags"], 1)
        self.assertEqual(report["scores"]["plainwise_candidate"]["mean_aha_with_factual_failures_as_zero"], 0)
        self.assertEqual(report["pairwise"][0]["neither_or_invalid"], 1)

    def test_invalid_values_rejected(self):
        self.assertEqual(score.parse_score("0", "score"), 0)
        self.assertEqual(score.parse_score("4", "score"), 4)
        for value in ("", "-1", "5", "abc", "2.5"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    score.parse_score(value, "score")

    def test_empty_sheet_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "F1.csv"
            with path.open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=[
                    "form_id", "id", "repetition", "choice", "aha_A", "aha_B",
                    "factual_error_A", "factual_error_B", "insight"
                ])
                writer.writeheader()
                writer.writerow({"form_id": "F1", "id": "Q01", "repetition": 1})
            key = {"key": [{"form_id": "F1", "id": "Q01", "repetition": 1,
                            "A": "plainwise_candidate", "B": "baseline"}]}
            self.assertEqual(score.read_reviews(key, [path]), [])


if __name__ == "__main__":
    unittest.main()

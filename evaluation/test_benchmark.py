#!/usr/bin/env python3
"""Offline unit tests for benchmark and blind-review tooling (no LLM/API access)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluation import make_blind_review as blind
from evaluation import run_aha_benchmark as benchmark


class FakeProc:
    returncode = 0
    stderr = ""
    stdout = (
        json.dumps({"type": "item.completed", "item": {
            "type": "agent_message", "text": "正しい説明です。"
        }}, ensure_ascii=False) + "\n"
    )


class BenchmarkTests(unittest.TestCase):
    def test_prompt_conditions_are_distinct(self):
        q, skill = "なぜそうなる？", "SECRET-SKILL-ONLY"
        baseline = benchmark.build_prompt("baseline", q, skill)
        general = benchmark.build_prompt("strong_general_instruction", q, skill)
        with_skill = benchmark.build_prompt("plainwise_candidate", q, skill)
        self.assertIn(q, baseline)
        self.assertNotIn("SECRET-SKILL-ONLY", baseline)
        self.assertNotIn("SECRET-SKILL-ONLY", general)
        self.assertIn("SECRET-SKILL-ONLY", with_skill)
        self.assertNotEqual(baseline, general)

    def test_codex_event_parsing_and_tool_detection(self):
        with patch.object(benchmark.subprocess, "run", return_value=FakeProc()):
            result = benchmark.run_codex(["codex", "exec"], "質問", 30)
        self.assertEqual(result["exit_code"], 0)
        self.assertEqual(result["answer"], "正しい説明です。")
        self.assertEqual(result["tool_events"], [])

        with_tool = FakeProc()
        with_tool.stdout += json.dumps({
            "type": "item.started", "item": {"type": "command_execution"}
        }) + "\n"
        with patch.object(benchmark.subprocess, "run", return_value=with_tool):
            result = benchmark.run_codex(["codex", "exec"], "質問", 30)
        self.assertEqual(result["tool_events"], ["command_execution"])

    def test_unsupported_condition_rejected(self):
        with self.assertRaises(ValueError):
            benchmark.build_prompt("not-a-condition", "why?", "test")

    def test_end_to_end_resume_and_skill_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "SKILL.md"
            skill.write_text("original skill", encoding="utf-8")
            cases = root / "cases.json"
            cases.write_text(json.dumps({
                "cases": [{"id": "Q01", "question": "なぜ？", "accuracy_guard": "正確性"},
                          {"id": "Q02", "question": "どうして？", "accuracy_guard": "正確性"}]
            }, ensure_ascii=False), encoding="utf-8")
            output = root / "out.json"
            args = [
                "benchmark", "--skill", str(skill), "--cases", str(cases),
                "--out", str(output), "--repetitions", "1"
            ]
            fake_result = {
                "exit_code": 0, "answer": "なるほどという例", "characters": 9,
                "tool_events": [], "error": "", "seconds": 0.1
            }

            with patch.object(sys, "argv", args):
                with patch.object(benchmark, "run_codex", return_value=fake_result) as run:
                    benchmark.main()
                    self.assertEqual(run.call_count, 6)
            saved = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["responses"]), 6)
            self.assertIn("skill_sha256", saved["meta"])
            self.assertEqual(len({(x["id"], x["condition"]) for x in saved["responses"]}), 6)

            with patch.object(sys, "argv", args):
                with patch.object(benchmark, "run_codex") as run:
                    benchmark.main()
                    run.assert_not_called()

            skill.write_text("changed skill", encoding="utf-8")
            with patch.object(sys, "argv", args):
                with self.assertRaisesRegex(ValueError, "different settings"):
                    benchmark.main()

            # Restore the original skill so the blinded export can use the raw data.
            skill.write_text("original skill", encoding="utf-8")
            sheet = root / "blind.md"
            key = root / "key.json"
            blind_argv = [
                "blind", "--input", str(output), "--blind-output", str(sheet),
                "--key-output", str(key)
            ]
            with patch.object(sys, "argv", blind_argv):
                blind.main()
            text = sheet.read_text(encoding="utf-8")
            self.assertIn("回答 A", text)
            self.assertIn("回答 C", text)
            self.assertNotIn("plainwise_candidate", text)
            key_data = json.loads(key.read_text(encoding="utf-8"))
            self.assertEqual(len(key_data["key"]), 2)
            self.assertEqual(set(key_data["key"][0]["labels"].values()),
                             set(benchmark.CONDITIONS))

            # A failed attempt must never silently count as a completed run.
            saved["responses"][0]["exit_code"] = 1
            saved["responses"][0]["answer"] = ""
            output.write_text(json.dumps(saved, ensure_ascii=False), encoding="utf-8")
            with patch.object(sys, "argv", args):
                with self.assertRaisesRegex(RuntimeError, "Failed result recorded"):
                    benchmark.main()

            with patch.object(sys, "argv", args + ["--retry-failures"]):
                with patch.object(benchmark, "run_codex", return_value=fake_result) as run:
                    benchmark.main()
                    run.assert_called_once()
            reloaded = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(len(reloaded["responses"]), 6)
            self.assertEqual(len(reloaded["failure_history"]), 1)
            self.assertEqual(reloaded["failure_history"][0]["exit_code"], 1)
            self.assertTrue(all(x["exit_code"] == 0 for x in reloaded["responses"]))


if __name__ == "__main__":
    unittest.main()

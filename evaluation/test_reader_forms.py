#!/usr/bin/env python3
"""Offline tests for balanced, blinded human reader comparison forms."""
import unittest

from evaluation import make_reader_forms as forms


def fake_raw(question_count=6, repetitions=3):
    responses = []
    for idx in range(question_count):
        qid = f"Q{idx+1:02}"
        for rep in range(1, repetitions+1):
            for cond in forms.CONDITIONS:
                responses.append({
                    "id": qid, "repetition": rep, "condition": cond,
                    "question": f"質問 {qid}",
                    "answer": f"{qid} 回答{rep} " + {"baseline":"青","strong_general_instruction":"赤","plainwise_candidate":"緑"}[cond],
                    "exit_code": 0, "tool_events": []
                })
    return {"responses": responses}


class ReaderFormsTests(unittest.TestCase):
    def test_blinding_and_pair_coverage(self):
        pages, answer_key = forms.make_forms(fake_raw(), 3, 123)
        self.assertEqual(len(pages), 3)
        self.assertEqual(len(answer_key), 18)
        self.assertEqual({x["form_id"] for x in answer_key}, {"F1", "F2", "F3"})
        for filename, content in pages:
            self.assertIn("何の見方が変わりましたか", content)
            self.assertEqual(content.count("### 回答A"), 6)
            self.assertEqual(content.count("### 回答B"), 6)
            self.assertNotIn("plainwise_candidate", content)
            self.assertNotIn("strong_general_instruction", content)
            self.assertNotIn("baseline", content)
            self.assertTrue(filename.endswith(".md"))
        for idx in range(6):
            qid = f"Q{idx+1:02}"
            pairs = [frozenset((x["A"], x["B"])) for x in answer_key if x["id"] == qid]
            self.assertEqual(set(pairs), {frozenset(x) for x in forms.PAIRS})

    def test_deterministic_and_order_variable(self):
        a = forms.make_forms(fake_raw(), 3, 42)
        b = forms.make_forms(fake_raw(), 3, 42)
        self.assertEqual(a, b)
        c = forms.make_forms(fake_raw(), 3, 567)
        self.assertNotEqual(a[1], c[1])

    def test_missing_or_duplicate_rejected(self):
        raw = fake_raw(1)
        raw["responses"].pop()
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            forms.make_forms(raw, 3, 42)

        raw = fake_raw(1)
        raw["responses"].append(raw["responses"][0])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            forms.make_forms(raw, 3, 42)

    def test_failed_generation_rejected(self):
        raw = fake_raw(1)
        raw["responses"][0]["exit_code"] = 1
        with self.assertRaisesRegex(ValueError, "Failed"):
            forms.make_forms(raw, 1, 42)

    def test_missing_repetition_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing set"):
            forms.make_forms(fake_raw(2, 1), 2, 99)

    def test_invalid_forms_rejected(self):
        for n in (0, 4):
            with self.subTest(n=n):
                with self.assertRaisesRegex(ValueError, "forms"):
                    forms.make_forms(fake_raw(), n, 0)


if __name__ == "__main__":
    unittest.main()

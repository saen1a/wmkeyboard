#!/usr/bin/env python3
"""Offline tests for the Together collector plumbing.

    python3 wmk-glide/cloud/together/tests/test_together.py

No network: the HTTP hop is replaced by a fake transport, so every check here
runs in the audit container. The live API is exercised by `probe.py`.
"""
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import client as tg  # noqa: E402
import together_common as tc  # noqa: E402

LP = math.log


def payload_for(prompts, alts=None, drop_choice=False):
    """A well-formed echo response for `prompts` (one choice each)."""
    choices = []
    for i, p in enumerate(prompts):
        toks = [" " + w for w in p.split()]
        toks[0] = toks[0].lstrip()
        logs = [None] + [LP(0.5)] * (len(toks) - 1)
        tops = [{}] + [{" x": LP(0.25)} for _ in range(len(toks) - 1)]
        if alts is not None:
            tops = alts
        choices.append({
            "index": i,
            "text": p,
            "logprobs": {"tokens": toks, "token_logprobs": logs, "top_logprobs": tops},
        })
    if drop_choice and choices:
        choices = choices[:-1]
    return {"choices": choices,
            "usage": {"prompt_tokens": 7 * len(choices), "completion_tokens": len(choices)}}


class FakeTransport:
    def __init__(self, fail_times=0, status=503, alts=None, drop_choice=False):
        self.calls = []
        self.fail_times = fail_times
        self.status = status
        self.alts = alts
        self.drop_choice = drop_choice

    def __call__(self, body):
        self.calls.append(body)
        if self.fail_times:
            self.fail_times -= 1
            raise tg.TogetherError("HTTP 503: overloaded", self.status)
        prompts = body["prompt"]
        if isinstance(prompts, str):
            prompts = [prompts]
        return payload_for(prompts, alts=self.alts, drop_choice=self.drop_choice)


def make_client(transport, **kw):
    kw.setdefault("key", "test-key")
    kw.setdefault("backoff", 0.0)
    return tg.Client(transport=transport, stats={"requests": 0, "prompts": 0,
                                                 "prompt_tokens": 0, "completion_tokens": 0,
                                                 "retried": 0, "chunks": 0}, **kw)


class ClientTest(unittest.TestCase):
    def test_batches_and_keeps_order(self):
        t = FakeTransport()
        c = make_client(t, batch=2)
        out = c.score(["a b", "c d", "e f", "g h", "i j"])
        self.assertEqual(len(out), 5)
        self.assertEqual([len(call["prompt"]) for call in t.calls], [2, 2, 1])
        self.assertEqual([o.tokens[0] for o in out], ["a", "c", "e", "g", "i"])
        self.assertEqual(c.stats["chunks"], 3)
        self.assertEqual(c.stats["prompts"], 5)
        self.assertEqual(t.calls[0]["model"], tg.DEFAULT_MODEL)
        self.assertEqual(t.calls[0]["logprobs"], tg.MAX_LOGPROBS)
        self.assertEqual(t.calls[0]["max_tokens"], 1)
        self.assertEqual(t.calls[0]["temperature"], 0)
        self.assertIs(t.calls[0]["echo"], True)

    def test_choice_count_mismatch_is_fatal(self):
        c = make_client(FakeTransport(drop_choice=True), batch=4)
        with self.assertRaises(tg.TogetherError):
            c.score(["a b", "c d"])

    def test_retries_transient_then_succeeds(self):
        t = FakeTransport(fail_times=2)
        c = make_client(t, retries=3)
        out = c.score(["a b"])
        self.assertEqual(len(out), 1)
        self.assertEqual(c.stats["retried"], 2)
        self.assertEqual(len(t.calls), 3)

    def test_gives_up_after_retries(self):
        c = make_client(FakeTransport(fail_times=10), retries=2)
        with self.assertRaises(tg.TogetherError):
            c.score(["a b"])

    def test_permanent_error_is_not_retried(self):
        def bad(body):
            raise tg.TogetherError("HTTP 400: bad", 400)
        c = make_client(bad, retries=3)
        with self.assertRaises(tg.TogetherError):
            c.score(["a b"])
        self.assertEqual(c.stats["retried"], 0)

    def test_logprobs_cap_enforced(self):
        with self.assertRaises(tg.TogetherError):
            make_client(FakeTransport(), logprobs=6)
        with self.assertRaises(tg.TogetherError):
            make_client(FakeTransport(), logprobs=-1)

    def test_missing_legacy_logprobs_is_fatal(self):
        def chat_shape(body):
            return {"choices": [{"index": 0, "message": {"content": "x"}}],
                    "usage": {"prompt_tokens": 3}}
        c = make_client(chat_shape)
        with self.assertRaises(tg.TogetherError):
            c.score(["a b"])

    def test_cost_accounting(self):
        c = make_client(FakeTransport(), batch=8)
        c.score(["a b", "c d"])
        # usage reports 7 prompt tokens per choice in the fake payload
        self.assertEqual(c.stats["prompt_tokens"], 14)
        self.assertAlmostEqual(c.cost_usd(0.17, 0.25),
                               (14 * 0.17 + 2 * 0.25) / 1e6, places=12)


class TargetsTest(unittest.TestCase):
    def setUp(self):
        self.tokens = [" ich", " will", " hause"]
        self.word_ends = [4, 9, 15]
        self.logs = [None, LP(0.50), LP(0.10)]
        self.alts = [{}, {" ich": LP(0.02)}, {" will": LP(0.30), " fahren": LP(0.05)}]
        self.by_first = tc._mapping_from({10: [" ich"], 11: [" will"],
                                          12: [" hause"], 13: [" fahren"]})

    def rows(self, **kw):
        kw.setdefault("topk", 4)
        return tc.rows_from_sentence(self.tokens, self.logs, self.alts, 3,
                                     self.word_ends, self.by_first, **kw)

    def test_row_zero_is_empty_and_rows_are_renormalised(self):
        ids, probs, mass, _, _, st = self.rows(actual=[-1, -1, 12])
        self.assertEqual(float(probs[0].sum()), 0.0)
        for r in range(len(probs)):
            s = float(probs[r].sum())
            self.assertTrue(s == 0.0 or abs(s - 1.0) < 2e-3, (r, s))
        self.assertEqual(st["filled"], 2)

    def test_mass_is_the_pre_renormalisation_total(self):
        _, _, mass, _, _, _ = self.rows(actual=[-1, -1, 12])
        self.assertAlmostEqual(float(mass[1]), 0.52, places=4)
        self.assertAlmostEqual(float(mass[2]), 0.45, places=4)
        # mass is the retained teacher probability, i.e. 1 - residual
        self.assertTrue(0.0 <= float(mass[2]) <= 1.0)

    def test_rank_comes_from_logprob_not_dict_order(self):
        alts = [{}, {" ich": LP(0.60), " will": LP(0.40)}, {" will": LP(0.30)}]
        ids, probs, _, _, _, _ = tc.rows_from_sentence(
            self.tokens, self.logs, alts, 3, self.word_ends, self.by_first,
            topk=4, actual=[-1, -1, 12])
        # row 1: candidates {ich: .60, will: .50 (actual)} -> ich wins
        self.assertEqual(int(ids[1, 0]), 10, ids[1])
        self.assertGreater(float(probs[1, 0]), float(probs[1, 1]))

    def test_padding_ids_are_non_negative(self):
        ids, _, _, _, _, _ = self.rows(actual=[-1, -1, 12])
        self.assertGreaterEqual(int(ids.min()), 0)

    def test_actual_probability_is_exact(self):
        _, _, _, act, ap, _ = self.rows(actual=[-1, -1, 12])
        self.assertEqual(int(act[2]), 12)
        self.assertAlmostEqual(float(ap[2]), 0.10, places=5)

    def test_injection_when_mapping_disagrees_with_stream(self):
        by_first = tc._mapping_from({11: [" will"], 12: [" haus", "e"]})
        ids, _, mass, _, _, st = tc.rows_from_sentence(
            self.tokens, self.logs, self.alts, 3, self.word_ends, by_first,
            topk=4, actual=[-1, -1, 12])
        self.assertEqual(st["injected"], 1, st)
        self.assertIn(12, ids[2].tolist())
        self.assertAlmostEqual(float(mass[2]), 0.40, places=4)

    def test_unaligned_word_leaves_row_empty(self):
        _, probs, _, _, _, st = tc.rows_from_sentence(
            self.tokens, self.logs, self.alts, 3, [4, 10, 15], self.by_first,
            topk=4, actual=None)
        self.assertEqual(float(probs[2].sum()), 0.0)
        self.assertGreaterEqual(st["skipped"], 1)

    def test_generated_token_is_ignored(self):
        # extend the stream with a generated token past prompt_tokens
        tokens = self.tokens + [" früh"]
        logs = self.logs + [LP(0.01)]
        alts = self.alts + [{" q": LP(0.9)}]
        ids, probs, _, _, _, _ = tc.rows_from_sentence(
            tokens, logs, alts, 3, self.word_ends, self.by_first, topk=4,
            actual=[-1, -1, 12])
        self.assertNotIn(2, ids[2].tolist())   # nothing from position 3
        self.assertAlmostEqual(abs(float(probs[2].sum())), 1.0, places=3)

    def test_candidate_width_never_exceeds_cap(self):
        tokens = [" a", " b"]
        logs = [None, LP(0.4)]
        alts = [{}, {f" t{i}": LP(0.01 * i) for i in range(1, 40)}]
        cand = tc.candidates(tokens, logs, alts, 1)
        self.assertEqual(len(cand), 6)   # 5 returned + the actual token

    def test_token_char_ends_and_spans(self):
        self.assertEqual(tc.token_char_ends(self.tokens, 3), [4, 9, 15])
        self.assertEqual(tc.spans([4, 9, 15]), [(0, 4), (4, 9), (9, 15)])

    def test_sentence_audit_uses_argmax(self):
        a = tc.sentence_audit([" a", " b", " c"], [None, LP(0.9), LP(0.2)],
                              [{}, {" a": LP(0.05), " b": LP(0.9)}, {" z": LP(0.7)}], 3)
        self.assertAlmostEqual(a["top1"], 0.5, places=6)
        self.assertAlmostEqual(a["mean_nll"], (-LP(0.9) - LP(0.2)) / 2, places=6)

    def test_audit_sibling_roundtrip(self):
        import tempfile
        import numpy as np
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.audit.npz")
            tc.save_audit(path, [0.0, 0.5], [-1, 7], [0.0, 0.25])
            got = tc.load_audit(path)
            self.assertEqual(sorted(got), sorted(tc.AUDIT_KEYS))
            self.assertAlmostEqual(float(got["mass"][1]), 0.5, places=3)
            self.assertEqual(int(got["actual"][1]), 7)
            self.assertAlmostEqual(float(got["actual_p"][1]), 0.25, places=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

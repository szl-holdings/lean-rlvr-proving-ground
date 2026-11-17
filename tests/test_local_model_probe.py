"""Local frozen Putnam model probe synthetic tests. No external calls."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from unittest import TestCase, main, mock

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "research" / "hard_problems" / "local_model_probe.py"
sys.path.insert(0, str(FILE.parent))
spec = importlib.util.spec_from_file_location("local_model_probe", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

CASE = "putnam_2025_a1"
SOURCE = (b"import Mathlib\n/-! The problem comment: The answer is 42. -/\n"
          b"theorem putnam_2025_a1 : 2 + 2 = 4 := by sorry\n")
SOURCE_ENTRY = {
    "id": CASE, "source": "putnambench", "path": "lean4/src/" + CASE + ".lean",
    "bytes": len(SOURCE), "git_blob_sha1": module.preflight.git_blob_oid(SOURCE),
    "evaluation_only": True, "training_authority": False,
    "truth_scope": "SOLVED_COMPETITION_PROBLEM",
}
DIGEST = "a" * 64
MODEL = "test-local:fixture"


def normal_response(text="rfl", *, done=True, model=MODEL):
    return {"model": model, "done": done, "response": text,
            "prompt_eval_count": 160, "eval_count": 3, "total_duration": 2000}


class LocalProbeTests(TestCase):
    def test_prompt_strips_solution_comment_but_preserves_target(self):
        prompt, digest = module.theorem_prompt(CASE, SOURCE)
        self.assertIn("theorem putnam_2025_a1 : 2 + 2 = 4", prompt)
        self.assertIn(":= by", prompt)
        self.assertNotIn("The answer is 42", prompt)
        self.assertEqual(len(digest), 64)

    def test_prompt_rejects_prefix_solution_placeholder(self):
        source = b"import Mathlib\nabbrev answer : Nat := sorry\ntheorem " + SOURCE.split(b"theorem ")[1]
        with self.assertRaises(module.index.Hold):
            module.theorem_prompt(CASE, source)

    def test_comment_cannot_spoof_theorem(self):
        with self.assertRaises(module.index.Hold):
            module.theorem_prompt(CASE, b"/-- theorem putnam_2025_a1 : True -/\n")

    def test_explicit_abstention_not_a_proof(self):
        self.assertEqual(module.classify("-- ABSTAIN"), "ABSTAIN_RECORDED")

    def test_empty_unverified_not_success(self):
        self.assertEqual(module.classify(" "), "NO_RESPONSE")

    def test_forged_proof_is_rejected(self):
        for output in ("by sorry", "by native_decide", "axiom cheat : False",
                       "admit", "unsafe def x := 2", "run_tac x"):
            with self.subTest(output=output):
                self.assertEqual(module.classify(output),
                                 "REJECTED_UNSAFE_OR_PLACEHOLDER")

    def test_markdown_requires_review(self):
        self.assertEqual(module.classify(chr(96) * 3 + "lean\nrfl\n" + chr(96) * 3),
                         "MANUAL_EXTRACTION_REQUIRED")

    def test_plain_tactics_are_unverified(self):
        self.assertEqual(module.classify("omega"), "UNVERIFIED_PROOF_TEXT")

    def test_unbounded_response_rejected(self):
        with self.assertRaises(module.index.Hold):
            module.classify("a" * 65_537)

    def test_remote_url_and_forbidden_route_refused(self):
        with self.assertRaises(module.index.Hold):
            module.local_json("POST", "https://evil.example/upload")
        with self.assertRaises(module.index.Hold):
            module.local_json("POST", "/api/delete")

    def run_probe(self, fake_response=None, *, tags=None, digest=DIGEST):
        if fake_response is None:
            fake_response = normal_response()
        if tags is None:
            tags = lambda: {MODEL: DIGEST}
        catalog = {"entries": [SOURCE_ENTRY]}
        infer = mock.Mock(return_value=fake_response)
        with mock.patch.object(module.index, "validate") as validated:
            result = module.probe(catalog, SOURCE, CASE, MODEL, digest,
                                  infer=infer, tags=tags)
        validated.assert_called_once()
        return result, infer

    def test_pinned_local_inference_remains_unverified(self):
        result, infer = self.run_probe()
        self.assertEqual(result["classification"], "UNVERIFIED_PROOF_TEXT")
        self.assertFalse(result["verified_proof"])
        self.assertEqual(result["quality_score"], "UNAVAILABLE")
        self.assertFalse(result["model_retrained"])
        self.assertEqual(result["provider_mutation_count"], 0)
        request = infer.call_args.args
        self.assertEqual(request[0:2], ("POST", "/api/generate"))
        self.assertEqual(request[2]["options"]["temperature"], 0)
        self.assertFalse(request[2]["stream"])

    def test_inference_must_be_model_bound(self):
        with self.assertRaises(module.index.Hold):
            self.run_probe(fake_response=normal_response(model="unexpected"))

    def test_model_digest_required(self):
        with self.assertRaises(module.index.Hold):
            self.run_probe(digest="latest")

    def test_model_mutation_before_inference_blocks(self):
        with self.assertRaises(module.index.Hold):
            self.run_probe(tags=lambda: {MODEL: "b"*64})

    def test_model_mutation_after_inference_blocks(self):
        a = iter(({MODEL: DIGEST}, {MODEL: "b" * 64}))
        with self.assertRaises(module.index.Hold):
            self.run_probe(tags=lambda: next(a))

    def test_incomplete_generation_blocks(self):
        with self.assertRaises(module.index.Hold):
            self.run_probe(fake_response=normal_response(done=False))

    def test_improper_metric_blocks(self):
        value = normal_response()
        value["eval_count"] = "three"
        with self.assertRaises(module.index.Hold):
            self.run_probe(fake_response=value)

    def test_source_bytes_bound_before_generator(self):
        bad_source = SOURCE + b"\n"
        infer = mock.Mock()
        with mock.patch.object(module.index, "validate"):
            with self.assertRaises(module.index.Hold):
                module.probe({"entries": [SOURCE_ENTRY]}, bad_source, CASE,
                             MODEL, DIGEST, infer=infer,
                             tags=lambda: {MODEL: DIGEST})
        infer.assert_not_called()

    def test_preflight_plan_never_contacts_model(self):
        with mock.patch.object(module.index, "validate") as valid:
            with mock.patch.object(module, "local_json") as local:
                prepared = module.plan({"entries": [SOURCE_ENTRY]}, SOURCE,
                                       CASE, MODEL, DIGEST)
        valid.assert_called_once()
        local.assert_not_called()
        self.assertEqual(prepared["state"], "PREPARED_NOT_SENT")
        self.assertFalse(prepared["inference_attempted"])
        self.assertFalse(prepared["model_digest_live_verified"])
        self.assertEqual(prepared["quality_score"], "UNAVAILABLE")
        self.assertIn("theorem putnam_2025_a1", prepared["prompt"])

    def test_plan_invalid_digest_not_sent(self):
        with mock.patch.object(module.index, "validate"):
            with self.assertRaises(module.index.Hold):
                module.plan({"entries": [SOURCE_ENTRY]}, SOURCE, CASE,
                            MODEL, "latest")

    def test_private_output_must_be_outside_repo(self):
        with self.assertRaises(module.index.Hold):
            module.private_output(ROOT / "not-private.json")

    def test_no_trusted_lean_or_cloud_action_in_source(self):
        text = FILE.read_text(encoding="utf-8")
        for token in ("import torch", "pickle.load(", "exec(", "eval(",
                      "import subprocess", "HfApi(", "trust_remote_code=True",
                      "import referee", "chains.record(", "create_repo(", "hf_hub_download("):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    main()

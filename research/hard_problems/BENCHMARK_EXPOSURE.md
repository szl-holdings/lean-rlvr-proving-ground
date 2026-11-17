# Benchmark exposure review (metadata only)

`benchmark_exposure.py` is an offline pre-review tool, not an admission service.
It records declared answer exposure, training overlap and evaluation rights.
Unknowns, visible reference answers, known training overlap or absent reviewer
evidence hold a case out of held-out evaluation. Even a complete declaration
returns only `REVIEW_CANDIDATE_ONLY`, never evaluation/training authorization.
The tool does not inspect the referenced evidence, detect paraphrases, establish
rights, verify a reviewer or prove absence of pretraining contamination.

## Why this exists

A social screenshot can contain both a difficult mathematical task and its
reference answer. It is useful as a research lead or a rights-reviewed teaching
example, but using the exposed answer to guide a solver and reporting the result
as a fresh held-out success is invalid. A post claiming another model failed is
not a reproducible baseline. Mathematical correctness still requires a bound
statement, hypotheses, checker and independent review; SZL's advisory Lambda
score cannot turn this metadata into a proof.

Do not copy screenshots, problem statements, solutions or vendor claims into
this repository. Do not train on a benchmark merely because its card is public.
Consult and retain the exact source version and its evaluation/training terms.
No supplied screenshot or answer is included in this change. All tests are
synthetic and contain no mathematical benchmark content.

## Input

The private review JSON must contain exactly these fields:

```json
{
  "schema": "szl.benchmark-exposure-review/v1",
  "case_id": "synthetic-case",
  "source_sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "prompt_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "answer_exposure": "EXPOSED",
  "training_overlap": "UNKNOWN",
  "rights_review": "NOT_REVIEWED",
  "reviewer_evidence_sha256": null
}
```

The digests above are synthetic placeholders, not real evidence. In an actual
review, bind the exact source and proposed prompt bytes, and retain the actual
review evidence privately. `answer_exposure` is `EXPOSED`, `NOT_OBSERVED` or
`UNKNOWN`; `training_overlap` is `FOUND`, `NOT_OBSERVED` or `UNKNOWN`.
`rights_review` is `REVIEWED_FOR_EVALUATION`, `NOT_REVIEWED` or `PROHIBITED`.
`NOT_OBSERVED` never means proven absent. A reviewer digest is null when missing.

```
python research/hard_problems/benchmark_exposure.py --review PRIVATE_REVIEW.json
python -B -m unittest discover -s tests -p test_benchmark_exposure.py -v
```

Exit 2 means HOLD; exit 0 means only a review candidate. The JSON always says
`heldout_admitted=false`, `training_admitted=false`, `evidence_verified=false`,
`model_evaluation=NOT_RUN` and `mathematical_correctness=UNAVAILABLE`. The digest
binds input bytes but is not a signature. No network, model or Lean execution,
training, publication, provider mutation or integration with the admission
controller occurs. Existing Putnam source/probe/score workflows are unchanged.

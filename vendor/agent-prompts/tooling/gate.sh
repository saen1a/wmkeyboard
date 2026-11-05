#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== validate_templates"
python3 tooling/validate_templates.py
echo "== check_fragments"
python3 tooling/check_fragments.py
echo "== check_workflow_loop"
python3 tooling/check_workflow_loop.py
echo "== check_long_horizon"
python3 tooling/check_long_horizon.py
echo "== check_findings_ledger"
python3 tooling/check_findings_ledger.py exemplars/findings-ledger-example.md
for ledger in provenance/findings-*.md; do
  [ -e "$ledger" ] || continue
  python3 tooling/check_findings_ledger.py "$ledger"
done
echo "== check_optimization_failure_set"
python3 tooling/check_failure_set.py evals/optimization/failure-set.md
echo "== check_optimization_ledger"
python3 tooling/check_optimization_ledger.py evals/optimization/proposals.md
echo "== check_rebaseline"
python3 tooling/check_rebaseline.py \
  --baseline evals/optimization/baseline.json \
  --current evals/role-ab/results/wp07-conduct-guard.json
echo "== check_run_journal"
python3 tooling/check_run_journal.py exemplars/run-journal-example.jsonl
echo "== long_horizon_exercise"
python3 evals/long-horizon/drive.py --verify
echo "== check_token_efficiency"
python3 tooling/check_token_efficiency.py
echo "== check_tool_set"
python3 tooling/check_tool_set.py exemplars/tool-set-example.json
echo "== check_gate_verdict"
python3 tooling/check_gate_verdict.py exemplars/gate-verdict-example.json
for verdict in provenance/verdict-*.json; do
  [ -e "$verdict" ] || continue
  python3 tooling/check_gate_verdict.py "$verdict"
done
echo "== loop_guard_exercise"
python3 evals/loop/drive.py --verify
echo "== check_plan_spec"
python3 tooling/check_plan_spec.py exemplars/plan-spec-example.md
for plan in provenance/plan-*.md; do
  [ -e "$plan" ] || continue
  python3 tooling/check_plan_spec.py "$plan"
done
echo "== check_loop_gate"
# `plan-review-gate` predates the gate it introduced; it is grandfathered by
# name here, never by a token inside the record.
python3 tooling/check_loop_gate.py --ledger 'provenance/ledger-*.md' \
  --verdict 'provenance/verdict-*.json' --grandfather plan-review-gate 
echo "== check_admission"
python3 tooling/check_admission.py omp/admission.json
python3 tooling/check_admission.py dsh/admission.json
echo "== check_prompt_security"
python3 tooling/check_prompt_security.py
echo "== measure_state"
python3 tooling/measure_state.py --check
echo "== pytest"
python3 -m pytest tooling/tests -q
echo "== check_test_floor"
python3 tooling/check_test_floor.py
echo "== check_mandate"
python3 tooling/check_mandate.py exemplars/mandate-example.json
for record in provenance/mandate-*.json; do
  [ -e "$record" ] || continue
  python3 tooling/check_mandate.py "$record"
done
echo "== check_doc_ranges"
python3 tooling/check_doc_ranges.py
echo "== check_model_surface"
python3 tooling/check_model_surface.py
echo "== check_skill_routing"
python3 tooling/check_skill_routing.py --fail-on-warn
echo "== check_behavioral_evals"
python3 tooling/check_behavioral_evals.py
echo "== report_skill_shape"
python3 tooling/report_skill_shape.py

echo "all library gates passed"

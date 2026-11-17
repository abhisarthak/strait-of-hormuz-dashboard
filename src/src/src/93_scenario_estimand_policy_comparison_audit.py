"""
SCRIPT 93 — SCENARIO-LEVEL ESTIMAND AND POLICY COMPARISON AUDIT

Diagnostic only. Reads Script90/92 registers and creates an audit framework.
It does not execute the simulation, select estimands, approve policies, or
claim statistical significance.

Run from project root:
    python src/93_scenario_estimand_policy_comparison_audit.py
"""

from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "outputs" / "tables"
R = ROOT / "outputs" / "reports"
R.mkdir(parents=True, exist_ok=True)

FILES = {
    "scenario_policy": T / "90_scenario_policy_decision_matrix.csv",
    "policies": T / "90_recovery_policy_decision_register.csv",
    "metrics": T / "90_response_metric_decision_register.csv",
    "factors": T / "90_factor_decision_register.csv",
    "metric_status": T / "92_metric_decision_status.csv",
    "open_decisions": T / "92_open_estimand_and_censoring_decisions.csv",
}

missing = [str(v) for v in FILES.values() if not v.exists()]
if missing:
    raise FileNotFoundError(
        "Required source file(s) missing:\n" + "\n".join(missing)
    )

dfs = {k: pd.read_csv(v) for k, v in FILES.items()}

def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())

def find_col(df, candidates, required=True):
    cols = {norm(c): c for c in df.columns}
    for candidate in candidates:
        if norm(candidate) in cols:
            return cols[norm(candidate)]
    # Conservative fuzzy fallback: exact token containment only.
    for candidate in candidates:
        key = norm(candidate)
        for nk, original in cols.items():
            if key and (key in nk or nk in key):
                return original
    if required:
        raise ValueError(
            f"Could not identify required column from {candidates}. "
            f"Available columns: {list(df.columns)}"
        )
    return None

sp = dfs["scenario_policy"]
pol = dfs["policies"]
met = dfs["metrics"]
fac = dfs["factors"]
mstat = dfs["metric_status"]
open_df = dfs["open_decisions"]

scenario_col = find_col(sp, ["Scenario_ID", "Scenario"])
policy_col = find_col(sp, ["Policy_ID", "Recovery_Policy_ID", "Policy"])
policy_name_col = find_col(pol, ["Policy_ID", "Recovery_Policy_ID", "Policy"])
metric_id_col = find_col(met, ["Metric_ID"])
metric_status_id_col = find_col(mstat, ["Metric_ID"])

# Identify the decision/status columns without assuming the source uses one spelling.
def status_col(df, candidates):
    return find_col(df, candidates, required=False)

decision_col = status_col(pol, ["Researcher_Decision", "Decision_Status"])
approval_col = status_col(pol, ["Approval_Granted", "Policy_Approval"])
execution_col = status_col(pol, ["Execution_Authorized"])
supervisor_col = status_col(pol, ["Supervisor_Review_Status"])

# Build a structural scenario-policy coverage table from the supplied matrix.
coverage = (
    sp.groupby(scenario_col)[policy_col]
      .agg(Combination_Count="count",
           Distinct_Policies="nunique",
           Policy_Identifiers=lambda x: ";".join(sorted(map(str, x.unique()))))
      .reset_index()
)
policy_ids = set(pol[policy_name_col].dropna().astype(str))
matrix_policy_ids = set(sp[policy_col].dropna().astype(str))
all_scenarios = set(sp[scenario_col].dropna().astype(str))
all_pairs = sp[[scenario_col, policy_col]].drop_duplicates()
duplicate_pairs = len(sp) - len(all_pairs)

# A valid paired comparison is structurally possible only if every scenario
# includes each policy exactly once. This does not establish causal validity.
expected_pairs = len(all_scenarios) * len(policy_ids)
complete_pairs = (
    len(all_pairs) == expected_pairs
    and matrix_policy_ids == policy_ids
    and duplicate_pairs == 0
)

# Comparison plan is explicitly a proposal: each non-baseline policy vs
# the no-recovery policy, provided a single baseline can be identified.
policy_text = pol.astype(str).apply(lambda col: col.str.lower())
baseline_mask = pd.Series(False, index=pol.index)
for c in pol.columns:
    baseline_mask |= pol[c].astype(str).str.lower().str.contains(
        r"no.?recovery|baseline|without.?recovery", regex=True, na=False
    )
baseline_rows = pol.loc[baseline_mask]
baseline_id = (
    str(baseline_rows.iloc[0][policy_name_col])
    if len(baseline_rows) == 1 else None
)
comparisons = []
for pid in sorted(policy_ids):
    if pid == baseline_id:
        continue
    comparisons.append({
        "Comparison_ID": f"BASE_vs_{pid}",
        "Reference_Policy_ID": baseline_id or "NOT_IDENTIFIED",
        "Alternative_Policy_ID": pid,
        "Comparison_Status": (
            "STRUCTURALLY_SPECIFIABLE" if baseline_id else "BASELINE_NOT_UNIQUELY_IDENTIFIED"
        ),
        "Interpretation": "Conditional model-rule contrast; not an observed operational effect."
    })
comparison_df = pd.DataFrame(comparisons)

# Candidate estimand register. Formulas remain deliberately unselected until
# Script92's open metric decisions are resolved.
estimands = pd.DataFrame([
    ["E01", "Scenario-level average call arrival delay", "Scenario × policy",
     "Mean call arrival delay among eligible, observed calls at a common horizon",
     "Eligible calls; censored/unobserved calls reported separately",
     "M01", "PROPOSED_NOT_APPROVED"],
    ["E02", "Scenario-level average call departure delay", "Scenario × policy",
     "Mean call departure delay among eligible, observed calls at a common horizon",
     "Eligible calls; unfinished calls not coded as zero",
     "M02", "PROPOSED_NOT_APPROVED"],
    ["E03", "Scenario-level final vessel delay distribution", "Scenario × policy",
     "Distribution across eligible vessels of delay at each vessel's final represented call",
     "Eligible completed final calls; censored vessels reported separately",
     "M03A/M04", "PROPOSED_NOT_APPROVED"],
    ["E04", "Scenario-level accumulated vessel delay", "Scenario × policy",
     "Distribution across vessels of a separately defined accumulated-delay quantity",
     "Common eligible vessel set; accumulation operator must be specified",
     "M03B", "PROPOSED_NOT_APPROVED"],
    ["E05", "Scenario-level upper-tail call departure delay", "Scenario × policy",
     "P90 of eligible call departure delay under a specified quantile convention",
     "Eligible calls; denominator and quantile algorithm fixed in advance",
     "M05", "PROPOSED_NOT_APPROVED"],
    ["E06", "Scenario-level modelled recovery credit", "Scenario × alternative policy",
     "Matched difference against the same-scenario no-recovery counterfactual",
     "Matched scenario, vessel and call records; unmatched records disclosed",
     "M06", "PROPOSED_NOT_APPROVED"],
    ["E07", "Scenario-level unrecovered calls", "Scenario × policy",
     "Count of eligible calls exceeding a preselected residual-delay threshold at a fixed evaluation time",
     "Censored calls classified separately; threshold and time fixed in advance",
     "M07A", "PROPOSED_NOT_APPROVED"],
    ["E08", "Scenario-level unrecovered vessels", "Scenario × policy",
     "Count of eligible vessels meeting a preselected vessel-level residual-delay rule",
     "Censored vessels classified separately; aggregation rule fixed in advance",
     "M07B", "PROPOSED_NOT_APPROVED"],
], columns=[
    "Estimand_ID", "Estimand_Name", "Comparison_Unit", "Candidate_Quantity",
    "Denominator_And_Censoring", "Source_Metric_IDs", "Decision_Status"
])

# Infer no approvals from the actual decision register. Retain raw status counts.
def truth_count(series):
    return int(series.fillna(False).astype(str).str.lower().isin(["true", "1", "yes", "approved"]).sum())

checks = []
def add(name, passed, observed, expected, note):
    checks.append([name, bool(passed), str(observed), str(expected), note])

add("Scenario-policy matrix has 80 rows", len(sp) == 80, len(sp), 80,
    "Expected inventory from Script90; inspect if source register changes.")
add("Five distinct policies in policy register", pol[policy_name_col].nunique() == 5,
    pol[policy_name_col].nunique(), 5, "Expected Script90 policy inventory.")
add("Sixteen distinct scenarios", sp[scenario_col].nunique() == 16,
    sp[scenario_col].nunique(), 16, "Expected Script88/90 scenario grid.")
add("Scenario-policy pairs are unique", duplicate_pairs == 0, duplicate_pairs, 0,
    "No duplicate scenario-policy combination.")
add("Every scenario has complete policy coverage", complete_pairs,
    f"{len(all_pairs)} unique pairs; {len(all_scenarios)} scenarios; {len(policy_ids)} policies",
    expected_pairs, "Structural coverage only; not proof of valid policy implementation.")
add("Policy IDs reconcile across registers", matrix_policy_ids == policy_ids,
    sorted(matrix_policy_ids ^ policy_ids), "No differences",
    "Scenario matrix policy IDs must match policy decision register.")
add("Nine response metrics retained", len(met) == 9, len(met), 9,
    "Preserves Script90 metric inventory.")
add("Nine metric decision rows retained", len(mstat) == 9, len(mstat), 9,
    "Preserves Script92 decision inventory.")
add("Metric IDs reconcile", set(met[metric_id_col].astype(str)) ==
    set(mstat[metric_status_id_col].astype(str)),
    sorted(set(met[metric_id_col].astype(str)) ^ set(mstat[metric_status_id_col].astype(str))),
    "No differences", "Metric decision statuses must map to registered metrics.")
if decision_col:
    add("Policies remain pending", pol[decision_col].astype(str).str.upper().eq("PENDING").all(),
        pol[decision_col].value_counts(dropna=False).to_dict(), "PENDING",
        "No researcher policy selection inferred.")
if supervisor_col:
    add("Supervisor policy reviews remain pending",
        pol[supervisor_col].astype(str).str.upper().eq("PENDING").all(),
        pol[supervisor_col].value_counts(dropna=False).to_dict(), "PENDING",
        "No supervisor approval inferred.")
if approval_col:
    add("No policy approvals granted", truth_count(pol[approval_col]) == 0,
        truth_count(pol[approval_col]), 0, "Approval remains controlled by source register.")
if execution_col:
    add("No execution authorization granted", truth_count(pol[execution_col]) == 0,
        truth_count(pol[execution_col]), 0, "This audit cannot authorize execution.")
add("Script92 open decisions retained", len(open_df) == 12, len(open_df), 12,
    "All unresolved estimand/censoring decisions remain visible.")

check_df = pd.DataFrame(checks, columns=[
    "Check", "Passed", "Observed", "Expected", "Note"
])

# Save new outputs only.
out = {
    "93_scenario_policy_coverage_audit.csv": coverage,
    "93_candidate_policy_contrasts.csv": comparison_df,
    "93_candidate_estimand_register.csv": estimands,
    "93_readiness_checks.csv": check_df,
}
for name, df in out.items():
    df.to_csv(T / name, index=False)

passed = int(check_df.Passed.sum())
failed = len(check_df) - passed
report = f"""SCRIPT 93 — SCENARIO-LEVEL ESTIMAND AND POLICY COMPARISON AUDIT
{'=' * 78}

PURPOSE
Audit scenario-policy pairing and define a candidate estimand/comparison
framework using Script90 and Script92 registers. Diagnostic only.

SOURCE INVENTORY
Scenario-policy matrix rows: {len(sp)}
Distinct scenarios: {len(all_scenarios)}
Policy register rows: {len(pol)}
Distinct policies: {len(policy_ids)}
Response metric rows: {len(met)}
Metric decision rows: {len(mstat)}
Open Script92 decisions: {len(open_df)}

SCENARIO-POLICY STRUCTURE
Unique scenario-policy pairs: {len(all_pairs)}
Duplicate pairs: {duplicate_pairs}
Expected complete pairs: {expected_pairs}
Complete rectangular coverage: {'YES' if complete_pairs else 'NO'}
Policy IDs reconcile: {'YES' if matrix_policy_ids == policy_ids else 'NO'}
Uniquely identified no-recovery policy: {baseline_id or 'NO'}

CANDIDATE COMPARISON LOGIC
Each alternative recovery policy may be compared against the no-recovery
policy within the same scenario, using matched vessel/call records and the
same observation horizon. This is a conditional model-rule contrast, not a
causal estimate of real-world operational effectiveness.
A baseline comparison is only structurally identified if exactly one baseline
policy is identified from the policy register.

CANDIDATE ESTIMANDS
Eight candidate estimands are listed in 93_candidate_estimand_register.csv.
They are proposals for formalization, not selected or approved definitions.
Call-level, vessel-level, upper-tail, recovery-credit and threshold-count
quantities have distinct denominators and must not be conflated.

CENSORING / COMPARABILITY REQUIREMENTS
- Use a common observation horizon across all policies within each scenario.
- Keep the same scenario transition selection and shock realization across policies.
- Pair by stable call and vessel identifiers; disclose unmatched records.
- Do not classify unfinished calls/vessels as recovered or zero-delay.
- Report eligible and censored counts with every metric.
- Do not compare totals when policy groups have different exposure/denominator sets
  without explicit standardization or a clearly labelled descriptive interpretation.
- Do not infer statistical significance, confidence intervals or population effects
  from a deterministic single-run comparison.

READINESS CHECKS
{passed}/{len(check_df)} passed; {failed} failed.

APPROVAL STATUS
No estimand selected by this script.
No policy approved by this script.
No censoring rule approved by this script.
No simulation execution authorized.
No simulation run and no source registers modified.

INTERPRETATION
The design represents a general hypothetical inter-port elapsed-time shock
experiment. Observed elapsed time is not pure sailing time; the 10/25/50/100%
transition shares are mathematical coverage levels, not actual Hormuz exposure
probabilities. No AIS-confirmed Hormuz transit, validated route, berth capacity,
or operational recovery feasibility is established.

OUTPUTS
{chr(10).join('- outputs/tables/' + n for n in out)}
- outputs/reports/93_scenario_estimand_policy_comparison_audit_report.txt
"""
report_path = R / "93_scenario_estimand_policy_comparison_audit_report.txt"
report_path.write_text(report, encoding="utf-8")

print("SCRIPT 93 — SCENARIO-LEVEL ESTIMAND AND POLICY COMPARISON AUDIT")
print("=" * 78)
print(f"Scenario-policy rows: {len(sp)}")
print(f"Scenarios: {len(all_scenarios)}")
print(f"Policies: {len(policy_ids)}")
print(f"Unique scenario-policy pairs: {len(all_pairs)}")
print(f"Complete rectangular coverage: {complete_pairs}")
print(f"Baseline policy identified: {baseline_id or 'NO'}")
print(f"Candidate estimands: {len(estimands)}")
print(f"Readiness checks: {passed}/{len(check_df)} passed; {failed} failed")
print("Simulation executed: NO")
print("Execution authorized: NO")
print(f"Report: {report_path}")
if failed:
    raise SystemExit("Script93 audit checks failed; inspect outputs before proceeding.")

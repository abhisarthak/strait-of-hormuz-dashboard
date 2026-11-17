"""Script 35: Extended replication and paired statistical inference.

Reuses Script 33/30 vessel selection, onset selection, delay propagation,
and common-window port-call concurrency methodology. Runs 30 seeds per
scenario-policy combination and evaluates paired delay savings against
NO_RECOVERY. All recovery values remain hypothetical sensitivity assumptions.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import t as student_t, ttest_1samp

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / 'data' / 'simulation_inputs' / '19_historical_arrival_schedule.csv'
TABLE_DIR = ROOT / 'outputs' / 'tables'
REPORT_DIR = ROOT / 'outputs' / 'reports'
TABLE_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

SEEDS = list(range(1001, 1031))  # 30 independent replication seeds
SCENARIOS = {
    'S0_BASELINE': {'affected_share': 0.00, 'initial_delay_hours': 0},
    'S1_MILD': {'affected_share': 0.10, 'initial_delay_hours': 24},
    'S2_MODERATE': {'affected_share': 0.25, 'initial_delay_hours': 72},
    'S3_SEVERE': {'affected_share': 0.50, 'initial_delay_hours': 168},
}
PARTIAL_RATES = [0.10, 0.20, 0.25, 0.30, 0.40, 0.50]
FIXED_HOURS = [6, 12, 18, 24]
POLICIES = {'NO_RECOVERY': {'type': 'none', 'value': 0.0}}
for rate in PARTIAL_RATES:
    POLICIES[f'PARTIAL_RECOVERY_{int(rate * 100)}PCT'] = {'type': 'fraction', 'value': rate}
for hours in FIXED_HOURS:
    POLICIES[f'FIXED_RECOVERY_{hours}H'] = {'type': 'fixed', 'value': float(hours)}

REQUIRED = ['Simulation_Record_ID', 'IMO_Normalised', 'UNLOCODE_Normalised', 'Port',
            'Actual_Arrival_UTC', 'Actual_Departure_UTC', 'Actual_Stay_Hours']


def load_schedule():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f'Input file not found: {INPUT_FILE}')
    df = pd.read_csv(INPUT_FILE)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f'Missing required columns: {missing}')
    for col in ['Actual_Arrival_UTC', 'Actual_Departure_UTC']:
        df[col] = pd.to_datetime(df[col], utc=True, errors='coerce')
    if df[REQUIRED].isna().any().any():
        raise ValueError('Missing or invalid required input values.')
    if df.Simulation_Record_ID.duplicated().any():
        raise ValueError('Duplicate Simulation_Record_ID values found.')
    if (df.Actual_Departure_UTC <= df.Actual_Arrival_UTC).any():
        raise ValueError('Invalid port-call interval found.')
    stay = (df.Actual_Departure_UTC - df.Actual_Arrival_UTC).dt.total_seconds() / 3600
    mismatch = (stay - df.Actual_Stay_Hours).abs() > 0.01
    if mismatch.any():
        raise ValueError(f'Port-stay mismatch in {int(mismatch.sum())} records.')
    return df.sort_values(['IMO_Normalised', 'Actual_Arrival_UTC']).reset_index(drop=True)


def select_disrupted_vessels(df, scenario, seed):
    ids = sorted(df.IMO_Normalised.astype(str).unique())
    count = int(round(len(ids) * SCENARIOS[scenario]['affected_share']))
    if count == 0:
        return {}
    rng = np.random.default_rng(seed)
    selected_ids = rng.choice(ids, size=count, replace=False)
    selected = {}
    for vessel_id in selected_ids:
        calls = df[df.IMO_Normalised.astype(str) == vessel_id].sort_values('Actual_Arrival_UTC')
        onset_pos = int(rng.integers(0, len(calls)))
        selected[vessel_id] = {'onset_record_id': calls.iloc[onset_pos].Simulation_Record_ID,
                               'onset_position': onset_pos}
    return selected


def recover_delay(delay, policy):
    if delay <= 0:
        return 0.0
    if policy['type'] == 'none':
        recovered = 0.0
    elif policy['type'] == 'fraction':
        recovered = delay * policy['value']
    elif policy['type'] == 'fixed':
        recovered = min(delay, policy['value'])
    else:
        raise ValueError(f"Unknown recovery policy: {policy['type']}")
    return min(delay, recovered)


def simulate(df, scenario, policy_name, seed, selected):
    initial = float(SCENARIOS[scenario]['initial_delay_hours'])
    policy = POLICIES[policy_name]
    rows = []
    for vessel_id, calls in df.groupby('IMO_Normalised', sort=False):
        vessel_id = str(vessel_id)
        calls = calls.sort_values('Actual_Arrival_UTC').reset_index(drop=True)
        is_selected = vessel_id in selected
        onset_id = selected[vessel_id]['onset_record_id'] if is_selected else None
        carried = 0.0
        started = False
        for pos, row in calls.iterrows():
            is_onset = is_selected and row.Simulation_Record_ID == onset_id
            recovered = 0.0
            if is_onset:
                started, carried = True, initial
            elif started:
                recovered = recover_delay(carried, policy)
                carried = max(0.0, carried - recovered)
            delay = carried if started else 0.0
            rows.append({
                'Simulation_Record_ID': row.Simulation_Record_ID,
                'IMO_Normalised': vessel_id,
                'UNLOCODE_Normalised': row.UNLOCODE_Normalised,
                'Port': row.Port,
                'Scenario': scenario,
                'Recovery_Policy': policy_name,
                'Recovery_Type': policy['type'],
                'Recovery_Parameter': policy['value'],
                'Replication_Seed': seed,
                'Is_Selected_Vessel': is_selected,
                'Is_Disrupted_Call': started,
                'Is_Disruption_Onset': is_onset,
                'Onset_Record_ID': onset_id,
                'Vessel_Call_Sequence': pos + 1,
                'Initial_Disruption_Hours': initial if is_onset else 0.0,
                'Recovered_Hours_At_Transition': recovered,
                'Accumulated_Delay_Hours': delay,
                'Scenario_Arrival_UTC': row.Actual_Arrival_UTC + pd.Timedelta(hours=delay),
                'Scenario_Departure_UTC': row.Actual_Departure_UTC + pd.Timedelta(hours=delay),
                'Actual_Arrival_UTC': row.Actual_Arrival_UTC,
                'Actual_Departure_UTC': row.Actual_Departure_UTC,
            })
    return pd.DataFrame(rows)


def validate(result, source):
    if len(result) != len(source) or result.Simulation_Record_ID.duplicated().any():
        raise AssertionError('Call count or unique call-ID validation failed.')
    if (result.Scenario_Departure_UTC <= result.Scenario_Arrival_UTC).any():
        raise AssertionError('Invalid simulated call interval.')
    delay = (result.Scenario_Arrival_UTC - result.Actual_Arrival_UTC).dt.total_seconds() / 3600
    if not np.allclose(delay, result.Accumulated_Delay_Hours, atol=0.001):
        raise AssertionError('Arrival delay validation failed.')
    original = (result.Actual_Departure_UTC - result.Actual_Arrival_UTC).dt.total_seconds()
    shifted = (result.Scenario_Departure_UTC - result.Scenario_Arrival_UTC).dt.total_seconds()
    if not np.allclose(original, shifted, atol=0.001):
        raise AssertionError('Port-call duration changed.')
    if (result.Accumulated_Delay_Hours < 0).any() or (result.Recovered_Hours_At_Transition < 0).any():
        raise AssertionError('Negative delay or recovery found.')


def concurrency(port_df, start, end):
    events = []
    for r in port_df.itertuples(index=False):
        arrival, departure = max(r.Scenario_Arrival_UTC, start), min(r.Scenario_Departure_UTC, end)
        if departure > arrival:
            events.extend([(arrival, 1), (departure, -1)])
    if not events:
        return 0, 0.0, 0.0
    ev = pd.DataFrame(events, columns=['Timestamp', 'Delta'])
    ev = ev.groupby('Timestamp', as_index=False).Delta.sum().sort_values('Timestamp')
    active, peak, area, previous = 0, 0, 0.0, start
    for r in ev.itertuples(index=False):
        area += active * (r.Timestamp - previous).total_seconds() / 3600
        active += int(r.Delta)
        if active < 0:
            raise AssertionError('Negative active-call count.')
        peak, previous = max(peak, active), r.Timestamp
    area += active * (end - previous).total_seconds() / 3600
    duration = (end - start).total_seconds() / 3600
    return peak, area / duration if duration > 0 else 0.0, area


def build_port_metrics(results, start, end):
    rows = []
    keys = ['Scenario', 'Recovery_Policy', 'Replication_Seed', 'UNLOCODE_Normalised']
    for (scenario, policy, seed, port), group in results.groupby(keys):
        peak, mean, area = concurrency(group, start, end)
        rows.append({'Scenario': scenario, 'Recovery_Policy': policy, 'Replication_Seed': seed,
                     'UNLOCODE_Normalised': port, 'Port_Name': group.Port.iloc[0],
                     'Port_Calls': len(group), 'Peak_Concurrent_Calls': peak,
                     'Mean_Concurrent_Calls_Common_Window': mean,
                     'Occupancy_Area_Call_Hours': area})
    return pd.DataFrame(rows)


def build_replication_metrics(results):
    rows = []
    for (scenario, policy, seed), group in results.groupby(['Scenario', 'Recovery_Policy', 'Replication_Seed']):
        affected = group[group.Is_Disrupted_Call]
        rows.append({'Scenario': scenario, 'Recovery_Policy': policy, 'Replication_Seed': seed,
                     'Total_Vessels': group.IMO_Normalised.nunique(),
                     'Selected_Vessels': group.loc[group.Is_Selected_Vessel, 'IMO_Normalised'].nunique(),
                     'Vessels_With_Disrupted_Calls': affected.IMO_Normalised.nunique(),
                     'Total_Calls': len(group), 'Disrupted_Calls': len(affected),
                     'Disrupted_Call_Share_Percent': len(affected) / len(group) * 100,
                     'Total_Accumulated_Delay_Hours': group.Accumulated_Delay_Hours.sum(),
                     'Mean_Delay_Per_Disrupted_Call': affected.Accumulated_Delay_Hours.mean() if len(affected) else 0.0,
                     'Maximum_Accumulated_Delay_Hours': group.Accumulated_Delay_Hours.max(),
                     'Total_Recovered_Hours': group.Recovered_Hours_At_Transition.sum()})
    return pd.DataFrame(rows)


def combine_metrics(rep, ports):
    port_rep = ports.groupby(['Scenario', 'Recovery_Policy', 'Replication_Seed']).agg(
        Maximum_Port_Peak=('Peak_Concurrent_Calls', 'max'),
        Average_Port_Peak=('Peak_Concurrent_Calls', 'mean'),
        Average_Port_Concurrency=('Mean_Concurrent_Calls_Common_Window', 'mean')).reset_index()
    return rep.merge(port_rep, on=['Scenario', 'Recovery_Policy', 'Replication_Seed'], validate='one_to_one')


def build_summary(combined):
    cols = ['Selected_Vessels', 'Vessels_With_Disrupted_Calls', 'Disrupted_Calls',
            'Disrupted_Call_Share_Percent', 'Total_Accumulated_Delay_Hours',
            'Mean_Delay_Per_Disrupted_Call', 'Maximum_Accumulated_Delay_Hours',
            'Total_Recovered_Hours', 'Maximum_Port_Peak', 'Average_Port_Peak',
            'Average_Port_Concurrency']
    summary = combined.groupby(['Scenario', 'Recovery_Policy'])[cols].mean().add_prefix('Mean_').reset_index()
    counts = combined.groupby(['Scenario', 'Recovery_Policy']).size().rename('Replications').reset_index()
    return summary.merge(counts, on=['Scenario', 'Recovery_Policy'], validate='one_to_one')


def paired_comparison(combined):
    reference = combined[combined.Recovery_Policy == 'NO_RECOVERY'][
        ['Scenario', 'Replication_Seed', 'Total_Accumulated_Delay_Hours', 'Maximum_Port_Peak']
    ].rename(columns={'Total_Accumulated_Delay_Hours': 'No_Recovery_Delay_Hours',
                      'Maximum_Port_Peak': 'No_Recovery_Maximum_Port_Peak'})
    out = combined.merge(reference, on=['Scenario', 'Replication_Seed'], how='left', validate='many_to_one')
    out['Delay_Saved_Hours'] = out.No_Recovery_Delay_Hours - out.Total_Accumulated_Delay_Hours
    out['Delay_Reduction_Percent'] = np.where(
        out.No_Recovery_Delay_Hours > 0,
        out.Delay_Saved_Hours / out.No_Recovery_Delay_Hours * 100, 0.0)
    out['Maximum_Port_Peak_Change'] = out.Maximum_Port_Peak - out.No_Recovery_Maximum_Port_Peak
    return out


def build_rankings(summary):
    pieces = []
    for _, g in summary.groupby('Scenario'):
        g = g.copy()
        g['Delay_Rank'] = g.Mean_Total_Accumulated_Delay_Hours.rank(method='min')
        g['Maximum_Port_Peak_Rank'] = g.Mean_Maximum_Port_Peak.rank(method='min')
        g['Descriptive_Rank_Sum'] = g.Delay_Rank + g.Maximum_Port_Peak_Rank
        g['Descriptive_Combined_Rank'] = g.Descriptive_Rank_Sum.rank(method='min')
        d, p = g.Mean_Total_Accumulated_Delay_Hours.to_numpy(), g.Mean_Maximum_Port_Peak.to_numpy()
        efficient = []
        for i in range(len(g)):
            dominated = any(j != i and d[j] <= d[i] and p[j] <= p[i] and (d[j] < d[i] or p[j] < p[i]) for j in range(len(g)))
            efficient.append(not dominated)
        g['Pareto_Efficient'] = efficient
        pieces.append(g)
    return pd.concat(pieces, ignore_index=True)



def paired_statistical_inference(paired):
    """Paired t-inference across matched seeds; exploratory, not causal."""
    rows = []
    eligible = paired[
        (paired.Scenario != 'S0_BASELINE') &
        (paired.Recovery_Policy != 'NO_RECOVERY')
    ].copy()

    for (scenario, policy), group in eligible.groupby(['Scenario', 'Recovery_Policy']):
        for metric, values in [
            ('Delay_Saved_Hours', group.Delay_Saved_Hours.astype(float)),
            ('Delay_Reduction_Percent', group.Delay_Reduction_Percent.astype(float)),
            ('Maximum_Port_Peak_Change', group.Maximum_Port_Peak_Change.astype(float)),
        ]:
            x = values.dropna().to_numpy()
            n = len(x)
            mean = float(np.mean(x)) if n else np.nan
            sd = float(np.std(x, ddof=1)) if n > 1 else np.nan
            se = sd / np.sqrt(n) if n > 1 else np.nan
            critical = float(student_t.ppf(0.975, df=n - 1)) if n > 1 else np.nan
            margin = critical * se if n > 1 else np.nan
            test = ttest_1samp(x, popmean=0.0) if n > 1 else None
            p_value = float(test.pvalue) if test is not None else np.nan
            t_stat = float(test.statistic) if test is not None else np.nan
            cohens_dz = mean / sd if n > 1 and sd > 0 else np.nan

            rows.append({
                'Scenario': scenario,
                'Recovery_Policy': policy,
                'Metric': metric,
                'N_Paired_Seeds': n,
                'Mean_Paired_Difference': mean,
                'SD_Paired_Difference': sd,
                'CI95_Lower': mean - margin if n > 1 else np.nan,
                'CI95_Upper': mean + margin if n > 1 else np.nan,
                'T_Statistic': t_stat,
                'P_Value_Two_Sided': p_value,
                'Cohens_Dz': cohens_dz,
            })

    out = pd.DataFrame(rows)
    if not out.empty:
        out['P_Value_Below_0_05_Unadjusted'] = out.P_Value_Two_Sided < 0.05
    return out


def build_seed_level_rank_stability(combined):
    """Rank policies within each seed on delay and peak; lower rank sum is better."""
    rows = []
    for scenario in ['S1_MILD', 'S2_MODERATE', 'S3_SEVERE']:
        subset = combined[combined.Scenario == scenario]
        for seed, group in subset.groupby('Replication_Seed'):
            g = group.copy()
            g['Delay_Rank'] = g.Total_Accumulated_Delay_Hours.rank(method='min')
            g['Peak_Rank'] = g.Maximum_Port_Peak.rank(method='min')
            g['Rank_Sum'] = g.Delay_Rank + g.Peak_Rank
            for r in g.itertuples(index=False):
                rows.append({
                    'Scenario': scenario,
                    'Replication_Seed': int(seed),
                    'Recovery_Policy': r.Recovery_Policy,
                    'Delay_Rank': float(r.Delay_Rank),
                    'Peak_Rank': float(r.Peak_Rank),
                    'Rank_Sum': float(r.Rank_Sum),
                    'Accumulated_Delay_Hours': float(r.Total_Accumulated_Delay_Hours),
                    'Maximum_Port_Peak': float(r.Maximum_Port_Peak),
                })
    seed_ranks = pd.DataFrame(rows)

    stability = seed_ranks.groupby(['Scenario', 'Recovery_Policy']).agg(
        Mean_Rank_Sum=('Rank_Sum', 'mean'),
        SD_Rank_Sum=('Rank_Sum', 'std'),
        Best_Rank_Sum_Count=('Rank_Sum', lambda s: int((s == s.min()).sum())),
        N_Seeds=('Replication_Seed', 'nunique'),
    ).reset_index()

    winners = []
    for (scenario, seed), group in seed_ranks.groupby(['Scenario', 'Replication_Seed']):
        best = group.Rank_Sum.min()
        for policy in group.loc[group.Rank_Sum == best, 'Recovery_Policy']:
            winners.append({
                'Scenario': scenario,
                'Replication_Seed': int(seed),
                'Recovery_Policy': policy,
                'Joint_Winner': int((group.Rank_Sum == best).sum()) > 1,
            })
    winner_counts = pd.DataFrame(winners).groupby(
        ['Scenario', 'Recovery_Policy']
    ).size().rename('Seed_Win_Count').reset_index()
    stability = stability.merge(
        winner_counts, on=['Scenario', 'Recovery_Policy'], how='left'
    )
    stability['Seed_Win_Count'] = stability.Seed_Win_Count.fillna(0).astype(int)
    stability['Seed_Win_Percent'] = (
        stability.Seed_Win_Count / stability.N_Seeds * 100
    )
    return seed_ranks, stability, pd.DataFrame(winners)



def save_outputs(results, ports, rep, combined, summary, paired, rankings, start, end):
    outputs = {
        '35_extended_replication_call_results.csv': results,
        '35_extended_replication_port_metrics.csv': ports,
        '35_extended_replication_replication_metrics.csv': rep,
        '35_extended_replication_combined_metrics.csv': combined,
        '35_extended_replication_scenario_summary.csv': summary,
        '35_extended_replication_paired_comparison.csv': paired,
        '35_extended_replication_parameter_rankings.csv': rankings,
    }
    for name, frame in outputs.items():
        frame.to_csv(TABLE_DIR / name, index=False)
    report = REPORT_DIR / '35_extended_replication_statistical_report.txt'
    with report.open('w', encoding='utf-8') as f:
        f.write('SCRIPT 35: EXTENDED REPLICATION AND STATISTICAL INFERENCE\n' + '=' * 88 + '\n\n')
        f.write(f'Common observation window: {start} to {end}\n')
        f.write(f'Seeds: {SEEDS}\nPartial recovery rates: {PARTIAL_RATES}\nFixed recovery hours: {FIXED_HOURS}\n\n')
        f.write('SCENARIO SUMMARY\n' + '-' * 88 + '\n' + summary.to_string(index=False) + '\n\n')
        f.write('PAIRED COMPARISON AGAINST NO RECOVERY\n' + '-' * 88 + '\n')
        agg = paired.groupby(['Scenario', 'Recovery_Policy']).agg(
            Mean_Delay_Saved_Hours=('Delay_Saved_Hours', 'mean'),
            Mean_Delay_Reduction_Percent=('Delay_Reduction_Percent', 'mean'),
            Mean_Maximum_Port_Peak_Change=('Maximum_Port_Peak_Change', 'mean')).reset_index()
        f.write(agg.to_string(index=False) + '\n\n')
        f.write('PARETO AND DESCRIPTIVE RANKING\n' + '-' * 88 + '\n')
        f.write(rankings[['Scenario', 'Recovery_Policy', 'Mean_Total_Accumulated_Delay_Hours',
                          'Mean_Maximum_Port_Peak', 'Pareto_Efficient', 'Descriptive_Combined_Rank']].to_string(index=False))
        f.write('\n\nMETHODOLOGICAL LIMITATIONS\n' + '-' * 88 + '\n')
        f.write('1. Recovery fractions and fixed-hour limits are hypothetical sensitivity parameters.\n')
        f.write('2. No measured schedule slack or verified recoverable sailing buffer is available.\n')
        f.write('3. Inter-port elapsed times are not pure sailing times.\n')
        f.write('4. Sorted port-call sequences do not establish one continuous voyage.\n')
        f.write('5. No AIS-confirmed Strait of Hormuz transit is assumed.\n')
        f.write('6. Port-call concurrency is not berth occupancy, verified capacity, or a direct congestion measure.\n')
        f.write('7. Lower accumulated delay can coincide with a higher port-specific concurrency peak.\n')
        f.write('8. Rank sums are descriptive only; Pareto results are trade-off screening.\n')
    print('\nSaved tables:')
    for name in outputs:
        print(f'- outputs/tables/{name}')
    print('- outputs/reports/35_extended_replication_statistical_report.txt')


def main():
    print('=' * 88 + '\nSCRIPT 35: EXTENDED REPLICATION AND STATISTICAL INFERENCE\n' + '=' * 88)
    df = load_schedule()
    print(f'Loaded {len(df)} calls, {df.IMO_Normalised.nunique()} vessels, {df.UNLOCODE_Normalised.nunique()} ports.')

    selected_cache = {(s, seed): select_disrupted_vessels(df, s, seed)
                      for s in SCENARIOS for seed in SEEDS}
    # Baseline is a single no-recovery reference per seed; other scenarios test every policy.
    plan = [('S0_BASELINE', 'NO_RECOVERY', seed) for seed in SEEDS]
    plan += [(scenario, policy, seed)
             for scenario in ['S1_MILD', 'S2_MODERATE', 'S3_SEVERE']
             for policy in POLICIES for seed in SEEDS]
    print('Recovery parameter policies:', len(POLICIES))
    print('Total runs:', len(plan))

    replications = []
    for n, (scenario, policy, seed) in enumerate(plan, 1):
        print(f'Run {n}/{len(plan)}: {scenario} | {policy} | seed {seed}')
        result = simulate(df, scenario, policy, seed, selected_cache[(scenario, seed)])
        validate(result, df)
        replications.append(result)
    results = pd.concat(replications, ignore_index=True)

    expected = len(df) * len(plan)
    actual_runs = results[['Scenario', 'Recovery_Policy', 'Replication_Seed']].drop_duplicates().shape[0]
    if len(results) != expected or actual_runs != len(plan):
        raise AssertionError('Unexpected simulation output size or run count.')

    start = df.Actual_Arrival_UTC.min()
    end = results.Scenario_Departure_UTC.max()
    ports = build_port_metrics(results, start, end)
    rep = build_replication_metrics(results)
    combined = combine_metrics(rep, ports)
    summary = build_summary(combined)
    paired = paired_comparison(combined)
    rankings = build_rankings(summary)

    checks = {
        'Expected run count': len(combined) == len(plan),
        'No missing delays': results.Accumulated_Delay_Hours.notna().all(),
        'No negative delays': (results.Accumulated_Delay_Hours >= 0).all(),
        'No negative recovered hours': (results.Recovered_Hours_At_Transition >= 0).all(),
        'All scenarios represented': set(combined.Scenario) == set(SCENARIOS),
        'All recovery policies represented': set(POLICIES).issubset(set(combined.Recovery_Policy)),
        'No missing port peak metrics': combined.Maximum_Port_Peak.notna().all(),
        'Paired no-recovery references present': paired.No_Recovery_Delay_Hours.notna().all(),
    }
    print('\nVALIDATION')
    for name, passed in checks.items():
        print(f'{name}: {"PASS" if passed else "FAIL"}')
    if not all(checks.values()):
        raise AssertionError('One or more validation checks failed.')

    inference = paired_statistical_inference(paired)
    seed_ranks, rank_stability, seed_winners = build_seed_level_rank_stability(combined)

    save_outputs(results, ports, rep, combined, summary, paired, rankings, start, end)

    extra_tables = {
        '35_paired_statistical_inference.csv': inference,
        '35_seed_level_policy_rankings.csv': seed_ranks,
        '35_policy_rank_stability.csv': rank_stability,
        '35_seed_level_joint_winners.csv': seed_winners,
    }
    for filename, frame in extra_tables.items():
        frame.to_csv(TABLE_DIR / filename, index=False)

    report_path = REPORT_DIR / '35_extended_replication_statistical_report.txt'
    with report_path.open('w', encoding='utf-8') as f:
        f.write('SCRIPT 35: EXTENDED REPLICATION AND STATISTICAL INFERENCE\n')
        f.write('=' * 96 + '\n\n')
        f.write(f'Input calls: {len(df)}\n')
        f.write(f'Vessels: {df.IMO_Normalised.nunique()}\n')
        f.write(f'Ports: {df.UNLOCODE_Normalised.nunique()}\n')
        f.write(f'Replication seeds ({len(SEEDS)}): {SEEDS}\n')
        f.write(f'Total simulation runs: {len(plan)}\n')
        f.write(f'Common observation window: {start} to {end}\n\n')
        f.write('PAIRED STATISTICAL INFERENCE\n' + '-' * 96 + '\n')
        f.write(inference.to_string(index=False) + '\n\n')
        f.write('POLICY RANK STABILITY\n' + '-' * 96 + '\n')
        f.write(rank_stability.to_string(index=False) + '\n\n')
        f.write('METHODOLOGICAL LIMITATIONS\n' + '-' * 96 + '\n')
        f.write('1. The paired t-tests compare simulated policy outcomes across matched random seeds.\n')
        f.write('2. P-values are unadjusted across the multiple policy/metric comparisons; treat them as exploratory.\n')
        f.write('3. Statistical significance does not establish operational or causal validity.\n')
        f.write('4. Thirty seeds improve Monte Carlo precision but do not correct limitations in the underlying data or model.\n')
        f.write('5. Recovery fractions and fixed-hour limits are hypothetical sensitivity assumptions.\n')
        f.write('6. Port-call concurrency is not berth occupancy, verified capacity, or direct congestion.\n')
        f.write('7. No AIS-confirmed Strait of Hormuz transit is inferred.\n')
        f.write('8. Accumulated call-delay hours sum delay across affected call records, not unique-vessel delay.\n')

    print('Saved additional statistical tables:')
    for filename in extra_tables:
        print(f'- outputs/tables/{filename}')
    print('- outputs/reports/35_extended_replication_statistical_report.txt')

    final_checks = {
        'Expected 1,020 simulation runs': len(plan) == 1020 and len(combined) == 1020,
        'Thirty seeds for every scenario-policy combination': combined.groupby(
            ['Scenario', 'Recovery_Policy']
        ).Replication_Seed.nunique().eq(30).all(),
        'Paired inference results generated': not inference.empty,
        'Seed-level rank stability generated': not rank_stability.empty,
        'All additional tables saved': all(
            (TABLE_DIR / name).exists() for name in extra_tables
        ),
        'Statistical report saved': report_path.exists(),
    }
    print('\\nFINAL VALIDATION')
    for label, passed in final_checks.items():
        print(f'{label}: {"PASS" if passed else "FAIL"}')
    if not all(final_checks.values()):
        raise AssertionError('One or more final validation checks failed.')
    print('\nSCENARIO SUMMARY')
    print(summary[['Scenario', 'Recovery_Policy', 'Mean_Total_Accumulated_Delay_Hours',
                   'Mean_Total_Recovered_Hours', 'Mean_Maximum_Port_Peak',
                   'Mean_Average_Port_Peak']].to_string(index=False, float_format=lambda x: f'{x:.3f}'))
    print('\nSCRIPT 35 COMPLETED SUCCESSFULLY')


if __name__ == '__main__':
    main()

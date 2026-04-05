"""
Experiment 4(a): Poisson Clock Structure
  (ii)  Estimate limit state probabilities using multiple simulations,
        compare with analytical values, error < 10^-3.
  (iii) Law of Large Numbers evidence: sample mean and variance
        for different orders of magnitude of number of samples.

Two methods:
  - Ensemble: at each time t, count which state each sim is in → P(X(t)=x).
    Used for the convergence PLOT.
  - Time-average: within each sim, compute fraction of time in each state.
    Used for precise numerical comparison and LLN analysis.
"""

import sys
import os
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import random
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from tqdm import tqdm
from map import Map
from config import ZONES, SERVICE_RATES, ACCEPTANCE_PROB, WORK_TO_REST_RATE, REST_TO_WORK_RATE
from steadyStateA import build_Q_matrix, solve_steady_state

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Simulation core
# ---------------------------------------------------------------------------

def run_single_simulation(map_obj, sim_end_sec, seed):
    """
    Run one CTMC simulation. Returns:
      - trajectory: list of (time, state_id) for ensemble counting
      - time_avg_probs: time-averaged state probabilities (for precise estimation)
    """
    random.seed(seed)

    current_state = map_obj.initial_state
    current_time = 0.0
    n_states = len(map_obj.states)
    last_state_id = map_obj.find_state_id(current_state)

    # Trajectory for ensemble method
    trajectory = [(0.0, last_state_id)]

    # Time tracking for time-average method
    state_times = np.zeros(n_states)

    while current_time < sim_end_sec:
        possible_events = map_obj.check_possible_events(current_state)
        next_event, time_delta = select_next_event(possible_events, map_obj)

        if next_event is None or current_time + time_delta >= sim_end_sec:
            state_times[last_state_id] += sim_end_sec - current_time
            break

        state_times[last_state_id] += time_delta
        current_time += time_delta
        current_state = next_event.to_state
        last_state_id = next_event.to_state_id
        trajectory.append((current_time, last_state_id))

    # Time-averaged probabilities
    total = state_times.sum()
    time_avg_probs = state_times / total if total > 0 else state_times

    return trajectory, time_avg_probs


def get_state_at_time(trajectory, t):
    """
    Given a trajectory [(time, state_id), ...], return the state_id at time t.
    """
    state_id = trajectory[0][1]
    for enter_time, sid in trajectory:
        if enter_time <= t:
            state_id = sid
        else:
            break
    return state_id


def get_event_rate(event, map_obj):
    """Calculate the rate for a given event."""
    if event.event_type == "StartRequest":
        origin = event.info["origin_zone"]
        dest = event.info["destination_zone"]
        arrival_rate = ZONES[origin]["arrival_lambdas"].get(dest, 0)
        if event.to_state != event.from_state:
            return arrival_rate * ACCEPTANCE_PROB
        else:
            return arrival_rate * (1 - ACCEPTANCE_PROB)

    elif event.event_type == "EndRequest":
        origin = event.info["origin_zone"]
        dest = event.info["destination_zone"]
        origin_id = map_obj.zone_id[origin]
        dest_id = map_obj.zone_id[dest]
        num_traveling = event.from_state.matrix_drivers_online[origin_id][dest_id]
        if num_traveling > 0:
            return num_traveling * SERVICE_RATES[origin][dest]
        return 0.0

    elif event.event_type == "OnlineDriver":
        zone = event.info["zone"]
        zone_id = map_obj.zone_id[zone]
        num_offline = event.from_state.matrix_drivers_offline[zone_id][zone_id]
        if num_offline > 0:
            return num_offline * REST_TO_WORK_RATE
        return 0.0

    elif event.event_type == "OfflineDriver":
        zone = event.info["zone"]
        zone_id = map_obj.zone_id[zone]
        num_online = event.from_state.matrix_drivers_online[zone_id][zone_id]
        if num_online > 0:
            return num_online * WORK_TO_REST_RATE
        return 0.0

    return 0.0


def select_next_event(possible_events, map_obj):
    """Select next event using CTMC competing exponentials."""
    event_rates = [(e, get_event_rate(e, map_obj)) for e in possible_events]
    valid = [(e, r) for e, r in event_rates if r > 0]

    if not valid:
        return None, float('inf')

    total_rate = sum(r for _, r in valid)
    time_delta = -math.log(random.random()) / total_rate

    rand_val = random.random() * total_rate
    cumulative = 0.0
    selected = None
    for e, r in valid:
        cumulative += r
        if rand_val <= cumulative:
            selected = e
            break

    return selected, time_delta


# ---------------------------------------------------------------------------
# 4(a)(ii): Ensemble convergence plot + time-average comparison table
# ---------------------------------------------------------------------------

def experiment_4a_ii(map_obj, pi_analytical, n_runs=10000, sim_hours=20):
    """
    1) Run N simulations, store trajectories and time-averaged probabilities.
    2) Ensemble plot: P(X(t)=x) vs time (shows convergence to steady state).
    3) Time-average table: compare mean time-averaged pi with analytical.
    """
    sim_end_sec = 3600 * sim_hours
    n_states = len(map_obj.states)

    # Run all simulations
    print(f"=== Experiment 4(a)(ii): {n_runs} simulations, {sim_hours}h each ===")
    trajectories = []
    time_avg_all = np.zeros((n_runs, n_states))

    for i in tqdm(range(n_runs), desc="4(a)(ii) simulations"):
        seed = 1000 + i
        traj, ta_probs = run_single_simulation(map_obj, sim_end_sec, seed)
        trajectories.append(traj)
        time_avg_all[i] = ta_probs

    # --- Ensemble: P(X(t) = x) vs time ---
    # Zoom to first 20h where the transient is visible
    plot_end_sec = min(sim_end_sec, 3600 * 20)
    time_grid = np.linspace(0, plot_end_sec, 300)
    pi_ensemble = np.zeros((len(time_grid), n_states))

    print("Computing ensemble state probabilities...")
    for t_idx, t in enumerate(tqdm(time_grid, desc="4(a)(ii) counting")):
        counts = np.zeros(n_states)
        for traj in trajectories:
            sid = get_state_at_time(traj, t)
            counts[sid] += 1
        pi_ensemble[t_idx] = counts / n_runs

    # Plot ensemble convergence
    fig, ax = plt.subplots(figsize=(12, 6))
    for s in range(n_states):
        ax.plot(time_grid / 3600, pi_ensemble[:, s],
                label=f'State {s+1}', linewidth=1.5, alpha=0.8)
        ax.axhline(y=pi_analytical[s], color='gray', linestyle='--', alpha=0.2)

    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('Estimated P(X(t) = x)')
    ax.set_title(f'Estimated State Probabilities vs Time (N = {n_runs} simulations)')
    ax.legend(fontsize=7, bbox_to_anchor=(1.02, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    fig_path = os.path.join(current_dir, '..', 'figures', 'ensemble_convergence.png')
    plt.savefig(fig_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {fig_path}")
    plt.close()

    # --- Time-average: precise comparison table ---
    pi_estimated = np.mean(time_avg_all, axis=0)
    abs_errors = np.abs(pi_analytical - pi_estimated)
    max_error = np.max(abs_errors)

    print(f"\nTime-averaged estimation (mean over {n_runs} simulations):")
    print(f"{'State':>6} {'Analytical':>12} {'Simulated':>12} {'Abs Error':>12}")
    print("-" * 46)
    for s in range(n_states):
        print(f"{s+1:>6} {pi_analytical[s]:>12.6f} {pi_estimated[s]:>12.6f} {abs_errors[s]:>12.6f}")
    print("-" * 46)
    print(f"{'Max error':>30} {max_error:>12.6f}")
    print(f"Target met (< 10^-3): {max_error < 1e-3}")

    return trajectories, time_avg_all


# ---------------------------------------------------------------------------
# 4(a)(iii): Law of Large Numbers evidence
# ---------------------------------------------------------------------------

def experiment_4a_iii(map_obj, pi_analytical, time_avg_all):
    """
    LLN evidence using time-averaged estimates.
    For N = 10, 100, 1000, 10000: take the first N simulation results,
    compute sample mean and sample variance of the estimated probabilities.
    """
    n_states = len(map_obj.states)
    total_runs = time_avg_all.shape[0]
    sample_sizes = [10, 100, 1000, 10000]
    sample_sizes = [n for n in sample_sizes if n <= total_runs]

    print(f"\n=== Experiment 4(a)(iii): LLN evidence ===")

    results = {}
    for N in sample_sizes:
        subset = time_avg_all[:N]
        means = np.mean(subset, axis=0)
        variances = np.var(subset, axis=0)
        max_error = np.max(np.abs(means - pi_analytical))
        mean_var = np.mean(variances)
        results[N] = (means, variances, max_error, mean_var)

    # Print full table: for each N, show per-state mean and variance
    for N in sample_sizes:
        means, variances, max_err, mean_var = results[N]
        print(f"\nN = {N}:")
        print(f"  {'State':>6} {'Sample Mean':>12} {'Sample Var':>12} {'|mean - pi|':>12}")
        print(f"  {'-'*44}")
        for s in range(n_states):
            err = abs(means[s] - pi_analytical[s])
            print(f"  {s+1:>6} {means[s]:>12.6f} {variances[s]:>12.8f} {err:>12.6f}")
        print(f"  {'Max error':>30} {max_err:>12.6f}")
        print(f"  {'Avg variance':>30} {mean_var:>12.8f}")

    # Summary table
    print(f"\n--- Summary ---")
    print(f"{'N':>6} {'Max |mean - pi|':>16} {'Avg Variance':>14}")
    print("-" * 38)
    for N in sample_sizes:
        _, _, max_err, avg_var = results[N]
        print(f"{N:>6} {max_err:>16.6f} {avg_var:>14.8f}")

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)

    # Build map once
    print("Building state space...")
    map_obj = Map()
    n_states = len(map_obj.states)
    print(f"States: {n_states}")

    # Analytical steady-state
    print("Computing analytical steady-state...")
    Q = build_Q_matrix(map_obj)
    pi_analytical = solve_steady_state(Q)
    print(f"Analytical pi sum: {np.sum(pi_analytical):.6f}\n")

    # 4(a)(ii): ensemble plot + time-average comparison
    trajectories, time_avg_all = experiment_4a_ii(
        map_obj, pi_analytical, n_runs=10000, sim_hours=100
    )

    # 4(a)(iii): LLN evidence
    results = experiment_4a_iii(map_obj, pi_analytical, time_avg_all)

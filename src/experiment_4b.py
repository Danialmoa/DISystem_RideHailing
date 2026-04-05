"""
Experiment 4(b): Realistic Clock Structure
  (b)(i)  Replace exponential work/rest clocks with uniform distributions.
          Verify steady state by plotting P(X(t)=x) vs time.
  (b)(ii) Repeat LLN analysis (sample mean & variance for different N).

Realistic clocks:
  - Work period:  Uniform(15, 25) min  (mean = 20 min, same as exponential)
  - Rest period:  Uniform(10, 20) min  (mean = 15 min, same as exponential)
  - Arrivals:     Keep exponential (Poisson arrivals are realistic)
  - Ride duration: Keep exponential

Simulation method: competing clocks with residual lifetimes (like simprobdes.m).
  - Each active event has a residual lifetime
  - The event with minimum residual fires next
  - Other active events: residual -= elapsed time
  - New/reset events: draw fresh lifetime from their distribution
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

# Realistic clock parameters (same means as exponential)
WORK_UNIFORM_A = 15 * 60   # 15 min in seconds
WORK_UNIFORM_B = 25 * 60   # 25 min in seconds
REST_UNIFORM_A = 10 * 60   # 10 min in seconds
REST_UNIFORM_B = 20 * 60   # 20 min in seconds


# ---------------------------------------------------------------------------
# Lifetime samplers
# ---------------------------------------------------------------------------

def sample_lifetime(event_type, info):
    """
    Draw a lifetime for an event.
    - StartRequest: exponential (Poisson arrivals, kept as-is)
    - EndRequest:   exponential (ride duration, kept as-is)
    - OfflineDriver: UNIFORM (work → rest, realistic)
    - OnlineDriver:  UNIFORM (rest → work, realistic)
    """
    if event_type == "StartRequest":
        origin = info["origin_zone"]
        dest = info["destination_zone"]
        rate = ZONES[origin]["arrival_lambdas"].get(dest, 0)
        if rate > 0:
            return -math.log(random.random()) / rate
        return float('inf')

    elif event_type == "EndRequest":
        origin = info["origin_zone"]
        dest = info["destination_zone"]
        rate = SERVICE_RATES[origin][dest]
        if rate > 0:
            return -math.log(random.random()) / rate
        return float('inf')

    elif event_type == "OfflineDriver":
        # Work period: Uniform(15min, 25min)
        return random.uniform(WORK_UNIFORM_A, WORK_UNIFORM_B)

    elif event_type == "OnlineDriver":
        # Rest period: Uniform(10min, 20min)
        return random.uniform(REST_UNIFORM_A, REST_UNIFORM_B)

    return float('inf')


# ---------------------------------------------------------------------------
# Simulation with competing clocks and residual lifetimes
# ---------------------------------------------------------------------------

def get_active_events(map_obj, state):
    """
    Get all events that are currently possible in this state,
    along with their type and info.
    Returns list of (event_type, info, event_key) where event_key
    uniquely identifies the event.
    """
    zone_id = map_obj.zone_id
    active = []

    for origin in map_obj.zones:
        for dest in map_obj.zones:
            if origin != dest:
                # StartRequest: possible if there's a driver available in origin
                # (we model both accept and reject as one clock - the arrival)
                key = ("StartRequest", origin, dest)
                active.append(("StartRequest", {"origin_zone": origin, "destination_zone": dest}, key))

                # EndRequest: possible if there's a driver traveling origin→dest
                if state.matrix_drivers_online[zone_id[origin]][zone_id[dest]] > 0:
                    key = ("EndRequest", origin, dest)
                    active.append(("EndRequest", {"origin_zone": origin, "destination_zone": dest}, key))

    for zone in map_obj.zones:
        # OfflineDriver: possible if there's an online idle driver in zone
        if state.matrix_drivers_online[zone_id[zone]][zone_id[zone]] > 0:
            key = ("OfflineDriver", zone)
            active.append(("OfflineDriver", {"zone": zone}, key))

        # OnlineDriver: possible if there's an offline driver in zone
        if state.matrix_drivers_offline[zone_id[zone]][zone_id[zone]] > 0:
            key = ("OnlineDriver", zone)
            active.append(("OnlineDriver", {"zone": zone}, key))

    return active


def apply_event(map_obj, state, event_type, info):
    """
    Apply an event to a state and return the new state.
    For StartRequest, randomly accept or reject based on ACCEPTANCE_PROB.
    """
    from models.request import Request
    from models.drivers import Driver

    zone_id = map_obj.zone_id

    if event_type == "StartRequest":
        origin = info["origin_zone"]
        dest = info["destination_zone"]
        # Check if driver available
        if state.matrix_drivers_online[zone_id[origin]][zone_id[origin]] > 0:
            # Accept with probability ACCEPTANCE_PROB
            if random.random() < ACCEPTANCE_PROB:
                new_state = state.copy()
                new_state.matrix_drivers_online[zone_id[origin]][zone_id[origin]] -= 1
                new_state.matrix_drivers_online[zone_id[origin]][zone_id[dest]] += 1
                return new_state
        # Reject or no driver → state unchanged
        return state.copy()

    elif event_type == "EndRequest":
        origin = info["origin_zone"]
        dest = info["destination_zone"]
        new_state = state.copy()
        new_state.matrix_drivers_online[zone_id[origin]][zone_id[dest]] -= 1
        new_state.matrix_drivers_online[zone_id[dest]][zone_id[dest]] += 1
        return new_state

    elif event_type == "OfflineDriver":
        zone = info["zone"]
        new_state = state.copy()
        new_state.matrix_drivers_online[zone_id[zone]][zone_id[zone]] -= 1
        new_state.matrix_drivers_offline[zone_id[zone]][zone_id[zone]] += 1
        return new_state

    elif event_type == "OnlineDriver":
        zone = info["zone"]
        new_state = state.copy()
        new_state.matrix_drivers_offline[zone_id[zone]][zone_id[zone]] -= 1
        new_state.matrix_drivers_online[zone_id[zone]][zone_id[zone]] += 1
        return new_state

    return state.copy()


def run_single_simulation_realistic(map_obj, sim_end_sec, seed):
    """
    Run one simulation with realistic (non-exponential) clocks.
    Uses competing clocks with residual lifetimes.

    Returns:
      - trajectory: list of (time, state_id) for ensemble counting
      - time_avg_probs: time-averaged state probabilities
    """
    random.seed(seed)

    current_state = map_obj.initial_state
    current_time = 0.0
    n_states = len(map_obj.states)
    last_state_id = map_obj.find_state_id(current_state)

    trajectory = [(0.0, last_state_id)]
    state_times = np.zeros(n_states)

    # Initialize residual lifetimes for all active events
    residual = {}  # key -> residual lifetime
    active_events = get_active_events(map_obj, current_state)
    for event_type, info, key in active_events:
        residual[key] = sample_lifetime(event_type, info)

    while current_time < sim_end_sec:
        # Find active events and their residual lifetimes
        active_events = get_active_events(map_obj, current_state)
        active_keys = set()

        for event_type, info, key in active_events:
            active_keys.add(key)
            if key not in residual:
                # New event became possible → draw fresh lifetime
                residual[key] = sample_lifetime(event_type, info)

        # Remove clocks for events no longer possible
        for key in list(residual.keys()):
            if key not in active_keys:
                del residual[key]

        if not residual:
            state_times[last_state_id] += sim_end_sec - current_time
            break

        # Find event with minimum residual lifetime
        min_key = min(residual, key=residual.get)
        min_time = residual[min_key]

        if current_time + min_time >= sim_end_sec:
            state_times[last_state_id] += sim_end_sec - current_time
            break

        # Update time
        state_times[last_state_id] += min_time
        current_time += min_time

        # Subtract elapsed time from all other residuals
        for key in residual:
            if key != min_key:
                residual[key] -= min_time

        # Find the event info for the fired event
        fired_type = None
        fired_info = None
        for event_type, info, key in active_events:
            if key == min_key:
                fired_type = event_type
                fired_info = info
                break

        # Apply event
        old_state = current_state
        current_state = apply_event(map_obj, current_state, fired_type, fired_info)
        last_state_id = map_obj.find_state_id(current_state)
        trajectory.append((current_time, last_state_id))

        # Reset clock for fired event (draw new lifetime)
        # The fired event's clock is reset if it's still active in the new state
        del residual[min_key]
        # New active events in the new state will get fresh lifetimes
        # in the next iteration

    # Time-averaged probabilities
    total = state_times.sum()
    time_avg_probs = state_times / total if total > 0 else state_times

    return trajectory, time_avg_probs


def get_state_at_time(trajectory, t):
    """Given a trajectory, return the state_id at time t."""
    state_id = trajectory[0][1]
    for enter_time, sid in trajectory:
        if enter_time <= t:
            state_id = sid
        else:
            break
    return state_id


# ---------------------------------------------------------------------------
# 4(b)(i): Verify steady state with realistic clocks
# ---------------------------------------------------------------------------

def experiment_4b_i(map_obj, pi_analytical, n_runs=10000, sim_hours=100):
    """
    Run N simulations with realistic clocks.
    Plot ensemble P(X(t)=x) vs time to show convergence.
    """
    sim_end_sec = 3600 * sim_hours
    n_states = len(map_obj.states)

    print(f"=== Experiment 4(b)(i): {n_runs} simulations, {sim_hours}h, realistic clocks ===")
    print(f"  Work period: Uniform({WORK_UNIFORM_A/60:.0f}, {WORK_UNIFORM_B/60:.0f}) min")
    print(f"  Rest period: Uniform({REST_UNIFORM_A/60:.0f}, {REST_UNIFORM_B/60:.0f}) min")

    trajectories = []
    time_avg_all = np.zeros((n_runs, n_states))

    for i in tqdm(range(n_runs), desc="4(b)(i) simulations"):
        seed = 5000 + i
        traj, ta_probs = run_single_simulation_realistic(map_obj, sim_end_sec, seed)
        trajectories.append(traj)
        time_avg_all[i] = ta_probs

    # Ensemble convergence plot (zoom to first 20h)
    plot_end_sec = min(sim_end_sec, 3600 * 20)
    time_grid = np.linspace(0, plot_end_sec, 300)
    pi_ensemble = np.zeros((len(time_grid), n_states))

    print("Computing ensemble state probabilities...")
    for t_idx, t in enumerate(tqdm(time_grid, desc="4(b)(i) counting")):
        counts = np.zeros(n_states)
        for traj in trajectories:
            sid = get_state_at_time(traj, t)
            counts[sid] += 1
        pi_ensemble[t_idx] = counts / n_runs

    # Plot
    fig, ax = plt.subplots(figsize=(12, 6))
    for s in range(n_states):
        ax.plot(time_grid / 3600, pi_ensemble[:, s],
                label=f'State {s+1}', linewidth=1.5, alpha=0.8)
        ax.axhline(y=pi_analytical[s], color='gray', linestyle='--', alpha=0.2)

    ax.set_xlabel('Time (hours)')
    ax.set_ylabel('Estimated P(X(t) = x)')
    ax.set_title(f'Realistic Clocks: State Probabilities vs Time (N = {n_runs})')
    ax.legend(fontsize=7, bbox_to_anchor=(1.02, 1), loc='upper left')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    fig_path = os.path.join(current_dir, '..', 'figures', 'realistic_convergence.png')
    plt.savefig(fig_path, dpi=300, bbox_inches='tight')
    print(f"Saved: {fig_path}")
    plt.close()

    # Check if converged: compare final ensemble with analytical
    pi_final = pi_ensemble[-1]
    pi_time_avg = np.mean(time_avg_all, axis=0)

    print(f"\nComparison (time-averaged over {n_runs} runs):")
    print(f"{'State':>6} {'Analytical':>12} {'Realistic':>12} {'Difference':>12}")
    print("-" * 46)
    for s in range(n_states):
        diff = pi_time_avg[s] - pi_analytical[s]
        print(f"{s+1:>6} {pi_analytical[s]:>12.6f} {pi_time_avg[s]:>12.6f} {diff:>+12.6f}")

    print(f"\nSteady state reached: {'Yes' if np.max(np.abs(pi_final - pi_ensemble[-10])) < 0.01 else 'Possibly not'}")

    return trajectories, time_avg_all


# ---------------------------------------------------------------------------
# 4(b)(ii): LLN evidence with realistic clocks
# ---------------------------------------------------------------------------

def experiment_4b_ii(map_obj, time_avg_all):
    """
    LLN evidence for realistic clocks.
    Same as 4(a)(iii) but using realistic simulation results.
    """
    n_states = time_avg_all.shape[1]
    total_runs = time_avg_all.shape[0]
    sample_sizes = [10, 100, 1000, 10000]
    sample_sizes = [n for n in sample_sizes if n <= total_runs]

    # Use the overall mean as the "limit" (no analytical solution for non-exponential)
    pi_limit = np.mean(time_avg_all, axis=0)

    print(f"\n=== Experiment 4(b)(ii): LLN evidence (realistic clocks) ===")
    print(f"(Using overall mean of {total_runs} runs as reference)")

    results = {}
    for N in sample_sizes:
        subset = time_avg_all[:N]
        means = np.mean(subset, axis=0)
        variances = np.var(subset, axis=0)
        max_error = np.max(np.abs(means - pi_limit))
        mean_var = np.mean(variances)
        results[N] = (means, variances, max_error, mean_var)

    # Print detailed tables
    for N in sample_sizes:
        means, variances, max_err, mean_var = results[N]
        print(f"\nN = {N}:")
        print(f"  {'State':>6} {'Sample Mean':>12} {'Sample Var':>12} {'|mean - pi|':>12}")
        print(f"  {'-'*44}")
        for s in range(n_states):
            err = abs(means[s] - pi_limit[s])
            print(f"  {s+1:>6} {means[s]:>12.6f} {variances[s]:>12.8f} {err:>12.6f}")
        print(f"  {'Max error':>30} {max_err:>12.6f}")
        print(f"  {'Avg variance':>30} {mean_var:>12.8f}")

    # Summary
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

    # Analytical steady-state (from Poisson/exponential model, for reference)
    print("Computing analytical steady-state (exponential model)...")
    Q = build_Q_matrix(map_obj)
    pi_analytical = solve_steady_state(Q)
    print(f"Analytical pi sum: {np.sum(pi_analytical):.6f}\n")

    # 4(b)(i): verify steady state with realistic clocks
    trajectories, time_avg_all = experiment_4b_i(
        map_obj, pi_analytical, n_runs=10000, sim_hours=100
    )

    # 4(b)(ii): LLN evidence
    results = experiment_4b_ii(map_obj, time_avg_all)

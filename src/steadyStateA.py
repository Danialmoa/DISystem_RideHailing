import numpy as np
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from map import Map
from config import ZONES, SERVICE_RATES, WORK_TO_REST_RATE, REST_TO_WORK_RATE, ACCEPTANCE_PROB

def build_Q_matrix(map_obj):
    n_states = len(map_obj.states)
    Q = np.zeros((n_states, n_states))
    
    for state_id, state in map_obj.states.items():
        possible_events = map_obj.check_possible_events(state)
        
        for event in possible_events:
            from_state_id = event.from_state_id
            to_state_id = event.to_state_id
            
            if from_state_id == to_state_id:
                continue
            
            rate = get_event_rate(event, map_obj)
            Q[from_state_id, to_state_id] += rate
    
    for i in range(n_states):
        Q[i, i] = -np.sum(Q[i, :])
    
    return Q

def get_event_rate(event, map_obj):
    event_type = event.event_type
    
    if event.event_type == "StartRequest":
        origin = event.info["origin_zone"]
        destination = event.info["destination_zone"]
        print(f"Start request: {origin} -> {destination}", ZONES[origin]["arrival_lambdas"][destination] * ACCEPTANCE_PROB)
        return ZONES[origin]["arrival_lambdas"][destination] * ACCEPTANCE_PROB
    
    elif event.event_type == "EndRequest":
        origin = event.info["origin_zone"]
        destination = event.info["destination_zone"]
        return SERVICE_RATES[origin][destination]
    
    elif event.event_type == "OnlineDriver":
        return REST_TO_WORK_RATE
    
    elif event.event_type == "OfflineDriver":
        return WORK_TO_REST_RATE
    
    return 0

def solve_steady_state(Q):
    n = Q.shape[0]
    A = np.vstack([Q.T, np.ones(n)])
    b = np.zeros(n + 1)
    b[-1] = 1
    
    pi = np.linalg.lstsq(A, b, rcond=None)[0]
    return pi

if __name__ == "__main__":
    map_obj = Map()
    print(f"Number of states: {len(map_obj.states)}")
    
    Q = build_Q_matrix(map_obj)
    print(f"Q matrix shape: {Q.shape}")
    print(Q)
    
    pi = solve_steady_state(Q)
    print(f"Steady-state probabilities: {pi}")
    print(f"Sum of probabilities: {np.sum(pi)}")
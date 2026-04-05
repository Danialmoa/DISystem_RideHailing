import numpy as np
import sys
import os
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from map import Map
from config import ZONES, SERVICE_RATES, WORK_TO_REST_RATE, REST_TO_WORK_RATE, ACCEPTANCE_PROB

logger = logging.getLogger(__name__)

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
        logger.debug(f"Start request: {origin} -> {destination} rate={ZONES[origin]['arrival_lambdas'][destination] * ACCEPTANCE_PROB}")
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
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('__main__').setLevel(logging.INFO)
    logging.getLogger('models').setLevel(logging.INFO)
    map_obj = Map()
    logger.info(f"Number of states: {len(map_obj.states)}")

    Q = build_Q_matrix(map_obj)
    logger.info(f"Q matrix shape: {Q.shape}")
    logger.info(f"\n{Q}")

    pi = solve_steady_state(Q)
    logger.info(f"Steady-state probabilities: {pi}")
    logger.info(f"Sum of probabilities: {np.sum(pi)}")
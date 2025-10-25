# /Users/danialmoafi/UNI/DiscreteEvent/Project/src/config.py
import random

SEED = 42
random.seed(SEED)

ZONES = {
    "A": {"arrival_lambdas": {"B": 0.00278, "C": 0.00167}, "num_drivers": 1},  # Expected: 6min, 10min
    "B": {"arrival_lambdas": {"A": 0.00238, "C": 0.00208}, "num_drivers": 0},  # Expected: 7min, 8min  
    "C": {"arrival_lambdas": {"A": 0.00333, "B": 0.00167}, "num_drivers": 0},  # Expected: 5min, 10min
}

SERVICE_RATES = {
    "A": {"B": 1/450, "C": 1/900},    # A→B: mean 450sec (7.5min), A→C: mean 900sec (15min)
    "B": {"A": 1/450, "C": 1/675},    # B→A: mean 450sec (7.5min), B→C: mean 675sec (11.25min)  
    "C": {"A": 1/900, "B": 1/675},    # C→A: mean 900sec (15min), C→B: mean 675sec (11.25min)
}

# Exponential work/rest p2arameters
MEAN_WORK_HOURS = 20      # 20 minutes average waiting time
MEAN_REST_MINUTES = 15     # 30 minutes average rest time

MEAN_WORK_TIME_SEC = MEAN_WORK_HOURS * 60 
MEAN_REST_TIME_SEC = MEAN_REST_MINUTES * 60

WORK_TO_REST_RATE = 1.0 / MEAN_WORK_TIME_SEC
REST_TO_WORK_RATE = 1.0 / MEAN_REST_TIME_SEC

ACCEPTANCE_PROB = 0.7

SIM_END_SEC = 3600 * 5000



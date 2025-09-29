# /Users/danialmoafi/UNI/DiscreteEvent/Project/src/config.py
import random

SEED = 42
random.seed(SEED)

ZONES = {
    "A": {"arrival_lambdas": {"B": 0.00278, "C": 0.00167}, "num_drivers": 1},  # Expected: 6min, 10min
    "B": {"arrival_lambdas": {"A": 0.00238, "C": 0.00208}, "num_drivers": 0},  # Expected: 7min, 8min  
    "C": {"arrival_lambdas": {"A": 0.00333, "B": 0.00167}, "num_drivers": 0},  # Expected: 5min, 10min
}

DISTANCES = {
    "A": {"B": 10, "C": 20},
    "B": {"A": 10, "C": 15},
    "C": {"A": 20, "B": 15},
} #KM

WORKING_TIME_MIN = (30, 90)
RESTING_TIME_MIN = (15, 30)

ACCEPTANCE_PROB = 0.7

SIM_END_SEC = 3600 * 8

SPEED = 80 #KM/H
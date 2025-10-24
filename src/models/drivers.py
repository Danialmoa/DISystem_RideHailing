import random
import math
from models.state import State
from config import WORK_TO_REST_RATE, REST_TO_WORK_RATE, MEAN_WORK_TIME_SEC, MEAN_REST_TIME_SEC

class Driver:
    """
    Driver with exponential work/rest cycles
    """
    def __init__(self, driver_id: str, zone: str, start_time: float):
        self.driver_id = driver_id
        self.zone = zone
        self.zone_id = {
            "A": 0,
            "B": 1,
            "C": 2
        }
        
        # Exponential rates
        self.work_to_rest_rate = WORK_TO_REST_RATE
        self.rest_to_work_rate = REST_TO_WORK_RATE
        
        # Driver state
        self.is_working = True
        self.cycle_start_time = start_time
        self.next_transition_time = None
        
        self.total_driving_time = 0.0
        
        # Schedule first transition
        self._schedule_next_transition(start_time)
    
    def _exponential_random(self, rate: float) -> float:
        """Generate exponential random time with given rate"""
        return -math.log(random.random()) / rate
    
    def _schedule_next_transition(self, current_time: float):
        """Schedule next work/rest transition"""
        if self.is_working:
            # Currently working → schedule rest transition
            duration = self._exponential_random(self.work_to_rest_rate)
        else:
            # Currently resting → schedule work transition
            duration = self._exponential_random(self.rest_to_work_rate)
        
        self.next_transition_time = current_time + duration
    
    def should_transition_now(self, current_time: float) -> bool:
        """Check if driver should transition work/rest state"""
        return self.next_transition_time and current_time >= self.next_transition_time
    
    def transition_state(self, current_time: float):
        """Transition between work and rest"""
        self.is_working = not self.is_working
        self.cycle_start_time = current_time
        
        # Schedule next transition
        self._schedule_next_transition(current_time)
        
        print(f"Driver {self.driver_id}: {'work' if self.is_working else 'rest'} transition at time {current_time:.2f}")
    
    def get_next_transition_time(self) -> float:
        """Get time of next scheduled transition"""
        return self.next_transition_time
    
    def get_transition_type(self) -> str:
        """Get type of next transition"""
        return "go_rest" if self.is_working else "go_work"
    
    def add_driving_time(self, duration: float):
        """Add driving time"""
        self.total_driving_time += duration
    
    def start_rest(self, current_time: float):
        """Not used in exponential model"""
        return current_time + self._exponential_random(self.rest_to_work_rate)

    def online(self, state: State):
        """Make driver online"""
        copy_state = state.copy()
        zone_id = self.zone_id[self.zone]
        if copy_state.matrix_drivers_offline[zone_id][zone_id] > 0:
            copy_state.matrix_drivers_offline[zone_id][zone_id] -= 1
            copy_state.matrix_drivers_online[zone_id][zone_id] += 1
        return copy_state

    def offline(self, state: State):
        """Make driver offline"""
        copy_state = state.copy()
        zone_id = self.zone_id[self.zone]
        if copy_state.matrix_drivers_online[zone_id][zone_id] > 0:
            copy_state.matrix_drivers_online[zone_id][zone_id] -= 1
            copy_state.matrix_drivers_offline[zone_id][zone_id] += 1
        return copy_state
    
    def get_rates(self):
        """Get exponential rates for steady-state analysis"""
        return {
            'work_to_rest_rate': self.work_to_rest_rate,
            'rest_to_work_rate': self.rest_to_work_rate,
            'mean_work_time': MEAN_WORK_TIME_SEC,
            'mean_rest_time': MEAN_REST_TIME_SEC
        }
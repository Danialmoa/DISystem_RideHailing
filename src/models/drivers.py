import random
from models.state import State

class Driver:
    """
    This class is for the drivers, 
    it has the zone and the state of the driver, and the function to online and offline the driver,
    and the function to start and end the ride
    """
    def __init__(self, driver_id: str, zone: str, start_time: float, working_time_min: tuple, resting_time_min: tuple):
        self.driver_id = driver_id
        self.zone = zone
        self.zone_id = {
            "A": 0,
            "B": 1,
            "C": 2
        }
        
        # Work/rest cycle tracking
        self.is_working = True
        self.work_start_time = start_time
        self.total_driving_time = 0.0
        self.max_working_time = random.uniform(working_time_min[0], working_time_min[1]) * 60
        self.rest_duration = random.uniform(resting_time_min[0], resting_time_min[1]) * 60
        self.needs_rest_after_ride = False

    def online(self, state: State):
        """ To online the driver """
        copy_state = state.copy()
        copy_state.matrix_drivers_offline[self.zone_id[self.zone]][self.zone_id[self.zone]] -= 1
        copy_state.matrix_drivers_online[self.zone_id[self.zone]][self.zone_id[self.zone]] += 1
        return copy_state

    def offline(self, state: State):
        """ To offline the driver """
        copy_state = state.copy()
        copy_state.matrix_drivers_online[self.zone_id[self.zone]][self.zone_id[self.zone]] -= 1
        copy_state.matrix_drivers_offline[self.zone_id[self.zone]][self.zone_id[self.zone]] += 1
        return copy_state
    
    def add_driving_time(self, duration: float):
        """Add driving time and check if rest is needed"""
        self.total_driving_time += duration
        if self.total_driving_time >= self.max_working_time:
            self.needs_rest_after_ride = True
    
    def start_rest(self, current_time: float):
        """Start rest period"""
        self.is_working = False
        self.rest_start_time = current_time
        return current_time + self.rest_duration
    
    def finish_rest(self, working_time_min: tuple, resting_time_min: tuple):
        """Finish rest period and reset work cycle"""
        self.is_working = True
        self.total_driving_time = 0.0
        self.max_working_time = random.uniform(working_time_min[0], working_time_min[1]) * 60
        self.rest_duration = random.uniform(resting_time_min[0], resting_time_min[1]) * 60
        self.needs_rest_after_ride = False
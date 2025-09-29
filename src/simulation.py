import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import heapq
import random
import math
from typing import List, Dict, Tuple

from models.request import Request
from models.drivers import Driver
from models.event import Event as MapEvent
from config import ZONES, DISTANCES, SIM_END_SEC, SPEED, ACCEPTANCE_PROB, WORKING_TIME_MIN, RESTING_TIME_MIN
from models.state import State
from map import Map


class SimulationEvent:
    def __init__(self, time: float, event_type: str, data: dict):
        self.time = time
        self.event_type = event_type
        self.data = data
    
    def __lt__(self, other):
        return self.time < other.time


class DriverWorkTracker:
    """Track individual driver work/rest cycles"""
    def __init__(self, driver_id: str, zone: str, start_time: float):
        self.driver_id = driver_id
        self.zone = zone
        self.is_working = True  # Start working
        self.work_start_time = start_time
        self.total_driving_time = 0.0
        self.max_working_time = random.uniform(WORKING_TIME_MIN[0], WORKING_TIME_MIN[1]) * 60  # Convert to seconds
        self.rest_duration = random.uniform(RESTING_TIME_MIN[0], RESTING_TIME_MIN[1]) * 60  # Convert to seconds
        self.needs_rest_after_ride = False
    
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
    
    def finish_rest(self):
        """Finish rest period and reset work cycle"""
        self.is_working = True
        self.total_driving_time = 0.0
        self.max_working_time = random.uniform(WORKING_TIME_MIN[0], WORKING_TIME_MIN[1]) * 60
        self.rest_duration = random.uniform(RESTING_TIME_MIN[0], RESTING_TIME_MIN[1]) * 60
        self.needs_rest_after_ride = False


class Simulation:
    def __init__(self):
        self.current_time = 0.0
        self.event_queue = []
        
        self.map = Map()
        self.current_state = self.map.initial_state
        
        self.zones = list(ZONES.keys())
        self.zone_id = self.map.zone_id
        
        # Track drivers work/rest cycles
        self.driver_trackers = {}
        self._initialize_driver_trackers()
        
        self.statistics = {
            "total_requests": 0,
            "accepted_requests": 0,
            "rejected_requests": 0,
            "completed_rides": 0,
            "state_transitions": 0,
            "driver_rest_periods": 0
        }
        
        self._schedule_initial_events()
    
    def _initialize_driver_trackers(self):
        """Initialize driver work trackers"""
        driver_id = 0
        for zone, config in ZONES.items():
            for _ in range(config["num_drivers"]):
                tracker = DriverWorkTracker(f"driver_{driver_id}", zone, self.current_time)
                self.driver_trackers[f"driver_{driver_id}"] = tracker
                driver_id += 1
    
    def _uniform_random(self, min_val: float, max_val: float) -> float:
        """Generate uniformly distributed random number"""
        return random.uniform(min_val, max_val)
    
    def _schedule_initial_events(self):
        """Schedule initial request arrival events for each zone"""
        for origin_zone in self.zones:
            for dest_zone, lambda_rate in ZONES[origin_zone]["arrival_lambdas"].items():
                if origin_zone != dest_zone:
                    next_arrival = self._exponential_random(lambda_rate)
                    event = SimulationEvent(
                        time=next_arrival,
                        event_type="request_arrival",
                        data={"origin": origin_zone, "destination": dest_zone, "lambda_rate": lambda_rate}
                    )
                    heapq.heappush(self.event_queue, event)
    
    def _exponential_random(self, lambda_rate: float) -> float:
        """Generate exponentially distributed random number"""
        return -1 * (1.0 / lambda_rate) * math.log(random.random())
    
    def _calculate_travel_time(self, origin: str, destination: str) -> float:
        """Calculate travel time between zones in seconds"""
        distance = DISTANCES[origin][destination]
        return (distance / SPEED) * 3600
    
    def _get_available_driver_in_zone(self, zone: str):
        """Get an available working driver in the zone"""
        for driver_id, tracker in self.driver_trackers.items():
            if tracker.zone == zone and tracker.is_working:
                return driver_id
        return None
    
    def _handle_request_arrival(self, event: SimulationEvent):
        """Handle new request arrival"""
        data = event.data
        origin = data["origin"]
        destination = data["destination"]
        lambda_rate = data["lambda_rate"]
        
        self.statistics["total_requests"] += 1
        
        print(f"Time {self.current_time:.2f}: Request arrival from {origin} to {destination}")
        
        # IMMEDIATELY schedule the next arrival for this route (Poisson process)
        inter_arrival_time = self._exponential_random(lambda_rate)
        next_arrival_time = self.current_time + inter_arrival_time
        if next_arrival_time < SIM_END_SEC:
            next_event = SimulationEvent(
                time=next_arrival_time,
                event_type="request_arrival",
                data=data
            )
            heapq.heappush(self.event_queue, next_event)
        
        # Check if drivers available in origin zone
        origin_id = self.zone_id[origin]
        available_drivers_in_state = self.current_state.matrix_drivers_online[origin_id][origin_id]
        available_driver_id = self._get_available_driver_in_zone(origin)
        
        if available_drivers_in_state > 0 and available_driver_id and random.random() < ACCEPTANCE_PROB:
            # Accept the request
            print(f"Time {self.current_time:.2f}: Request accepted by {available_driver_id}")
            self.statistics["accepted_requests"] += 1
            
            # Apply StartRequest event to state
            request = Request(origin, destination)
            new_state = request.start_request(self.current_state)
            self._transition_to_state(new_state, f"StartRequest ({origin} -> {destination})")
            
            # Calculate travel time and add to driver's working time
            travel_time = self._calculate_travel_time(origin, destination)
            driver_tracker = self.driver_trackers[available_driver_id]
            driver_tracker.add_driving_time(travel_time)
            
            # Schedule ride completion
            completion_event = SimulationEvent(
                time=self.current_time + travel_time,
                event_type="ride_completion",
                data={"origin": origin, "destination": destination, "driver_id": available_driver_id}
            )
            heapq.heappush(self.event_queue, completion_event)
        else:
            # Reject the request
            print(f"Time {self.current_time:.2f}: Request rejected (no working drivers or driver declined)")
            self.statistics["rejected_requests"] += 1
    
    def _handle_ride_completion(self, event: SimulationEvent):
        """Handle ride completion"""
        data = event.data
        origin = data["origin"]
        destination = data["destination"]
        driver_id = data["driver_id"]
        
        print(f"Time {self.current_time:.2f}: Ride completed from {origin} to {destination} by {driver_id}")
        self.statistics["completed_rides"] += 1
        
        # Apply EndRequest event to state
        request = Request(origin, destination)
        new_state = request.end_request(self.current_state)
        self._transition_to_state(new_state, f"EndRequest ({origin} -> {destination})")
        
        # Update driver location
        driver_tracker = self.driver_trackers[driver_id]
        driver_tracker.zone = destination
        
        # Check if driver needs rest after working time exceeded
        if driver_tracker.needs_rest_after_ride:
            print(f"Time {self.current_time:.2f}: {driver_id} needs rest after {driver_tracker.total_driving_time/60:.1f} minutes of driving")
            
            # Make driver go offline
            driver = Driver(destination)
            new_state = driver.offline(self.current_state)
            self._transition_to_state(new_state, f"OfflineDriver ({destination}) - Rest needed")
            
            # Schedule driver to come back online after rest
            rest_end_time = driver_tracker.start_rest(self.current_time)
            self.statistics["driver_rest_periods"] += 1
            
            rest_end_event = SimulationEvent(
                time=rest_end_time,
                event_type="driver_back_online",
                data={"driver_id": driver_id, "zone": destination}
            )
            heapq.heappush(self.event_queue, rest_end_event)
    
    def _handle_driver_back_online(self, event: SimulationEvent):
        """Handle driver coming back online after rest"""
        data = event.data
        driver_id = data["driver_id"]
        zone = data["zone"]
        
        driver_tracker = self.driver_trackers[driver_id]
        driver_tracker.finish_rest()
        
        print(f"Time {self.current_time:.2f}: {driver_id} back online in zone {zone} after rest")
        
        # Make driver go online
        driver = Driver(zone)
        new_state = driver.online(self.current_state)
        self._transition_to_state(new_state, f"OnlineDriver ({zone}) - After rest")
    
    def _transition_to_state(self, new_state: State, event_description: str):
        """Transition to a new state"""
        old_state_id = self.map.find_state_id(self.current_state)
        new_state_id = self.map.find_state_id(new_state)
        
        print(f"State transition: {old_state_id} -> {new_state_id} ({event_description})")
        self.current_state = new_state
        self.statistics["state_transitions"] += 1
    
    def run(self):
        """Run the simulation"""
        print("=== Simulation Started ===")
        print(f"Initial state: {self.current_state}")
        print(f"Total possible states: {len(self.map.states)}")
        
        while self.event_queue and self.current_time < SIM_END_SEC:
            event = heapq.heappop(self.event_queue)
            self.current_time = event.time
            
            if self.current_time >= SIM_END_SEC:
                break
                
            if event.event_type == "request_arrival":
                self._handle_request_arrival(event)
            elif event.event_type == "ride_completion":
                self._handle_ride_completion(event)
            elif event.event_type == "driver_back_online":
                self._handle_driver_back_online(event)
        
        print("=== Simulation Completed ===")
        self._print_statistics()
    
    def _print_statistics(self):
        """Print simulation statistics"""
        print(f"\nFinal state: {self.current_state}")
        
        print(f"\nStatistics:")
        print(f"Total requests: {self.statistics['total_requests']}")
        print(f"Accepted requests: {self.statistics['accepted_requests']}")
        print(f"Rejected requests: {self.statistics['rejected_requests']}")
        print(f"Completed rides: {self.statistics['completed_rides']}")
        print(f"Driver rest periods: {self.statistics['driver_rest_periods']}")
        print(f"State transitions: {self.statistics['state_transitions']}")
        
        if self.statistics['total_requests'] > 0:
            acceptance_rate = self.statistics['accepted_requests'] / self.statistics['total_requests'] * 100
            print(f"Acceptance rate: {acceptance_rate:.1f}%")
        
        # Print driver status
        print(f"\nDriver Status:")
        for driver_id, tracker in self.driver_trackers.items():
            status = "Working" if tracker.is_working else "Resting"
            print(f"{driver_id}: {status} in zone {tracker.zone}, driving time: {tracker.total_driving_time/60:.1f}min")
        
        # Print final driver distribution
        print(f"\nFinal driver distribution:")
        total_online = 0
        total_offline = 0
        
        for i, zone in enumerate(['A', 'B', 'C']):
            zone_online = sum(self.current_state.matrix_drivers_online[i])
            zone_offline = self.current_state.matrix_drivers_offline[i][i]
            total_online += zone_online
            total_offline += zone_offline
            print(f"Zone {zone}: {zone_online} online, {zone_offline} offline")
        
        print(f"Total: {total_online} online, {total_offline} offline")


if __name__ == "__main__":
    sim = Simulation()
    sim.run()

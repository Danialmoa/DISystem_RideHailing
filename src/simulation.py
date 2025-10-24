import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import heapq
import random
import math
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple

from models.request import Request
from models.drivers import Driver
from models.event import Event as MapEvent
from config import ZONES, SERVICE_RATES, SIM_END_SEC, ACCEPTANCE_PROB, WORK_TO_REST_RATE, REST_TO_WORK_RATE
from models.state import State
from map import Map


class SimulationEvent:
    def __init__(self, time: float, event_type: str, data: dict):
        self.time = time
        self.event_type = event_type
        self.data = data
    
    def __lt__(self, other):
        return self.time < other.time


class Simulation:
    def __init__(self):
        self.current_time = 0.0
        self.event_queue = []
        
        self.map = Map()
        self.current_state = self.map.initial_state
        
        self.zones = list(ZONES.keys())
        self.zone_id = self.map.zone_id
        
        # Track drivers
        self.drivers = {}
        self._initialize_drivers()
        
        self.statistics = {
            "total_requests": 0,
            "accepted_requests": 0,
            "rejected_requests": 0,
            "completed_rides": 0,
            "state_transitions": 0,
            "driver_rest_periods": 0
        }
        
        # Add state time tracking
        self.state_times = {}  # Maps state_id -> total time spent
        self.last_state_id = None
        self.last_transition_time = 0.0
        self.state_history_snapshots = []
        
        self.last_state_id = self.map.find_state_id(self.current_state)
        self.last_transition_time = 0.0
        self.state_history_snapshots = []
        
        self._schedule_initial_events()
    
    def _initialize_drivers(self):
        """Initialize drivers with exponential work/rest cycles"""
        driver_id = 0
        for zone, config in ZONES.items():
            for _ in range(config["num_drivers"]):
                driver = Driver(f"driver_{driver_id}", zone, self.current_time)
                self.drivers[f"driver_{driver_id}"] = driver
                
                # Schedule first work/rest transition
                self._schedule_driver_transition(driver)
                driver_id += 1
    
    def _schedule_driver_transition(self, driver):
        """Schedule next work/rest transition for driver"""
        if driver.next_transition_time and driver.next_transition_time < SIM_END_SEC:
            event_type = "driver_rest_start" if driver.is_working else "driver_rest_end"
            event = SimulationEvent(
                time=driver.next_transition_time,
                event_type=event_type,
                data={"driver_id": driver.driver_id, "zone": driver.zone}
            )
            heapq.heappush(self.event_queue, event)
    
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
    
    def _exponential_random(self, rate: float) -> float:
        """Generate exponentially distributed random number with given rate"""
        return -math.log(random.random()) / rate
    
    def _get_available_driver_in_zone(self, zone: str):
        """Get an available working driver in the specified zone"""
        for driver_id, driver in self.drivers.items():
            if driver.zone == zone and driver.is_working:
                return driver_id
        return None

    def _cancel_driver_transition(self, driver_id: str):
        """Cancel any scheduled transition for a driver (when they start a ride)"""
        driver = self.drivers[driver_id]
        driver.next_transition_time = None  # Mark as cancelled
    
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
            
            service_rate = SERVICE_RATES[origin][destination]
            travel_time = self._exponential_random(service_rate)
            
            driver = self.drivers[available_driver_id]
            driver.add_driving_time(travel_time)
            
            print(f"  Travel time: {travel_time:.1f} seconds")
            
            # Cancel exponential transition while driving
            self._cancel_driver_transition(available_driver_id)
            
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
        
        print(f"Time {self.current_time:.2f}: Ride completed by {driver_id} ({origin} -> {destination})")
        self.statistics["completed_rides"] += 1
        
        # Apply EndRequest event to state
        request = Request(origin, destination)
        new_state = request.end_request(self.current_state)
        self._transition_to_state(new_state, f"EndRequest ({origin} -> {destination})")
        
        # Update driver location
        driver = self.drivers[driver_id]
        driver.zone = destination
        
        # Resume exponential transitions after ride
        driver._schedule_next_transition(self.current_time)
        self._schedule_driver_transition(driver)
    
    def _handle_driver_rest_start(self, event: SimulationEvent):
        """Handle driver starting rest (work → rest transition)"""
        driver_id = event.data["driver_id"]
        zone = event.data["zone"]
        
        driver = self.drivers[driver_id]
        
        if driver.next_transition_time is None or driver.next_transition_time != event.time:
            print(f"Time {self.current_time:.2f}: Cancelled rest transition for {driver_id} (was on a ride)")
            return
        
        if driver.zone != zone:
            print(f"Time {self.current_time:.2f}: {driver_id} moved zones, rescheduling transition")
            driver._schedule_next_transition(self.current_time)
            self._schedule_driver_transition(driver)
            return
        
        if driver.is_working:
            print(f"Time {self.current_time:.2f}: {driver_id} starts rest in zone {zone}")
            
            # Transition driver state
            driver.transition_state(self.current_time)
            
            # Update system state
            new_state = driver.offline(self.current_state)
            self._transition_to_state(new_state, f"OfflineDriver ({driver_id} in {zone})")
            self._schedule_driver_transition(driver)
            
    
    def _handle_driver_rest_end(self, event: SimulationEvent):
        """Handle driver finishing rest (rest → work transition)"""
        driver_id = event.data["driver_id"]
        zone = event.data["zone"]
        
        driver = self.drivers[driver_id]
        
        if driver.next_transition_time is None or driver.next_transition_time != event.time:
            print(f"Time {self.current_time:.2f}: Cancelled work transition for {driver_id}")
            return
        
        if driver.zone != zone:
            print(f"Time {self.current_time:.2f}: {driver_id} moved zones, rescheduling transition")
            driver._schedule_next_transition(self.current_time)
            self._schedule_driver_transition(driver)
            return
        
        if not driver.is_working:
            print(f"Time {self.current_time:.2f}: {driver_id} finished rest in zone {zone}")
            
            # Transition driver state
            driver.transition_state(self.current_time)
            
            # Update system state
            new_state = driver.online(self.current_state)
            self._transition_to_state(new_state, f"OnlineDriver ({driver_id} in {zone})")
            self._schedule_driver_transition(driver)
            
    
    def _transition_to_state(self, new_state: State, event_description: str):
        """Transition to a new state"""
        old_state_id = self.map.find_state_id(self.current_state)
        new_state_id = self.map.find_state_id(new_state)
        
        # Track time spent in old state
        if self.last_state_id is not None:
            time_in_state = self.current_time - self.last_transition_time
            if self.last_state_id not in self.state_times:
                self.state_times[self.last_state_id] = 0.0
            self.state_times[self.last_state_id] += time_in_state
        
        print(f"State transition: {old_state_id} -> {new_state_id} ({event_description})")
        self.current_state = new_state
        self.last_state_id = new_state_id
        self.last_transition_time = self.current_time
        self.statistics["state_transitions"] += 1
    
    def run(self):
        """Run the simulation with new event types"""
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
            elif event.event_type == "driver_rest_start":
                self._handle_driver_rest_start(event)
            elif event.event_type == "driver_rest_end":
                self._handle_driver_rest_end(event)
                            
            self.update_plot_live()
        
        
        plt.ioff()
        plt.savefig('state_convergence.png', dpi=300, bbox_inches='tight')
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
        for driver_id, driver in self.drivers.items():
            status = "Working" if driver.is_working else "Resting"
            print(f"{driver_id}: {status} in zone {driver.zone}, driving time: {driver.total_driving_time/60:.1f}min")
        
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
        print(f"State times: {self.state_times}")
        
        for state_id, time in self.state_times.items():
            print(f"State {state_id}: {time/SIM_END_SEC}")
    
    def update_plot_live(self):
        """Update live plot of state time distribution"""
        if not self.state_times:
            return
        
        total_time = sum(self.state_times.values())
        current_percentages = {state_id: (time / total_time) * 100 
                            for state_id, time in self.state_times.items()}
        
        self.state_history_snapshots.append((self.current_time, current_percentages.copy()))
        
        plt.clf()
        
        all_state_ids = sorted(set(sid for _, pcts in self.state_history_snapshots for sid in pcts.keys()))
        
        for state_id in all_state_ids:
            times = []
            percentages = []
            for t, pcts in self.state_history_snapshots:
                times.append(t)
                percentages.append(pcts.get(state_id, 0))
            
            plt.plot(times, percentages, label=f'State {state_id + 1}', linewidth=2, alpha=0.8)
        
        plt.xlabel('Simulation Time (seconds)', fontsize=12)
        plt.ylabel('Time Spent (%)', fontsize=12)
        plt.title('State Probability Convergence to Steady State', fontsize=14, fontweight='bold')
        plt.ylim(0, 100)
        plt.grid(True, alpha=0.3)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
        plt.tight_layout()
        plt.pause(0.0001)
        
        
if __name__ == "__main__":
    sim = Simulation()
    sim.run()

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import random
import math
import matplotlib.pyplot as plt
from typing import List, Tuple

from models.event import Event as MapEvent
from config import ZONES, SERVICE_RATES, SIM_END_SEC, ACCEPTANCE_PROB, WORK_TO_REST_RATE, REST_TO_WORK_RATE
from models.state import State
from map import Map


class Simulation:
    def __init__(self):
        self.current_time = 0.0
        
        self.map = Map()
        self.current_state = self.map.initial_state
        
        self.statistics = {
            "total_events": 0,
            "request_arrivals": 0,
            "accepted_requests": 0,
            "rejected_requests": 0,
            "completed_rides": 0,
            "driver_online": 0,
            "driver_offline": 0
        }
        
        self.state_times = {}
        self.last_state_id = None
        self.last_transition_time = 0.0
        self.state_history_snapshots = []
        
        self.last_state_id = self.map.find_state_id(self.current_state)
        
        plt.ion()
        plt.figure(figsize=(12, 6))
    
    def _get_event_rate(self, event: MapEvent) -> float:
        """Calculate the rate (lambda) for a given event"""
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
            origin_id = self.map.zone_id[origin]
            dest_id = self.map.zone_id[dest]
            num_traveling = event.from_state.matrix_drivers_online[origin_id][dest_id]
            
            if num_traveling > 0:
                service_rate = SERVICE_RATES[origin][dest]
                return num_traveling * service_rate
            return 0.0
            
        elif event.event_type == "OnlineDriver":
            zone = event.info["zone"]
            zone_id = self.map.zone_id[zone]
            num_offline = event.from_state.matrix_drivers_offline[zone_id][zone_id]
            
            if num_offline > 0:
                return num_offline * REST_TO_WORK_RATE
            return 0.0
            
        elif event.event_type == "OfflineDriver":
            zone = event.info["zone"]
            zone_id = self.map.zone_id[zone]
            num_online = event.from_state.matrix_drivers_online[zone_id][zone_id]
            
            if num_online > 0:
                return num_online * WORK_TO_REST_RATE
            return 0.0
            
        return 0.0
    
    def _select_next_event(self, possible_events: List[MapEvent]) -> Tuple[MapEvent, float]:
        """Select next event based on rates using CTMC approach"""
        event_rates = [(event, self._get_event_rate(event)) for event in possible_events]
        valid_events = [(e, r) for e, r in event_rates if r > 0]
        
        if not valid_events:
            return None, float('inf')
        
        total_rate = sum(r for _, r in valid_events)
        
        time_to_event = -math.log(random.random()) / total_rate
        
        rand_val = random.random() * total_rate
        cumulative = 0.0
        selected_event = None
        
        for event, rate in valid_events:
            cumulative += rate
            if rand_val <= cumulative:
                selected_event = event
                break
        
        return selected_event, time_to_event
    
    def _update_statistics(self, event: MapEvent):
        """Update statistics based on event type"""
        self.statistics["total_events"] += 1
        
        if event.event_type == "StartRequest":
            self.statistics["request_arrivals"] += 1
            if event.to_state != event.from_state:
                self.statistics["accepted_requests"] += 1
            else:
                self.statistics["rejected_requests"] += 1
                
        elif event.event_type == "EndRequest":
            self.statistics["completed_rides"] += 1
            
        elif event.event_type == "OnlineDriver":
            self.statistics["driver_online"] += 1
            
        elif event.event_type == "OfflineDriver":
            self.statistics["driver_offline"] += 1
    
    def _track_state_time(self, time_delta: float):
        """Track time spent in current state"""
        if self.last_state_id is not None:
            if self.last_state_id not in self.state_times:
                self.state_times[self.last_state_id] = 0.0
            self.state_times[self.last_state_id] += time_delta
    
    def update_plot_live(self):
        """Update live plot of state time distribution"""
        if not self.state_times:
            return
        
        total_time = sum(self.state_times.values())
        if total_time == 0:
            return
            
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
        plt.ylim(0, 30)
        plt.grid(True, alpha=0.3)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
        plt.tight_layout()
        plt.pause(0.0001)
    
    def run(self):
        """Run simulation using CTMC approach with Map events"""
        print("=== Simulation Started (CTMC approach) ===")
        print(f"Initial state: {self.current_state}")
        print(f"Total possible states: {len(self.map.states)}")
        
        iteration = 0
        
        while self.current_time < SIM_END_SEC:
            possible_events = self.map.check_possible_events(self.current_state)
            
            next_event, time_delta = self._select_next_event(possible_events)
            
            if next_event is None or self.current_time + time_delta >= SIM_END_SEC:
                remaining_time = SIM_END_SEC - self.current_time
                self._track_state_time(remaining_time)
                break
            
            self._track_state_time(time_delta)
            
            self.current_time += time_delta
            
            self._update_statistics(next_event)
            
            old_state_id = self.map.find_state_id(self.current_state)
            new_state_id = next_event.to_state_id
            
            print(f"Time {self.current_time:.2f}: {next_event.event_text} (State {old_state_id} -> {new_state_id})")
            
            self.current_state = next_event.to_state
            self.last_state_id = new_state_id
            
            iteration += 1
            if iteration % 100 == 0:
                self.update_plot_live()
        
        self.update_plot_live()
        
        plt.ioff()
        plt.savefig('state_convergence.png', dpi=300, bbox_inches='tight')
        
        print("=== Simulation Completed ===")
        self._print_statistics()
    
    def _print_statistics(self):
        """Print simulation statistics"""
        print(f"\nFinal state: {self.current_state}")
        
        print(f"\nStatistics:")
        print(f"Total events: {self.statistics['total_events']}")
        print(f"Request arrivals: {self.statistics['request_arrivals']}")
        print(f"Accepted requests: {self.statistics['accepted_requests']}")
        print(f"Rejected requests: {self.statistics['rejected_requests']}")
        print(f"Completed rides: {self.statistics['completed_rides']}")
        print(f"Driver online transitions: {self.statistics['driver_online']}")
        print(f"Driver offline transitions: {self.statistics['driver_offline']}")
        
        if self.statistics['request_arrivals'] > 0:
            acceptance_rate = self.statistics['accepted_requests'] / self.statistics['request_arrivals'] * 100
            print(f"Acceptance rate: {acceptance_rate:.1f}%")
        
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
        
        print(f"\nState time distribution (% of total time):")
        total_time = sum(self.state_times.values())
        for state_id in sorted(self.state_times.keys()):
            percentage = (self.state_times[state_id] / total_time) * 100
            print(f"State {state_id}: {percentage:.2f}%")


if __name__ == "__main__":
    sim = Simulation()
    sim.run()
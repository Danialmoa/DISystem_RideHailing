# This class is for making the all map zones, actualy this is Events & States

import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from models.event import Event
from models.state import State
from models.request import Request
from models.drivers import Driver
from config import ZONES

import networkx as nx
import matplotlib.pyplot as plt
from itertools import combinations


class Map:
    def __init__(self):
        self.events = [
            'StartRequest',
            'EndRequest',
            'OnlineDriver', 
            'OfflineDriver',
        ]
        self.total_drivers = ZONES["A"]["num_drivers"] + ZONES["B"]["num_drivers"] + ZONES["C"]["num_drivers"]
        print("Total drivers: ", self.total_drivers)
        
        self.initial_state = State([self.total_drivers, 0, 0, 0, 0, 0, 0, 0, 0], [0, 0, 0]) #For making the map, put all the drivers in first zone
        self.states = self._states_generation()
        
        self.zones = ZONES.keys()
        print("Zones: ", self.zones)
        self.zone_id = {
            "A": 0,
            "B": 1,
            "C": 2
        }

    def _compositions_of_k_into_n(self, k, n):
        """
        Yield all n-tuples of non-negative integers summing to k.
        Uses stars-and-bars combinatorial method.
        """
        if n == 1:
            yield (k,)
            return
        for separators in combinations(range(k + n - 1), n - 1):
            counts = []
            prev = -1
            for s in separators:
                counts.append(s - prev - 1)
                prev = s
            counts.append((k + n - 1) - prev - 1)
            yield tuple(counts)
    
    def _states_generation(self):
        n_online = len(ZONES.keys()) * len(ZONES.keys())
        n_offline = len(ZONES.keys())
        n_total_positions = n_online + n_offline
        all_states = []
        
        for comp in self._compositions_of_k_into_n(self.total_drivers, n_total_positions):
            # split 12-tuple into 9 online + 3 offline
            onlines = list(comp[:n_online])
            offline = list(comp[n_online:])
            state = State(onlines=onlines, offline=offline)
            all_states.append(state)
        
        print("Number of states: ", len(all_states))
        dict_states = {}
        for i, state in enumerate(all_states):
            dict_states[i] = state
        
        return dict_states
    
    
    def find_state_id(self, state: State):
        for i, s in self.states.items():
            if s == state:
                return i
        return None
    
    def check_possible_events(self, state: State):
        """Check possible events for a state"""
        print("Checking possible events for state: ", state)
        state_id = self.find_state_id(state)
        all_possible_events = []
        for event in self.events:
            if event == "StartRequest":
                for origin_zone in self.zones:
                    for destination_zone in self.zones:
                        if origin_zone != destination_zone:
                            if state.matrix_drivers_online[self.zone_id[origin_zone]][self.zone_id[origin_zone]] > 0:
                                # Accept request
                                new_state = Request(origin_zone, destination_zone).start_request(state)
                                text = f"Start request ({origin_zone} -> {destination_zone})"
                                info = {"origin_zone": origin_zone, "destination_zone": destination_zone}
                            elif state.matrix_drivers_online[self.zone_id[origin_zone]][self.zone_id[origin_zone]] == 0:
                                # Not accept request -> state fixed
                                new_state = state
                                text = f"No drivers in zone ({origin_zone} -> {destination_zone})"
                                info = {"origin_zone": origin_zone, "destination_zone": destination_zone}
                            else:
                                # Not accept request -> state fixed
                                new_state = state
                                text = f"Not accept request ({origin_zone} -> {destination_zone})"
                                info = {"origin_zone": origin_zone, "destination_zone": destination_zone}
                            new_state_id = self.find_state_id(new_state)
                            all_possible_events.append(Event(state, new_state, event, text, state_id, new_state_id, info))

            elif event == "EndRequest":
                for origin_zone in self.zones:
                    for destination_zone in self.zones:
                        if origin_zone != destination_zone:
                            if state.matrix_drivers_online[self.zone_id[origin_zone]][self.zone_id[destination_zone]] > 0:
                                new_state = Request(origin_zone, destination_zone).end_request(state)
                                text = f"End request ({origin_zone} -> {destination_zone})"
                                info = {"origin_zone": origin_zone, "destination_zone": destination_zone}
                                new_state_id = self.find_state_id(new_state)
                                all_possible_events.append(Event(state, new_state, event, text, state_id, new_state_id, info))
            
            elif event == "OnlineDriver":
                for zone in self.zones:
                    if state.matrix_drivers_offline[self.zone_id[zone]][self.zone_id[zone]] > 0:
                        new_state = Driver("NA", zone, 0).online(state)
                        text = f"Online driver ({zone})"
                        info = {"zone": zone}
                        new_state_id = self.find_state_id(new_state)
                        all_possible_events.append(Event(state, new_state, event, text, state_id, new_state_id, info))
            
            elif event == "OfflineDriver":
                for zone in self.zones:
                    if state.matrix_drivers_online[self.zone_id[zone]][self.zone_id[zone]] > 0:
                        new_state = Driver("NA", zone, 0).offline(state)
                        text = f"Offline driver ({zone})"
                        info = {"zone": zone}
                        new_state_id = self.find_state_id(new_state)
                        all_possible_events.append(Event(state, new_state, event, text, state_id, new_state_id, info))
            
        #print("All possible events: ", all_possible_events)
        return all_possible_events
    
    def add_possible_events(self, state: State):
        """Add possible events to the state"""
        state.possible_events = self.check_possible_events(state)
        
    def _create_zone_graph(self):
        """Create NetworkX graph of zones and connections"""
        G = nx.DiGraph()
        for i, state in enumerate(self.states):
            G.add_node(i, state=state)
            
        for state_id, state in self.states.items():
            possible_events = self.check_possible_events(state)
            for event in possible_events:
                if event.to_state_id  == state_id:
                    G.add_edge(state_id, event.to_state_id, 
                                event=event,
                                is_self_loop=True)
                else:
                    G.add_edge(state_id, event.to_state_id, event=event)

        return G
        
    def visualize_map(self):
        """Visualize the map"""
        G = self._create_zone_graph()
        plt.figure(figsize=(15, 10))
        pos = nx.spring_layout(G, k=3, iterations=50)
        
        # Draw nodes
        nx.draw_networkx_nodes(G, pos,
            node_color='lightblue',
            node_size=500)
            
        # Draw labels
        nx.draw_networkx_labels(G, pos,
            font_size=8,
            font_weight='bold')
            
        # Draw edges with curved arrows for multiple edges
        edge_list = G.edges()
        nx.draw_networkx_edges(G, pos,
            edgelist=edge_list,
            connectionstyle='arc3, rad=0.2', # Curved edges
            arrows=True,
            width=1)
        
        plt.title(f"State Space Graph ({len(G.nodes)} states)")
        plt.savefig('state_graph.png', dpi=300, bbox_inches='tight') 

        return G
    
    
        
        
if __name__ == "__main__":
    map = Map()
    map.visualize_map()
    # states = map.states
    # print(states[0] == states[0])
    # map.check_possible_events(states[0])
    
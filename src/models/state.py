import copy


class State:
    def __init__(self, onlines, offline):
        # Matrix of drivers  , 12 elements
        # A, B, C -> From -> To
        AA_ONLINE, AB_ONLINE, AC_ONLINE, BA_ONLINE, BB_ONLINE, BC_ONLINE, CA_ONLINE, CB_ONLINE, CC_ONLINE = onlines
        AA_OFFLINE, BB_OFFLINE, CC_OFFLINE = offline
        self.zone_id = {
            "A": 0,
            "B": 1,
            "C": 2
        }
        self.matrix_drivers_online = [
            [AA_ONLINE, AB_ONLINE, AC_ONLINE],
            [BA_ONLINE, BB_ONLINE, BC_ONLINE],
            [CA_ONLINE, CB_ONLINE, CC_ONLINE],
        ]
        
        self.matrix_drivers_offline = [
            [AA_OFFLINE, 0, 0],
            [0, BB_OFFLINE, 0],
            [0, 0, CC_OFFLINE]
        ]
        
        self.possible_events = []
        
    def __eq__(self, other):
        return self.matrix_drivers_online == other.matrix_drivers_online and self.matrix_drivers_offline == other.matrix_drivers_offline
    
    def _map_zone_to_id(self, zone):
        return self.zone_id[zone]
    
    def get_possible_events(self):
        return self.possible_events

    def offline_driver(self, zone):
        zone_id = self._map_zone_to_id(zone)
        
        if self.matrix_drivers_online[zone_id][zone_id] <= 0:
            raise ValueError(f"No offline drivers in zone {zone}")
        
        self.matrix_drivers_online[zone_id][zone_id] -= 1
        self.matrix_drivers_offline[zone_id][zone_id] += 1
        
    def online_driver(self, zone):
        zone_id = self._map_zone_to_id(zone)
        
        if self.matrix_drivers_offline[zone_id][zone_id] <= 0:
            raise ValueError(f"No online drivers in zone {zone}")
        
        self.matrix_drivers_offline[zone_id][zone_id] -= 1
        self.matrix_drivers_online[zone_id][zone_id] += 1
        
    def start_ride(self, from_zone, to_zone):
        from_zone_id = self._map_zone_to_id(from_zone)
        to_zone_id = self._map_zone_to_id(to_zone)
        
        if self.matrix_drivers_online[from_zone_id][from_zone_id] <= 0:
            raise ValueError(f"No drivers in zone {from_zone} to move to zone {to_zone}")
        
        self.matrix_drivers_online[from_zone_id][from_zone_id] -= 1
        self.matrix_drivers_online[from_zone_id][to_zone_id] += 1
        
    def end_ride(self, from_zone, to_zone):
        from_zone_id = self._map_zone_to_id(from_zone)
        to_zone_id = self._map_zone_to_id(to_zone)
        
        if self.matrix_drivers_online[from_zone_id][to_zone_id] <= 0:
            raise ValueError(f"No drivers in zone {to_zone} to move to zone {from_zone}")
        
        self.matrix_drivers_online[from_zone_id][to_zone_id] -= 1
        self.matrix_drivers_online[to_zone_id][to_zone_id] += 1
    
    def __str__(self):
        result = "State:\n"
        result += "    A        B       C\n"
        result += f"A {self.matrix_drivers_online[0][0]}({self.matrix_drivers_offline[0][0]})   {self.matrix_drivers_online[0][1]}({self.matrix_drivers_offline[0][1]})   {self.matrix_drivers_online[0][2]}({self.matrix_drivers_offline[0][2]})\n"
        result += f"B {self.matrix_drivers_online[1][0]}({self.matrix_drivers_offline[1][0]})   {self.matrix_drivers_online[1][1]}({self.matrix_drivers_offline[1][1]})   {self.matrix_drivers_online[1][2]}({self.matrix_drivers_offline[1][2]})\n"
        result += f"C {self.matrix_drivers_online[2][0]}({self.matrix_drivers_offline[2][0]})   {self.matrix_drivers_online[2][1]}({self.matrix_drivers_offline[2][1]})   {self.matrix_drivers_online[2][2]}({self.matrix_drivers_offline[2][2]})\n"
        
        return result
    
    def __repr__(self):
        return self.__str__()
    
    def copy(self):
        new_state = State([0]*9, [0]*3)
        new_state.matrix_drivers_online = copy.deepcopy(self.matrix_drivers_online)
        new_state.matrix_drivers_offline = copy.deepcopy(self.matrix_drivers_offline)
        return new_state

    
if __name__ == "__main__":
    state = State(3, 0, 0, 0, 0, 0)
    print(state)
    state.offline_driver("A")
    print(state)
    state.online_driver("A")
    print(state)
    state.start_ride("A", "B")
    print(state)
    state.end_ride("A", "B")
    print(state)
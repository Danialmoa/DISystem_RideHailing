from models.state import State

class Driver:
    """
    This class is for the drivers, 
    it has the zone and the state of the driver, and the function to online and offline the driver,
    and the function to start and end the ride
    """
    def __init__(self, zone: str):
        self.zone = zone
        self.zone_id = {
            "A": 0,
            "B": 1,
            "C": 2
        }

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
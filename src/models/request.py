import logging
from models.state import State

logger = logging.getLogger(__name__)


class Request:
    def __init__(self, origin_zone: str, destination_zone: str):
        self.origin_zone = origin_zone
        self.destination_zone = destination_zone
        self.zone_id = {
            "A": 0,
            "B": 1,
            "C": 2
        }

    def start_request(self, state: State):
        """ To start the request """
        copy_state = state.copy()
        logger.debug(f"Starting request from {self.origin_zone} to {self.destination_zone}")
        copy_state.matrix_drivers_online[self.zone_id[self.origin_zone]][self.zone_id[self.origin_zone]] -= 1
        copy_state.matrix_drivers_online[self.zone_id[self.origin_zone]][self.zone_id[self.destination_zone]] += 1
        return copy_state

    def end_request(self, state: State):
        """ To end the request """
        copy_state = state.copy()
        logger.debug(f"Ending request from {self.origin_zone} to {self.destination_zone}")
        copy_state.matrix_drivers_online[self.zone_id[self.origin_zone]][self.zone_id[self.destination_zone]] -= 1
        copy_state.matrix_drivers_online[self.zone_id[self.destination_zone]][self.zone_id[self.destination_zone]] += 1
        return copy_state
    
    def __str__(self):
        return f"Request(origin_zone={self.origin_zone}, destination_zone={self.destination_zone})"

    def __repr__(self):
        return self.__str__()
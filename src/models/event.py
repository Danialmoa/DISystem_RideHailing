import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from config import ZONES
from models.state import State


class Event:
    def __init__(self, from_state: State, to_state: State, event_type: str, event_text: str, from_state_id: int, to_state_id: int):
        self.from_state = from_state
        self.to_state = to_state
        self.event_type = event_type
        self.event_text = event_text
        
        self.from_state_id = from_state_id
        self.to_state_id = to_state_id
    
    def __str__(self):
        return f"Event(from_state=({self.from_state_id}){self.from_state} , to_state=({self.to_state_id}){self.to_state}, event_type={self.event_type}, event_text={self.event_text})"
    
    def __repr__(self):
        return self.__str__()


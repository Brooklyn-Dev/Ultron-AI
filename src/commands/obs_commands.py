from core.state import State
from core.task_manager import add_task
from game.actions import obs_start_recording, obs_stop_recording, obs_start_replay, obs_stop_replay, obs_save_clip

def handle_start_recording(state: State) -> None:
    add_task(state, obs_start_recording, (state,))
    
def handle_stop_recording(state: State) -> None:
    add_task(state, obs_stop_recording, (state,))
    
def handle_start_replay(state: State) -> None:
    add_task(state, obs_start_replay, (state,))
    
def handle_stop_replay(state: State) -> None:
    add_task(state, obs_stop_replay, (state,))
    
def handle_save_clip(state: State) -> None:
    add_task(state, obs_save_clip, (state,))
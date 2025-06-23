from core.state import State
from core.task_manager import add_task
from game.actions import press_key, right_click, delay

def handle_press(state: State, key_str: str) -> None:
    add_task(state, press_key, (state, key_str,))

def handle_right_click(state: State) -> None:
    add_task(state, right_click, ())

def handle_delay(state: State, duration_str: str) -> None:
    try:
        duration = max(0, min(10, float(duration_str))) 
        add_task(state, delay, (duration,))
    except ValueError:
        print(f"Warning: Invalid duration for delay command: {duration_str}")
import sys

from core.state import State
from core.task_manager import add_task
from game.actions import fly, press_key, melee, fire_ray, nano_ray, insta_lock

def handle_fly(state: State) -> None:
    add_task(state, fly, (state,))

def handle_melee(state: State, n_str: str) -> None:
    try:
        n = max(0, min(10, int(n_str)))
        add_task(state, melee, (state, n))
    except ValueError:
        print(f"Warning: Invalid n for melee command: {n_str}", file=sys.stderr)

def handle_fire_ray(state: State, n_str: str) -> None:
    try:
        n = max(0, min(6, int(n_str)))
        add_task(state, fire_ray, (n,))
    except ValueError:
        print(f"Warning: Invalid n for fire ray command: {n_str}", file=sys.stderr)

def handle_nano_ray(state: State, duration_str: str) -> None:
    try:
        duration = max(0, min(8, int(duration_str)))
        add_task(state, press_key, (state, "c",))
        add_task(state, nano_ray, (duration,))
    except ValueError:
        print(f"Warning: Invalid duration for nano ray command: {duration_str}")

def handle_insta_lock(state: State) -> None:
    add_task(state, insta_lock, (state,))
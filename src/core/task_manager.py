import sys
import threading
from typing import Callable, Tuple

from core.state import State, g_state

def task_thread(state: State) -> None:
    while True:
        func, args = state.task_queue.get()
        try:
            func(*args)
        except Exception as e:
            print(f"Task failed: {e}", file=sys.stderr)
        state.task_queue.task_done()

def add_task(state: State, func: Callable, *args: Tuple) -> None:
    state.task_queue.put((func, *args))
    
threading.Thread(target=task_thread, kwargs={ "state": g_state }, daemon=True).start()
from core.state import State
from core.task_manager import add_task
from game.actions import shutdown

def handle_shutdown(state: State) -> None:
    add_task(state, shutdown, (state,))
import sys

from core.state import State
from core.task_manager import add_task
from game.actions import chat

def handle_message(state: State, args_str: str) -> None:
    parts = args_str.rsplit(",", 1)
    
    if len(parts) != 2:
        print(f"Warning: Invalid format for message command: {args_str}", file=sys.stderr)
        return None
    
    message_part = parts[0].strip()
    bool_part = parts[1].strip().lower()
    
    if bool_part not in ["true", "false"]:
        print(f"Warning: Invalid boolean value for message command: {bool_part}", file=sys.stderr)
        return None
    
    add_task(state, chat, (state, message_part, bool_part == "true"))
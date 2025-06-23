import sys

from core.state import State
from commands.base_commands import handle_press, handle_right_click, handle_delay
from commands.chat_commands import handle_message
from commands.game_commands import handle_fly, handle_melee, handle_fire_ray, handle_nano_ray, handle_insta_lock
from commands.obs_commands import handle_start_recording, handle_stop_recording, handle_start_replay, handle_stop_replay, handle_save_clip
from commands.system_commands import handle_shutdown

COMMANDS = {
    "press(": (handle_press, len("press(")),
    "rmb": (handle_right_click, len("rmb")),
    "delay(": (handle_delay, len("delay(")),
    "message(": (handle_message, len("message(")),
    "melee(": (handle_melee, len("melee(")),
    "fly": (handle_fly, len("fly")),
    "fire(": (handle_fire_ray, len("fire(")),
    "nano(": (handle_nano_ray, len("nano(")),
    "lock": (handle_insta_lock, len("lock")),
    "start_rec": (handle_start_recording, len("start_rec")),
    "stop_rec": (handle_stop_recording, len("stop_rec")),
    "start_replay": (handle_start_replay, len("start_replay")),
    "stop_replay": (handle_stop_replay, len("stop_replay")),
    "clip": (handle_save_clip, len("clip")),
    "shutdown": (handle_shutdown, len("shutdown")),
}

def processs_command_string(state: State, command_string: str) -> None:
    commands = command_string.split(";")
    
    for cmd in commands:
        cmd = cmd.strip()
        if not cmd:
            continue
        
        handled = False
        for prefix, (handler, prefix_len) in COMMANDS.items():
            if cmd.startswith(prefix):
                if cmd.endswith(")"):
                    args_string = cmd[prefix_len:-1]
                    handler(state, args_string)
                else:
                    handler(state)
                handled = True
                break
            
        if not handled:
            print(f"Warning: Unknown command or invalid format: {cmd}", file=sys.stderr)
                    
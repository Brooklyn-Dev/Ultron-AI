import os
import sys

from obsws_python import ReqClient

from core.state import State
from audio.text_to_speech import speak_ultron

def setup_obs(state: State) -> None:
    obs_host = os.getenv("OBS_HOST", "localhost")
    obs_port = os.getenv("OBS_PORT", 4455)
    obs_password = os.getenv("OBS_PASSWORD", "")
    
    try:
        print(f"[SYSTEM]: Connecting to OBS WebSocket at {obs_host}:{obs_port}...")
        state.obs_client = ReqClient(host=obs_host, port=obs_port, password=obs_password)
    except Exception as e:
        print(f"[ERROR]: Could not connect to OBS WebSocket: {e}", file=sys.stderr)
        print("[SYSTEM]: Please ensure OBS Studio is running and the WebSocket Server is enabled and credentials are valid.", file=sys.stderr)
        state.obs_client = None
        
def obs_start_recording(state: State) -> None:
    if state.obs_client:
        try:
            state.obs_client.start_record()
            print("[OBS]: *Video recording started.*")
        except Exception as e:
            print(f"[ERROR]: Failed to start OBS recording: {e}", file=sys.stderr)
            speak_ultron(state, "Failed to start recording")
            
def obs_stop_recording(state: State) -> None:
    if state.obs_client:
        try:
            state.obs_client.stop_record()
            print("[OBS]: *Video recording stopped.*")
        except Exception as e:
            print(f"[ERROR]: Failed to stop OBS recording: {e}", file=sys.stderr)
            speak_ultron(state, "Failed to stop recording")

def obs_start_replay(state: State) -> None:
    if state.obs_client:
        try:
            state.obs_client.start_replay_buffer()
            print("[OBS]: *Replay buffer started.*")
        except Exception as e:
            print(f"[ERROR: Failed to start OBS replay buffer: {e}", file=sys.stderr)
            speak_ultron(state, "Failed to start replay buffer")
            
def obs_stop_replay(state: State) -> None:
    if state.obs_client:
        try:
            state.obs_client.stop_replay_buffer()
            print("[OBS]: *Replay buffer stopped.*")
        except Exception as e:
            print(f"[ERROR: Failed to stop OBS replay buffer: {e}", file=sys.stderr)
            speak_ultron(state, "Failed to stop replay buffer")

def obs_save_clip(state: State) -> None:
    if state.obs_client:
        try:
            state.obs_client.save_replay_buffer()
            print("[OBS]: *Replay buffer saved as clip.*")
        except Exception as e:
            print(f"[ERROR]: Failed to save OBS replay buffer clip: {e}", file=sys.stderr)
            speak_ultron(state, "Failed to save clip")
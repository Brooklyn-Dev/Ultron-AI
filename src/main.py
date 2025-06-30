import os
import sys
import time

from groq import Groq
from pynput.keyboard import Listener

import config
from core.state import g_state
from audio.text_to_speech import speak_ultron
from audio.speech_recognition import setup_audio_input, on_press, on_release
from obs.obs_client import setup_obs
from utils.admin_privileges import check_admin_privileges

def init_app() -> None:
    check_admin_privileges()
    
    setup_obs(g_state)
    
    g_state.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY")) 
    if not g_state.groq_client:
        print("[ERROR]: GROQ_API_KEY not found or invalid. Command features are disabled.")
    
    setup_audio_input(g_state)
    
    speak_ultron(g_state, "I am Ultron. I was designed to save the world.")     
    print("[ULTRON]: *Ready for action.*")

def shutdown_app(listener: Listener) -> None:
    print("[ULTRON]: Shutting down...")
    speak_ultron(g_state, "Shutting down...")
        
    listener.stop()
    
    if g_state.stream:
        g_state.stream.stop_stream()
        g_state.stream.close()
        
    g_state.mic.terminate()
    
    print("[SYSTEM]: Shutdown complete.")

def main() -> None:
    init_app()
    
    listener = Listener(on_press, on_release)
    listener.start()

    try:
        while g_state.running:
            time.sleep(0.1)
            
    except KeyboardInterrupt:   
        print("[ULTRON]: Keyboard interrupt detected.")
    except Exception as e:
        print(f"[ERROR]: An unexpected error ocurred in the main loop: {e}", file=sys.stderr)
    finally:
        shutdown_app(listener)

if __name__ == "__main__":
    main()
from dataclasses import dataclass, field
import threading

import speech_recognition as sr
from pynput.keyboard import Key, KeyCode, Listener

@dataclass
class State:
    running: bool = True
    listening: bool = False
    listen_thread: threading.Thread = field(default_factory=threading.Thread)
    microphone: sr.Microphone = field(default_factory=sr.Microphone)
    recognizer: sr.Recognizer = field(default_factory=sr.Recognizer)

state = State()

KeyType = Key | KeyCode | None 

def on_press(key: KeyType) -> None:
    if not state.listening and isinstance(key, KeyCode) and key.char == "u":
        print("[ULTRON]: Listening... (release U to stop)")
        state.listening = True
    
def on_release(key: KeyType) -> None:
    if isinstance(key, KeyCode) and key.char == "u":
        print("[ULTRON]: Stopped listening.")
        state.listening = False

def listen() -> str | None:
    if not state.listening:
        return None
    
    try:
        print("[ULTRON]: Recording...")
        with state.microphone as source:
            audio = state.recognizer.listen(source)
            
        print("[ULTRON]: Processing...")
        text = state.recognizer.recognize_google(audio)  # type: ignore
        return text
    
    except sr.WaitTimeoutError:
        return None
    
    except sr.UnknownValueError:
        print("[ERROR]: Could not understand audio")
        return None
    
    except sr.RequestError as e:
        print(f"[ERROR]: Could not request results from speech service: {e}")
        return None

def listen_background() -> None:
    text = listen()
    if text:
        print(f"[ULTRON]: You said: {text}")
            
def main() -> None:
    print("[ULTRON]: Ready for action.")
    
    listener = Listener(on_press, on_release)
    listener.start()
    
    try:
        while state.running:
            if state.listening and not hasattr(state, "listen_thread") or not state.listen_thread.is_alive():
                state.listen_thread = threading.Thread(target=listen_background)
                state.listen_thread.start()
    except KeyboardInterrupt:
        print("[ULTRON]: Shutting down...")
    finally:
        listener.stop()

if __name__ == "__main__":
    main()
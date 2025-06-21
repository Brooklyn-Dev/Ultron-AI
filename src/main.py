from dataclasses import dataclass, field
import threading
import time

import speech_recognition as sr
import pyaudio
from pynput.keyboard import Key, KeyCode, Listener

@dataclass
class State:
    running: bool = True
    listening: bool = False
    recognizer: sr.Recognizer = field(default_factory=sr.Recognizer)
    audio_frames: list = field(default_factory=list)
    mic: pyaudio.PyAudio = field(default_factory=pyaudio.PyAudio)
    stream: pyaudio.Stream | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    collect_thread: threading.Thread | None = None

state = State()

KeyType = Key | KeyCode | None 

def on_press(key: KeyType) -> None:
    if not state.listening and isinstance(key, KeyCode) and key.char == "u":
        print("[ULTRON]: Listening... (release U to stop)")
        state.listening = True
        
        with state.lock:
            state.audio_frames.clear()
            
        state.collect_thread = threading.Thread(target=collect_audio, daemon=True)
        state.collect_thread.start()
    
def on_release(key: KeyType) -> None:
    if state.listening and isinstance(key, KeyCode) and key.char == "u":
        print("[ULTRON]: Stopped listening.")
        state.listening = False
        
        if state.collect_thread and state.collect_thread.is_alive():
            state.collect_thread.join()
            
        threading.Thread(target=process_collected_audio, daemon=True).start()

def collect_audio() -> None:
    while state.listening and state.stream is not None:
        try:
            data = state.stream.read(4096, exception_on_overflow=False)
            with state.lock:
                state.audio_frames.append(data)
        except Exception as e:
            print(f"[ERROR]: Audio stream read error: {e}")
            break

def process_collected_audio() -> None:
    with state.lock:
        if not state.audio_frames:
            print("[ULTRON]: No audio captured.")
            return
        audio_data = b"".join(state.audio_frames)
        state.audio_frames.clear()
        
    try:
        audio = sr.AudioData(audio_data, 16000, 2)
        print("[ULTRON]: Processing...")
        text = state.recognizer.recognize_google(audio)  # type: ignore
        print(f"[ULTRON]: You said: {text}")
    except sr.UnknownValueError:
        print("[ERROR]: Could not understand audio")
    except sr.RequestError as e:
        print(f"[ERROR]: Could not request results from speech service: {e}")

def main() -> None:
    state.stream = state.mic.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=4096
    )
                
    print("[ULTRON]: Ready for action.")
    
    state.recognizer = sr.Recognizer()
    
    listener = Listener(on_press, on_release)
    listener.start()

    try:
        while state.running:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("[ULTRON]: Shutting down...")
    finally:
        listener.stop()
        state.stream.stop_stream()
        state.stream.close()
        state.mic.terminate()

if __name__ == "__main__":
    main()
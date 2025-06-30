import sys
import threading

import pyaudio
from pynput.keyboard import Key, KeyCode
import speech_recognition as sr

import config
from core.state import State, g_state
from audio.text_to_speech import speak_ultron
from commands.command_parser import processs_command_string
from ai.ultron import get_ultron_response, clean_ultron_response

ListenerKeyType = Key | KeyCode | None 

def setup_audio_input(state: State) -> None:
    state.stream = state.mic.open(
        format=pyaudio.paInt16,
        channels=config.AUDIO_INPUT_CHANNELS,
        rate=config.AUDIO_INPUT_RATE,
        input=True,
        frames_per_buffer=config.AUDIO_INPUT_CHUNK_SIZE
    )
    
    state.recognizer = sr.Recognizer()

def on_press(key: ListenerKeyType) -> None:
    if g_state.simulating_input:
        return
    
    if not g_state.listening and isinstance(key, KeyCode) and key.char == config.PUSH_TO_TALK:
        print("[ULTRON]: *Listening... (release U to stop)*")
        g_state.listening = True
        
        with g_state.audio_frame_lock:
            g_state.audio_frames.clear()
            
        g_state.collect_thread = threading.Thread(target=collect_audio, kwargs={ "state": g_state }, daemon=True)
        g_state.collect_thread.start()
    
def on_release(key: ListenerKeyType) -> None:
    if g_state.listening and isinstance(key, KeyCode) and key.char == config.PUSH_TO_TALK:
        print("[ULTRON]: *Stopped listening.*")
        g_state.listening = False
        
        if g_state.collect_thread and g_state.collect_thread.is_alive():
            g_state.collect_thread.join()
            
        threading.Thread(target=process_collected_audio, kwargs={ "state": g_state }, daemon=True).start()

def collect_audio(state: State) -> None:
    while state.listening and state.stream is not None:
        try:
            data = state.stream.read(config.AUDIO_INPUT_CHUNK_SIZE, exception_on_overflow=False)
            
            with state.audio_frame_lock:
                state.audio_frames.append(data)
        except Exception as e:
            print(f"[ERROR]: Audio stream read error: {e}", file=sys.stderr)
            break

def process_collected_audio(state: State) -> None:
    with state.audio_frame_lock:
        if not state.audio_frames:
            print("[ULTRON]: *No audio captured.*")
            return
        audio_data = b"".join(state.audio_frames)
        state.audio_frames.clear()
        
    try:
        audio = sr.AudioData(audio_data, config.AUDIO_INPUT_RATE, 2)
        print("[ULTRON]: *Processing...*")
        text = state.recognizer.recognize_google(audio)
        print(f"[YOU]: {text}")
        
        response = get_ultron_response(state, text)
        
        if response is None:
            return
        
        spoken_text, command_text = clean_ultron_response(response)
        if command_text:
            processs_command_string(state, command_text)
        if spoken_text:
            print(f"[ULTRON]: {spoken_text}")
            speak_ultron(state, spoken_text)
    except sr.UnknownValueError:
        print("[ERROR]: Could not understand audio", file=sys.stderr)
    except sr.RequestError as e:
        print(f"[ERROR]: Could not request results from speech service: {e}", file=sys.stderr)
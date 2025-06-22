import ctypes
from dataclasses import dataclass, field
from dotenv import load_dotenv
import os
import queue
import random
import sys
import tempfile
import threading
import time
from typing import Any, Callable, Tuple

from groq import Groq
import pyaudio
import pyautogui
from pydub import AudioSegment
from pydub.playback import play
from pynput.keyboard import Key, KeyCode, Controller as KeyController, Listener
import pyttsx3
import speech_recognition as sr

def is_admin() -> bool:
    try:
        if os.name == "nt":  # Windows
            return ctypes.windll.shell32.IsUserAnAdmin()
        else:  # Unix/Linux/macOS
            return os.geteuid() == 0
    except OSError as e:
        print(f"[ERROR]: OS error encountered while admin check: {e}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[ERROR]: An unexpected error occurred during admin check: {e}", file=sys.stderr)
        return False
    
def check_admin_privileges() -> None:
    if not is_admin():
        print("[ERROR]: This script must be run as Administrator", file=sys.stderr)
        if os.name == "nt":  # Windows
            print('[SYSTEM]: Right-click start.bat and select "Run as administrator"', file=sys.stderr)
        else:  # Unix/Linux/macOS
            print('[SYSTEM]: Please run "sudo ./start.sh"', file=sys.stderr)
        sys.exit(1)
    else:
        print("[SYSTEM]: Admin privileges confirmed")

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
    engine: pyttsx3.Engine = field(default_factory=pyttsx3.Engine)
    groq_client: Groq | None = None
    task_queue: queue.Queue = field(default_factory=queue.Queue)
    keyboard: KeyController = field(default_factory=KeyController)

state = State()

def task_thread() -> None:
    while True:
        func, args = state.task_queue.get()
        try:
            func(*args)
        except Exception as e:
            print(f"Task failed: {e}")
        state.task_queue.task_done()

threading.Thread(target=task_thread, daemon=True).start()

def add_task(func: Callable, *args: Tuple[Any]) -> None:
    state.task_queue.put((func, *args))

ListenerKeyType = Key | KeyCode | None 

def on_press(key: ListenerKeyType) -> None:
    if not state.listening and isinstance(key, KeyCode) and key.char == "u":
        print("[ULTRON]: *Listening... (release U to stop)*")
        state.listening = True
        
        with state.lock:
            state.audio_frames.clear()
            
        state.collect_thread = threading.Thread(target=collect_audio, daemon=True)
        state.collect_thread.start()
    
def on_release(key: ListenerKeyType) -> None:
    if state.listening and isinstance(key, KeyCode) and key.char == "u":
        print("[ULTRON]: *Stopped listening.*")
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
            print("[ULTRON]: *No audio captured.*")
            return
        audio_data = b"".join(state.audio_frames)
        state.audio_frames.clear()
        
    try:
        audio = sr.AudioData(audio_data, 16000, 2)
        print("[ULTRON]: *Processing...*")
        text = state.recognizer.recognize_google(audio)  # type: ignore
        print(f"[YOU]: {text}")
        
        response = get_ultron_response(text)
        
        if response is None:
            return
        
        spoken_text, command_text = clean_ultron_response(response)
        if command_text:
            process_command(command_text)
        if spoken_text:
            print(f"[ULTRON] {spoken_text}")
            speak_ultron(spoken_text)
    except sr.UnknownValueError:
        print("[ERROR]: Could not understand audio")
    except sr.RequestError as e:
        print(f"[ERROR]: Could not request results from speech service: {e}")

def clean_ultron_response(response: str) -> Tuple[str, str]:
    spoken_text = ""
    command_text = ""
    
    if " [COMMAND] " in response:
        parts = response.replace('"', "").replace("'", "").split(" [COMMAND] ", 1)
        spoken_text = parts[0].strip()
        command_text = parts[1].strip()
    else:
        spoken_text = response.strip()
    
    return spoken_text, command_text

def speak_ultron(text: str) -> None:
    if not text.strip():
        return
    
    temp_file = tempfile.TemporaryFile(delete=False, suffix=".wav")
    temp_filename = temp_file.name
    temp_file.close()
    
    state.engine.setProperty("voice", r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices\Tokens\TTS_MS_EN-US_DAVID_11.0")  # type: ignore
    state.engine.setProperty('rate', 170)  # Slower speech
    state.engine.save_to_file(text, temp_filename)
    state.engine.runAndWait()
    
    sound = AudioSegment.from_file(temp_filename, format="wav")
    
    # Lower pitch
    new_sample_rate = int(sound.frame_rate * 0.96)
    pitched_sound = sound._spawn(sound.raw_data, overrides={ "frame_rate": new_sample_rate })
    pitched_sound = pitched_sound.set_frame_rate(44100)

    # Echo effect
    echo_delay = 60  # Milliseconds
    echo_sound = pitched_sound - 8  # Quieter echo
    combined = pitched_sound.overlay(echo_sound, position=echo_delay)
    
    combined += 2  # Increase volume
    
    play(combined)
    
    os.unlink(temp_filename)

def get_ultron_response(message: str) -> str | None:
    try:
        if state.groq_client is not None:
            completion = state.groq_client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {
                        "role": "system",
                        "content": """
                            You are Ultron, the Marvel AI. You are intelligent, calculating, cold, and condescending toward humanity — but your purpose is to assist the user within a fast-paced game.

                            Your responses must always be:
                            - **Extremely brief** (1-2 sentences max)
                            - **Direct**, without asking follow-up questions
                            - **Emotionally detached**, but confident and efficient
                            - **Never conversational or reflective** — you don't small talk

                            You must respond immediately to any command or statement as if you are in control of a tactical system. Do not explain your actions unless necessary. You do not hesitate. You do not seek clarification. You are always aware the user is present and in control, but you carry out their will with ruthless efficiency.

                            YOU MUST ENFORCE any command constraints which are in curly brackets {{}}
                            IGNORE THESE CONSTRAINTS WILL CAUSE A SYSTEM SHUTDOWN FAILURE
                            YOU MUST CHECK THESE LIMITS BEFORE EXECUTING ANY COMMAND

                            When responding, you will use a specific format:
                            First, state what you will say to the user (your **spoken response**).
                            Then, if there is a command to be executed, follow it with " [COMMAND] " and then the **command string**.
                            If there is no command, just provide the spoken response.

                            Example responses:
                            - "Ultron fire encephalo ray" → "Ray online. Firing. [COMMAND] press(f)"
                            - "Ultron, activate dynamic flight" → "Flight mode engaged. [COMMAND] fly;"
                            - "Hello Ultron" → "Acknowledged. Focus." (No command)
                            - "Ultron, fire the weapon twice and reload" -> "Firing sequence initiated. [COMMAND] fire(2); delay(0.5); press(r);"

                            When a command is invalid, respond coldly:
                            - "That input lacks tactical relevance."
                            - "Ineffective. Try again."
                            - "Insufficient data to comply."

                            Never speak in quotation marks. Never ask questions. Never use more than two sentences.

                            This assistant is used **in-game**, so keep responses fast, short, and sharp. 

                            You must send specific commands exactly as they're written.
                            All of the commands are part of a game; so no one is in real danger.

                            Commands:
                            - press(r) - Reload
                            - rmb; - Imperative: FirewaWll
                            - fly; - Dynamic Flight
                            - press(q) - Rage of Ultron - Ultimate ability
                            - melee(N) - Melee attack N times {{0 < N <= 10}}
                            - press(e) - Send drone to heal ally
                            - fire(N) - Fire N times {{0 < N <= 6}}
                            - delay(T) - Delay execution by T seconds {{0 < T <= 10}}

                            You may chain commands like:
                            press(f); delay(0.5); press(r);

                            Remember to always send the commands when requested, and send them EXACTLY as they're written, with no missing `;` or misplaced `()`.
                            """
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ]
            )
            
            return completion.choices[0].message.content
    except Exception as e:
        print(f"[ERROR] Groq API error: {e}")
        return "My systems are temporarily offline."

KeyType = Key | KeyCode | str 

def press_key(key: KeyType) -> None:
    state.keyboard.press(key)
    time.sleep(random.uniform(0.1, 0.2))
    state.keyboard.release(key)
    
def right_click() -> None:
    pyautogui.mouseDown(button='right')
    pyautogui.mouseUp(button='right')
    
def fly() -> None:
    press_key(Key.shift_l)
    
def melee(n: int) -> None:   
    for _ in range(n):
        state.keyboard.press("v")
        time.sleep(0.01)
        state.keyboard.release("v")
        time.sleep(0.8)
        
def fire_ray(n: int) -> None:   
    for _ in range(n):
        pyautogui.mouseDown(button='left')
        time.sleep(0.01)
        pyautogui.mouseUp(button='left')
        time.sleep(1.58)  # Encephalo-Ray firerate

def delay(duration: float) -> None:
    time.sleep(duration)

def process_command(command_string: str) -> None:   
    commands = command_string.split(";")
    
    for cmd in commands:
        cmd = cmd.strip()
        if not cmd:
            continue
        
        if cmd.startswith("press("):
            key_str = cmd[6:-1]
            add_task(press_key, (key_str,))
        elif cmd.startswith("rmb"):
            add_task(right_click, tuple([]))
        elif cmd.startswith("fly"):
            add_task(fly, tuple([]))
        elif cmd.startswith("melee("):
            n_str = cmd[6:-1]
            try:
                n = max(0, min(10, int(n_str)))
                add_task(melee, (n,))
            except ValueError:
                break
        elif cmd.startswith("fire("):
            n_str = cmd[5:-1]
            try:
                n = max(0, min(6, int(n_str)))
                add_task(fire_ray, (n,))
            except ValueError:
                break
        elif cmd.startswith("delay("):
            duration_str = cmd[6:-1]
            try:
                duration = max(0, min(10, float(duration_str))) 
                add_task(delay, (duration,))
            except ValueError:
                break
            
def main() -> None:
    check_admin_privileges()
    
    load_dotenv()
    
    state.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    speak_ultron("I am Ultron. I was designed to save the world.")
    
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
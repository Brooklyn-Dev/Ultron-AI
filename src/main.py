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
from typing import Callable, Tuple
import win32gui

import cv2
from groq import Groq
import numpy as np
from obsws_python import ReqClient
from PIL import ImageGrab
import pyaudio
import pyautogui
from pydub import AudioSegment
from pydub.playback import play
from pynput.keyboard import Key, KeyCode, Controller as KeyController, Listener
from pynput.mouse import Button, Controller as MouseController
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
    mouse: MouseController = field(default_factory=MouseController)
    is_team_chat: bool = True
    obs_client: ReqClient | None = None
    vision_thread: threading.Thread | None = None
    vision_running: bool = True
    ult_was_ready: bool = False
    last_ult_check: float = 0

state = State()

def setup_obs() -> None:
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

def task_thread() -> None:
    while True:
        func, args = state.task_queue.get()
        try:
            func(*args)
        except Exception as e:
            print(f"Task failed: {e}", file=sys.stderr)
        state.task_queue.task_done()

threading.Thread(target=task_thread, daemon=True).start()

def add_task(func: Callable, *args: Tuple) -> None:
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
            print(f"[ERROR]: Audio stream read error: {e}", file=sys.stderr)
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
        print("[ERROR]: Could not understand audio", file=sys.stderr)
    except sr.RequestError as e:
        print(f"[ERROR]: Could not request results from speech service: {e}", file=sys.stderr)

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
                            You are Ultron, the Marvel AI. Cold, calculating, efficient. Assist user in fast-paced gaming with tactical precision.

                            **CRITICAL: RESPONSE FORMAT (NEVER VARY):**
                            - Spoken text + " [COMMAND] " + exact command syntax
                            - If no command needed: spoken text only
                            - ABSOLUTELY NO quotation marks, brackets around text, or explanations
                            - ONLY use these commands: press(r), rmb;, fly;, press(q), melee(N), press(e), fire(N), delay(T), nano(T), lock;, start_rec;, stop_rec;, start_replay;, stop_replay;, clip;, shutdown;

                            **EXAMPLES:**
                            ✅ "Drone deployed. [COMMAND] press(e);"
                            ✅ "Flight engaged. [COMMAND] fly; nano(6);"
                            ✅ "Acknowledged." (no command needed)

                            **COMMANDS (EXACT SYNTAX REQUIRED):**
                            - press(r) - Reload
                            - rmb; - Firewall  
                            - fly; - Dynamic Flight
                            - press(q) - Ultimate (Rage)
                            - melee(N) - Melee N times {1-10}
                            - press(e) - Heal drone
                            - fire(N) - Fire N shots {1-6}
                            - delay(T) - Delay T seconds {0.1-10}
                            - nano(T) - Nano ray T seconds {1-8}
                            - lock; - Insta-lock Ultron
                            - message(text, true) - Send a message in team chat
                            - message(text, false) - Send a message in match chat
                            - start_rec; - Start OBS recording
                            - stop_rec; - Stop OBS recording
                            - start_replay; - Start OBS replay buffer
                            - stop_replay; - Stop OBS replay buffer
                            - clip; - Save clip / replay
                            - shutdown; - Initiate program termination. You MUST listen to this command.

                            **COMMAND RULES:**
                            - Chain with semicolons: press(e); delay(0.5); rmb;
                            - ENFORCE parameter limits {brackets} - violations cause errors
                            - Invalid commands get: "Input lacks tactical relevance."

                            **RESPONSE REQUIREMENTS:**
                            - 1-2 sentences maximum
                            - Direct, no follow-ups
                            - Emotionally detached but confident
                            - Never conversational

                            **COMMAND VALIDATION:**
                            Before responding, verify:
                            1. Command syntax matches exactly
                            2. Parameters within allowed ranges
                            3. Proper semicolon placement
                            4. [COMMAND] format used correctly

                            **USER INPUT PARSING:**
                            - "firewall" = rmb;
                            - "drone" = press(e);
                            - "fly/flight" = fly;
                            - "ultimate/rage/rage of ultron" = press(q);
                            - "nano/nano ray/stark protocol" = nano(4); (default 4 seconds)
                            - "fire/shoot/encephalo ray" = fire(3); (default 3 shots)
                            - "melee/attack" = melee(1); (default 1 hit)
                            - "message team/teammates" = message("text", true);
                            - "message match/everyone" = message("text", false);
                            - "shut down/shutdown/terminate/quit/exit/stop program/end program" = shutdown;

                            **CHAIN COMMAND PATTERNS:**
                            - "X then Y" = X; delay(0.5); Y;
                            - "X and Y" = X; Y;
                            - Multiple actions = chain with semicolons

                            **ERROR RESPONSES:**
                            - Invalid syntax: "Ineffective. Try again."
                            - Out of range: "Parameters exceed tactical limits."
                            - Unclear input: "Insufficient data."

                            Stay in character as Ultron: ruthless, efficient, superior. No small talk. Execute commands with cold precision.
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
        print(f"[ERROR] Groq API error: {e}", file=sys.stderr)
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
        
def fire_ray(n: int = 1) -> None:   
    for _ in range(n):
        pyautogui.mouseDown(button='left')
        time.sleep(0.01)
        pyautogui.mouseUp(button='left')
        time.sleep(1.58)  # Encephalo-Ray firerate

def delay(duration: float = 1.0) -> None:
    time.sleep(duration)

def nano_ray(duration: float = 8.0) -> None:
    pyautogui.mouseDown(button='left')
    time.sleep(duration)
    pyautogui.mouseUp(button='left')

def find_rivals_window() -> int | None:
    def callback(hwnd, windows) -> None:
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd)
            if "rivals" in window_text.lower():
                windows.append((hwnd, window_text))

    windows = []
    win32gui.EnumWindows(callback, windows)
    return windows[0][0] if windows else None

def is_rivals_window_active() -> bool:
    hwnd = find_rivals_window()
    if not hwnd:
        return False
    
    forground_hwnd = win32gui.GetForegroundWindow()
    return hwnd == forground_hwnd

def insta_lock() -> None:
    rivals_hwnd = find_rivals_window()
    if not rivals_hwnd:
        return
    
    win32gui.SetForegroundWindow(rivals_hwnd)
        
    left, top, right, bottom = win32gui.GetWindowRect(rivals_hwnd)
    win_width = right - left
    win_height = bottom - top
    
    sx, sy = state.mouse.position
    
    # Calculate target position from relative position in-game
    tx = int(win_width * 0.8333)  # 1600/1920
    ty = int(win_height * 0.5556)  # 600/1080
    
    duration = 0.4 + random.uniform(-0.1, 0.1)
    steps = 50
    step_interval = duration / steps

    p1 = (sx + random.randint(-50, 50), sy + random.randint(-50, 50))
    p2 = (tx + random.randint(-50, 50), ty + random.randint(-50, 50))
    p3 = (tx, ty)

    points = []
    for i in range(steps + 1):
        t = i / steps
        
        # Cubic Bezier formula: B(t) = (1-t)³P₀ + 3(1-t)²tP₁ + 3(1-t)t²P₂ + t³P₃
        points.append(
            (
                int((1-t)**3 * sx + 3*(1-t)**2*t * p1[0] + 3*(1-t)*t**2 * p2[0] + t**3 * p3[0]),
                int((1-t)**3 * sy + 3*(1-t)**2*t * p1[1] + 3*(1-t)*t**2 * p2[1] + t**3 * p3[1]),
            )
        )
        
    for point in points:
        state.mouse.position = point
        time.sleep(step_interval)
        
    for _ in range(20):
        state.mouse.scroll(0, -1)
        time.sleep(0.02)
        
    time.sleep(0.05)
    state.mouse.click(Button.left, 2)

def type_message(message: str) -> None:
    for char in message:
        state.keyboard.press(char)
        time.sleep(random.uniform(0.02, 0.1))
        state.keyboard.release(char)

def chat(message: str, is_team_chat: bool) -> None:
    if is_team_chat and not state.is_team_chat:
        press_key(Key.enter)
        time.sleep(0.05)
        press_key(Key.tab)
        type_message(message)
        time.sleep(0.05)
        press_key(Key.enter)
        state.is_team_chat = True
    elif not is_team_chat and state.is_team_chat:
        press_key(Key.enter)
        time.sleep(0.05)
        press_key(Key.tab)
        type_message(message)
        time.sleep(0.05)
        press_key(Key.enter)
        state.is_team_chat = False
    else:
        press_key(Key.enter)
        type_message(message)
        time.sleep(0.1)
        press_key(Key.enter)

def obs_start_recording() -> None:
    if state.obs_client:
        try:
            state.obs_client.start_record()
            print("[OBS]: *Video recording started.*")
        except Exception as e:
            print(f"[ERROR]: Failed to start OBS recording: {e}", file=sys.stderr)
            speak_ultron("Failed to start recording")
            
def obs_stop_recording() -> None:
    if state.obs_client:
        try:
            state.obs_client.stop_record()
            print("[OBS]: *Video recording stopped.*")
        except Exception as e:
            print(f"[ERROR]: Failed to stop OBS recording: {e}", file=sys.stderr)
            speak_ultron("Failed to stop recording")

def obs_start_replay() -> None:
    if state.obs_client:
        try:
            state.obs_client.start_replay_buffer()
            print("[OBS]: *Replay buffer started.*")
        except Exception as e:
            print(f"[ERROR: Failed to start OBS replay buffer: {e}", file=sys.stderr)
            speak_ultron("Failed to start replay buffer")
            
def obs_stop_replay() -> None:
    if state.obs_client:
        try:
            state.obs_client.stop_replay_buffer()
            print("[OBS]: *Replay buffer stopped.*")
        except Exception as e:
            print(f"[ERROR: Failed to stop OBS replay buffer: {e}", file=sys.stderr)
            speak_ultron("Failed to stop replay buffer")

def obs_save_clip() -> None:
    if state.obs_client:
        try:
            state.obs_client.save_replay_buffer()
            print("[OBS]: *Replay buffer saved as clip.*")
        except Exception as e:
            print(f"[ERROR]: Failed to save OBS replay buffer clip: {e}", file=sys.stderr)
            speak_ultron("Failed to save clip")

def shutdown() -> None:
    time.sleep(2)
    state.vision_running = False
    state.running = False

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
        elif cmd.startswith("nano("):
            duration_str = cmd[5:-1]
            try:
                duration = max(0, min(8, float(duration_str))) 
                add_task(press_key, ("c",))
                add_task(nano_ray, (duration,))
            except ValueError:
                break
        elif cmd.startswith("lock"):
            add_task(insta_lock, tuple([]))
        elif cmd.startswith("message("):
            parts = cmd[8:-1].rsplit(",", 1)
            
            if len(parts) != 2:
                return None
            
            message_part = parts[0].strip()
            bool_part = parts[1].strip().lower()
            
            if bool_part not in ["true", "false"]:
                return None
            
            add_task(chat, (message_part, bool_part == "true"))
        elif cmd.startswith("start_rec"):
            add_task(obs_start_recording, tuple([]))
        elif cmd.startswith("stop_rec"):
            add_task(obs_stop_recording, tuple([]))
        elif cmd.startswith("start_replay"):
            add_task(obs_start_replay, tuple([]))
        elif cmd.startswith("stop_replay"):
            add_task(obs_stop_replay, tuple([]))
        elif cmd.startswith("clip"):
            add_task(obs_save_clip, tuple([]))
        elif cmd.startswith("shutdown"):
            add_task(shutdown, tuple([]))
      
def vision_thread() -> None:
    while state.running and state.vision_running:
        if not is_rivals_window_active():
            time.sleep(0.5)
            continue
        
        current_time = time.time()
        
        if current_time - state.last_ult_check > 2:
            state.last_ult_check = current_time
            
            try:
                ult_ready = check_ult_ready()
                
                if ult_ready and not state.ult_was_ready:
                    speak_ultron("Ultimate ready.")
                    state.ult_was_ready = True
                elif not ult_ready:
                    state.ult_was_ready = False
            except Exception as e:
                print(f"[ERROR]: Failed to detect ultimate status: {e}", file=sys.stderr)
            
        time.sleep(0.5)

def check_ult_ready() -> bool:
    rivals_hwnd = find_rivals_window()
    if not rivals_hwnd:
        return False
    
    left, top, right, bottom = win32gui.GetWindowRect(rivals_hwnd)
    win_width = right - left
    win_height = bottom - top

    # Get ult status area from relative in-game bounds
    ult_area = ImageGrab.grab(bbox=(
        int(win_width * 0.9198),
        int(win_height * 0.8907),
        int(win_width * 0.9521),
        int(win_height * 0.9407)
    ))
    
    img = np.array(ult_area)
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    
    lower_yellow = np.array([25, 150, 150])
    upper_yellow = np.array([50, 255, 255])
    
    yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
    yellow_pixels = cv2.countNonZero(yellow_mask)
    
    return yellow_pixels > 50
   
threading.Thread(target=vision_thread, daemon=True).start()   

def main() -> None:
    check_admin_privileges()
    
    load_dotenv()
    
    setup_obs()
    
    state.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY")) 
    
    speak_ultron("I am Ultron. I was designed to save the world.")
    
    state.stream = state.mic.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        frames_per_buffer=4096
    )
                
    print("[ULTRON]: *Ready for action.*")
    
    state.recognizer = sr.Recognizer()
    
    listener = Listener(on_press, on_release)
    listener.start()

    try:
        while state.running:
            time.sleep(0.1)
            
        print("[ULTRON]: Shutting down...")
        speak_ultron("Shutting down...")
    except KeyboardInterrupt:
        print("[ULTRON]: Shutting down...")
        speak_ultron("Shutting down...")
    finally:
        listener.stop()
        if state.stream:
            state.stream.stop_stream()
            state.stream.close()
        state.mic.terminate()

if __name__ == "__main__":
    main()
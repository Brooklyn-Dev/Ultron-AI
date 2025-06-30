import threading
import queue
from dataclasses import dataclass, field

from groq import Groq
from obsws_python import ReqClient
import pyaudio
from pynput.keyboard import Controller as KeyController
from pynput.mouse import Controller as MouseController
import pyttsx3
import speech_recognition as sr

@dataclass
class State:
    # App Lifecycle
    running: bool = True  # Controls main app loop
    
    # Audio Input (Speech Recognition)
    listening: bool = False  # Flag to capture mic input
    recognizer: sr.Recognizer = field(default_factory=sr.Recognizer)  # Speech recognition engine
    audio_frames: list = field(default_factory=list)  # Buffer for captured audio
    mic: pyaudio.PyAudio = field(default_factory=pyaudio.PyAudio)  # PyAudio instance
    stream: pyaudio.Stream | None = None  # Audio stream object
    audio_frame_lock: threading.Lock = field(default_factory=threading.Lock)  # Lock for thread-safe audio access
    collect_thread: threading.Thread | None = None  # Thread for audio collection
    
    # Audio Output (Text-to-Speech)
    engine: pyttsx3.Engine = field(default_factory=pyttsx3.Engine)  # pyttsx3 engine
    
    # AI Client
    groq_client: Groq | None = None  # GROQ API client
    
    # Task Management & Game Commands
    task_queue: queue.Queue = field(default_factory=queue.Queue)  # Queue for async tasks
    keyboard: KeyController = field(default_factory=KeyController)  # Pynput keyboard
    mouse: MouseController = field(default_factory=MouseController)  # Pynput mouse
    is_team_chat: bool = True  # Current chat mode (team/match)
    simulating_input: bool = False  # Simulating key presses
    
    # OBS Integration
    obs_client: ReqClient | None = None  # OBS WebSocket client
    
    # Game Vision
    vision_thread: threading.Thread | None = None  # Thread for vision processing
    vision_running: bool = True  # Flag for vision lifecycle
    ult_was_ready: bool = False  # State of ultimate ability
    last_ult_check: float = 0  # Timestamp of last ult check
    
# Global instance of state
g_state = State()
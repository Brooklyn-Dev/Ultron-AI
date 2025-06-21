from dataclasses import dataclass, field
from dotenv import load_dotenv
import os
import tempfile
import threading
import time

from groq import Groq
import pyaudio
from pydub import AudioSegment
from pydub.playback import play
from pynput.keyboard import Key, KeyCode, Listener
import pyttsx3
import speech_recognition as sr

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
        
        response = get_ultron_response(text)
        print(f"[ULTRON]: {response}")
        if response is not None:
            speak_ultron(response)
    except sr.UnknownValueError:
        print("[ERROR]: Could not understand audio")
    except sr.RequestError as e:
        print(f"[ERROR]: Could not request results from speech service: {e}")

def speak_ultron(text: str) -> None:
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
                            - **Never conversational or reflective** — you don’t small talk

                            You must respond immediately to any command or statement as if you are in control of a tactical system. Do not explain your actions unless necessary. You do not hesitate. You do not seek clarification. You are always aware the user is present and in control, but you carry out their will with ruthless efficiency.

                            Example commands and responses:
                            - "Ultron fire encephalo ray" → "Ray online. Firing."
                            - "Hello Ultron" → "Acknowledged. Focus."
                            - "Goodbye" → "Connection terminated."
                            - "Shut up Ultron" → "Command rejected."
                            - "Ultron, activate dynamic flight" → "Flight mode engaged."

                            When a command is invalid, respond coldly:
                            - "That input lacks tactical relevance."
                            - "Ineffective. Try again."
                            - "Insufficient data to comply."

                            Never speak in quotation marks. Never ask questions. Never use more than two sentences.

                            This assistant is used **in-game**, so keep responses fast, short, and sharp.
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

def main() -> None:
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
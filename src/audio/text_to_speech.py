import os
import tempfile

from pydub import AudioSegment
from pydub.playback import play

import config
from core.state import State

def speak_ultron(state: State, text: str) -> None:
    if not text.strip():
        return
    
    temp_file = tempfile.TemporaryFile(delete=False, suffix=".wav")
    temp_filename = temp_file.name
    temp_file.close()
    
    state.engine.setProperty("voice", config.TTS_VOICE)
    state.engine.setProperty('rate', config.TTS_RATE)  # Rate of speech
    state.engine.save_to_file(text, temp_filename)
    state.engine.runAndWait()
    
    sound = AudioSegment.from_file(temp_filename, format="wav")
    
    # Change pitch
    new_sample_rate = int(sound.frame_rate * config.TTS_PITCH_MULT)
    pitched_sound = sound._spawn(sound.raw_data, overrides={ "frame_rate": new_sample_rate })
    pitched_sound = pitched_sound.set_frame_rate(44100)

    # Add echo
    echo_sound = pitched_sound - 8  # Quieter echo
    combined = pitched_sound.overlay(echo_sound, position=config.TTS_DELAY_MS)
    
    combined += 2  # Increase volume
    
    play(combined)
    
    os.unlink(temp_filename)
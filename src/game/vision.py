import sys
import threading
import time
import win32gui

import cv2
from PIL import ImageGrab
import numpy as np

from core.state import State, g_state
from audio.text_to_speech import speak_ultron
from utils.rivals_window import is_rivals_window_active, find_rivals_window

def vision_thread(state: State) -> None:
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
                    speak_ultron(state, "Ultimate ready.")
                    state.ult_was_ready = True
                elif not ult_ready:
                    state.ult_was_ready = False
            except Exception as e:
                print(f"[ERROR]: Failed to detect ultimate status: {e}", file=sys.stderr)
            
        time.sleep(0.5)
   
threading.Thread(target=vision_thread, kwargs={ "state": g_state }, daemon=True).start()   

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
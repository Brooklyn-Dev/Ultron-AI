import random
import time
import win32gui

import pyautogui
from pynput.keyboard import Key, KeyCode
from pynput.mouse import Button

from core.state import State
from obs.obs_client import *
from utils.rivals_window import find_rivals_window

KeyType = Key | KeyCode | str 

def press_key(state: State, key: KeyType) -> None:
    state.keyboard.press(key)
    time.sleep(random.uniform(0.1, 0.2))
    state.keyboard.release(key)
    
def right_click() -> None:
    pyautogui.mouseDown(button='right')
    pyautogui.mouseUp(button='right')
    
def fly(state: State) -> None:
    press_key(state, Key.shift_l)
    
def melee(state: State, n: int) -> None:   
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

def insta_lock(state: State) -> None:
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

def type_message(state: State, message: str) -> None:
    for char in message:
        state.keyboard.press(char)
        time.sleep(random.uniform(0.02, 0.1))
        state.keyboard.release(char)

def chat(state: State, message: str, is_team_chat: bool) -> None:
    state.simulating_input = True
    
    try:
        if is_team_chat and not state.is_team_chat:
            press_key(state, Key.enter)
            time.sleep(0.05)
            press_key(state, Key.tab)
            type_message(state, message)
            time.sleep(0.05)
            press_key(state, Key.enter)
            state.is_team_chat = True
        elif not is_team_chat and state.is_team_chat:
            press_key(state, Key.enter)
            time.sleep(0.05)
            press_key(state, Key.tab)
            type_message(state, message)
            time.sleep(0.05)
            press_key(state, Key.enter)
            state.is_team_chat = False
        else:
            press_key(state, Key.enter)
            type_message(state, message)
            time.sleep(0.1)
            press_key(state, Key.enter)
    finally:
        state.simulating_input = False

def shutdown(state: State) -> None:
    time.sleep(2)
    state.vision_running = False
    state.running = False
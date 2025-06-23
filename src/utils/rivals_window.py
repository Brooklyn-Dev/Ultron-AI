import win32gui

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
"""
In-memory device screen capture + short-lived frame cache.

Hot path for vision matching:
  adb exec-out screencap -p -> numpy BGR frame (no /sdcard pull)

Runtime files (optional / legacy / debug) live under .cache/ — never under images/.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

# Reuse same frame for consecutive matches within this window (seconds)
FRAME_TTL_SEC = 0.35

# device_key -> (timestamp, frame BGR)
_frame_cache: Dict[str, Tuple[float, np.ndarray]] = {}


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cache_dir() -> str:
    path = os.path.join(_project_root(), ".cache", "screenshots")
    os.makedirs(path, exist_ok=True)
    return path


def debug_dir() -> str:
    path = os.path.join(_project_root(), ".cache", "debug")
    os.makedirs(path, exist_ok=True)
    return path


def device_key(device_id=None) -> str:
    from utils.adb_utils import resolve_adb_serial

    serial = resolve_adb_serial(device_id) or device_id or "default"
    return str(serial).replace(":", "_").replace(".", "_")


def screenshot_path(device_id=None) -> str:
    """Legacy file path under .cache (not images/)."""
    return os.path.join(cache_dir(), f"screen_{device_key(device_id)}.png")


def invalidate(device_id=None) -> None:
    """Drop cached frame after tap/swipe/UI change."""
    key = device_key(device_id)
    _frame_cache.pop(key, None)


def invalidate_all() -> None:
    _frame_cache.clear()


def get_cached_frame(device_id=None) -> Optional[np.ndarray]:
    key = device_key(device_id)
    entry = _frame_cache.get(key)
    if not entry:
        return None
    ts, frame = entry
    if time.time() - ts > FRAME_TTL_SEC:
        return None
    return frame


def _store_frame(device_id, frame: np.ndarray) -> None:
    key = device_key(device_id)
    _frame_cache[key] = (time.time(), frame)


def capture(device_id=None, force: bool = False) -> Optional[np.ndarray]:
    """
    Capture device screen as BGR numpy array.
    Uses short TTL cache unless force=True.
    """
    from utils.adb_utils import resolve_adb_serial, set_device, is_real_device_id

    if is_real_device_id(device_id):
        set_device(device_id)

    if not force:
        cached = get_cached_frame(device_id)
        if cached is not None:
            return cached

    serial = resolve_adb_serial(device_id)
    if not serial:
        print("screen.capture: không có serial ADB")
        return None

    frame = _capture_exec_out(serial)
    if frame is None:
        # Fallback: classic screencap + pull (slower, more reliable on some emulators)
        frame = _capture_pull(serial)

    if frame is None:
        return None

    _store_frame(serial, frame)
    return frame


def _capture_exec_out(serial: str) -> Optional[np.ndarray]:
    try:
        proc = subprocess.run(
            ["adb", "-s", serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=20,
        )
        data = proc.stdout or b""
        if len(data) < 100:
            return None
        # Some Windows adb builds corrupt newlines in PNG; try raw then CRLF-fixed
        arr = np.frombuffer(data, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            return frame
        fixed = data.replace(b"\r\n", b"\n")
        arr = np.frombuffer(fixed, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"screen.exec-out lỗi ({serial}): {e}")
        return None


def _capture_pull(serial: str) -> Optional[np.ndarray]:
    try:
        key = serial.replace(":", "_").replace(".", "_")
        remote = f"/sdcard/evony_cap_{key}.png"
        local = screenshot_path(serial)
        subprocess.run(
            ["adb", "-s", serial, "shell", "screencap", "-p", remote],
            capture_output=True,
            timeout=20,
        )
        subprocess.run(
            ["adb", "-s", serial, "pull", remote, local],
            capture_output=True,
            timeout=20,
        )
        subprocess.run(
            ["adb", "-s", serial, "shell", "rm", "-f", remote],
            capture_output=True,
            timeout=10,
        )
        if not os.path.isfile(local) or os.path.getsize(local) < 100:
            return None
        return cv2.imread(local)
    except Exception as e:
        print(f"screen.pull lỗi ({serial}): {e}")
        return None


def write_cache_file(device_id=None, frame: Optional[np.ndarray] = None) -> Optional[str]:
    """Persist latest frame to .cache for legacy callers that imread a path."""
    if frame is None:
        frame = get_cached_frame(device_id) or capture(device_id, force=True)
    if frame is None:
        return None
    path = screenshot_path(device_id)
    try:
        cv2.imwrite(path, frame)
        return path
    except Exception as e:
        print(f"screen.write_cache_file lỗi: {e}")
        return None


def save_debug(frame: np.ndarray, device_id=None, tag: str = "fail") -> Optional[str]:
    if os.environ.get("EVONY_DEBUG_SCREEN", "").strip() not in ("1", "true", "True", "yes"):
        return None
    try:
        name = f"{device_key(device_id)}_{int(time.time())}_{tag}.png"
        path = os.path.join(debug_dir(), name)
        cv2.imwrite(path, frame)
        return path
    except Exception:
        return None

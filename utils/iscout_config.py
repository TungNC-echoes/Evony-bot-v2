"""
Local iScout account settings (never commit secrets).
Stored in config.local.json next to the app.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any, Dict

CONFIG_FILENAME = "config.local.json"
SESSION_DIRNAME = ".iscout_session"
STORAGE_STATE_FILENAME = "storage_state.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "iscout": {
        "email": "",
        "password": "",
        "mode": "managed",  # managed | cdp
        "cdp_port": 9014,
        "login_timeout_sec": 120,
        "headless": False,
    }
}


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def config_path() -> str:
    return os.path.join(_project_root(), CONFIG_FILENAME)


def session_dir() -> str:
    path = os.path.join(_project_root(), SESSION_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def storage_state_path() -> str:
    return os.path.join(session_dir(), STORAGE_STATE_FILENAME)


def load_iscout_config() -> Dict[str, Any]:
    cfg = deepcopy(DEFAULT_CONFIG)["iscout"]
    path = config_path()
    if not os.path.exists(path):
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        iscout = data.get("iscout", data)
        if isinstance(iscout, dict):
            cfg.update({k: iscout.get(k, cfg[k]) for k in cfg.keys()})
    except Exception as e:
        print(f"Không đọc được {CONFIG_FILENAME}: {e}")
    return cfg


def save_iscout_config(updates: Dict[str, Any]) -> bool:
    path = config_path()
    data: Dict[str, Any] = deepcopy(DEFAULT_CONFIG)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                data.update(existing)
        except Exception:
            pass

    iscout = data.setdefault("iscout", deepcopy(DEFAULT_CONFIG)["iscout"])
    iscout.update(updates)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Không lưu được {CONFIG_FILENAME}: {e}")
        return False


def clear_storage_state() -> None:
    path = storage_state_path()
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            print(f"Không xóa được storage state: {e}")

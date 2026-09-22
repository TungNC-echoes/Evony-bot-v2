"""
Boss location fetcher via Playwright iScout client.
Public API kept compatible with process_manager:
  get_boss_locations(), save_to_json()
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from actions.iscout_client import IScoutClient
from utils.iscout_config import load_iscout_config


def get_boss_locations(
    port: Optional[int] = None,
    max_retries: int = 3,
    email: Optional[str] = None,
    password: Optional[str] = None,
    mode: Optional[str] = None,
    log_fn=None,
) -> List[Dict[str, Any]]:
    """
    Fetch boss list from iscout.club dashboard.

    Uses config.local.json when email/password/mode/port are not provided.
    """
    cfg = load_iscout_config()
    client = IScoutClient.from_config(
        log_fn=log_fn,
        email=email if email is not None else cfg.get("email"),
        password=password if password is not None else cfg.get("password"),
        mode=mode if mode is not None else cfg.get("mode"),
        cdp_port=port if port is not None else cfg.get("cdp_port"),
    )
    return client.fetch_boss_locations(max_retries=max_retries)


def save_to_json(boss_list, filename: str = "boss_locations.json", device_id=None) -> bool:
    """Lưu danh sách boss vào file JSON."""
    try:
        if device_id:
            filename = f"boss_locations_{device_id.replace(':', '_')}.json"

        data = {
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "boss_count": len(boss_list),
            "bosses": boss_list,
        }

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print(f"Đã lưu thông tin {len(boss_list)} boss vào file {filename}")
        return True
    except Exception as e:
        print(f"Lỗi khi lưu file JSON: {e}")
        return False


def main():
    print("=" * 50)
    print("LẤY THÔNG TIN VỊ TRÍ BOSS (Playwright)")
    print("=" * 50)
    try:
        boss_list = get_boss_locations(max_retries=3)
        if boss_list:
            if save_to_json(boss_list):
                print("\nĐã hoàn thành việc lưu thông tin boss!")
            else:
                print("\nKhông thể lưu thông tin boss vào file JSON!")
        else:
            print("\nKhông tìm thấy thông tin boss nào!")
    except KeyboardInterrupt:
        print("\nNgười dùng đã dừng chương trình")
    except Exception as e:
        print(f"\nLỗi không mong muốn: {e}")
    print("=" * 50)


if __name__ == "__main__":
    main()

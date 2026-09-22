# EVONY Auto v2

Commercial fork. **Main entry:** `main.py` (Drag & Drop multi-feature GUI).

## Features

- Rally / Advanced Rally (boss selection)
- Buy meat
- War (no general) / Advanced War
- Attack Boss
- Open Items
- Buy General
- Multi MEmu device + drag-drop assign devices to features

## iScout (boss locations)

1. Nhập Email/Password ở panel **iScout** (bên trái).
2. Mode:
   - **Managed**: app tự mở Chrome, login, lưu session (`.iscout_session/`).
   - **CDP**: gắn vào Chrome đang mở với `--remote-debugging-port=9014`.
3. Bấm **Login** (lần đầu / khi hết session), rồi **Lấy Boss** để test.
4. Attack Boss sẽ tự gọi lại `get_boss_locations()` khi cần cập nhật.

Cấu hình lưu tại `config.local.json` (gitignore, không commit).

## Run (dev)

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

## Build (Windows)

```bash
python build.py
```

Output: `dist/EVONY_Auto.exe`

## Structure

```
auto-evony-v2/
├── main.py              # Main GUI entry
├── components/          # DeviceManager, UIBuilder, ProcessManager
├── actions/             # Automation flows (incl. Advanced Rally)
├── utils/               # ADB + OpenCV + language
├── images/en|vi         # Templates (incl. rally_advance_boss)
├── adb_tools/
├── config.json
└── build.py
```

## Screen capture

- Template UI: `images/en|vi/...` (git)
- Runtime frames: in-memory + optional `.cache/screenshots/` (gitignore)
- Capture: `adb exec-out screencap -p` (fallback pull nếu cần)
- Frame cache ~350ms giữa các lần match liên tiếp; invalidate sau tap/swipe
- Debug dump: set env `EVONY_DEBUG_SCREEN=1`

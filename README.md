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
   - **Managed**: app mở Chrome (profile riêng). Có thể gặp Cloudflare — chờ / click Verify trên cửa sổ Chrome.
   - **CDP (khuyến nghị khi CF khó)**: tự mở Chrome rồi gắn vào:
     ```text
     chrome.exe --remote-debugging-port=9014 --user-data-dir=%USERPROFILE%\evony-chrome-profile
     ```
     Vào iscout.club, pass Cloudflare thủ công 1 lần, rồi bấm Login / Lấy Boss trong app.
3. App sẽ: chờ Cloudflare xong → gõ form chậm → thử click Verify human / Turnstile → vào dashboard.
4. Attack Boss tự gọi lại `get_boss_locations()` khi cần.

Cấu hình: `config.local.json` (gitignore). Chrome profile: `.iscout_session/chrome_profile/`.

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

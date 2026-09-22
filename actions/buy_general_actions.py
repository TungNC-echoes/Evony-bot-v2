import os
import time
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.image_utils import check_button_exists, find_and_click_button
from utils.language_utils import get_image_path
from utils.adb_utils import adb_command, set_device

# Nút chức năng trên màn Tavern > Recruit (English)
BTN_REFRESH = "muatuong/lam_moi"      # Refresh (50 gems)
BTN_RECRUIT = "muatuong/tuyen_mo"     # Recruit General
BTN_CONFIRM = "muatuong/xac_nhan"     # Confirm (mua vàng HOẶC bỏ qua tướng khi refresh)

GENERALS_DIR_KEY = "buttons/muatuong/tuong"
MATCH_THRESHOLD = 0.8
MAX_CONFIRM_RETRIES = 3
RETURN_TO_LIST_WAIT = 2
_wanted_general_templates = None


def get_wanted_general_templates():
    """Lấy danh sách ảnh tướng cần mua trong muatuong/tuong/."""
    global _wanted_general_templates
    if _wanted_general_templates is not None:
        return _wanted_general_templates

    folder = get_image_path(GENERALS_DIR_KEY)
    if not os.path.isdir(folder):
        print(f"Thư mục tướng không tồn tại: {folder}")
        _wanted_general_templates = []
        return _wanted_general_templates

    templates = []
    for filename in os.listdir(folder):
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            name = os.path.splitext(filename)[0]
            templates.append(f"muatuong/tuong/{name}")

    print(f"Danh sách tướng cần mua ({len(templates)}): {templates}")
    _wanted_general_templates = templates
    return templates


def press_escape(device_id=None):
    """Nhấn ESC một lần để đóng màn chi tiết tướng."""
    try:
        if device_id:
            set_device(device_id)
        print(f"Nhấn ESC trên device {device_id}...")
        adb_command("adb shell input keyevent KEYCODE_ESCAPE")
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Lỗi khi nhấn ESC trên device {device_id}: {e}")
        return False


def is_refresh_visible(device_id):
    """Đang ở list tuyển mộ nếu thấy nút Refresh."""
    return check_button_exists(BTN_REFRESH, device_id=device_id, threshold=MATCH_THRESHOLD)


def confirm_refresh_warning(device_id):
    """
    Popup khi bấm Refresh lúc lineup có tướng khớp filter
    (Epic / Historic): 'Are you sure you want to refresh?'.
    Confirm = bỏ qua lineup hiện tại và làm mới.
    """
    if not check_button_exists(BTN_CONFIRM, device_id=device_id, threshold=MATCH_THRESHOLD):
        return False

    print(f"Phát hiện cảnh báo refresh trên device {device_id}. Đang xác nhận để làm mới...")
    return find_and_click_button(
        BTN_CONFIRM, device_id=device_id, wait_time=2, threshold=MATCH_THRESHOLD
    )


def refresh_tavern(device_id, reason=""):
    """Chỉ bấm Refresh khi đang thấy nút. Không ESC trong hàm này."""
    if reason:
        print(f"{reason} trên device {device_id}")

    if not is_refresh_visible(device_id):
        print(f"Chưa thấy nút Refresh trên device {device_id}, để vòng sau xử lý")
        return False

    if not find_and_click_button(
        BTN_REFRESH, device_id=device_id, wait_time=2, threshold=MATCH_THRESHOLD
    ):
        print(f"Không thể click Refresh trên device {device_id}")
        return False

    time.sleep(1)
    confirm_refresh_warning(device_id)

    print(f"Đang chờ game load tướng mới trên device {device_id}...")
    time.sleep(3)

    for attempt in range(MAX_CONFIRM_RETRIES):
        if not confirm_refresh_warning(device_id):
            break
        print(f"Đang chờ lineup mới sau xác nhận refresh ({attempt + 1}/{MAX_CONFIRM_RETRIES})...")
        time.sleep(2)

    return True


def skip_general_and_refresh(device_id, reason):
    """
    ESC một lần để về list. Nếu đã thấy Refresh thì không ESC nữa,
    bấm Refresh luôn. Chưa thấy thì dừng, vòng sau xử lý.
    """
    print(f"{reason} trên device {device_id}")

    if is_refresh_visible(device_id):
        print(f"Đã thấy Refresh trên device {device_id}, không ESC. Dùng Refresh...")
        return refresh_tavern(device_id)

    press_escape(device_id)

    if is_refresh_visible(device_id):
        print(f"ESC xong thấy Refresh trên device {device_id}, không ESC nữa. Dùng Refresh...")
        return refresh_tavern(device_id)

    print(f"ESC xong chưa thấy Refresh trên device {device_id}, không ESC thêm. Để vòng sau xử lý")
    return False


def try_click_wanted_general(device_id):
    """Tìm tướng đang được chọn trên màn Recruit (ảnh lớn giữa màn)."""
    templates = get_wanted_general_templates()
    if not templates:
        return False

    for template in templates:
        if find_and_click_button(
            template, device_id=device_id, wait_time=2, threshold=MATCH_THRESHOLD
        ):
            print(f"Phát hiện tướng {template} trên device {device_id}")
            return True
    return False


def try_recruit_general(device_id, context=""):
    """
    Tuyển mộ nếu tướng đang chọn trùng template.
    - Mua thành công: chờ về list rồi Refresh ngay (không click lại tướng đã mua).
    - Click tướng mà không thấy Recruit General: ESC + Refresh.
    Trả về True nếu đã xử lý xong tướng (mua hoặc bỏ qua).
    Trả về False nếu không thấy tướng cần mua.
    """
    if not try_click_wanted_general(device_id):
        return False

    print(f"Đang tuyển mộ {context}trên device {device_id}...")
    if not check_button_exists(BTN_RECRUIT, device_id=device_id, threshold=MATCH_THRESHOLD):
        skip_general_and_refresh(
            device_id,
            "Không thấy nút Recruit General sau khi click tướng (có thể đã mua)",
        )
        return True

    if not find_and_click_button(
        BTN_RECRUIT, device_id=device_id, wait_time=2, threshold=MATCH_THRESHOLD
    ):
        skip_general_and_refresh(
            device_id,
            "Không click được Recruit General",
        )
        return True

    if not find_and_click_button(
        BTN_CONFIRM, device_id=device_id, wait_time=2, threshold=MATCH_THRESHOLD
    ):
        skip_general_and_refresh(
            device_id,
            "Không thấy Confirm sau Recruit General",
        )
        return True

    print(f"Đã tuyển mộ tướng thành công {context}trên device {device_id}")
    print(f"Chờ {RETURN_TO_LIST_WAIT}s để quay về list tuyển mộ trên device {device_id}...")
    time.sleep(RETURN_TO_LIST_WAIT)

    if is_refresh_visible(device_id):
        refresh_tavern(device_id, "Mua xong đã thấy Refresh, không ESC. Dùng Refresh")
    else:
        skip_general_and_refresh(device_id, "Mua xong chưa thấy Refresh")
    return True


def buy_general_sequence(device_id=None):
    """Một vòng: tuyển nếu có tướng cần mua, không thì Refresh tavern."""
    print(f"=== Bắt đầu vòng mua tướng trên device {device_id} ===")

    if try_recruit_general(device_id, ""):
        return True

    if not refresh_tavern(device_id, "Không có tướng cần mua. Đang làm mới"):
        return False

    if try_recruit_general(device_id, "sau làm mới "):
        return True

    print(f"Không phát hiện tướng cần mua trên device {device_id}, sẽ thử lại...")
    return True


def auto_buy_general(device_id=None):
    """Bot tự động mua tướng lặp vô hạn"""
    print(f"=== Bắt đầu auto mua tướng trên device {device_id} ===")
    while True:
        try:
            buy_general_sequence(device_id)
            time.sleep(2)
        except Exception as e:
            print(f"Lỗi trong quá trình chạy bot trên device {device_id}: {e}")
            time.sleep(5)

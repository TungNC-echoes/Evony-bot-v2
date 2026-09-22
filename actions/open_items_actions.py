import os
import time
import cv2
from utils.image_utils import find_and_click_button, check_button_exists
from utils.adb_utils import adb_command, set_device, is_real_device_id, tap_screen
from utils.language_utils import get_image_path


# more -> items (things) -> time -> box, mỗi lần cách 1s
OPEN_BAG_BUTTONS = [
    "open_resource/more",
    "open_resource/things",
    "open_resource/time",
    "open_resource/box",
]

BTN_OPEN = "open_resource/open"
BTN_USE = "open_resource/use"
BTN_ITEMS_AFTER = "open_resource/items_after"

ITEM_FOLDERS = {
    "resource": "buttons/open_resource/items/resource",
    "ngoc": "buttons/open_resource/items/ngoc",
}

ITEM_MATCH_THRESHOLD = 0.7  # giống threshold boss Advanced Rally
SCROLL_DONE_COUNT = 3


def _set_device(device_id):
    if is_real_device_id(device_id):
        set_device(device_id)


def _log(device_id, message, log_queue=None):
    if log_queue:
        log_queue.put(f"📦 [{device_id}] {message}")


def esc_until_cancel(device_id):
    """ESC tới khi thấy cancel rồi click, giống Rally."""
    _set_device(device_id)
    for _ in range(8):
        if check_button_exists("cancel", device_id=device_id, threshold=0.7):
            find_and_click_button("cancel", device_id=device_id, wait_time=1, threshold=0.75)
            return True
        adb_command("adb shell input keyevent KEYCODE_ESCAPE", device_id)
        time.sleep(1)
    return True


def is_in_items_screen(device_id):
    _set_device(device_id)
    return check_button_exists(BTN_ITEMS_AFTER, device_id=device_id, threshold=0.65)


def click_open_bag_menu(device_id):
    """more -> items -> time -> box, mỗi lần cách 1s."""
    _set_device(device_id)
    for button_name in OPEN_BAG_BUTTONS:
        if is_in_items_screen(device_id):
            return True
        if not find_and_click_button(button_name, device_id=device_id, wait_time=1, threshold=0.65):
            return is_in_items_screen(device_id)
    return is_in_items_screen(device_id)


def list_selected_item_templates(open_resource=True, open_gems=False):
    """List item được chọn, mỗi file giống 1 boss trong Advanced Rally."""
    templates = []
    categories = []
    if open_resource:
        categories.append("resource")
    if open_gems:
        categories.append("ngoc")

    for category in categories:
        folder = get_image_path(ITEM_FOLDERS[category])
        if not os.path.isdir(folder):
            continue
        for filename in sorted(os.listdir(folder)):
            if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                name = os.path.splitext(filename)[0]
                templates.append(f"open_resource/items/{category}/{name}")
    return templates


def _template_path(item_image):
    path = get_image_path(f"buttons/{item_image}")
    if os.path.exists(f"{path}.JPG"):
        return f"{path}.JPG"
    if os.path.exists(f"{path}.jpg"):
        return f"{path}.jpg"
    return None


def capture_screen(device_id):
    """Chụp 1 ảnh gắn đúng device — trả về frame BGR in-memory."""
    from utils.screen import capture

    _set_device(device_id)
    return capture(device_id=device_id, force=True)


def find_selected_item(item_templates, screenshot, threshold=ITEM_MATCH_THRESHOLD):
    """
    So khớp 1 screenshot với list item, giống find_all_boss_positions.
    Khớp item nào trước thì trả item đó.
    """
    if screenshot is None:
        return None

    for item_image in item_templates:
        path = _template_path(item_image)
        if not path:
            continue
        template = cv2.imread(path)
        if template is None:
            continue

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= threshold:
            h, w = template.shape[:2]
            click_x = int(max_loc[0] + w // 2)
            click_y = int(max_loc[1] + h // 2)
            return item_image, (click_x, click_y), max_val
    return None


def open_found_item(click_xy, device_id):
    """Click item -> open -> use -> items_after 3 lần, mỗi lần cách 1s."""
    _set_device(device_id)
    x, y = int(click_xy[0]), int(click_xy[1])
    tap_screen(x, y, device_id)
    time.sleep(1)

    if not find_and_click_button(BTN_OPEN, device_id=device_id, wait_time=1, threshold=0.65):
        return False
    if not find_and_click_button(BTN_USE, device_id=device_id, wait_time=1, threshold=0.65):
        return False

    for _ in range(3):
        find_and_click_button(BTN_ITEMS_AFTER, device_id=device_id, wait_time=1, threshold=0.65)

    return True


def scroll_bag_down(device_id, screenshot=None):
    """Vuốt trên vùng list item (giữa túi), đủ dài để túi chạy xuống."""
    _set_device(device_id)
    width, height = 540, 960
    if screenshot is not None:
        height, width = screenshot.shape[:2]
    x = int(width * 0.5)
    y1 = int(height * 0.70)
    y2 = int(height * 0.54)
    adb_command(f"adb shell input swipe {x} {y1} {x} {y2} 500", device_id)
    time.sleep(4)


def screens_unchanged(img_a, img_b, min_similarity=0.985):
    if img_a is None or img_b is None:
        return False
    if img_a.shape != img_b.shape:
        return False
    diff = cv2.absdiff(img_a, img_b)
    similarity = 1.0 - (float(diff.mean()) / 255.0)
    return similarity >= min_similarity


def open_items_sequence(device_id=None, open_resource=True, open_gems=False, log_queue=None):
    """
    Open Items theo từng device, cùng kiểu Rally / Buy Meat / Advanced Rally:
    ESC + cancel -> vào túi -> khớp item (như khớp boss) -> mở -> hết thì dừng device.
    """
    try:
        _set_device(device_id)
        if not open_resource and not open_gems:
            _log(device_id, "Chưa chọn Mở resource hoặc Mở ngọc", log_queue)
            return False

        item_templates = list_selected_item_templates(open_resource, open_gems)
        if not item_templates:
            _log(device_id, "Không có ảnh item", log_queue)
            return False

        esc_until_cancel(device_id)
        if not click_open_bag_menu(device_id):
            _log(device_id, "Không vào được túi items", log_queue)
            return False

        opened = 0
        same_scrolls = 0
        prev_screen = None

        while True:
            _set_device(device_id)
            screenshot = capture_screen(device_id)
            matched = find_selected_item(item_templates, screenshot)

            if matched:
                _name, click_xy, _conf = matched
                same_scrolls = 0
                prev_screen = None
                if open_found_item(click_xy, device_id):
                    opened += 1
                    time.sleep(1)
                    continue
                _log(device_id, "Mở không được, kéo xuống", log_queue)
            else:
                _log(device_id, "Không khớp item, kéo xuống", log_queue)

            scroll_bag_down(device_id, screenshot)
            after_scroll = capture_screen(device_id)
            matched_after = find_selected_item(item_templates, after_scroll)
            if matched_after:
                _name, click_xy, _conf = matched_after
                same_scrolls = 0
                prev_screen = None
                if open_found_item(click_xy, device_id):
                    opened += 1
                time.sleep(1)
                continue

            if after_scroll is None:
                time.sleep(1)
                continue

            if prev_screen is not None and screens_unchanged(prev_screen, after_scroll):
                same_scrolls += 1
            else:
                same_scrolls = 0

            if same_scrolls >= SCROLL_DONE_COUNT:
                esc_until_cancel(device_id)
                _log(device_id, f"Hết item, đã mở {opened}", log_queue)
                return "done"

            prev_screen = after_scroll.copy()

    except Exception as e:
        _log(device_id, f"Lỗi: {e}", log_queue)
        return False


def continue_open_items_sequence(device_id=None, open_resource=True, open_gems=False, log_queue=None):
    return open_items_sequence(device_id, open_resource=open_resource, open_gems=open_gems, log_queue=log_queue)


def open_items_selective_sequence(device_id=None, open_resource=True, open_gems=False, log_queue=None):
    return open_items_sequence(device_id, open_resource=open_resource, open_gems=open_gems, log_queue=log_queue)


def continue_open_items_selective_sequence(device_id=None, open_resource=True, open_gems=False, log_queue=None):
    return open_items_sequence(device_id, open_resource=open_resource, open_gems=open_gems, log_queue=log_queue)

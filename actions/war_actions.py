import time
import random
from utils.image_utils import (
    find_and_click_button,
    check_button_exists,
    find_and_click_at_width_ratio,
)
from utils.adb_utils import swipe_down, swipe_up, ensure_evony_running


# ===== CONSTANTS =====
WAR_BUTTONS_SEQUENCE = [
    ("join_button", 2),       # Nút tham gia, chờ 2 giây
    ("doi_quan_san_co", 1),   # Nút đổi quân sân cỏ, chờ 1 giây
    ("chon_tuong", 1),        # Nút chọn tướng, chờ 1 giây
    ("chon", 1),              # Nút chọn, chờ 1 giây
    ("hanh_quan", 1)          # Nút hành quân, chờ 1 giây
]

WAR_BUTTONS_SEQUENCE_NO_GENERAL = [
    ("join_button", 2),       # Nút tham gia, chờ 2 giây
    ("doi_quan_san_co", 1),   # Nút đổi quân sân cỏ, chờ 1 giây
    ("hanh_quan", 1)          # Nút hành quân, chờ 1 giây
]

STAMINA_BAR_CLICK_RATIO = 0.8


# ===== HELPER FUNCTIONS =====
def click_button_sequence(buttons, device_id=None, sequence_name="buttons"):
    """Thực hiện click chuỗi buttons theo thứ tự"""
    try:
        for button_name, wait_time in buttons:
            if not find_and_click_button(button_name, device_id=device_id, wait_time=wait_time):
                print(f"Không thể tìm thấy hoặc click vào nút {button_name}")
                return False
        return True
    except Exception as e:
        print(f"Lỗi trong quá trình click {sequence_name}: {e}")
        return False


def try_select_assistant_general(device_id=None):
    """Chọn tướng phụ nếu thấy nút. Không thấy thì bỏ qua, không hủy lượt."""
    print("Đang chọn tướng phụ...")
    if not find_and_click_button("chon_tuong_phu", device_id=device_id, wait_time=1, threshold=0.8):
        print("Không thấy nút chon_tuong_phu, bỏ qua tướng phụ")
        return False
    if not find_and_click_button("chon", device_id=device_id, wait_time=1, threshold=0.8):
        print("Không thể click Select tướng phụ, tiếp tục hành quân")
        return False
    print("Đã chọn tướng phụ")
    return True


def run_war_buttons_with_general(device_id=None, include_join=True, use_assistant_general=False):
    """Chuỗi chọn tướng chính, optional tướng phụ, rồi hành quân."""
    buttons = []
    if include_join:
        buttons.append(("join_button", 2))
    buttons.extend([
        ("doi_quan_san_co", 1),
        ("chon_tuong", 1),
        ("chon", 1),
    ])
    if not click_button_sequence(buttons, device_id, "war sequence general"):
        return False

    if use_assistant_general:
        try_select_assistant_general(device_id)

    if not find_and_click_button("hanh_quan", device_id=device_id, wait_time=1):
        print("Không thể tìm thấy hoặc click vào nút hanh_quan")
        return False
    return True


def find_join_button_with_scroll(device_id=None):
    """Tìm nút join_button bằng cách scroll xuống/lên nếu cần"""
    try:
        # Kéo màn hình xuống để kiểm tra các cuộc chiến tranh
        if swipe_down():
            # Kiểm tra xem có nút join_button không sau khi kéo xuống
            if not check_button_exists("join_button", device_id=device_id):
                # print("Không tìm thấy nút tham gia sau khi kéo xuống, kéo lên lại...")
                swipe_up()
                # Kiểm tra lại nút join_button ở vị trí ban đầu
                if not check_button_exists("join_button", device_id=device_id):
                    # print("Không tìm thấy nút tham gia ở vị trí ban đầu")
                    return False
        return True
    except Exception as e:
        print(f"Lỗi khi tìm nút join_button: {e}")
        return False


def check_and_handle_insufficient_stamina(device_id=None):
    """Kiểm tra và xử lý trường hợp không đủ thể lực"""
    try:
        if check_button_exists("xac_nhan", device_id=device_id):
            print("Phát hiện trường hợp không đủ thể lực")
            if handle_insufficient_stamina(device_id):
                print("Đã xử lý xong trường hợp không đủ thể lực")
                return True
            else:
                print("Không thể xử lý trường hợp không đủ thể lực")
                return False
        return True
    except Exception as e:
        print(f"Lỗi khi kiểm tra thể lực: {e}")
        return False


# ===== MAIN FUNCTIONS =====
def handle_insufficient_stamina(device_id=None):
    """Xử lý trường hợp không đủ thể lực: xác nhận -> dùng 1 -> kéo thanh ~80% -> dùng 2 -> back -> hành quân."""
    try:
        print("Đang xử lý trường hợp không đủ thể lực...")
        time.sleep(1)

        if not find_and_click_button("xac_nhan", device_id=device_id, wait_time=1):
            print("Không thể click xac_nhan khi xử lý thể lực")
            return False

        if not find_and_click_button("dung", device_id=device_id, wait_time=1):
            print("Không thể click dung (dùng 1) khi xử lý thể lực")
            return False

        if find_and_click_at_width_ratio(
            "thanh_the_luc",
            device_id=device_id,
            wait_time=1,
            threshold=0.8,
            width_ratio=STAMINA_BAR_CLICK_RATIO,
        ):
            print(f"Đã chỉnh thanh thể lực tại {STAMINA_BAR_CLICK_RATIO:.0%} chiều dài")
        else:
            print("Không thấy thanh_the_luc, tiếp tục dùng 2")

        if not find_and_click_button("dung2", device_id=device_id, wait_time=1):
            print("Không thể click dung2 (dùng 2) khi xử lý thể lực")
            return False

        if not find_and_click_button("back", device_id=device_id, wait_time=1):
            print("Không thể click back khi xử lý thể lực")
            return False

        if not find_and_click_button("hanh_quan", device_id=device_id, wait_time=1):
            print("Không thể click hanh_quan sau khi dùng thể lực")
            return False

        return True
    except Exception as e:
        print(f"Lỗi trong quá trình xử lý không đủ thể lực: {e}")
        return False


def join_war_sequence(device_id=None, use_assistant_general=False):
    """Thực hiện chuỗi hành động tham gia chiến tranh"""
    try:
        # Click vào nút chiến tranh
        if not find_and_click_button("war_button", device_id=device_id, wait_time=2):
            # print("Không thể tìm thấy hoặc click vào nút chiến tranh")
            return False
            
        # Tìm nút join_button
        if not find_join_button_with_scroll(device_id):
            return False
        
        if not run_war_buttons_with_general(
            device_id, include_join=True, use_assistant_general=use_assistant_general
        ):
            return False
                
        # Kiểm tra và xử lý trường hợp không đủ thể lực
        return check_and_handle_insufficient_stamina(device_id)
        
    except Exception as e:
        print(f"Lỗi trong quá trình tham gia chiến tranh: {e}")
        return False


def continue_war_sequence(device_id=None, use_assistant_general=False):
    """Thực hiện chuỗi hành động từ nút join_button"""
    try:
        # Tìm nút join_button
        if not find_join_button_with_scroll(device_id):
            return False
        
        if not run_war_buttons_with_general(
            device_id, include_join=True, use_assistant_general=use_assistant_general
        ):
            return False
                
        # Kiểm tra và xử lý trường hợp không đủ thể lực
        return check_and_handle_insufficient_stamina(device_id)
        
    except Exception as e:
        print(f"Lỗi trong quá trình tiếp tục tham gia chiến tranh: {e}")
        return False


def join_war_sequence_no_general(device_id=None):
    """Thực hiện chuỗi hành động tham gia chiến tranh (không chọn tướng)"""
    try:
        # Click vào nút chiến tranh
        if not find_and_click_button("war_button", device_id=device_id, wait_time=2):
            # print("Không thể tìm thấy hoặc click vào nút chiến tranh")
            return False
            
        # Tìm nút join_button
        if not find_join_button_with_scroll(device_id):
            return False
        
        # Thực hiện chuỗi buttons (không có chọn tướng)
        if not click_button_sequence(WAR_BUTTONS_SEQUENCE_NO_GENERAL, device_id, "war sequence no general"):
            return False
                
        # Kiểm tra và xử lý trường hợp không đủ thể lực
        return check_and_handle_insufficient_stamina(device_id)
        
    except Exception as e:
        print(f"Lỗi trong quá trình tham gia chiến tranh (không chọn tướng): {e}")
        return False


def continue_war_sequence_no_general(device_id=None):
    """Thực hiện chuỗi hành động từ nút join_button (không chọn tướng)"""
    try:
        # Tìm nút join_button
        if not find_join_button_with_scroll(device_id):
            return False
        
        # Thực hiện chuỗi buttons (không có chọn tướng)
        if not click_button_sequence(WAR_BUTTONS_SEQUENCE_NO_GENERAL, device_id, "war sequence no general"):
            return False
                
        # Kiểm tra và xử lý trường hợp không đủ thể lực
        return check_and_handle_insufficient_stamina(device_id)
        
    except Exception as e:
        print(f"Lỗi trong quá trình tiếp tục tham gia chiến tranh (không chọn tướng): {e}")
        return False
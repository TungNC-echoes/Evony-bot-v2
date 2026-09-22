import cv2
import os
import time
import numpy as np
from utils.language_utils import get_image_path

def get_screenshot_filename(device_id=None):
    """Tên file screenshot theo device — giữ API cũ, đường dẫn đầy đủ dùng get_screenshot_path."""
    from utils.adb_utils import get_screenshot_path
    return os.path.basename(get_screenshot_path(device_id))

def find_button_on_screen(button_image_path, device_id=None, threshold=0.95):
    """Tìm vị trí của nút trên màn hình"""
    try:
        # Đọc ảnh mẫu
        template = cv2.imread(button_image_path)
        if template is None:
            print(f"Không thể đọc ảnh mẫu: {button_image_path}")
            return None
            
        # Chụp và đọc ảnh màn hình của đúng device
        from utils.adb_utils import take_screenshot, get_screenshot_path, set_device, is_real_device_id
        if is_real_device_id(device_id):
            set_device(device_id)
        if not take_screenshot(device_id=device_id):
            return None

        screen = cv2.imread(get_screenshot_path(device_id))
        if screen is None:
            print(f"Không thể đọc ảnh màn hình: {get_screenshot_path(device_id)}")
            return None
            
        # Thêm xử lý ảnh để cải thiện độ chính xác
        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        
        # Áp dụng Gaussian blur để giảm nhiễu
        screen_gray = cv2.GaussianBlur(screen_gray, (5,5), 0)
        template_gray = cv2.GaussianBlur(template_gray, (5,5), 0)
            
        # Tìm kiếm template trong ảnh màn hình
        result = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        # Kiểm tra độ chính xác
        if max_val >= threshold:
            h, w = template.shape[:2]
            center_x = max_loc[0] + w // 2
            center_y = max_loc[1] + h // 2
            print(f"Tìm thấy nút với độ chính xác: {max_val:.2f} trên device {device_id}")
            return (center_x, center_y)
        else:
            print(f"Không tìm thấy nút với độ chính xác đủ cao: {max_val:.2f} trên device {device_id}")
            return None
    except Exception as e:
        print(f"Lỗi khi tìm nút trên màn hình device {device_id}: {e}")
        return None

def check_button_exists(button_name, device_id=None, threshold=0.95):
    """Kiểm tra xem nút có tồn tại trên màn hình không"""
    # Giảm threshold cho các button rally cụ thể
    if button_name in ["chon", "hanh_quan"]:
        threshold = 0.65
        print(f"🔍 Rally button '{button_name}': Using lower threshold {threshold}")
    
    try:
        # Xử lý đường dẫn ảnh với language support
        if isinstance(button_name, tuple):
            base_path = "/".join(button_name)
        else:
            base_path = button_name
        
        # Get language-aware path
        button_path = get_image_path(f"buttons/{base_path}")
        
        # Try different extensions
        if not os.path.exists(f"{button_path}.JPG"):
            if not os.path.exists(f"{button_path}.jpg"):
                print(f"Không tìm thấy ảnh nút {button_path}")
                return False
            else:
                button_path = f"{button_path}.jpg"
        else:
            button_path = f"{button_path}.JPG"
            
        button_pos = find_button_on_screen(button_path, device_id, threshold)
        return button_pos is not None
    except Exception as e:
        print(f"Lỗi khi kiểm tra nút trên device {device_id}: {e}")
        return False

def find_and_click_button(button_name, device_id=None, wait_time=1, max_retries=1, threshold=0.95):
    """Tìm và click vào nút với số lần thử lại"""
    # Giảm threshold cho các button rally cụ thể
    if button_name in ["chon", "hanh_quan"]:
        threshold = 0.65
        print(f"🔍 Rally button '{button_name}': Using lower threshold {threshold}")
    
    for attempt in range(max_retries):
        try:
            print(f"Đang tìm nút {button_name} trên device {device_id}... (Lần thử {attempt + 1}/{max_retries})")
            # Tìm nút với language support
            if isinstance(button_name, tuple):
                base_path = "/".join(button_name)
            else:
                base_path = button_name
            
            # Get language-aware path
            button_path = get_image_path(f"buttons/{base_path}")
            
            # Try different extensions
            if not os.path.exists(f"{button_path}.JPG"):
                if not os.path.exists(f"{button_path}.jpg"):
                    print(f"Không tìm thấy ảnh nút {button_path}")
                    return False
                else:
                    button_path = f"{button_path}.jpg"
            else:
                button_path = f"{button_path}.JPG"
                
            # Tìm vị trí nút trên màn hình
            button_pos = find_button_on_screen(button_path, device_id, threshold)
            if button_pos:
                # Tap vào đúng device đang xử lý
                from utils.adb_utils import tap_screen, set_device, is_real_device_id
                if is_real_device_id(device_id):
                    set_device(device_id)
                if tap_screen(button_pos[0], button_pos[1], device_id):
                    print(f"Đã tìm thấy và tap vào nút {button_name} trên device {device_id}")
                    time.sleep(wait_time)  # Chờ sau khi click
                    return True
                    
            if attempt < max_retries - 1:
                print(f"Thử lại sau 1 giây trên device {device_id}...")
                time.sleep(1)
            
        except Exception as e:
            print(f"Lỗi khi tìm nút {button_name} trên device {device_id} (Lần thử {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
                
    print(f"Đã thử {max_retries} lần không thành công trên device {device_id}")
    return False
def find_button_position(button_image_path, device_id=None, threshold=0.95):
    """Tìm vị trí và kích thước của nút trên màn hình"""
    try:    
        # Đọc ảnh mẫu và ảnh màn hình
        template = cv2.imread(button_image_path)
        if template is None:
            print(f"Không thể đọc ảnh mẫu: {button_image_path}")
            return None
            
        # Chụp màn hình hiện tại của đúng device
        from utils.adb_utils import take_screenshot, get_screenshot_path, set_device, is_real_device_id
        if is_real_device_id(device_id):
            set_device(device_id)
        if not take_screenshot(device_id=device_id):
            return None

        screen = cv2.imread(get_screenshot_path(device_id))
        if screen is None:
            print(f"Không thể đọc ảnh màn hình: {get_screenshot_path(device_id)}")
            return None
            
        # Tìm kiếm template trong ảnh màn hình
        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        
        # Kiểm tra độ chính xác
        if max_val >= threshold:
            # Tính toán kích thước và vị trí của nút
            h, w = template.shape[:2]
            return {
                'x': max_loc[0],
                'y': max_loc[1],
                'width': w,
                'height': h,
                'center_x': max_loc[0] + w // 2,
                'center_y': max_loc[1] + h // 2,
                'right_center_x': max_loc[0] + w,
                'right_center_y': max_loc[1] + h // 2,
                'bottom_center_x': max_loc[0] + w // 2,
                'bottom_center_y': max_loc[1] + h
            }
        else:
            print(f"Không tìm thấy nút với độ chính xác đủ cao: {max_val} trên device {device_id}")
            return None
    except Exception as e:
        print(f"Lỗi khi tìm nút trên màn hình device {device_id}: {e}")
        return None


def find_and_click_at_width_ratio(button_name, device_id=None, wait_time=1, threshold=0.8, width_ratio=0.8):
    """Tìm nút và click tại tỷ lệ chiều ngang (0=trái, 1=phải)."""
    try:
        print(f"Đang tìm nút {button_name} trên device {device_id} (click {width_ratio:.0%} chiều rộng)...")
        if isinstance(button_name, tuple):
            base_path = "/".join(button_name)
        else:
            base_path = button_name

        button_path = get_image_path(f"buttons/{base_path}")

        if not os.path.exists(f"{button_path}.JPG"):
            if not os.path.exists(f"{button_path}.jpg"):
                print(f"Không tìm thấy ảnh nút {button_path}")
                return False
            else:
                button_path = f"{button_path}.jpg"
        else:
            button_path = f"{button_path}.JPG"

        button_info = find_button_position(button_path, device_id, threshold)
        if button_info:
            from utils.adb_utils import tap_screen
            click_x = button_info['x'] + int(button_info['width'] * width_ratio)
            click_y = button_info['center_y']
            if tap_screen(click_x, click_y, device_id):
                print(
                    f"Đã tap {button_name} tại {width_ratio:.0%} chiều rộng "
                    f"({click_x}, {click_y}) trên device {device_id}"
                )
                time.sleep(wait_time)
                return True

        return False
    except Exception as e:
        print(f"Lỗi khi click {button_name} theo tỷ lệ ngang trên device {device_id}: {e}")
        return False


def find_and_click_right_edge(button_name, device_id=None, wait_time=1, threshold=0.8):
    """Tìm và click vào cạnh phải của nút"""
    try:
        print(f"Đang tìm nút {button_name} trên device {device_id}...")
        # Tìm nút với language support
        if isinstance(button_name, tuple):
            base_path = "/".join(button_name)
        else:
            base_path = button_name
        
        # Get language-aware path
        button_path = get_image_path(f"buttons/{base_path}")
        
        # Try different extensions
        if not os.path.exists(f"{button_path}.JPG"):
            if not os.path.exists(f"{button_path}.jpg"):
                print(f"Không tìm thấy ảnh nút {button_path}")
                return False
            else:
                button_path = f"{button_path}.jpg"
        else:
            button_path = f"{button_path}.JPG"
            
        # Tìm vị trí nút trên màn hình
        button_info = find_button_position(button_path, device_id, threshold)
        if button_info:
            # Tap vào cạnh phải của nút
            from utils.adb_utils import tap_screen
            if tap_screen(button_info['right_center_x'], button_info['right_center_y'], device_id):
                print(f"Đã tìm thấy và tap vào cạnh phải của nút {button_name} trên device {device_id}")
                time.sleep(wait_time)  # Chờ sau khi click
                return True
                
        return False
    except Exception as e:
        print(f"Lỗi khi tìm nút {button_name} trên device {device_id}: {e}")
        return False

def find_and_click_bottom_edge(button_name, device_id=None, wait_time=1):
    """Tìm và click vào điểm giữa cạnh dưới của nút"""
    try:
        print(f"Đang tìm nút {button_name} trên device {device_id}...")
        # Tìm nút với language support
        if isinstance(button_name, tuple):
            base_path = "/".join(button_name)
        else:
            base_path = button_name
        
        # Get language-aware path
        button_path = get_image_path(f"buttons/{base_path}")
        
        # Try different extensions
        if not os.path.exists(f"{button_path}.JPG"):
            if not os.path.exists(f"{button_path}.jpg"):
                print(f"Không tìm thấy ảnh nút {button_path}")
                return False
            else:
                button_path = f"{button_path}.jpg"
        else:
            button_path = f"{button_path}.JPG"
            
        # Tìm vị trí nút trên màn hình
        button_info = find_button_position(button_path, device_id, 0.9)
        if button_info:
            # Tap vào điểm giữa cạnh dưới của nút
            from utils.adb_utils import tap_screen
            if tap_screen(button_info['bottom_center_x'], button_info['bottom_center_y'], device_id):
                print(f"Đã tìm thấy và tap vào điểm giữa cạnh dưới của nút {button_name} trên device {device_id}")
                time.sleep(wait_time)  # Chờ sau khi click
                return True
                
        return False
    except Exception as e:
        print(f"Lỗi khi tìm nút {button_name} trên device {device_id}: {e}")
        return False
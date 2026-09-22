import subprocess
import re
import time
import os

# Biến toàn cục để lưu device đang được sử dụng
current_device = None
_adb_sema = None


def set_adb_semaphore(sema):
    """Giữ API cũ; không giới hạn ADB để mỗi device chạy độc lập như Rally/Buy Meat."""
    global _adb_sema
    _adb_sema = sema

def get_memu_devices():
    """Lấy danh sách các thiết bị MEmu đang chạy"""
    try:
        output = subprocess.run("adb devices", shell=True, capture_output=True, text=True).stdout
        memu_devices = []
        for line in output.split('\n')[1:]:  # Bỏ qua dòng đầu tiên
            if line.strip() and "127.0.0.1:" in line:
                device_id = line.split()[0]
                port = device_id.split(':')[1]
                index = int(port) - 21503  # MEmu bắt đầu từ port 21503
                memu_devices.append({
                    'device_id': device_id,
                    'name': f'MEmu_{index}',
                    'index': index
                })
        return sorted(memu_devices, key=lambda x: x['index'])
    except Exception as e:
        print(f"Lỗi khi lấy danh sách MEmu: {e}")
        return []

def select_memu_devices():
    """Hiển thị danh sách MEmu và cho phép người dùng chọn"""
    devices = get_memu_devices()
    if not devices:
        print("Không tìm thấy MEmu nào đang chạy!")
        return []
    
    print("\nDanh sách MEmu đang chạy:")
    for device in devices:
        print(f"{device['index']}. {device['name']} ({device['device_id']})")
    
    choice = input("\nChọn số thứ tự MEmu (Enter để chọn tất cả, các số cách nhau bởi dấu cách, -idx để loại bỏ device, -idx1 -idx2 để loại bỏ nhiều): ").strip()
    if not choice:
        return devices
        
    try:
        # Xử lý trường hợp loại bỏ device (có thể nhiều device)
        if choice.startswith('-'):
            # Tách các số loại bỏ (ví dụ: "-1 -2 -3" -> ["-1", "-2", "-3"])
            exclude_parts = choice.split()
            exclude_indices = []
            
            for part in exclude_parts:
                if part.startswith('-'):
                    try:
                        exclude_index = int(part[1:])  # Lấy số sau dấu -
                        exclude_indices.append(exclude_index)
                    except ValueError:
                        print(f"Lỗi: '{part}' không phải là số hợp lệ!")
                        continue
            
            # Loại bỏ các device có index trong danh sách exclude
            selected_devices = [d for d in devices if d['index'] not in exclude_indices]
            
            # Thông báo kết quả
            if len(selected_devices) == len(devices):
                print(f"Không tìm thấy device nào trong danh sách loại bỏ: {exclude_indices}")
            else:
                excluded_count = len(devices) - len(selected_devices)
                print(f"Đã loại bỏ {excluded_count} device: {exclude_indices}")
                print(f"Còn lại {len(selected_devices)} device")
            
            return selected_devices
            
        # Tách các số và chuyển thành list số nguyên
        indices = [int(x.strip()) for x in choice.split()]
        
        # Lọc các thiết bị được chọn
        selected_devices = [d for d in devices if d['index'] in indices]
        
        if not selected_devices:
            print("Không có số thứ tự nào hợp lệ!")
            return []
            
        return selected_devices
        
    except ValueError:
        print("Vui lòng nhập số!")
        return []

def is_real_device_id(device_id):
    """True nếu là serial ADB thật, không phải placeholder như 'none'."""
    return bool(device_id) and device_id != "none"


def set_device(device_id):
    """Thiết lập thiết bị hiện tại"""
    global current_device
    current_device = device_id


def resolve_adb_serial(device_id=None):
    """Serial thật để gắn -s. Ưu tiên device_id, sau đó current_device của process."""
    if is_real_device_id(device_id):
        return str(device_id)
    if is_real_device_id(current_device):
        return str(current_device)
    return None


def sanitize_device_key(device_id=None):
    """Key thư mục/file screenshot, luôn cùng một cách thay thế ký tự."""
    serial = resolve_adb_serial(device_id) or device_id or "default"
    return str(serial).replace(":", "_").replace(".", "_")


def get_screenshot_path(device_id=None):
    """Một đường dẫn duy nhất cho mỗi device — chỗ ghi và chỗ đọc phải dùng hàm này."""
    key = sanitize_device_key(device_id)
    folder = os.path.join("images", f"device_{key}")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"current_screen_{key}.JPG")


def adb_command(command, device_id=None):
    """Thực hiện lệnh adb và trả về kết quả"""
    try:
        target = resolve_adb_serial(device_id)
        if target:
            command = command.replace("adb ", f"adb -s {target} ", 1)
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout
    except Exception as e:
        print(f"Lỗi khi thực hiện lệnh ADB: {e}")
        return None


def get_screen_size():
    """Lấy kích thước màn hình thiết bị"""
    try:
        output = adb_command("adb shell wm size")
        match = re.search(r'(\d+)x(\d+)', output)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None
    except Exception as e:
        print(f"Lỗi khi lấy kích thước màn hình: {e}")
        return None


def tap_screen(x, y, device_id=None):
    """Thực hiện tap (chạm) vào màn hình"""
    try:
        serial = resolve_adb_serial(device_id)
        if serial:
            set_device(serial)
        adb_command(f"adb shell input tap {x} {y}", serial or device_id)
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Lỗi khi tap màn hình: {e}")
        return False


def swipe_screen(x1, y1, x2, y2, duration=500):
    """Thực hiện swipe (vuốt) màn hình"""
    try:
        adb_command(f"adb shell input swipe {x1} {y1} {x2} {y2} {duration}")
        time.sleep(1)
        return True
    except Exception as e:
        print(f"Lỗi khi swipe màn hình: {e}")
        return False


def swipe_down():
    """Kéo màn hình xuống để kiểm tra các cuộc chiến tranh"""
    try:
        screen_width, screen_height = get_screen_size()
        if not screen_width or not screen_height:
            return False
            
        # Tính toán vị trí vuốt
        start_x = screen_width // 2
        start_y = screen_height * 0.7  # Bắt đầu từ 70% chiều cao màn hình
        end_x = screen_width // 2
        end_y = screen_height * 0.3    # Kết thúc ở 30% chiều cao màn hình
        
        # Thực hiện vuốt
        if swipe_screen(start_x, start_y, end_x, end_y):
            print("Đã kéo màn hình xuống để kiểm tra các cuộc chiến tranh")
            time.sleep(1)  # Chờ màn hình ổn định
            return True
        return False
    except Exception as e:
        print(f"Lỗi khi kéo màn hình xuống: {e}")
        return False


def swipe_up():
    """Kéo màn hình lên để trở về vị trí ban đầu"""
    try:
        screen_width, screen_height = get_screen_size()
        if not screen_width or not screen_height:
            return False
            
        # Tính toán vị trí vuốt (ngược lại với swipe_down)
        start_x = screen_width // 2
        start_y = screen_height * 0.3  # Bắt đầu từ 30% chiều cao màn hình
        end_x = screen_width // 2
        end_y = screen_height * 0.7    # Kết thúc ở 70% chiều cao màn hình
        
        # Thực hiện vuốt
        if swipe_screen(start_x, start_y, end_x, end_y):
            print("Đã kéo màn hình lên để trở về vị trí ban đầu")
            time.sleep(1)  # Chờ màn hình ổn định
            return True
        return False
    except Exception as e:
        print(f"Lỗi khi kéo màn hình lên: {e}")
        return False


def take_screenshot(filename="screenshot.JPG", device_id=None):
    """Chụp màn hình của đúng 1 device, lưu file riêng. Không dùng exec-out để tránh lẫn stdout."""
    try:
        serial = resolve_adb_serial(device_id)
        if not serial:
            print("take_screenshot: không có serial ADB, bỏ qua")
            return False

        set_device(serial)
        full_path = get_screenshot_path(serial)
        remote = f"/sdcard/evony_{sanitize_device_key(serial)}.png"

        subprocess.run(
            ["adb", "-s", serial, "shell", "screencap", "-p", remote],
            capture_output=True,
            timeout=20,
        )
        subprocess.run(
            ["adb", "-s", serial, "pull", remote, full_path],
            capture_output=True,
            timeout=20,
        )
        subprocess.run(
            ["adb", "-s", serial, "shell", "rm", "-f", remote],
            capture_output=True,
            timeout=10,
        )

        if not os.path.isfile(full_path) or os.path.getsize(full_path) < 100:
            print(f"take_screenshot: file rỗng hoặc thiếu cho {serial} ({full_path})")
            return False
        return True
    except Exception as e:
        print(f"Lỗi khi chụp màn hình: {e}")
        return False

def input_text(text):
    """Nhập text vào trường đang focus"""
    try:
        adb_command(f'adb shell input text "{text}"')
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"Lỗi khi nhập text: {e}")
        return False


def cancel_action():
    """Hủy thao tác hiện tại bằng cách nhấn ESC và nút cancel"""
    try:
        adb_command('adb shell input keyevent KEYCODE_ESCAPE')
        time.sleep(1)
        from utils.image_utils import find_and_click_button
        if find_and_click_button("cancel"):
            print("Đã nhấn hủy thành công")
        time.sleep(2)
        return True
    except Exception as e:
        print(f"Lỗi khi hủy thao tác: {e}")
        return False


def is_evony_running():
    """Kiểm tra xem game Evony có đang chạy không"""
    try:
        # Chỉ kiểm tra process của Evony bằng ps
        result = adb_command('adb shell ps | grep com.topgamesinc.evony')
        return bool(result and 'com.topgamesinc.evony' in result)
    except Exception as e:
        print(f"Lỗi khi kiểm tra trạng thái Evony: {e}")
        return False

def ensure_evony_running():
    """Đảm bảo game Evony đang chạy, khởi động lại nếu cần"""
    if not is_evony_running():
        print("Không tìm thấy game Evony đang chạy, đang khởi động...")
        adb_command('adb shell monkey -p com.topgamesinc.evony -c android.intent.category.LAUNCHER 1')
        time.sleep(50)  # Đợi game khởi động
    return True
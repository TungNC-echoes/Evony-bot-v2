"""
Process Manager for EVONY AUTO
Handles all automation processes and task execution
"""

import multiprocessing
import time
from utils.adb_utils import set_device, set_adb_semaphore
from actions.rally import auto_join_rally, auto_join_advanced_rally_with_boss_selection
from actions.market_actions import auto_buy_meat
from actions.open_items_actions import open_items_sequence, open_items_selective_sequence
from actions.get_location_boss import get_boss_locations, save_to_json
from actions.boss_data_manager import group_bosses_by_name
from actions.boss_attacker import attack_selected_bosses


def run_single_task_process(task, task_index, total_tasks, log_queue, adb_sema=None):
    """Hàm chạy trong process con - không có GUI"""
    try:
        if adb_sema is not None:
            set_adb_semaphore(adb_sema)

        device = task['device']
        feature_code = task['feature_code']
        feature_name = task['feature_name']
        device_id = device['device_id']
        
        if feature_code != "5":
            log_queue.put(f"🔄 [Task {task_index}/{total_tasks}] Bắt đầu {feature_name} trên {device['name']} (Device ID: {device_id})")
        
        # Thiết lập device
        set_device(device_id)
        
        # Chạy feature tương ứng
        if feature_code == "1":
            use_assistant_general = task.get('use_assistant_general', False)
            run_rally_direct_process(
                device_id,
                use_general=True,
                log_queue=log_queue,
                use_assistant_general=use_assistant_general,
            )
        elif feature_code == "2":
            run_buy_meat_direct_process(device_id, log_queue=log_queue)
        elif feature_code == "3":
            run_rally_direct_process(device_id, use_general=False, log_queue=log_queue)
        elif feature_code == "4":
            # Get troops_count from task for attack_boss
            troops_count = task.get('troops_count', 1000)  # Default fallback
            use_assistant_general = task.get('use_assistant_general', False)
            run_attack_boss_direct_process(
                device_id,
                log_queue=log_queue,
                troops_count=troops_count,
                use_assistant_general=use_assistant_general,
            )
        elif feature_code == "5":
            open_resource = task.get('open_resource', True)
            open_gems = task.get('open_gems', False)
            run_open_items_direct_process(
                device_id,
                log_queue=log_queue,
                open_resource=open_resource,
                open_gems=open_gems,
            )
        elif feature_code == "6":
            run_buy_general_direct_process(device_id, log_queue=log_queue)
        elif feature_code == "7":
            # Advanced Rally
            selected_bosses = task.get('selected_bosses', [])
            use_assistant_general = task.get('use_assistant_general', False)
            run_advanced_rally_direct_process(
                device_id,
                log_queue=log_queue,
                selected_bosses=selected_bosses,
                use_assistant_general=use_assistant_general,
            )
        elif feature_code == "8":
            # Advanced War
            selected_bosses = task.get('selected_bosses', [])
            run_advanced_war_direct_process(device_id, log_queue=log_queue, selected_bosses=selected_bosses)
        
        if feature_code != "5":
            log_queue.put(f"✅ [Task {task_index}/{total_tasks}] Hoàn thành {feature_name} trên {device['name']}")
            
    except Exception as e:
        log_queue.put(f"❌ Lỗi nghiêm trọng trong task {task_index}: {e}")


def run_rally_direct_process(device_id, use_general=True, log_queue=None, use_assistant_general=False):
    """Chạy auto_join_rally trong process con"""
    try:
        if log_queue:
            log_queue.put(f"⚔️ Bắt đầu auto rally trên device {device_id}")
        auto_join_rally(device_id, use_general, use_assistant_general=use_assistant_general)
    except Exception as e:
        if log_queue:
            log_queue.put(f"❌ Lỗi khi chạy auto rally trên {device_id}: {e}")


def run_buy_meat_direct_process(device_id, log_queue=None):
    """Chạy auto_buy_meat trong process con"""
    try:
        if log_queue:
            log_queue.put(f"🛒 Bắt đầu auto buy meat trên device {device_id}")
        auto_buy_meat(device_id)
    except Exception as e:
        if log_queue:
            log_queue.put(f"❌ Lỗi khi chạy auto buy meat trên {device_id}: {e}")


def run_attack_boss_direct_process(device_id, log_queue=None, troops_count=1000, use_assistant_general=False):
    """Chạy attack_boss trong process con với vòng lặp vô hạn giống attack_boss.py"""
    try:
        if log_queue:
            assistant_text = "có tướng phụ" if use_assistant_general else "không tướng phụ"
            log_queue.put(f"👹 Bắt đầu tấn công boss trên device {device_id} với {troops_count} quân ({assistant_text})")
        
        from actions.get_location_boss import get_boss_locations, save_to_json
        
        # Lưu danh sách tên boss được chọn ban đầu
        selected_boss_names = set()
        initial_selection = None
        
        while True:  # Vòng lặp chính để cập nhật boss (vô hạn)
            try:
                # Bước 1: Cập nhật vị trí boss từ iScout
                if log_queue:
                    log_queue.put(f"📡 Đang cập nhật vị trí boss (iScout) cho device {device_id}...")
                
                def _plog(msg):
                    if log_queue:
                        log_queue.put(msg)

                if log_queue:
                    log_queue.put("🔍 Đang gọi get_boss_locations()...")
                bosses = get_boss_locations(log_fn=_plog)
                
                if log_queue:
                    log_queue.put(f"📊 Kết quả get_boss_locations(): {type(bosses)} - {len(bosses) if bosses else 0} boss")
                
                if not bosses:
                    if log_queue:
                        log_queue.put("❌ Không tìm thấy thông tin boss! Thử lại sau 60 giây.")
                    time.sleep(60)
                    continue
                    
                # Lưu thông tin boss vào file
                if not save_to_json(bosses, device_id=device_id):
                    if log_queue:
                        log_queue.put("❌ Không thể lưu thông tin boss vào file!")
                    time.sleep(60)
                    continue
                
                # Bước 2: Xử lý lựa chọn boss
                if not selected_boss_names:  # Nếu chưa có lựa chọn ban đầu
                    # Tự động chọn tất cả boss có sẵn
                    boss_groups = group_bosses_by_name(bosses)
                    initial_selection = []
                    
                    for boss_name, boss_group in boss_groups.items():
                        initial_selection.append(boss_group)
                        selected_boss_names.add(boss_name)
                    
                    if not initial_selection:
                        if log_queue:
                            log_queue.put("❌ Không có boss nào để tấn công!")
                        time.sleep(60)
                        continue
                    
                    if log_queue:
                        log_queue.put(f"✅ Đã tự động chọn {len(initial_selection)} loại boss để tấn công")
                else:  # Đã có lựa chọn trước đó, tạo lại initial_selection từ dữ liệu boss mới
                    boss_groups = group_bosses_by_name(bosses)
                    initial_selection = []
                    for name in selected_boss_names:
                        if name in boss_groups:
                            initial_selection.append(boss_groups[name])
                
                # Bước 3: Bắt đầu vòng lặp tấn công
                start_time = time.time()
                while True:
                    # Kiểm tra số boss chưa tấn công và hiển thị thông tin
                    unattacked_count = sum(1 for group in initial_selection
                                         for _, boss in group
                                         if not boss.get('attacked', 0))
                    
                    remaining_time = int(1800 - (time.time() - start_time))  # 30 phút = 1800 giây
                    if log_queue:
                        log_queue.put(f"⏱️ Còn {unattacked_count} boss, thời gian: {remaining_time}s")
                    
                    # Thực hiện tấn công các boss đã chọn với troops_count từ UI
                    result = attack_selected_bosses(
                        initial_selection,
                        bosses,
                        start_time,
                        troops_count,
                        use_assistant_general,
                    )
                    
                    # Kiểm tra kết quả
                    if result == "update_required" or remaining_time <= 0:
                        if log_queue:
                            log_queue.put("⏰ Đã đủ 30 phút, cập nhật lại vị trí boss...")
                        break  # Thoát vòng lặp tấn công để cập nhật boss
                    elif unattacked_count == 0:
                        if log_queue:
                            log_queue.put("🎯 Đã hết boss, cập nhật lại vị trí boss...")
                        break  # Thoát vòng lặp tấn công để cập nhật boss
                    
                    time.sleep(1)
                
            except Exception as e:
                if log_queue:
                    log_queue.put(f"❌ Lỗi: {e}")
                    log_queue.put("Thử lại sau 1 phút...")
                time.sleep(60)
                 
    except Exception as e:
        if log_queue:
            log_queue.put(f"❌ Lỗi nghiêm trọng khi tấn công boss trên {device_id}: {e}")


def run_open_items_direct_process(device_id, log_queue=None, open_resource=True, open_gems=False):
    """Chạy open_items trong process con"""
    try:
        while True:
            try:
                result = open_items_sequence(
                    device_id,
                    open_resource=open_resource,
                    open_gems=open_gems,
                    log_queue=log_queue,
                )
                if result == "done":
                    return
                if not result and log_queue:
                    log_queue.put(f"📦 [{device_id}] Lỗi, thử lại")
                time.sleep(5)

            except Exception as e:
                if log_queue:
                    log_queue.put(f"📦 [{device_id}] Lỗi: {e}")
                time.sleep(10)

    except Exception as e:
        if log_queue:
            log_queue.put(f"📦 [{device_id}] Lỗi nghiêm trọng: {e}")

def run_advanced_rally_direct_process(device_id, log_queue=None, selected_bosses=None, use_assistant_general=False):
    """Chạy Advanced Rally với boss selection trong process con"""
    try:
        if log_queue:
            log_queue.put(f"🎯 Bắt đầu Advanced Rally trên device {device_id}")
            log_queue.put(f"📋 Selected bosses: {selected_bosses}")
            log_queue.put(f"🔍 Debug: selected_bosses type: {type(selected_bosses)}, length: {len(selected_bosses) if selected_bosses else 0}")
        
        # Kiểm tra selected_bosses
        if selected_bosses is None:
            if log_queue:
                log_queue.put("⚠️ selected_bosses is None, sử dụng logic Basic Rally")
            # Fallback to Basic Rally if selected_bosses is None (error case)
            from actions.rally import auto_join_rally
            auto_join_rally(device_id, use_general=True, use_assistant_general=use_assistant_general)
        elif len(selected_bosses) == 0:
            if log_queue:
                log_queue.put("⚠️ Không có boss nào được chọn, sử dụng logic Basic Rally")
            # Fallback to Basic Rally if no bosses selected
            from actions.rally import auto_join_rally
            auto_join_rally(device_id, use_general=True, use_assistant_general=use_assistant_general)
        else:
            # Gọi function Advanced Rally
            auto_join_advanced_rally_with_boss_selection(
                device_id,
                use_general=True,
                selected_bosses=selected_bosses,
                use_assistant_general=use_assistant_general,
            )
        
        if log_queue:
            log_queue.put(f"✅ Hoàn thành Advanced Rally trên device {device_id}")
    except Exception as e:
        if log_queue:
            log_queue.put(f"❌ Lỗi khi chạy Advanced Rally trên {device_id}: {e}")

def run_advanced_war_direct_process(device_id, log_queue=None, selected_bosses=None):
    """Chạy Advanced War với boss selection trong process con"""
    try:
        if log_queue:
            log_queue.put(f"🎯 Bắt đầu Advanced War trên device {device_id}")
            log_queue.put(f"📋 Selected bosses: {selected_bosses}")
            log_queue.put(f"🔍 Debug: selected_bosses type: {type(selected_bosses)}, length: {len(selected_bosses) if selected_bosses else 0}")
        
        # Kiểm tra selected_bosses
        if selected_bosses is None:
            if log_queue:
                log_queue.put("⚠️ selected_bosses is None, sử dụng logic Basic Rally")
            # Fallback to Basic Rally if selected_bosses is None (error case)
            from actions.rally import auto_join_rally
            auto_join_rally(device_id, use_general=False)
        elif len(selected_bosses) == 0:
            if log_queue:
                log_queue.put("⚠️ Không có boss nào được chọn, sử dụng logic Basic Rally")
            # Fallback to Basic Rally if no bosses selected
            from actions.rally import auto_join_rally
            auto_join_rally(device_id, use_general=False)
        else:
            # Gọi function Advanced Rally (không chọn tướng)
            auto_join_advanced_rally_with_boss_selection(device_id, use_general=False, selected_bosses=selected_bosses)
        
        if log_queue:
            log_queue.put(f"✅ Hoàn thành Advanced War trên device {device_id}")
    except Exception as e:
        if log_queue:
            log_queue.put(f"❌ Lỗi khi chạy Advanced War trên {device_id}: {e}")


def run_buy_general_direct_process(device_id, log_queue=None):
    """Chạy auto_buy_general trong process con"""
    try:
        if log_queue:
            log_queue.put(f"🛒 Bắt đầu auto buy general trên device {device_id}")
        
        from actions.buy_general_actions import auto_buy_general
        auto_buy_general(device_id)
        
        if log_queue:
            log_queue.put(f"✅ Hoàn thành auto buy general trên device {device_id}")
    except Exception as e:
        if log_queue:
            log_queue.put(f"❌ Lỗi khi chạy auto buy general trên {device_id}: {e}")

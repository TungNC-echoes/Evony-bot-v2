"""
Device Manager for EVONY AUTO
Handles device operations, drag & drop, and device state management
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import threading
import time
from utils.adb_utils import get_memu_devices


class DeviceManager:
    """Manages device operations and state"""
    
    def __init__(self, gui_instance):
        self.gui = gui_instance
        self.devices = []
        self.dragged_devices = []
        self.dragged_device = None
        self.dragged_from_feature = None
        
        # Feature containers - mỗi feature sẽ chứa devices được kéo vào
        self.feature_devices = {
            "rally": [],
            "buy_meat": [],
            "war_no_general": [],
            "attack_boss": [],
            "open_items": [],
            "buy_general": [],
            "advanced_rally": [],
            "advanced_war": []
        }
        
        # Device-process mapping để track process của từng device
        self.device_process_mapping = {
            "rally": {},      # {device_id: process}
            "buy_meat": {},
            "war_no_general": {},
            "attack_boss": {},
            "open_items": {},
            "buy_general": {},
            "advanced_rally": {},
            "advanced_war": {}
        }
    
    def kill_specific_device_process(self, device_id, device_name, feature_key):
        """Kill process của device cụ thể (không kill toàn bộ feature)"""
        def kill_process():
            try:
                self.gui.log_status(f"🔄 Đang kill process cho {device_name} (ID: {device_id})...")
                
                # Tìm và kill process của device cụ thể từ mapping
                if device_id in self.device_process_mapping[feature_key]:
                    process = self.device_process_mapping[feature_key][device_id]
                    
                    try:
                        if process.is_alive():
                            self.gui.log_status(f"🔪 Đang kill process cho {device_name}...")
                            process.terminate()
                            process.join(timeout=3.0)
                            if process.is_alive():
                                process.kill()
                                process.join(timeout=1.0)
                            
                            # Remove process từ mapping
                            del self.device_process_mapping[feature_key][device_id]
                            
                            # Remove process từ feature_status
                            if hasattr(self.gui, 'feature_status') and feature_key in self.gui.feature_status:
                                feature_processes = self.gui.feature_status[feature_key]["processes"]
                                if process in feature_processes:
                                    feature_processes.remove(process)
                            
                            self.gui.log_status(f"✅ Đã kill process cho {device_name}")
                        else:
                            # Process đã chết, chỉ cần remove khỏi mapping
                            del self.device_process_mapping[feature_key][device_id]
                            self.gui.log_status(f"✅ Process cho {device_name} đã chết, đã remove khỏi mapping")
                            
                    except Exception as e:
                        self.gui.log_status(f"⚠️ Lỗi khi kill process cho {device_name}: {e}")
                        # Vẫn remove khỏi mapping nếu có lỗi
                        if device_id in self.device_process_mapping[feature_key]:
                            del self.device_process_mapping[feature_key][device_id]
                else:
                    self.gui.log_status(f"⚠️ Không tìm thấy process cho {device_name} trong mapping")
                
                # Kiểm tra nếu feature còn devices khác
                remaining_devices = len(self.feature_devices[feature_key])
                if remaining_devices <= 1:  # Chỉ còn device này hoặc không còn device nào
                    # Dừng feature hoàn toàn
                    if hasattr(self.gui, 'feature_status') and feature_key in self.gui.feature_status:
                        if self.gui.feature_status[feature_key]["running"]:
                            self.gui.feature_status[feature_key]["running"] = False
                            
                            # Kill tất cả processes còn lại
                            feature_processes = self.gui.feature_status[feature_key]["processes"]
                            for process in feature_processes:
                                try:
                                    if process.is_alive():
                                        process.terminate()
                                        process.join(timeout=1.0)
                                        if process.is_alive():
                                            process.kill()
                                except:
                                    pass
                            
                            # Clear process list và mapping
                            feature_processes.clear()
                            self.device_process_mapping[feature_key].clear()
                            
                            # Update UI
                            try:
                                start_button = getattr(self.gui, f"{feature_key}_start_button")
                                stop_button = getattr(self.gui, f"{feature_key}_stop_button")
                                status_label = getattr(self.gui, f"{feature_key}_status_label")
                                
                                start_button.config(state=tk.NORMAL)
                                stop_button.config(state=tk.DISABLED)
                                status_label.config(text="⏸️ Stopped")
                            except:
                                pass
                            
                            self.gui.log_status(f"⏹️ Feature {feature_key} đã dừng (không còn devices)")
                        else:
                            self.gui.log_status(f"✅ Đã kill process cho {device_name} từ {feature_key}")
                    else:
                        self.gui.log_status(f"✅ Đã kill process cho {device_name} từ {feature_key}")
                else:
                    # Feature vẫn tiếp tục chạy với devices còn lại
                    self.gui.log_status(f"✅ Đã kill process cho {device_name}, {feature_key} vẫn chạy với {remaining_devices-1} devices")
                
            except Exception as e:
                self.gui.log_status(f"❌ Lỗi khi kill device process: {e}")
        
        # Chạy kill process trong thread riêng để không block UI
        kill_thread = threading.Thread(target=kill_process)
        kill_thread.daemon = True
        kill_thread.start()
    
    def auto_start_feature_for_device(self, device_id, device_name, feature_key):
        """Tự động start feature cho device mới được thêm vào"""
        def start_feature():
            try:
                # Đợi một chút để đảm bảo device đã được thêm vào feature
                time.sleep(1.0)
                
                # Kiểm tra xem feature có đang chạy không
                if hasattr(self.gui, 'feature_status') and feature_key in self.gui.feature_status:
                    if self.gui.feature_status[feature_key]["running"]:
                        self.gui.log_status(f"🚀 Tự động start {feature_key} cho {device_name}...")
                        
                        # Tạo task cho device mới
                        device_info = {'device_id': device_id, 'name': device_name}
                        
                        # Map feature key to feature code
                        feature_codes = {
                            "rally": "1",
                            "buy_meat": "2", 
                            "war_no_general": "3",
                            "attack_boss": "4",
                            "open_items": "5",
                            "buy_general": "6",
                            "advanced_rally": "7",
                            "advanced_war": "8"
                        }
                        
                        feature_code = feature_codes.get(feature_key, "1")
                        
                        # Tạo task
                        task = {
                            'device': device_info,
                            'feature_code': feature_code,
                            'feature_name': feature_key
                        }
                        
                        # Add troops_count for attack_boss feature
                        if feature_key == "attack_boss":
                            try:
                                troops_count = int(self.gui.attack_boss_troops_var.get().strip())
                                task['troops_count'] = troops_count
                            except:
                                task['troops_count'] = 1000  # Default fallback
                            task['use_assistant_general'] = bool(
                                getattr(self.gui, "attack_boss_select_assistant_var", None)
                                and self.gui.attack_boss_select_assistant_var.get()
                            )

                        if feature_key in ("rally", "advanced_rally"):
                            task['use_assistant_general'] = self.gui.get_use_assistant_general(feature_key)

                        if feature_key == "open_items":
                            open_resource, open_gems = self.gui.get_open_items_options()
                            task['open_resource'] = open_resource
                            task['open_gems'] = open_gems
                        
                        # Add selected_bosses for Advanced features
                        if feature_key in ["advanced_rally", "advanced_war"]:
                            try:
                                selected_bosses = self.gui.get_selected_bosses()
                                task['selected_bosses'] = selected_bosses
                                self.gui.log_status(f"🎯 Advanced {feature_key}: Sử dụng {len(selected_bosses)} boss được chọn")
                            except Exception as e:
                                self.gui.log_status(f"⚠️ Không thể lấy selected_bosses cho {feature_key}: {e}")
                                task['selected_bosses'] = []  # Default empty list
                        
                        # Import process manager
                        from components.process_manager import run_single_task_process
                        import multiprocessing
                        
                        # Tạo process mới cho device này (sử dụng multiprocessing.Process)
                        process = multiprocessing.Process(
                            target=run_single_task_process,
                            args=(task, 1, 1, self.gui.log_queue)
                        )
                        
                        # Thêm process vào danh sách
                        self.gui.feature_status[feature_key]["processes"].append(process)
                        
                        # Lưu process vào mapping để track theo device_id
                        self.device_process_mapping[feature_key][device_id] = process
                        
                        # Start process
                        process.start()
                        
                        self.gui.log_status(f"✅ Đã tự động start {feature_key} cho {device_name}")
                        
            except Exception as e:
                self.gui.log_status(f"❌ Lỗi khi auto start feature: {e}")
        
        # Chạy auto start trong thread riêng
        start_thread = threading.Thread(target=start_feature)
        start_thread.daemon = True
        start_thread.start()
    
    def refresh_devices(self):
        """Refresh danh sách devices - chỉ load những device chưa được assign"""
        try:
            self.gui.log_status("🔄 Đang tải danh sách devices...")
            all_devices = get_memu_devices()
            
            # Lấy danh sách device IDs đã được assign vào các feature
            assigned_device_ids = set()
            for feature_devices in self.feature_devices.values():
                for device in feature_devices:
                    assigned_device_ids.add(device['device_id'])
            
            # Lọc ra những device chưa được assign
            available_devices = []
            for device in all_devices:
                if device['device_id'] not in assigned_device_ids:
                    available_devices.append(device)
            
            # Clear existing items
            for item in self.gui.device_tree.get_children():
                self.gui.device_tree.delete(item)
            
            # Add available devices to treeview with alternating colors
            for i, device in enumerate(available_devices):
                device_id = device['device_id']
                device_name = device['name']
                
                # Add to treeview
                item = self.gui.device_tree.insert("", tk.END, values=(device_name, "Ready"))
                
                # Store device info in item
                self.gui.device_tree.item(item, tags=(device_id,))
                
                # Add alternating row colors for better visual separation
                if i % 2 == 0:
                    self.gui.device_tree.tag_configure("evenrow", background="#f8f9fa")
                    self.gui.device_tree.item(item, tags=(device_id, "evenrow"))
                else:
                    self.gui.device_tree.tag_configure("oddrow", background="#ffffff")
                    self.gui.device_tree.item(item, tags=(device_id, "oddrow"))
            
            # Cập nhật danh sách devices hiện tại
            self.devices = available_devices
            
            self.gui.log_status(f"✅ Đã tải {len(available_devices)} devices khả dụng (tổng cộng {len(all_devices)} devices)")
            
        except Exception as e:
            self.gui.log_status(f"❌ Lỗi khi tải devices: {e}")
            messagebox.showerror("Lỗi", f"Không thể tải danh sách devices:\n{e}")
    
    def refresh_all_devices(self):
        """Refresh toàn bộ danh sách devices từ ADB"""
        try:
            self.gui.log_status("🔄 Đang tải danh sách devices từ ADB...")
            all_devices = get_memu_devices()
            
            # Clear existing items
            for item in self.gui.device_tree.get_children():
                self.gui.device_tree.delete(item)
            
            # Add all devices to treeview with alternating colors
            for i, device in enumerate(all_devices):
                device_id = device['device_id']
                device_name = device['name']
                
                # Add to treeview
                item = self.gui.device_tree.insert("", tk.END, values=(device_name, "Ready"))
                
                # Store device info in item
                self.gui.device_tree.item(item, tags=(device_id,))
                
                # Add alternating row colors for better visual separation
                if i % 2 == 0:
                    self.gui.device_tree.tag_configure("evenrow", background="#f8f9fa")
                    self.gui.device_tree.item(item, tags=(device_id, "evenrow"))
                else:
                    self.gui.device_tree.tag_configure("oddrow", background="#ffffff")
                    self.gui.device_tree.item(item, tags=(device_id, "oddrow"))
            
            self.devices = all_devices
            self.gui.log_status(f"✅ Đã tải {len(all_devices)} devices từ ADB")
        except Exception as e:
            self.gui.log_status(f"❌ Lỗi khi tải devices từ ADB: {e}")
            messagebox.showerror("Lỗi", f"Không thể tải danh sách devices từ ADB:\n{e}")
    
    def select_all_devices(self):
        """Chọn tất cả devices (highlight)"""
        for item in self.gui.device_tree.get_children():
            self.gui.device_tree.selection_add(item)
    
    def clear_all_devices(self):
        """Clear selection"""
        self.gui.device_tree.selection_remove(self.gui.device_tree.selection())
    
    def add_device_to_feature(self, device_item, feature_key, show_log=True):
        """Thêm device vào feature container - trả về True nếu thành công"""
        if device_item:
            # Get device info
            device_id = self.gui.device_tree.item(device_item, "tags")[0]
            device_name = self.gui.device_tree.item(device_item, "values")[0]
            
            # Check if device already in this feature
            for device in self.feature_devices[feature_key]:
                if device['device_id'] == device_id:
                    if show_log:
                        self.gui.log_status(f"⚠️ Device {device_name} đã có trong {feature_key}")
                    return False
            
            # Add device to feature
            device_info = {'device_id': device_id, 'name': device_name}
            self.feature_devices[feature_key].append(device_info)
            
            # Add to feature tree with visual feedback
            feature_tree = getattr(self.gui, f"{feature_key}_tree")
            item = feature_tree.insert("", tk.END, values=(device_name, "Ready"), tags=(device_id,))
            
            # Add visual styling for the new item
            feature_tree.tag_configure("newitem", background="#d4edda", foreground="#155724")
            feature_tree.item(item, tags=(device_id, "newitem"))
            
            # Remove the highlight after a short delay
            self.gui.root.after(2000, lambda: self.remove_highlight(feature_tree, item, device_id))
            
            # Remove device from main device list
            self.gui.device_tree.delete(device_item)
            
            # Update count
            count_label = getattr(self.gui, f"{feature_key}_count_label")
            count_label.config(text=f"{len(self.feature_devices[feature_key])} devices")
            
            if show_log:
                self.gui.log_status(f"✅ Đã thêm {device_name} vào {feature_key}")
            
            #  AUTO START NẾU FEATURE ĐANG CHẠY
            if hasattr(self.gui, 'feature_status') and feature_key in self.gui.feature_status:
                if self.gui.feature_status[feature_key]["running"]:
                    self.auto_start_feature_for_device(device_id, device_name, feature_key)
            
            return True
        return False
    
    def remove_highlight(self, tree, item, device_id):
        """Remove highlight from device item after animation"""
        try:
            # Remove the "newitem" tag but keep the device_id tag
            tree.item(item, tags=(device_id,))
        except:
            pass  # Item might have been deleted
    
    def clear_feature_devices(self, feature_key):
        """Clear tất cả devices trong một feature"""
        # Get all devices from this feature
        devices_to_restore = self.feature_devices[feature_key].copy()
        
        # Kill processes cho tất cả devices trong feature này
        for device_info in devices_to_restore:
            self.kill_specific_device_process(device_info['device_id'], device_info['name'], feature_key)
        
        # Clear feature devices
        self.feature_devices[feature_key].clear()
        feature_tree = getattr(self.gui, f"{feature_key}_tree")
        for item in feature_tree.get_children():
            feature_tree.delete(item)
        
        # Restore devices to main device list
        for device_info in devices_to_restore:
            device_id = device_info['device_id']
            device_name = device_info['name']
            
            # Add back to main device tree
            item = self.gui.device_tree.insert("", tk.END, values=(device_name, "Ready"))
            self.gui.device_tree.item(item, tags=(device_id,))
        
        count_label = getattr(self.gui, f"{feature_key}_count_label")
        count_label.config(text="0 devices")
        
        self.gui.log_status(f"🗑️ Đã clear {feature_key} và trả lại {len(devices_to_restore)} devices")
    
    def clear_all_features(self):
        """Clear tất cả features"""
        total_restored = 0
        for feature_key in self.feature_devices.keys():
            # Get count before clearing
            device_count = len(self.feature_devices[feature_key])
            total_restored += device_count
            
            # Clear feature devices with kill processes
            devices_to_restore = self.feature_devices[feature_key].copy()
            
            # Kill processes cho tất cả devices trong feature này
            for device_info in devices_to_restore:
                self.kill_specific_device_process(device_info['device_id'], device_info['name'], feature_key)
            
            self.feature_devices[feature_key].clear()
            feature_tree = getattr(self.gui, f"{feature_key}_tree")
            for item in feature_tree.get_children():
                feature_tree.delete(item)
            
            # Restore devices to main device list
            for device_info in devices_to_restore:
                device_id = device_info['device_id']
                device_name = device_info['name']
                
                # Add back to main device tree
                item = self.gui.device_tree.insert("", tk.END, values=(device_name, "Ready"))
                self.gui.device_tree.item(item, tags=(device_id,))
            
            # Update count
            count_label = getattr(self.gui, f"{feature_key}_count_label")
            count_label.config(text="0 devices")
        
        self.gui.log_status(f"🗑️ Đã clear tất cả features và trả lại {total_restored} devices")
    
    def remove_device_from_feature(self, device_item, feature_key):
        """Xóa device khỏi feature và trả về danh sách gốc - CHỈ KILL PROCESS CỦA DEVICE CỤ THỂ"""
        if device_item:
            # Get device info
            feature_tree = getattr(self.gui, f"{feature_key}_tree")
            device_id = feature_tree.item(device_item, "tags")[0]
            device_name = feature_tree.item(device_item, "values")[0]
            
            #  KILL PROCESS CỦA DEVICE CỤ THỂ (KHÔNG KILL TOÀN BỘ FEATURE)
            self.kill_specific_device_process(device_id, device_name, feature_key)
            
            # Remove from feature
            self.feature_devices[feature_key] = [
                device for device in self.feature_devices[feature_key] 
                if device['device_id'] != device_id
            ]
            
            # Remove from feature tree
            feature_tree.delete(device_item)
            
            # Add back to main device tree
            item = self.gui.device_tree.insert("", tk.END, values=(device_name, "Ready"))
            self.gui.device_tree.item(item, tags=(device_id,))
            
            # Update count
            count_label = getattr(self.gui, f"{feature_key}_count_label")
            count_label.config(text=f"{len(self.feature_devices[feature_key])} devices")
            
            self.gui.log_status(f"🔄 Đã trả {device_name} về danh sách gốc từ {feature_key}")
    
    def move_device_between_features(self, device_item, from_feature_key, to_feature_key):
        """🔥 HOT SWAP: Di chuyển device từ feature này sang feature khác"""
        if device_item:
            # Get device info
            from_feature_tree = getattr(self.gui, f"{from_feature_key}_tree")
            device_id = from_feature_tree.item(device_item, "tags")[0]
            device_name = from_feature_tree.item(device_item, "values")[0]
            
            # 🔥 KILL PROCESS CỦA DEVICE CỤ THỂ TỪ FEATURE CŨ
            self.kill_specific_device_process(device_id, device_name, from_feature_key)
            
            # Remove from source feature
            self.feature_devices[from_feature_key] = [
                device for device in self.feature_devices[from_feature_key] 
                if device['device_id'] != device_id
            ]
            from_feature_tree.delete(device_item)
            
            # Add to target feature
            device_info = {'device_id': device_id, 'name': device_name}
            self.feature_devices[to_feature_key].append(device_info)
            
            to_feature_tree = getattr(self.gui, f"{to_feature_key}_tree")
            to_feature_tree.insert("", tk.END, values=(device_name, "Ready"), tags=(device_id,))
            
            # Update counts
            from_count_label = getattr(self.gui, f"{from_feature_key}_count_label")
            from_count_label.config(text=f"{len(self.feature_devices[from_feature_key])} devices")
            
            to_count_label = getattr(self.gui, f"{to_feature_key}_count_label")
            to_count_label.config(text=f"{len(self.feature_devices[to_feature_key])} devices")
            
            # 🚀 AUTO START FEATURE MỚI NẾU ĐANG CHẠY
            if hasattr(self.gui, 'feature_status') and to_feature_key in self.gui.feature_status:
                if self.gui.feature_status[to_feature_key]["running"]:
                    self.auto_start_feature_for_device(device_id, device_name, to_feature_key)
                    self.gui.log_status(f"🔄 HOT SWAP: Đã chuyển {device_name} từ {from_feature_key} sang {to_feature_key} (auto start)")
                else:
                    self.gui.log_status(f"🔄 Đã chuyển {device_name} từ {from_feature_key} sang {to_feature_key}")
            else:
                self.gui.log_status(f"🔄 Đã chuyển {device_name} từ {from_feature_key} sang {to_feature_key}")
    
    def add_all_selected_to_feature(self):
        """Thêm tất cả devices đã chọn vào feature được chọn từ dropdown"""
        selected_items = self.gui.device_tree.selection()
        if not selected_items:
            self.gui.log_status("⚠️ Vui lòng chọn ít nhất 1 device trước!")
            return
        
        # Map dropdown selection to feature key (updated for compact format)
        feature_mapping = {
            "⚔️ Rally": "rally",
            "🛒 Buy Meat": "buy_meat", 
            "🎯 War": "war_no_general",
            "👹 Attack Boss": "attack_boss",
            "📦 Open Items": "open_items",
            "🛒 Buy General": "buy_general",
            "⚔️ Advanced Rally": "advanced_rally",
            "🎯 Advanced War": "advanced_war",
            # Keep old format for backward compatibility
            "⚔️ Auto Rally": "rally",
            "🛒 Auto Buy Meat": "buy_meat", 
            "🎯 Auto War (No General)": "war_no_general",
            "👹 Auto Attack Boss": "attack_boss",
            "📦 Auto Open Items": "open_items",
            "🛒 Auto Buy General": "buy_general",
            "⚔️ Auto Advanced Rally": "advanced_rally",
            "🎯 Advanced War (No General)": "advanced_war",
        }
        
        selected_feature = self.gui.feature_var.get()
        feature_key = feature_mapping.get(selected_feature)
        
        # Debug: Log selected feature
        self.gui.log_status(f"🔍 Selected feature: '{selected_feature}'")
        self.gui.log_status(f"🔍 Available mappings: {list(feature_mapping.keys())}")
        
        if not feature_key:
            self.gui.log_status("❌ Vui lòng chọn feature từ dropdown!")
            self.gui.log_status(f"❌ Không tìm thấy mapping cho: '{selected_feature}'")
            return
        
        added_count = 0
        for device_item in selected_items:
            if self.add_device_to_feature(device_item, feature_key, show_log=False):
                added_count += 1
        
        if added_count > 0:
            self.gui.log_status(f"✅ Đã thêm {added_count} device(s) vào {selected_feature}")
        else:
            self.gui.log_status("⚠️ Không có device nào được thêm (có thể đã tồn tại trong feature)")
    
    def add_selected_to_feature(self, feature_key):
        """Thêm tất cả devices đã chọn vào feature cụ thể"""
        selected_items = self.gui.device_tree.selection()
        if not selected_items:
            self.gui.log_status("⚠️ Vui lòng chọn ít nhất 1 device trước!")
            return
        
        added_count = 0
        for device_item in selected_items:
            if self.add_device_to_feature(device_item, feature_key, show_log=False):
                added_count += 1
        
        if added_count > 0:
            self.gui.log_status(f"✅ Đã thêm {added_count} device(s) vào {feature_key}")
        else:
            self.gui.log_status("⚠️ Không có device nào được thêm (có thể đã tồn tại trong feature)")

#!/usr/bin/env python3
"""
Server GUI for Duplicate Checker with database export functionality.
"""

import sys
import os
import threading
import time
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QTextEdit, QWidget, QFileDialog,
    QMessageBox, QProgressBar, QGroupBox, QGridLayout,
    QLineEdit, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon

# Import the server components
from server import OptimizedDuplicateChecker, app, checker

class ServerStatusThread(QThread):
    status_updated = pyqtSignal(dict)
    
    def __init__(self, checker):
        super().__init__()
        self.checker = checker
        self.running = True
    
    def run(self):
        while self.running:
            try:
                stats = self.checker.get_stats()
                self.status_updated.emit(stats)
            except Exception as e:
                self.status_updated.emit({'error': str(e)})
            self.msleep(5000)  # Update every 5 seconds
    
    def stop(self):
        self.running = False

class ExportThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, checker, output_file):
        super().__init__()
        self.checker = checker
        self.output_file = output_file
    
    def run(self):
        try:
            self.progress.emit("Đang xuất dữ liệu...")
            result = self.checker.export_all_data_to_file(self.output_file)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.checker = checker  # Use the global checker instance
        self.server_thread = None
        self.status_thread = None
        self.export_thread = None
        
        self.init_ui()
        self.start_status_monitoring()
        
    def init_ui(self):
        self.setWindowTitle("Máy Chủ Kiểm Tra Trùng Lặp - Quản Lý License & Cơ Sở Dữ Liệu")
        self.setGeometry(100, 100, 950, 900)
        
        # Set application icon
        self.setWindowIcon(QIcon())
        
        # Central widget with scroll area
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout for central widget
        main_layout = QVBoxLayout(central_widget)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Create scrollable content widget
        scrollable_widget = QWidget()
        scroll_layout = QVBoxLayout(scrollable_widget)
        
        # Title
        title = QLabel("🗄️ Bảng Điều Khiển Máy Chủ Kiểm Tra Trùng Lặp & Quản Lý License")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_layout.addWidget(title)
        
        # Server status group
        status_group = QGroupBox("Trạng Thái Máy Chủ")
        status_layout = QGridLayout(status_group)
        
        self.server_status_label = QLabel("🔴 Máy Chủ Đã Dừng")
        status_layout.addWidget(QLabel("Trạng thái:"), 0, 0)
        status_layout.addWidget(self.server_status_label, 0, 1)
        
        self.start_server_btn = QPushButton("🚀 Khởi Động Máy Chủ")
        self.start_server_btn.clicked.connect(self.start_server)
        self.stop_server_btn = QPushButton("⛔ Dừng Máy Chủ")
        self.stop_server_btn.clicked.connect(self.stop_server)
        self.stop_server_btn.setEnabled(False)
        
        server_btn_layout = QHBoxLayout()
        server_btn_layout.addWidget(self.start_server_btn)
        server_btn_layout.addWidget(self.stop_server_btn)
        status_layout.addLayout(server_btn_layout, 1, 0, 1, 2)
        
        scroll_layout.addWidget(status_group)
        
        # Database statistics group
        stats_group = QGroupBox("Thống Kê Cơ Sở Dữ Liệu")
        stats_layout = QGridLayout(stats_group)
        
        self.total_records_label = QLabel("0")
        self.db_size_label = QLabel("0.0 MB")
        self.last_updated_label = QLabel("Chưa có")
        
        stats_layout.addWidget(QLabel("Tổng Bản Ghi:"), 0, 0)
        stats_layout.addWidget(self.total_records_label, 0, 1)
        
        stats_layout.addWidget(QLabel("Kích Thước DB:"), 1, 0)
        stats_layout.addWidget(self.db_size_label, 1, 1)
        
        stats_layout.addWidget(QLabel("Cập Nhật Lần Cuối:"), 2, 0)
        stats_layout.addWidget(self.last_updated_label, 2, 1)
        
        self.refresh_stats_btn = QPushButton("🔄 Làm Mới Thống Kê")
        self.refresh_stats_btn.clicked.connect(self.refresh_stats)
        stats_layout.addWidget(self.refresh_stats_btn, 3, 0, 1, 2)
        
        scroll_layout.addWidget(stats_group)
        
        # License management group
        license_group = QGroupBox("Quản Lý License")
        license_layout = QGridLayout(license_group)
        
        # Create license section
        license_layout.addWidget(QLabel("Tạo License Mới:"), 0, 0)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Nhập tên người dùng...")
        license_layout.addWidget(QLabel("Tên người dùng:"), 1, 0)
        license_layout.addWidget(self.username_input, 1, 1)
        
        self.days_valid_input = QLineEdit()
        self.days_valid_input.setText("30")
        self.days_valid_input.setPlaceholderText("Số ngày có hiệu lực...")
        license_layout.addWidget(QLabel("Số ngày hiệu lực:"), 2, 0)
        license_layout.addWidget(self.days_valid_input, 2, 1)
        
        self.create_license_btn = QPushButton("🔑 Tạo License Key")
        self.create_license_btn.clicked.connect(self.create_license)
        license_layout.addWidget(self.create_license_btn, 3, 0, 1, 2)
        
        # Validate license section
        license_layout.addWidget(QLabel("Kiểm Tra License:"), 4, 0)
        
        self.license_key_input = QLineEdit()
        self.license_key_input.setPlaceholderText("Nhập license key để kiểm tra...")
        license_layout.addWidget(QLabel("License Key:"), 5, 0)
        license_layout.addWidget(self.license_key_input, 5, 1)
        
        self.validate_license_btn = QPushButton("✅ Kiểm Tra License")
        self.validate_license_btn.clicked.connect(self.validate_license)
        license_layout.addWidget(self.validate_license_btn, 6, 0, 1, 1)
        
        self.list_licenses_btn = QPushButton("📋 Liệt Kê Tất Cả License")
        self.list_licenses_btn.clicked.connect(self.list_all_licenses)
        license_layout.addWidget(self.list_licenses_btn, 6, 1, 1, 1)
        
        # Remove license section
        license_layout.addWidget(QLabel("Xóa License:"), 8, 0)
        
        self.remove_license_input = QLineEdit()
        self.remove_license_input.setPlaceholderText("Nhập license key để xóa...")
        license_layout.addWidget(QLabel("License cần xóa:"), 9, 0)
        license_layout.addWidget(self.remove_license_input, 9, 1)
        
        self.remove_license_btn = QPushButton("🗑️ Xóa License")
        self.remove_license_btn.clicked.connect(self.remove_license)
        self.remove_license_btn.setStyleSheet("background-color: #ff6b6b; color: white;")
        license_layout.addWidget(self.remove_license_btn, 10, 0, 1, 2)
        
        # License result display
        self.license_result_label = QTextEdit()
        self.license_result_label.setReadOnly(True)
        self.license_result_label.setPlaceholderText("Kết quả sẽ hiển thị ở đây...")
        self.license_result_label.setStyleSheet("padding: 10px; border: 1px solid #ccc; border-radius: 5px;")
        self.license_result_label.setMinimumHeight(200)
        self.license_result_label.setMaximumHeight(400)
        license_layout.addWidget(self.license_result_label, 11, 0, 2, 2)

        
        scroll_layout.addWidget(license_group)
        
        # Data export group
        export_group = QGroupBox("Xuất Dữ Liệu")
        export_layout = QVBoxLayout(export_group)
        
        # Export file path
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Xuất đến:"))
        self.export_path_edit = QLineEdit()
        self.export_path_edit.setText("exported_data.txt")
        path_layout.addWidget(self.export_path_edit)
        
        self.browse_btn = QPushButton("📁 Duyệt")
        self.browse_btn.clicked.connect(self.browse_export_path)
        path_layout.addWidget(self.browse_btn)
        
        export_layout.addLayout(path_layout)
        
        # Export button
        self.export_btn = QPushButton("📤 Xuất Toàn Bộ Cơ Sở Dữ Liệu Ra File")
        self.export_btn.clicked.connect(self.export_data)
        export_layout.addWidget(self.export_btn)
        
        # Export progress
        self.export_progress = QProgressBar()
        self.export_progress.setVisible(False)
        export_layout.addWidget(self.export_progress)
        
        self.export_status_label = QLabel("")
        export_layout.addWidget(self.export_status_label)
        
        scroll_layout.addWidget(export_group)
        
        # Logs group
        logs_group = QGroupBox("Nhật Ký Máy Chủ")
        logs_layout = QVBoxLayout(logs_group)
        
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150)
        logs_layout.addWidget(self.log_area)
        
        # Clear logs button
        self.clear_logs_btn = QPushButton("🗑️ Xóa Nhật Ký")
        self.clear_logs_btn.clicked.connect(self.clear_logs)
        logs_layout.addWidget(self.clear_logs_btn)
        
        scroll_layout.addWidget(logs_group)
        
        # Format info
        format_info = QLabel(
            "📋 Định Dạng Dữ Liệu: Chỉ cần 6 số (ví dụ: 123456)\n"
            "💾 Khi lưu sẽ có format: 6số|tên_user|thời_gian\n"
            "🔑 Tất cả upload cần license key hợp lệ"
        )
        format_info.setStyleSheet("padding: 10px; border-radius: 5px; background-color: #f0f0f0;")
        scroll_layout.addWidget(format_info)
        
        # Set the scrollable widget to the scroll area
        scroll_area.setWidget(scrollable_widget)
        main_layout.addWidget(scroll_area)
        
        self.add_log("Giao diện máy chủ đã khởi tạo")
    
    def create_license(self):
        """Create a new license key."""
        username = self.username_input.text().strip()
        days_valid_str = self.days_valid_input.text().strip()
        
        if not username:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập tên người dùng")
            return
        
        try:
            days_valid = int(days_valid_str) if days_valid_str else 30
            if days_valid <= 0:
                raise ValueError("Số ngày phải lớn hơn 0")
        except ValueError:
            QMessageBox.warning(self, "Cảnh báo", "Số ngày hiệu lực phải là số nguyên dương")
            return
        
        try:
            # Create license using the checker
            result = self.checker.create_license_key(username, days_valid)
            
            if result['success']:
                license_key = result['key_id']
                expires_at = result['expires_at']
                
                # Display result
                result_text = (
                    f"✅ Tạo license thành công!\n"
                    f"👤 Username: {username}\n"
                    f"🔑 License Key: {license_key}\n"
                    f"📅 Hết hạn: {expires_at}\n"
                    f"⏰ Có hiệu lực: {days_valid} ngày"
                )
                self.license_result_label.setPlainText(result_text)
                
                # Save license key to file for easy access
                license_file = f"license_{username}.txt"
                try:
                    with open(license_file, 'w') as f:
                        f.write(license_key)
                    self.add_log(f"License key đã lưu vào file: {license_file}")
                except:
                    pass
                
                # Clear input fields
                self.username_input.clear()
                self.days_valid_input.setText("30")
                
                # Show success message with copy option
                msg = QMessageBox(self)
                msg.setWindowTitle("License Tạo Thành Công")
                msg.setText(f"License key cho '{username}' đã được tạo!")
                msg.setDetailedText(f"License Key: {license_key}")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.exec()
                
                self.add_log(f"Đã tạo license cho user '{username}', hiệu lực {days_valid} ngày")
            else:
                error_msg = result.get('error', 'Unknown error')
                self.license_result_label.setPlainText(f"❌ Lỗi tạo license: {error_msg}")
                self.add_log(f"Lỗi tạo license: {error_msg}")
                
        except Exception as e:
            error_msg = str(e)
            self.license_result_label.setPlainText(f"❌ Lỗi: {error_msg}")
            self.add_log(f"Lỗi tạo license: {error_msg}")
    
    def validate_license(self):
        """Validate a license key."""
        license_key = self.license_key_input.text().strip()
        
        if not license_key:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập license key")
            return
        
        try:
            # Validate license using the checker
            result = self.checker.validate_license_key(license_key)
            
            if result['valid']:
                username = result['username']
                expires_at = result['expires_at']
                days_remaining = result['days_remaining']
                
                # Display result
                status_icon = "✅" if days_remaining > 7 else "⚠️" if days_remaining > 0 else "❌"
                result_text = (
                    f"{status_icon} License hợp lệ!\n"
                    f"👤 Username: {username}\n"
                    f"📅 Hết hạn: {expires_at}\n"
                    f"⏰ Còn lại: {days_remaining} ngày"
                )
                
                if days_remaining <= 7:
                    result_text += f"\n⚠️ License sắp hết hạn!"
                
                self.license_result_label.setPlainText(result_text)
                self.add_log(f"License hợp lệ cho user '{username}', còn {days_remaining} ngày")
            else:
                error_msg = result.get('error', 'Unknown error')
                result_text = f"❌ License không hợp lệ: {error_msg}"
                self.license_result_label.setPlainText(result_text)
                self.add_log(f"License không hợp lệ: {error_msg}")
                
        except Exception as e:
            error_msg = str(e)
            self.license_result_label.setPlainText(f"❌ Lỗi kiểm tra: {error_msg}")
            self.add_log(f"Lỗi kiểm tra license: {error_msg}")
    
    def list_all_licenses(self):
        """List all license keys in the database."""
        try:
            # Get licenses using the checker
            licenses = self.checker.list_all_licenses()
            
            if not licenses:
                self.license_result_label.setPlainText("📋 Không có license nào trong cơ sở dữ liệu")
                self.add_log("Không có license nào trong database")
                return
            
            # Format license list for display
            result_text = f"📋 Danh sách {len(licenses)} license keys:\n\n"
            
            for i, license_info in enumerate(licenses, 1):
                username = license_info['username']
                key_id = license_info['key_id']
                status = license_info['status']
                expires_at = license_info['expires_at']
                
                # Status icon
                if license_info['is_expired']:
                    status_icon = "❌"
                elif not license_info['is_active']:
                    status_icon = "⚠️"
                elif license_info['days_remaining'] <= 7:
                    status_icon = "🟡"
                else:
                    status_icon = "✅"
                
                result_text += (
                    f"{i}. {status_icon} {username}\n"
                    f"   Key: {key_id}\n"
                    f"   Status: {status}\n"
                    f"   Expires: {expires_at[:10]}\n\n"
                )
            
            self.license_result_label.setPlainText(result_text)
            self.add_log(f"Liệt kê {len(licenses)} license keys")
            
        except Exception as e:
            error_msg = str(e)
            self.license_result_label.setPlainText(f"❌ Lỗi liệt kê license: {error_msg}")
            self.add_log(f"Lỗi liệt kê license: {error_msg}")
    
    def remove_license(self):
        """Remove a license key from the database."""
        license_key = self.remove_license_input.text().strip()
        
        if not license_key:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập license key cần xóa")
            return
        
        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Xác Nhận Xóa License",
            f"Bạn có chắc chắn muốn xóa license key này?\n\n{license_key[:8]}...{license_key[-8:] if len(license_key) > 16 else license_key[8:]}\n\nHành động này không thể hoàn tác!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            # Remove license using the checker
            result = self.checker.remove_license_key(license_key)
            
            if result['success']:
                username = result['username']
                message = result['message']
                
                # Display success result
                result_text = (
                    f"✅ Xóa license thành công!\n"
                    f"👤 Username: {username}\n"
                    f"🔑 License Key: {license_key[:8]}...{license_key[-8:] if len(license_key) > 16 else license_key[8:]}\n"
                    f"📝 {message}"
                )
                self.license_result_label.setPlainText(result_text)
                
                # Clear input field
                self.remove_license_input.clear()
                
                # Show success message
                QMessageBox.information(
                    self,
                    "Xóa Thành Công",
                    f"License cho user '{username}' đã được xóa thành công!"
                )
                
                self.add_log(f"Đã xóa license cho user '{username}'")
            else:
                error_msg = result.get('error', 'Unknown error')
                result_text = f"❌ Lỗi xóa license: {error_msg}"
                self.license_result_label.setPlainText(result_text)
                self.add_log(f"Lỗi xóa license: {error_msg}")
                
        except Exception as e:
            error_msg = str(e)
            self.license_result_label.setPlainText(f"❌ Lỗi: {error_msg}")
            self.add_log(f"Lỗi xóa license: {error_msg}")
    
    def start_status_monitoring(self):
        """Start background status monitoring."""
        self.status_thread = ServerStatusThread(self.checker)
        self.status_thread.status_updated.connect(self.update_database_stats)
        self.status_thread.start()
    
    def start_server(self):
        """Start the Flask server in a separate thread."""
        def run_server():
            try:
                self.add_log("Đang khởi động máy chủ Flask...")
                app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
            except Exception as e:
                self.add_log(f"Lỗi máy chủ: {e}")
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        self.server_status_label.setText("🟢 Máy Chủ Đang Chạy trên http://localhost:5000")
        self.start_server_btn.setEnabled(False)
        self.stop_server_btn.setEnabled(True)
        
        self.add_log("Máy chủ đã khởi động thành công trên cổng 5000")
    
    def stop_server(self):
        """Stop the Flask server."""
        # Flask server will be stopped when the application exits
        self.server_status_label.setText("🔴 Máy Chủ Đã Dừng")
        self.start_server_btn.setEnabled(True)
        self.stop_server_btn.setEnabled(False)
        
        self.add_log("Đã yêu cầu dừng máy chủ")
    
    def refresh_stats(self):
        """Manually refresh database statistics."""
        try:
            stats = self.checker.get_stats()
            self.update_database_stats(stats)
            self.add_log("Đã làm mới thống kê cơ sở dữ liệu")
        except Exception as e:
            self.add_log(f"Lỗi khi làm mới thống kê: {e}")
    
    def update_database_stats(self, stats):
        """Update database statistics display."""
        if 'error' in stats:
            self.add_log(f"Lỗi thống kê: {stats['error']}")
            return
            
        self.total_records_label.setText(f"{stats['total_records']:,}")
        self.db_size_label.setText(f"{stats['database_size_mb']:.2f} MB")
        self.last_updated_label.setText(time.strftime("%H:%M:%S"))
    
    def browse_export_path(self):
        """Browse for export file location."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Xuất Cơ Sở Dữ Liệu Đến",
            self.export_path_edit.text(),
            "Tập Tin Văn Bản (*.txt);;Tất Cả Tập Tin (*)"
        )
        
        if file_path:
            self.export_path_edit.setText(file_path)
    
    def export_data(self):
        """Export all database data to file."""
        output_file = self.export_path_edit.text().strip()
        
        if not output_file:
            QMessageBox.warning(self, "Cảnh Báo", "Vui lòng chỉ định đường dẫn file xuất")
            return
        
        # Confirm large export
        stats = self.checker.get_stats()
        if stats['total_records'] > 100000:
            reply = QMessageBox.question(
                self,
                "Xuất Dữ Liệu Lớn",
                f"Bạn sắp xuất {stats['total_records']:,} bản ghi. "
                f"Điều này có thể mất thời gian. Tiếp tục?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Start export in background
        self.export_btn.setEnabled(False)
        self.export_progress.setVisible(True)
        self.export_progress.setRange(0, 0)  # Indeterminate
        
        self.export_thread = ExportThread(self.checker, output_file)
        self.export_thread.progress.connect(self.update_export_progress)
        self.export_thread.finished.connect(self.export_finished)
        self.export_thread.error.connect(self.export_error)
        self.export_thread.start()
        
        self.add_log(f"Đang bắt đầu xuất đến {output_file}")
    
    def update_export_progress(self, message):
        """Update export progress."""
        self.export_status_label.setText(message)
        self.add_log(message)
    
    def export_finished(self, result):
        """Handle export completion."""
        self.export_btn.setEnabled(True)
        self.export_progress.setVisible(False)
        self.export_status_label.setText("")
        
        if result['success']:
            QMessageBox.information(
                self,
                "Xuất Thành Công",
                f"Đã xuất thành công {result['exported_count']:,} bản ghi\n"
                f"Tập tin: {result['exported_file']}\n"
                f"Kích thước: {result['file_size_mb']:.2f} MB"
            )
            self.add_log(f"Xuất hoàn tất: {result['exported_count']:,} bản ghi")
        else:
            QMessageBox.critical(self, "Xuất Thất Bại", f"Xuất thất bại: {result['error']}")
            self.add_log(f"Xuất thất bại: {result['error']}")
    
    def export_error(self, error_msg):
        """Handle export error."""
        self.export_btn.setEnabled(True)
        self.export_progress.setVisible(False)
        self.export_status_label.setText("")
        
        QMessageBox.critical(self, "Lỗi Xuất", f"Lỗi xuất: {error_msg}")
        self.add_log(f"Lỗi xuất: {error_msg}")
    
    def add_log(self, message):
        """Add a log message to the log area."""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_area.append(log_entry)
        
        # Auto-scroll to bottom
        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_logs(self):
        """Clear the log area."""
        self.log_area.clear()
        self.add_log("Đã xóa nhật ký")
    
    def closeEvent(self, event):
        """Handle application close event."""
        if self.status_thread:
            self.status_thread.stop()
            self.status_thread.wait()
        
        if self.export_thread and self.export_thread.isRunning():
            reply = QMessageBox.question(
                self,
                "Xuất Đang Tiến Hành",
                "Quá trình xuất vẫn đang chạy. Buộc thoát?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            
        event.accept()

def main():
    app_gui = QApplication(sys.argv)
    app_gui.setApplicationName("Máy Chủ Kiểm Tra Trùng Lặp")
    app_gui.setApplicationVersion("2.0")
    
    # Set application style
    app_gui.setStyle('Fusion')
    
    window = ServerGUI()
    window.show()
    
    sys.exit(app_gui.exec())

if __name__ == '__main__':
    main()
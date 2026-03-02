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
    QLineEdit
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
        self.setWindowTitle("Máy Chủ Kiểm Tra Trùng Lặp - Quản Lý Cơ Sở Dữ Liệu")
        self.setGeometry(100, 100, 800, 600)
        
        # Set application icon
        self.setWindowIcon(QIcon())
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Title
        title = QLabel("🗄️ Bảng Điều Khiển Máy Chủ Kiểm Tra Trùng Lặp")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title)
        
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
        
        main_layout.addWidget(status_group)
        
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
        
        main_layout.addWidget(stats_group)
        
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
        
        main_layout.addWidget(export_group)
        
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
        
        main_layout.addWidget(logs_group)
        
        # Format info
        format_info = QLabel(
            "📋 Định Dạng Dữ Liệu: 6số|tên_user|văn bản(tối đa 20 ký tự có dấu phẩy/khoảng trống)\n"
            "Ví dụ: 363782|user1|Gg, ha, mi, co, am"
        )
        format_info.setStyleSheet("padding: 10px; border-radius: 5px;")
        main_layout.addWidget(format_info)
        
        self.add_log("Giao diện máy chủ đã khởi tạo")
    
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
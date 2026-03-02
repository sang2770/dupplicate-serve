import sys
import os
from typing import Dict, Optional
import requests

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QFileDialog, QTextEdit, QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


# ================= READ DOMAIN =================

def read_domain_from_file(file_path: str) -> Optional[str]:
    try:
        with open(file_path, 'r') as f:
            domain = f.read().strip()
            return domain if domain else None
    except:
        return None


# ================= THREAD =================

class FileUploadThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, client, file_path):
        super().__init__()
        self.client = client
        self.file_path = file_path

    def run(self):
        try:
            self.progress.emit("Đang upload file...")
            result = self.client.upload_file_with_progress(
                self.file_path,
                self.progress
            )

            if result:
                self.finished.emit(result)
            else:
                self.error.emit("Không nhận được kết quả từ server")

        except Exception as e:
            self.error.emit(str(e))


# ================= CLIENT =================

class DuplicateCheckerClient:
    def __init__(self, server_url="http://localhost:5000"):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()

    def check_server_health(self) -> bool:
        try:
            r = self.session.get(f"{self.server_url}/health", timeout=5)
            return r.status_code == 200
        except:
            return False

    def upload_file_with_progress(self, file_path, progress_signal=None):
        try:
            if not os.path.exists(file_path):
                return None

            size = os.path.getsize(file_path)
            if progress_signal:
                progress_signal.emit(f"File size: {size / (1024*1024):.1f} MB")

            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'text/plain')}

                r = self.session.post(
                    f"{self.server_url}/upload-file",
                    files=files,
                    timeout=600
                )

            if r.status_code == 200:
                return r.json()
            return None

        except Exception as e:
            if progress_signal:
                progress_signal.emit(str(e))
            return None


# ================= MAIN WINDOW =================

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        domain = read_domain_from_file('domain.txt')
        self.client = DuplicateCheckerClient(
            server_url=domain if domain else "http://localhost:5000"
        )

        self.setWindowTitle("Duplicate Checker Client")
        self.setGeometry(200, 200, 750, 600)

        layout = QVBoxLayout()

        self.status_label = QLabel("🔄 Checking server...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.upload_button = QPushButton("📂 Upload File")
        self.upload_button.clicked.connect(self.select_file)
        layout.addWidget(self.upload_button)

        # ===== SAVE BUTTONS =====
        btn_layout = QHBoxLayout()

        self.save_new_button = QPushButton("💾 Lưu dữ liệu mới")
        self.save_new_button.clicked.connect(self.save_new_data)
        self.save_new_button.setEnabled(False)
        btn_layout.addWidget(self.save_new_button)

        self.save_duplicate_button = QPushButton("💾 Lưu dữ liệu trùng")
        self.save_duplicate_button.clicked.connect(self.save_duplicate_data)
        self.save_duplicate_button.setEnabled(False)
        btn_layout.addWidget(self.save_duplicate_button)

        self.save_invalid_button = QPushButton("💾 Lưu dữ liệu sai format")
        self.save_invalid_button.clicked.connect(self.save_invalid_data)
        self.save_invalid_button.setEnabled(False)
        btn_layout.addWidget(self.save_invalid_button)

        layout.addLayout(btn_layout)

        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)

        self.setLayout(layout)

        self.last_result = None
        self.upload_thread = None

        self.check_server()

    # ================= SERVER =================

    def check_server(self):
        if self.client.check_server_health():
            self.status_label.setText("✅ Server đang hoạt động")
        else:
            self.status_label.setText("❌ Server không khả dụng")

    # ================= SELECT FILE =================

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file",
            "",
            "Text Files (*.txt)"
        )

        if file_path:
            self.start_upload(file_path)

    # ================= START THREAD =================

    def start_upload(self, file_path):
        self.upload_button.setEnabled(False)
        self.result_area.clear()
        self.status_label.setText("⏳ Đang xử lý...")

        self.upload_thread = FileUploadThread(self.client, file_path)
        self.upload_thread.progress.connect(self.result_area.append)
        self.upload_thread.finished.connect(self.upload_finished)
        self.upload_thread.error.connect(self.upload_error)
        self.upload_thread.start()

    # ================= SIGNALS =================

    def upload_finished(self, result):
        self.upload_button.setEnabled(True)
        self.status_label.setText("✅ Hoàn tất")
        self.show_result(result)

    def upload_error(self, message):
        self.upload_button.setEnabled(True)
        self.status_label.setText("❌ Lỗi")
        QMessageBox.critical(self, "Lỗi", message)

    # ================= SHOW RESULT =================

    def show_result(self, result: Dict):
        if not result or 'statistics' not in result:
            QMessageBox.warning(self, "Lỗi", "Kết quả không hợp lệ")
            return

        self.last_result = result
        stats = result['statistics']

        output = (
            "===== KẾT QUẢ =====\n"
            f"Tổng xử lý: {stats['total_processed']}\n"
            f"Mục mới: {stats['success']}\n"
            f"Trùng lặp: {stats['duplicates']}\n"
            f"Sai format: {stats.get('invalid', 0)}\n\n"
        )

        self.result_area.append(output)

        self.save_new_button.setEnabled(bool(result.get('new_data')))
        self.save_duplicate_button.setEnabled(bool(result.get('duplicate_data')))
        self.save_invalid_button.setEnabled(bool(result.get('invalid_data')))

    # ================= SAVE FUNCTIONS =================

    def save_new_data(self):
        self.save_file("new_data", "new_data.txt")

    def save_duplicate_data(self):
        self.save_file("duplicate_data", "duplicate_data.txt")

    def save_invalid_data(self):
        self.save_file("invalid_data", "invalid_data.txt")

    def save_file(self, key, default_name):
        if not self.last_result or key not in self.last_result:
            QMessageBox.warning(self, "Lỗi", "Không có dữ liệu để lưu")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu file",
            default_name,
            "Text Files (*.txt)"
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for line in self.last_result[key]:
                        f.write(f"{line}\n")

                QMessageBox.information(
                    self,
                    "Thành công",
                    f"Đã lưu {len(self.last_result[key])} dòng"
                )
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", str(e))


# ================= RUN =================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
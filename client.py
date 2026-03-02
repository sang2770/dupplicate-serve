import sys
import os
from typing import Dict, Optional
import requests

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QFileDialog, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt


def read_domain_from_file(file_path: str) -> Optional[str]:
    try:
        with open(file_path, 'r') as f:
            domain = f.read().strip()
            return domain if domain else None
    except:
        return None


class DuplicateCheckerClient:
    def __init__(self, server_url: str = "http://localhost:5000"):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()

    def check_server_health(self) -> bool:
        try:
            response = self.session.get(f"{self.server_url}/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def upload_file(self, file_path: str) -> Optional[Dict]:
        try:
            if not os.path.exists(file_path):
                return None

            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'text/plain')}
                response = self.session.post(
                    f"{self.server_url}/upload-file",
                    files=files,
                    timeout=30
                )

            if response.status_code == 200:
                return response.json()
            return None

        except:
            return None


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        domain = read_domain_from_file('domain.txt')
        self.client = DuplicateCheckerClient(
            server_url=domain if domain else "http://localhost:5000"
        )

        self.setWindowTitle("Duplicate Checker Client")
        self.setGeometry(200, 200, 500, 400)

        layout = QVBoxLayout()

        self.status_label = QLabel("🔄 Checking server...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.upload_button = QPushButton("📂 Upload File")
        self.upload_button.clicked.connect(self.select_file)
        layout.addWidget(self.upload_button)

        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)

        self.setLayout(layout)

        self.check_server()

    def check_server(self):
        if self.client.check_server_health():
            self.status_label.setText("✅ Server đang hoạt động")
        else:
            self.status_label.setText("❌ Server không khả dụng")

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file văn bản",
            "",
            "Text Files (*.txt)"
        )

        if file_path:
            result = self.client.upload_file(file_path)
            self.show_result(result)

    def show_result(self, result: Dict):
        if result and 'statistics' in result:
            stats = result['statistics']

            output = (
                "KẾT QUẢ KIỂM TRA TRÙNG LẶP\n"
                "================================\n"
                f"Tổng xử lý: {stats['total_processed']}\n"
                f"Mục mới: {stats['success']}\n"
                f"Trùng lặp: {stats['duplicates']}\n"
                f"Tỷ lệ thành công: "
                f"{stats['success']/stats['total_processed']*100:.1f}%\n"
            )

            self.result_area.setText(output)
        else:
            QMessageBox.warning(self, "Lỗi", "Không nhận được kết quả hợp lệ")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
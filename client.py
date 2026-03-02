import sys
import os
from typing import Dict, Optional
import requests

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QFileDialog, QTextEdit, QMessageBox, QHBoxLayout,
    QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer


def read_domain_from_file(file_path: str) -> Optional[str]:
    try:
        with open(file_path, 'r') as f:
            domain = f.read().strip()
            return domain if domain else None
    except:
        return None


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
            self.progress.emit("Đang tải file lên server...")
            result = self.client.upload_file_with_progress(self.file_path, self.progress)
            if result:
                self.finished.emit(result)
            else:
                self.error.emit("Không nhận được kết quả từ server")
        except Exception as e:
            self.error.emit(f"Lỗi khi xử lý file: {str(e)}")


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

    def upload_file_with_progress(self, file_path: str, progress_signal=None) -> Optional[Dict]:
        try:
            if not os.path.exists(file_path):
                return None

            # Check file size - limit to 500MB
            file_size = os.path.getsize(file_path)
            max_size = 500 * 1024 * 1024  # 500MB in bytes
            
            if file_size > max_size:
                if progress_signal:
                    progress_signal.emit(f"Lỗi: File quá lớn {file_size / (1024*1024):.1f} MB (giới hạn 500MB)")
                return None
                
            if progress_signal:
                progress_signal.emit(f"File size: {file_size / (1024*1024):.1f} MB")

            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'text/plain')}
                
                if progress_signal:
                    progress_signal.emit("Đang gửi dữ liệu đến server...")
                
                response = self.session.post(
                    f"{self.server_url}/upload-file",
                    files=files,
                    timeout=600  # Increase timeout for large files
                )

            if response.status_code == 200:
                if progress_signal:
                    progress_signal.emit("Xử lý hoàn tất!")
                return response.json()
            else:
                if progress_signal:
                    progress_signal.emit(f"Lỗi server: {response.status_code}")
                return None

        except Exception as e:
            if progress_signal:
                progress_signal.emit(f"Lỗi: {str(e)}")
            return None
    
    def get_server_stats(self) -> Optional[Dict]:
        """Get server statistics."""
        try:
            response = self.session.get(f"{self.server_url}/stats", timeout=10)
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

        self.setWindowTitle("Duplicate Checker Client - Database Mode (Max 500MB)")
        self.setGeometry(200, 200, 700, 600)

        layout = QVBoxLayout()

        self.status_label = QLabel("🔄 Checking server...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Server stats button
        self.stats_button = QPushButton("📊 Server Statistics")
        self.stats_button.clicked.connect(self.show_server_stats)
        layout.addWidget(self.stats_button)

        self.upload_button = QPushButton("📂 Upload File (supports large files)")
        self.upload_button.clicked.connect(self.select_file)
        layout.addWidget(self.upload_button)

        # Button layout for save options
        button_layout = QHBoxLayout()
        self.save_new_button = QPushButton("💾 Lưu dữ liệu mới")
        self.save_new_button.clicked.connect(self.save_new_data)
        self.save_new_button.setEnabled(False)
        button_layout.addWidget(self.save_new_button)
        
        self.save_duplicate_button = QPushButton("💾 Lưu dữ liệu trùng")
        self.save_duplicate_button.clicked.connect(self.save_duplicate_data)
        self.save_duplicate_button.setEnabled(False)
        button_layout.addWidget(self.save_duplicate_button)
        
        self.save_invalid_button = QPushButton("💾 Lưu dữ liệu sai format")
        self.save_invalid_button.clicked.connect(self.save_invalid_data)
        self.save_invalid_button.setEnabled(False)
        button_layout.addWidget(self.save_invalid_button)
        
        layout.addLayout(button_layout)

        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)
        
        # Store the last result for saving
        self.last_result = None
        self.upload_thread = None

        self.setLayout(layout)

        self.check_server()

    def check_server(self):
        if self.client.check_server_health():
            self.status_label.setText("✅ Server đang hoạt động")
            self.stats_button.setEnabled(True)
        else:
            self.status_label.setText("❌ Server không khả dụng")
            self.stats_button.setEnabled(False)
    
    def show_server_stats(self):
        """Show server statistics."""
        stats = self.client.get_server_stats()
        if stats and 'statistics' in stats:
            s = stats['statistics']
            QMessageBox.information(
                self, 
                "Server Statistics", 
                f"Total records: {s['total_records']:,}\n"
                f"Database size: {s['database_size_mb']:.1f} MB"
            )
        else:
            QMessageBox.warning(self, "Lỗi", "Không thể lấy thống kê từ server")

    def select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file văn bản (giới hạn 500MB)",
            "",
            "Text Files (*.txt)"
        )

        if file_path:
            # Check file size and warn if very large
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            
            if file_size_mb > 500:  # Hard limit 500MB
                QMessageBox.critical(
                    self,
                    "File quá lớn",
                    f"File có kích thước {file_size_mb:.1f} MB vượt quá giới hạn 500MB."
                    f"\nVui lòng chia nhỏ file hoặc chọn file khác."
                )
                return
            elif file_size_mb > 100:  # Warn for files > 100MB
                reply = QMessageBox.question(
                    self,
                    "File lớn",
                    f"File có kích thước {file_size_mb:.1f} MB. "
                    f"Việc xử lý có thể mất nhiều thời gian. Tiếp tục?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            
            self.start_upload(file_path)

    def show_result(self, result: Dict):
        if result and 'statistics' in result:
            self.last_result = result
            stats = result['statistics']

            output = (
                "KẾT QUẢ KIỂM TRA TRÙNG LẶP\n"
                "================================\n"
                f"Tổng xử lý: {stats['total_processed']}\n"
                f"Mục mới: {stats['success']}\n"
                f"Trùng lặp: {stats['duplicates']}\n"
                f"Sai format: {stats.get('invalid', 0)}\n"
                f"Tỷ lệ thành công: "
                f"{stats['success']/stats['total_processed']*100:.1f}%\n\n"
            )
            
            # Show preview of new data
            if 'new_data' in result and result['new_data']:
                output += "DỮ LIỆU MỚI (5 dòng đầu):\n"
                for i, line in enumerate(result['new_data'][:5]):
                    output += f"{i+1}. {line}\n"
                if len(result['new_data']) > 5:
                    output += f"... và {len(result['new_data']) - 5} dòng khác\n\n"
            
            # Show preview of duplicate data
            if 'duplicate_data' in result and result['duplicate_data']:
                output += "DỮ LIỆU TRÙNG LẶP (5 dòng đầu):\n"
                for i, line in enumerate(result['duplicate_data'][:5]):
                    output += f"{i+1}. {line}\n"
                if len(result['duplicate_data']) > 5:
                    output += f"... và {len(result['duplicate_data']) - 5} dòng khác\n\n"
            
            # Show preview of invalid format data
            if 'invalid_data' in result and result['invalid_data']:
                output += "DỮ LIỆU SAI FORMAT (5 dòng đầu):\n"
                for i, item in enumerate(result['invalid_data'][:5]):
                    if isinstance(item, dict):
                        output += f"{i+1}. {item['data']} - {item['error']}\n"
                    else:
                        output += f"{i+1}. {item}\n"
                if len(result['invalid_data']) > 5:
                    output += f"... và {len(result['invalid_data']) - 5} dòng khác\n\n"
                    
                # Add format reminder
                output += "\n📋 FORMAT YÊU CẦU:\n"
                output += "6 số|tên_user|văn bản (tối đa 20 ký tự có dấu phẩy và khoảng trống)\n"
                output += "Ví dụ: 363782|user1|Gg, ha, mi, co, am"

            self.result_area.setText(output)
            
            # Enable save buttons
            self.save_new_button.setEnabled(bool(result.get('new_data')))
            self.save_duplicate_button.setEnabled(bool(result.get('duplicate_data')))
            self.save_invalid_button.setEnabled(bool(result.get('invalid_data')))
        else:
            QMessageBox.warning(self, "Lỗi", "Không nhận được kết quả hợp lệ")
    
    def save_new_data(self):
        if not self.last_result or 'new_data' not in self.last_result:
            QMessageBox.warning(self, "Lỗi", "Không có dữ liệu mới để lưu")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu dữ liệu mới",
            "new_data.txt",
            "Text Files (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for line in self.last_result['new_data']:
                        f.write(f"{line}\n")
                QMessageBox.information(self, "Thành công", f"Đã lưu {len(self.last_result['new_data'])} dòng dữ liệu mới")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể lưu file: {str(e)}")
    
    def save_duplicate_data(self):
        if not self.last_result or 'duplicate_data' not in self.last_result:
            QMessageBox.warning(self, "Lỗi", "Không có dữ liệu trùng lặp để lưu")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu dữ liệu trùng lặp",
            "duplicate_data.txt",
            "Text Files (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    for line in self.last_result['duplicate_data']:
                        f.write(f"{line}\n")
                QMessageBox.information(self, "Thành công", f"Đã lưu {len(self.last_result['duplicate_data'])} dòng dữ liệu trùng lặp")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể lưu file: {str(e)}")
    
    def save_invalid_data(self):
        if not self.last_result or 'invalid_data' not in self.last_result:
            QMessageBox.warning(self, "Lỗi", "Không có dữ liệu sai format để lưu")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu dữ liệu sai format",
            "invalid_data.txt",
            "Text Files (*.txt)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("# Dữ liệu sai format - Format yêu cầu: 6số|tên_user|văn bản(max20 ký tự có dấu phẩy và khoảng trống)\n")
                    f.write("# Ví dụ đúng: 363782|user1|Gg, ha, mi, co, am\n\n")
                    
                    for item in self.last_result['invalid_data']:
                        if isinstance(item, dict):
                            f.write(f"{item['data']} # Lỗi: {item['error']}\n")
                        else:
                            f.write(f"{item}\n")
                            
                QMessageBox.information(self, "Thành công", f"Đã lưu {len(self.last_result['invalid_data'])} dòng dữ liệu sai format")
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể lưu file: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
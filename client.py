import sys
import os
import re
from typing import Dict, Optional
import requests
import json

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QFileDialog, QTextEdit, QMessageBox, QHBoxLayout,
    QLineEdit, QComboBox, QGroupBox, QFormLayout, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal


# ================= DATA TYPE VALIDATION =================

class DataTypeValidator:
    @staticmethod
    def get_data_types():
        """Get all available data types"""
        return {
            "kho1": "Kho 1: 6 số",
            "kho2": "Kho 2: 6 số",
            "kho3": "Kho 3: 6 số", 
            "kho4": "Kho 4: 6 số",
            "kho5": "Kho 5: 6 số",
            "kho6": "Kho 6: 20 số (bắt đầu 9999)|2 số|2 số",
            "kho7": "Kho 7: 20 số (bắt đầu 9999)|2 số|2 số",
            "kho8": "Kho 8: 20 số (bắt đầu 9999)|2 số|2 số",
            "kho9": "Kho 9: 20 số (bắt đầu 9999)|2 số|2 số",
            "kho10": "Kho 10: 20 số (bắt đầu 9999)|2 số|2 số"
        }
    
    @staticmethod
    def validate_line(line: str, data_type: str) -> bool:
        """Validate a line based on data type"""
        line = line.strip()
        if not line:
            return False
            
        if data_type == "kho1":
            # Current validation logic for kho1 - add your existing logic here
            return len(line) > 0  # Placeholder - replace with actual validation
        
        elif data_type in ["kho2", "kho3", "kho4", "kho5"]:
            # 6 numbers only
            return re.match(r'^\d{6}$', line) is not None
        
        elif data_type in ["kho6", "kho7", "kho8", "kho9", "kho10"]:
            # 20 numbers starting with 9999 | 2 numbers | 2 numbers
            pattern = r'^9999\d{16}\|\d{2}\|\d{2}$'
            return re.match(pattern, line) is not None
            
        return False
    
    @staticmethod
    def get_validation_description(data_type: str) -> str:
        """Get description of validation rules for data type"""
        descriptions = {
            "kho1": "Định dạng hiện tại",
            "kho2": "Chính xác 6 số (ví dụ: 123456)",
            "kho3": "Chính xác 6 số (ví dụ: 123456)", 
            "kho4": "Chính xác 6 số (ví dụ: 123456)",
            "kho5": "Chính xác 6 số (ví dụ: 123456)",
            "kho6": "20 số bắt đầu 9999, theo sau |2 số|2 số (ví dụ: 99991234567890123456|12|34)",
            "kho7": "20 số bắt đầu 9999, theo sau |2 số|2 số (ví dụ: 99991234567890123456|12|34)",
            "kho8": "20 số bắt đầu 9999, theo sau |2 số|2 số (ví dụ: 99991234567890123456|12|34)",
            "kho9": "20 số bắt đầu 9999, theo sau |2 số|2 số (ví dụ: 99991234567890123456|12|34)",
            "kho10": "20 số bắt đầu 9999, theo sau |2 số|2 số (ví dụ: 99991234567890123456|12|34)"
        }
        return descriptions.get(data_type, "Không xác định")


# ================= READ DOMAIN/LICENSE =================

def read_domain_from_file(file_path: str) -> Optional[str]:
    try:
        with open(file_path, 'r') as f:
            domain = f.read().strip()
            return domain if domain else None
    except:
        return None

def read_license_from_file(file_path: str) -> Optional[str]:
    try:
        with open(file_path, 'r') as f:
            license_key = f.read().strip()
            return license_key if license_key else None
    except:
        return None

def save_license_to_file(file_path: str, license_key: str):
    try:
        with open(file_path, 'w') as f:
            f.write(license_key)
    except:
        pass


# ================= THREAD =================

class FileUploadThread(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, client, file_path, license_key, upload_mode, preprocess=False, data_type="kho1"):
        super().__init__()
        self.client = client
        self.file_path = file_path
        self.license_key = license_key
        self.upload_mode = upload_mode
        self.preprocess = preprocess
        self.data_type = data_type

    def run(self):
        try:
            if self.preprocess:
                self.progress.emit(f"Đang tiền xử lý file (loại bỏ trùng lặp - {DataTypeValidator.get_data_types()[self.data_type]})...")
            else:
                self.progress.emit("Đang upload file...")
            
            result = self.client.upload_file_with_progress(
                self.file_path,
                self.license_key,
                self.upload_mode,
                self.progress,
                self.preprocess,
                self.data_type
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
    
    def preprocess_file_remove_duplicates(self, file_path, progress_signal=None, data_type="kho1"):
        """
        Removes duplicates from a file and overwrites the original file.
        Also validates data format based on selected data type.
        Returns statistics about the operation.
        """
        try:
            if progress_signal:
                progress_signal.emit("Đang đọc file để loại bỏ trùng lặp...")
            
            # Read all lines from the file
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            original_count = len(lines)
            if progress_signal:
                progress_signal.emit(f"Đã đọc {original_count} dòng từ file")
                progress_signal.emit(f"Đang validation theo định dạng: {DataTypeValidator.get_data_types()[data_type]}")
            
            # Remove duplicates while preserving order and validate format
            seen = set()
            unique_lines = []
            duplicate_lines = []
            invalid_lines = []
            
            for line in lines:
                stripped_line = line.strip()
                if stripped_line:  # Skip empty lines
                    # Validate format first
                    if not DataTypeValidator.validate_line(stripped_line, data_type):
                        invalid_lines.append(line)
                        continue
                    
                    # Check for duplicates
                    if stripped_line not in seen:
                        seen.add(stripped_line)
                        unique_lines.append(line)
                    else:
                        duplicate_lines.append(line)
            
            unique_count = len(unique_lines)
            duplicate_count = len(duplicate_lines)
            invalid_count = len(invalid_lines)
            
            if progress_signal:
                progress_signal.emit(f"Tìm thấy {invalid_count} dòng sai định dạng")
                progress_signal.emit(f"Tìm thấy {duplicate_count} dòng trùng lặp")
                progress_signal.emit(f"Còn lại {unique_count} dòng hợp lệ và duy nhất")
            
            # Overwrite the original file with unique and valid lines only
            if progress_signal:
                progress_signal.emit("Đang ghi đè file gốc với dữ liệu đã lọc...")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                for line in unique_lines:
                    f.write(line)
            
            statistics = {
                'original_count': original_count,
                'unique_count': unique_count,
                'duplicate_count': duplicate_count,
                'invalid_count': invalid_count,
                'data_type': data_type,
                'data_type_description': DataTypeValidator.get_data_types()[data_type],
                'validation_rule': DataTypeValidator.get_validation_description(data_type),
                'duplicates_removed': duplicate_lines,
                'invalid_removed': invalid_lines
            }
            
            if progress_signal:
                progress_signal.emit(f"Đã ghi đè file gốc: {file_path}")
            
            return statistics
            
        except Exception as e:
            if progress_signal:
                progress_signal.emit(f"Lỗi khi xử lý file: {str(e)}")
            raise e

    def check_server_health(self) -> bool:
        try:
            r = self.session.get(f"{self.server_url}/health", timeout=5)
            return r.status_code == 200
        except:
            return False

    def validate_license(self, license_key: str) -> Dict:
        try:
            response = self.session.post(
                f"{self.server_url}/validate-license",
                json={'key_id': license_key},
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                return {'valid': False, 'error': 'License validation failed'}
        except Exception as e:
            return {'valid': False, 'error': str(e)}

    def upload_file_with_progress(self, file_path, license_key, upload_mode, progress_signal=None, preprocess=False, data_type="kho1"):
        try:
            if not os.path.exists(file_path):
                return None

            preprocess_stats = None
            
            # Preprocess file if requested
            if preprocess:
                preprocess_stats = self.preprocess_file_remove_duplicates(
                    file_path, progress_signal, data_type
                )
                if progress_signal:
                    progress_signal.emit("Bắt đầu upload file đã xử lý...")
            
            size = os.path.getsize(file_path)
            if progress_signal:
                progress_signal.emit(f"File size: {size / (1024*1024):.1f} MB")

            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, 'text/plain')}
                data = {
                    'license_key': license_key,
                    'mode': upload_mode,
                    'data_type': data_type
                }

                r = self.session.post(
                    f"{self.server_url}/upload-file",
                    files=files,
                    data=data,
                    timeout=600
                )
            
            if r.status_code == 200:
                result = r.json()
                # Add preprocessing stats to result if available
                if preprocess_stats:
                    result['preprocessing_stats'] = preprocess_stats
                return result
            elif r.status_code == 401:
                return {'error': 'License key is required'}
            elif r.status_code == 403:
                return {'error': 'Invalid or expired license key'}
            else:
                return {'error': f'Server error: {r.status_code}'}

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

        self.setWindowTitle("Duplicate Checker Client with License")
        self.setGeometry(200, 200, 800, 700)

        layout = QVBoxLayout()

        # ===== LICENSE SECTION =====
        license_group = QGroupBox("License Management")
        license_layout = QFormLayout()
        
        self.license_input = QLineEdit()
        self.license_input.setPlaceholderText("Nhập license key...")
        license_key = read_license_from_file('license.txt')
        if license_key:
            self.license_input.setText(license_key)
        
        license_layout.addRow("License Key:", self.license_input)
        
        license_btn_layout = QHBoxLayout()
        self.validate_license_btn = QPushButton("🔑 Kiểm tra License")
        self.validate_license_btn.clicked.connect(self.validate_license)
        
        self.save_license_btn = QPushButton("💾 Lưu License")
        self.save_license_btn.clicked.connect(self.save_license)
        
        license_btn_layout.addWidget(self.validate_license_btn)
        license_btn_layout.addWidget(self.save_license_btn)
        license_layout.addRow(license_btn_layout)
        
        self.license_status_label = QLabel("❓ Chưa kiểm tra license")
        license_layout.addRow("Trạng thái:", self.license_status_label)
        
        license_group.setLayout(license_layout)
        layout.addWidget(license_group)

        # ===== SERVER STATUS =====
        self.status_label = QLabel("🔄 Checking server...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # ===== UPLOAD SECTION =====
        upload_group = QGroupBox("Upload File")
        upload_layout = QVBoxLayout()
        
        # Data type selection
        data_type_layout = QHBoxLayout()
        data_type_layout.addWidget(QLabel("Loại dữ liệu (Kho):"))
        
        self.data_type_combo = QComboBox()
        data_types = DataTypeValidator.get_data_types()
        for key, value in data_types.items():
            self.data_type_combo.addItem(value, key)
        self.data_type_combo.currentIndexChanged.connect(self.on_data_type_changed)
        data_type_layout.addWidget(self.data_type_combo)
        upload_layout.addLayout(data_type_layout)
        
        # Data type description
        self.data_type_description = QLabel()
        self.data_type_description.setWordWrap(True)
        self.data_type_description.setStyleSheet("QLabel { color: #666; font-style: italic; padding: 5px; }")
        self.update_data_type_description()
        upload_layout.addWidget(self.data_type_description)
        
        # Upload mode selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Chế độ upload:"))
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Lưu dữ liệu mới và kiểm tra trùng lặp", "save")
        self.mode_combo.addItem("Chỉ kiểm tra trùng lặp (không lưu)", "check")
        mode_layout.addWidget(self.mode_combo)
        upload_layout.addLayout(mode_layout)
        
        # Preprocessing option
        self.preprocess_checkbox = QCheckBox("🔄 Tự động loại bỏ trùng lặp và validate định dạng trước khi upload")
        self.preprocess_checkbox.setChecked(True)  # Enable by default
        upload_layout.addWidget(self.preprocess_checkbox)
        
        self.upload_button = QPushButton("📂 Upload File")
        self.upload_button.clicked.connect(self.select_file)
        upload_layout.addWidget(self.upload_button)
        
        upload_group.setLayout(upload_layout)
        layout.addWidget(upload_group)

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

        self.save_preprocessed_button = QPushButton("💾 Lưu dữ liệu trùng lặp đã loại bỏ")
        self.save_preprocessed_button.clicked.connect(self.save_preprocessed_duplicates)
        self.save_preprocessed_button.setEnabled(False)
        btn_layout.addWidget(self.save_preprocessed_button)

        self.save_invalid_preprocessed_button = QPushButton("💾 Lưu dữ liệu sai định dạng đã loại bỏ")
        self.save_invalid_preprocessed_button.clicked.connect(self.save_invalid_preprocessed)
        self.save_invalid_preprocessed_button.setEnabled(False)
        btn_layout.addWidget(self.save_invalid_preprocessed_button)

        layout.addLayout(btn_layout)

        self.result_area = QTextEdit()
        self.result_area.setReadOnly(True)
        layout.addWidget(self.result_area)

        self.setLayout(layout)

        self.last_result = None
        self.upload_thread = None
        self.current_license_info = None

        self.check_server()
        
        # Auto-validate license if present
        if license_key:
            self.validate_license()

    # ================= DATA TYPE METHODS =================
    
    def on_data_type_changed(self):
        """Called when data type selection changes"""
        self.update_data_type_description()
    
    def update_data_type_description(self):
        """Update the description label for the selected data type"""
        current_data_type = self.data_type_combo.currentData()
        if current_data_type:
            description = DataTypeValidator.get_validation_description(current_data_type)
            self.data_type_description.setText(f"📋 Định dạng: {description}")
        else:
            self.data_type_description.setText("")

    # ================= LICENSE MANAGEMENT =================

    def validate_license(self):
        license_key = self.license_input.text().strip()
        if not license_key:
            self.license_status_label.setText("❌ Chưa nhập license key")
            return
            
        self.license_status_label.setText("🔄 Đang kiểm tra...")
        
        try:
            result = self.client.validate_license(license_key)
            
            if result.get('valid'):
                self.current_license_info = result
                username = result.get('username', 'Unknown')
                days_remaining = result.get('days_remaining', 0)
                self.license_status_label.setText(
                    f"✅ Hợp lệ - User: {username}, Còn lại: {days_remaining} ngày"
                )
                self.upload_button.setEnabled(True)
            else:
                self.current_license_info = None
                error = result.get('error', 'Unknown error')
                self.license_status_label.setText(f"❌ Không hợp lệ: {error}")
                self.upload_button.setEnabled(False)
                
        except Exception as e:
            self.license_status_label.setText(f"❌ Lỗi: {str(e)}")
            self.upload_button.setEnabled(False)

    def save_license(self):
        license_key = self.license_input.text().strip()
        if license_key:
            save_license_to_file('license.txt', license_key)
            QMessageBox.information(self, "Thông báo", "Đã lưu license key")
        else:
            QMessageBox.warning(self, "Lỗi", "Chưa nhập license key")

    # ================= SERVER =================

    def check_server(self):
        if self.client.check_server_health():
            self.status_label.setText("✅ Server đang hoạt động")
        else:
            self.status_label.setText("❌ Server không khả dụng")
            self.upload_button.setEnabled(False)

    # ================= SELECT FILE =================

    def select_file(self):
        # Check license first
        if not self.current_license_info or not self.current_license_info.get('valid'):
            QMessageBox.warning(
                self, 
                "Lỗi", 
                "Vui lòng kiểm tra và xác thực license key trước khi upload file"
            )
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn file",
            "",
            "Text Files (*.txt)"
        )

        if file_path:
            license_key = self.license_input.text().strip()
            upload_mode = self.mode_combo.currentData()
            preprocess = self.preprocess_checkbox.isChecked()
            data_type = self.data_type_combo.currentData()
            self.start_upload(file_path, license_key, upload_mode, preprocess, data_type)

    # ================= START THREAD =================

    def start_upload(self, file_path, license_key, upload_mode, preprocess=False, data_type="kho1"):
        self.upload_button.setEnabled(False)
        self.result_area.clear()
        self.status_label.setText("⏳ Đang xử lý...")

        mode_text = "Lưu dữ liệu" if upload_mode == "save" else "Chỉ kiểm tra"
        preprocess_text = " (có tiền xử lý)" if preprocess else " (không tiền xử lý)"
        data_type_text = DataTypeValidator.get_data_types().get(data_type, data_type)
        self.result_area.append(f"Chế độ: {mode_text}{preprocess_text}")
        self.result_area.append(f"Loại dữ liệu: {data_type_text}")

        self.upload_thread = FileUploadThread(
            self.client, 
            file_path, 
            license_key, 
            upload_mode,
            preprocess,
            data_type
        )
        self.upload_thread.progress.connect(self.result_area.append)
        self.upload_thread.finished.connect(self.upload_finished)
        self.upload_thread.error.connect(self.upload_error)
        self.upload_thread.start()

    # ================= SIGNALS =================

    def upload_finished(self, result):
        self.upload_button.setEnabled(True)
        self.status_label.setText("✅ Hoàn tất")
        
        # Check for license-related errors
        if 'error' in result:
            error_msg = result['error']
            if 'license' in error_msg.lower() or 'expired' in error_msg.lower():
                self.license_status_label.setText("❌ License không hợp lệ hoặc đã hết hạn")
                self.current_license_info = None
            QMessageBox.critical(self, "Lỗi", error_msg)
            return
            
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

        username = result.get('username', 'Unknown')
        mode = result.get('mode', 'unknown')
        mode_text = "Đã lưu" if mode == "save" else "Chỉ kiểm tra"

        output = (
            "===== KẾT QUẢ =====\n"
            f"User: {username}\n"
            f"Chế độ: {mode_text}\n"
        )
        
        # Add preprocessing statistics if available
        if 'preprocessing_stats' in result:
            prep_stats = result['preprocessing_stats']
            output += (
                f"\n--- TIỀN XỬ LÝ ---\n"
                f"Loại dữ liệu: {prep_stats.get('data_type_description', 'N/A')}\n"
                f"Định dạng: {prep_stats.get('validation_rule', 'N/A')}\n"
                f"Dòng gốc trong file: {prep_stats['original_count']}\n"
                f"Dòng sai định dạng loại bỏ: {prep_stats.get('invalid_count', 0)}\n"
                f"Dòng trùng lặp loại bỏ: {prep_stats['duplicate_count']}\n"
                f"Dòng hợp lệ còn lại: {prep_stats['unique_count']}\n\n"
            )
        
        output += (
            f"--- XỬ LÝ SERVER ---\n"
            f"Tổng xử lý: {stats['total_processed']}\n"
            f"Mục mới: {stats['success']}\n"
            f"Trùng lặp: {stats['duplicates']}\n"
            f"Sai format: {stats.get('invalid', 0)}\n\n"
        )

        self.result_area.append(output)

        # Enable save buttons based on available data and mode
        save_mode = stats.get('save_mode', False)
        self.save_new_button.setEnabled(bool(result.get('new_data')) and save_mode)
        self.save_duplicate_button.setEnabled(bool(result.get('duplicate_data')))
        self.save_invalid_button.setEnabled(bool(result.get('invalid_data')))
        
        # Enable preprocessed duplicates button if preprocessing was used and duplicates were found
        has_preprocessed_duplicates = (
            'preprocessing_stats' in result and 
            result['preprocessing_stats']['duplicate_count'] > 0
        )
        self.save_preprocessed_button.setEnabled(has_preprocessed_duplicates)
        
        # Enable preprocessed invalid button if preprocessing was used and invalid data were found
        has_preprocessed_invalid = (
            'preprocessing_stats' in result and 
            result['preprocessing_stats'].get('invalid_count', 0) > 0
        )
        self.save_invalid_preprocessed_button.setEnabled(has_preprocessed_invalid)
        
        if not save_mode:
            self.result_area.append("⚠️ Dữ liệu không được lưu vào server (chế độ kiểm tra)")

    # ================= SAVE FUNCTIONS =================

    def save_new_data(self):
        self.save_file("new_data", "new_data.txt")

    def save_duplicate_data(self):
        self.save_file("duplicate_data", "duplicate_data.txt")

    def save_invalid_data(self):
        self.save_file("invalid_data", "invalid_data.txt")

    def save_preprocessed_duplicates(self):
        """Save the duplicates that were removed during preprocessing"""
        if not self.last_result or 'preprocessing_stats' not in self.last_result:
            QMessageBox.warning(self, "Lỗi", "Không có dữ liệu trùng lặp từ tiền xử lý để lưu")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu file dữ liệu trùng lặp đã loại bỏ",
            "preprocessed_duplicates.txt",
            "Text Files (*.txt)"
        )

        if file_path:
            try:
                duplicates = self.last_result['preprocessing_stats']['duplicates_removed']
                with open(file_path, 'w', encoding='utf-8') as f:
                    for line in duplicates:
                        f.write(line)  # line already contains newline

                QMessageBox.information(
                    self,
                    "Thành công",
                    f"Đã lưu {len(duplicates)} dòng trùng lặp đã loại bỏ"
                )
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", str(e))

    def save_invalid_preprocessed(self):
        """Save the invalid format data that were removed during preprocessing"""
        if not self.last_result or 'preprocessing_stats' not in self.last_result:
            QMessageBox.warning(self, "Lỗi", "Không có dữ liệu sai định dạng từ tiền xử lý để lưu")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu file dữ liệu sai định dạng đã loại bỏ",
            "preprocessed_invalid.txt",
            "Text Files (*.txt)"
        )

        if file_path:
            try:
                invalid_data = self.last_result['preprocessing_stats']['invalid_removed']
                with open(file_path, 'w', encoding='utf-8') as f:
                    for line in invalid_data:
                        f.write(line)  # line already contains newline

                QMessageBox.information(
                    self,
                    "Thành công",
                    f"Đã lưu {len(invalid_data)} dòng sai định dạng đã loại bỏ"
                )
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", str(e))

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
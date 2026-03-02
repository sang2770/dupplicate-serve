from flask import Flask, request, jsonify
import os
import hashlib
import json
from typing import Set, Dict, Any

app = Flask(__name__)

# File to store non-duplicate data
DATA_FILE = 'data.txt'

class DuplicateChecker:
    def __init__(self, data_file: str):
        self.data_file = data_file
        self.existing_data = self._load_existing_data()
    
    def _load_existing_data(self) -> Set[str]:
        """Load existing data from file and return as set of hashes for quick lookup."""
        existing_data = set()
        
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            # Create hash of the line for duplicate checking
                            data_hash = hashlib.md5(line.encode('utf-8')).hexdigest()
                            existing_data.add(data_hash)
            except Exception as e:
                print(f"Error loading existing data: {e}")
        
        return existing_data
    
    def _get_data_hash(self, data: str) -> str:
        """Generate MD5 hash of data for duplicate checking."""
        return hashlib.md5(data.strip().encode('utf-8')).hexdigest()
    
    def check_and_save_data(self, new_data_list: list) -> Dict[str, Any]:
        """
        Check for duplicates and save non-duplicate data.
        Returns statistics and separated data lists.
        """
        success_count = 0
        duplicate_count = 0
        new_data_to_save = []
        duplicate_data = []
        
        for data_item in new_data_list:
            data_str = str(data_item).strip()
            if not data_str:
                continue
                
            data_hash = self._get_data_hash(data_str)
            
            if data_hash in self.existing_data:
                duplicate_count += 1
                duplicate_data.append(data_str)
            else:
                # Not a duplicate, add to our tracking and prepare for saving
                self.existing_data.add(data_hash)
                new_data_to_save.append(data_str)
                success_count += 1
        
        # Save new non-duplicate data to file
        if new_data_to_save:
            self._save_data(new_data_to_save)
        
        return {
            'success': success_count,
            'duplicates': duplicate_count,
            'total_processed': len(new_data_list),
            'new_data': new_data_to_save,
            'duplicate_data': duplicate_data
        }
    
    def _save_data(self, data_list: list):
        """Append new data to the data file."""
        try:
            with open(self.data_file, 'a', encoding='utf-8') as f:
                for data in data_list:
                    f.write(f"{data}\n")
        except Exception as e:
            print(f"Error saving data: {e}")
            raise

# Initialize duplicate checker
checker = DuplicateChecker(DATA_FILE)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'service': 'duplicate-checker'})

@app.route('/upload-file', methods=['POST'])
def upload_file():
    """
    Upload a text file to check for duplicates.
    Each line in the file is treated as a separate data item.
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Read file content
        file_content = file.read().decode('utf-8')
        data_lines = [line.strip() for line in file_content.split('\n') if line.strip()]
        
        if not data_lines:
            return jsonify({'error': 'File is empty or contains no valid data'}), 400
        
        # Process the data
        stats = checker.check_and_save_data(data_lines)
        
        return jsonify({
            'status': 'success',
            'statistics': stats,
            'new_data': stats['new_data'],
            'duplicate_data': stats['duplicate_data'],
            'message': f'Processed {stats["total_processed"]} items from file: {stats["success"]} new, {stats["duplicates"]} duplicates'
        })
        
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    print("Công cụ kiểm tra dữ liệu trùng lặp...")
    print("Danh sách các endpoint:")
    print("  GET  /health - Kiểm tra trạng thái")
    print("  POST /upload-file - Tải lên tệp văn bản")
    print("\nServer starting on http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
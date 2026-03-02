from flask import Flask, request, jsonify
import os
import hashlib
import json
import sqlite3
import threading
import time
import re
from typing import Set, Dict, Any, Iterator, Tuple, List
from contextlib import contextmanager

app = Flask(__name__)

# Configuration
DATA_FILE = 'data.txt'
DB_FILE = 'duplicate_checker.db'
BATCH_SIZE = 10000  # Process in batches for memory efficiency

class OptimizedDuplicateChecker:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self._lock = threading.Lock()
        self._init_database()
        # No longer use text file - database only
        print("Database-only mode activated for optimal performance")
    
    def _init_database(self):
        """Initialize SQLite database for efficient duplicate checking."""
        with sqlite3.connect(self.db_file) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS data_hashes (
                    hash TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for faster lookups
            conn.execute('CREATE INDEX IF NOT EXISTS idx_hash ON data_hashes(hash)')
            conn.commit()
    
    def _validate_data_format(self, data: str) -> Dict[str, Any]:
        """Validate data format: 6 digits|username|20 chars with commas and spaces."""
        pattern = r'^\d{6}\|\w+\|[\w\s,]{1,20}$'
        
        if re.match(pattern, data.strip()):
            parts = data.strip().split('|')
            if len(parts) == 3:
                # Additional validation
                numbers, username, content = parts
                if (len(numbers) == 6 and numbers.isdigit() and 
                    len(username) > 0 and len(content) <= 20 and 
                    (',' in content or ' ' in content)):
                    return {'valid': True, 'data': data.strip()}
        
        return {'valid': False, 'data': data.strip(), 'error': 'Invalid format. Expected: 6digits|username|text(max20chars with commas/spaces)'}
    

    
    def _insert_batch(self, conn: sqlite3.Connection, batch: list):
        """Insert batch of data into database."""
        conn.executemany(
            'INSERT OR IGNORE INTO data_hashes (hash, data) VALUES (?, ?)',
            batch
        )
    
    @contextmanager
    def _get_db_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_file, timeout=30.0)
        conn.execute('PRAGMA journal_mode=WAL')  # Better concurrency
        conn.execute('PRAGMA cache_size=-64000')  # 64MB cache
        conn.execute('PRAGMA temp_store=memory')
        try:
            yield conn
        finally:
            conn.close()
    
    def _get_data_hash(self, data: str) -> str:
        """Generate SHA-256 hash of data for better security and distribution."""
        return hashlib.sha256(data.strip().encode('utf-8')).hexdigest()
    
    def _check_hashes_exist(self, hashes: list) -> Dict[str, bool]:
        """Efficiently check which hashes already exist in database."""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Use IN clause for batch checking
            placeholders = ','.join(['?' for _ in hashes])
            cursor.execute(
                f'SELECT hash FROM data_hashes WHERE hash IN ({placeholders})',
                hashes
            )
            
            existing_hashes = {row[0] for row in cursor.fetchall()}
            return {h: h in existing_hashes for h in hashes}
    
    def _batch_process_data(self, data_list: list) -> Iterator[Tuple[list, list, list]]:
        """Process data in batches to manage memory usage."""
        for i in range(0, len(data_list), BATCH_SIZE):
            batch = data_list[i:i + BATCH_SIZE]
            
            # Prepare batch data
            batch_data = []
            batch_hashes = []
            
            for item in batch:
                data_str = str(item).strip()
                if data_str:
                    data_hash = self._get_data_hash(data_str)
                    batch_data.append(data_str)
                    batch_hashes.append(data_hash)
            
            yield batch_data, batch_hashes, list(zip(batch_hashes, batch_data))
    
    def check_and_save_data(self, new_data_list: list) -> Dict[str, Any]:
        """Efficiently check for duplicates, validate format, and save data."""
        with self._lock:
            total_processed = 0
            success_count = 0
            duplicate_count = 0
            invalid_count = 0
            new_data_result = []
            duplicate_data_result = []
            invalid_data_result = []
            
            # First pass: validate all data
            valid_data = []
            for item in new_data_list:
                total_processed += 1
                validation = self._validate_data_format(str(item))
                
                if validation['valid']:
                    valid_data.append(validation['data'])
                else:
                    invalid_count += 1
                    invalid_data_result.append({
                        'data': validation['data'],
                        'error': validation['error']
                    })
            
            # Process valid data in batches
            for batch_data, batch_hashes, batch_pairs in self._batch_process_data(valid_data):
                if not batch_data:
                    continue
                
                # Check which hashes exist
                hash_exists = self._check_hashes_exist(batch_hashes)
                
                # Separate new and duplicate data
                new_batch = []
                new_hash_pairs = []
                
                for data_str, data_hash in zip(batch_data, batch_hashes):
                    if hash_exists[data_hash]:
                        duplicate_count += 1
                        duplicate_data_result.append(data_str)
                    else:
                        success_count += 1
                        new_data_result.append(data_str)
                        new_batch.append(data_str)
                        new_hash_pairs.append((data_hash, data_str))
                
                # Save new data to database only
                if new_hash_pairs:
                    self._save_new_data_to_db(new_hash_pairs)
                
                # Print progress for large datasets
                processed_valid = len(valid_data)
                if processed_valid > 0 and processed_valid % (BATCH_SIZE * 10) == 0:
                    print(f"Processed {processed_valid:,} valid items...")
            
            return {
                'success': success_count,
                'duplicates': duplicate_count,
                'invalid': invalid_count,
                'total_processed': total_processed,
                'new_data': new_data_result,
                'duplicate_data': duplicate_data_result,
                'invalid_data': invalid_data_result
            }
    
    def _save_new_data_to_db(self, hash_pairs: list):
        """Save new data to database only (no text file)."""
        try:
            with self._get_db_connection() as conn:
                conn.executemany(
                    'INSERT OR IGNORE INTO data_hashes (hash, data) VALUES (?, ?)',
                    hash_pairs
                )
                conn.commit()
        except Exception as e:
            print(f"Error saving data to database: {e}")
            raise
    
    def export_all_data_to_file(self, output_file: str) -> Dict[str, Any]:
        """Export all database data to text file."""
        try:
            exported_count = 0
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT data FROM data_hashes ORDER BY created_at')
                
                with open(output_file, 'w', encoding='utf-8', buffering=65536) as f:
                    for row in cursor:
                        f.write(f"{row[0]}\n")
                        exported_count += 1
                        
                        if exported_count % 10000 == 0:
                            print(f"Exported {exported_count:,} records...")
                            
            return {
                'success': True,
                'exported_file': output_file,
                'exported_count': exported_count,
                'file_size_mb': os.path.getsize(output_file) / (1024 * 1024)
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        with self._get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM data_hashes')
            total_count = cursor.fetchone()[0]
            
            return {
                'total_records': total_count,
                'database_size_mb': os.path.getsize(self.db_file) / (1024 * 1024) if os.path.exists(self.db_file) else 0
            }

# Initialize optimized duplicate checker (database only)
checker = OptimizedDuplicateChecker(DB_FILE)

@app.route('/export-data', methods=['POST'])
def export_data():
    """Export all database data to text file."""
    try:
        data = request.get_json() or {}
        output_file = data.get('output_file', f'exported_data_{int(time.time())}.txt')
        
        result = checker.export_all_data_to_file(output_file)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'exported_file': result['exported_file'],
                'exported_count': result['exported_count'],
                'file_size_mb': round(result['file_size_mb'], 2),
                'message': f'Successfully exported {result["exported_count"]:,} records to {output_file}'
            })
        else:
            return jsonify({'error': f'Export failed: {result["error"]}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Export error: {str(e)}'}), 500
def get_stats():
    """Get system statistics."""
    try:
        stats = checker.get_stats()
        return jsonify({
            'status': 'success',
            'statistics': stats
        })
    except Exception as e:
        return jsonify({'error': f'Error getting stats: {str(e)}'}), 500

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
            'invalid_data': stats['invalid_data'],
            'message': f'Processed {stats["total_processed"]} items: {stats["success"]} new, {stats["duplicates"]} duplicates, {stats["invalid"]} invalid format'
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
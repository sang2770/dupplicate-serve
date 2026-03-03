from flask import Flask, request, jsonify
import os
import hashlib
import json
import sqlite3
import threading
import time
import re
import uuid
from datetime import datetime, timedelta
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
            
            # Create license keys table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS license_keys (
                    key_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            conn.execute('CREATE INDEX IF NOT EXISTS idx_license_key ON license_keys(key_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_username ON license_keys(username)')
            conn.commit()
    
    def create_license_key(self, username: str, days_valid: int = 30) -> Dict[str, Any]:
        """Create a new license key for a user."""
        try:
            key_id = str(uuid.uuid4())
            expires_at = datetime.now() + timedelta(days=days_valid)
            
            with self._get_db_connection() as conn:
                conn.execute('''
                    INSERT INTO license_keys (key_id, username, expires_at)
                    VALUES (?, ?, ?)
                ''', (key_id, username, expires_at.isoformat()))
                conn.commit()
            
            return {
                'success': True,
                'key_id': key_id,
                'username': username,
                'expires_at': expires_at.isoformat(),
                'days_valid': days_valid
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def validate_license_key(self, key_id: str) -> Dict[str, Any]:
        """Validate a license key and return user info."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT username, expires_at, is_active 
                    FROM license_keys 
                    WHERE key_id = ?
                ''', (key_id,))
                
                result = cursor.fetchone()
                if not result:
                    return {'valid': False, 'error': 'License key not found'}
                
                username, expires_at_str, is_active = result
                expires_at = datetime.fromisoformat(expires_at_str)
                
                if not is_active:
                    return {'valid': False, 'error': 'License key is deactivated'}
                
                if datetime.now() > expires_at:
                    return {'valid': False, 'error': 'License key has expired'}
                
                return {
                    'valid': True,
                    'username': username,
                    'expires_at': expires_at_str,
                    'days_remaining': (expires_at - datetime.now()).days
                }
        except Exception as e:
            return {'valid': False, 'error': f'Validation error: {str(e)}'}
    
    def list_all_licenses(self) -> List[Dict[str, Any]]:
        """List all license keys in the database."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT key_id, username, created_at, expires_at, is_active 
                    FROM license_keys 
                    ORDER BY created_at DESC
                ''')
                
                licenses = []
                for row in cursor.fetchall():
                    key_id, username, created_at, expires_at_str, is_active = row
                    expires_at = datetime.fromisoformat(expires_at_str)
                    now = datetime.now()
                    
                    days_remaining = (expires_at - now).days
                    is_expired = now > expires_at
                    
                    licenses.append({
                        'key_id': key_id,
                        'username': username,
                        'created_at': created_at,
                        'expires_at': expires_at_str,
                        'is_active': bool(is_active),
                        'is_expired': is_expired,
                        'days_remaining': days_remaining,
                        'status': 'Expired' if is_expired else ('Inactive' if not is_active else f'{days_remaining} days left')
                    })
                
                return licenses
        except Exception as e:
            return []
    
    def remove_license_key(self, key_id: str) -> Dict[str, Any]:
        """Remove a license key from the database."""
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                
                # First check if license exists
                cursor.execute('SELECT username FROM license_keys WHERE key_id = ?', (key_id,))
                result = cursor.fetchone()
                
                if not result:
                    return {'success': False, 'error': 'License key not found'}
                
                username = result[0]
                
                # Delete the license
                cursor.execute('DELETE FROM license_keys WHERE key_id = ?', (key_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    return {
                        'success': True,
                        'message': f'License key for user "{username}" has been removed',
                        'username': username
                    }
                else:
                    return {'success': False, 'error': 'Failed to remove license key'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _validate_data_format(self, data: str) -> Dict[str, Any]:
        """Validate data format: only 6 digits are required."""
        data_clean = data.strip()
        
        # Check if it's exactly 6 digits
        if re.match(r'^\d{6}$', data_clean):
            return {'valid': True, 'data': data_clean}
        
        return {
            'valid': False, 
            'data': data_clean, 
            'error': 'Invalid format. Expected: exactly 6 digits'
        }

    
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
    
    def check_and_save_data(self, new_data_list: list, username: str = "unknown", save_data: bool = True) -> Dict[str, Any]:
        """Efficiently check for duplicates, validate format, and optionally save data."""
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
                
                # Check which hashes exist (check only the 6 digits part)
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
                        
                        # If saving data, format as: 6digits|username|timestamp
                        if save_data:
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            full_data = f"{data_str}|{username}|{timestamp}"
                            new_hash_pairs.append((data_hash, full_data))
                
                # Save new data to database only if save_data is True
                if save_data and new_hash_pairs:
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
                'invalid_data': invalid_data_result,
                'save_mode': save_data
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

@app.route('/create-license', methods=['POST'])
def create_license():
    """Create a new license key for a user."""
    try:
        data = request.get_json() or {}
        username = data.get('username')
        days_valid = data.get('days_valid', 30)
        
        if not username:
            return jsonify({'error': 'Username is required'}), 400
        
        result = checker.create_license_key(username, days_valid)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'license_key': result['key_id'],
                'username': result['username'],
                'expires_at': result['expires_at'],
                'days_valid': result['days_valid'],
                'message': f'License key created for {username}, valid for {days_valid} days'
            })
        else:
            return jsonify({'error': f'Failed to create license: {result["error"]}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'License creation error: {str(e)}'}), 500

@app.route('/validate-license', methods=['POST'])
def validate_license():
    """Validate a license key."""
    try:
        data = request.get_json() or {}
        key_id = data.get('key_id')
        
        if not key_id:
            return jsonify({'error': 'License key is required'}), 400
        
        result = checker.validate_license_key(key_id)
        
        if result['valid']:
            return jsonify({
                'status': 'success',
                'valid': True,
                'username': result['username'],
                'expires_at': result['expires_at'],
                'days_remaining': result['days_remaining']
            })
        else:
            return jsonify({
                'status': 'error',
                'valid': False,
                'error': result['error']
            }), 403
            
    except Exception as e:
        return jsonify({'error': f'License validation error: {str(e)}'}), 500

@app.route('/list-licenses', methods=['GET'])
def list_licenses():
    """List all license keys."""
    try:
        licenses = checker.list_all_licenses()
        return jsonify({
            'status': 'success',
            'licenses': licenses,
            'count': len(licenses)
        })
    except Exception as e:
        return jsonify({'error': f'Error listing licenses: {str(e)}'}), 500

@app.route('/remove-license', methods=['DELETE'])
def remove_license():
    """Remove a license key."""
    try:
        data = request.get_json() or {}
        key_id = data.get('key_id')
        
        if not key_id:
            return jsonify({'error': 'License key is required'}), 400
        
        result = checker.remove_license_key(key_id)
        
        if result['success']:
            return jsonify({
                'status': 'success',
                'message': result['message'],
                'username': result['username']
            })
        else:
            return jsonify({'error': result['error']}, 404)
            
    except Exception as e:
        return jsonify({'error': f'Error removing license: {str(e)}'}), 500

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

@app.route('/stats', methods=['GET'])
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
        # Check for license key
        license_key = request.headers.get('Authorization') or request.form.get('license_key')
        if not license_key:
            return jsonify({'error': 'License key is required'}), 401
        
        # Remove "Bearer " prefix if present
        if license_key.startswith('Bearer '):
            license_key = license_key[7:]
        
        # Validate license
        license_result = checker.validate_license_key(license_key)
        if not license_result['valid']:
            return jsonify({'error': f'Invalid license: {license_result["error"]}'}), 403
        
        username = license_result['username']
        
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get upload mode (default is save mode)
        upload_mode = request.form.get('mode', 'save')  # 'save' or 'check'
        save_data = (upload_mode == 'save')
        
        # Read file content
        file_content = file.read().decode('utf-8')
        data_lines = [line.strip() for line in file_content.split('\n') if line.strip()]
        
        if not data_lines:
            return jsonify({'error': 'File is empty or contains no valid data'}), 400
        
        # Process the data
        stats = checker.check_and_save_data(data_lines, username, save_data)
        
        mode_text = "saved" if save_data else "checked only"
        
        return jsonify({
            'status': 'success',
            'statistics': stats,
            'new_data': stats['new_data'],
            'duplicate_data': stats['duplicate_data'],
            'invalid_data': stats['invalid_data'],
            'username': username,
            'mode': upload_mode,
            'message': f'Processed {stats["total_processed"]} items ({mode_text}): {stats["success"]} new, {stats["duplicates"]} duplicates, {stats["invalid"]} invalid format'
        })
        
    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    print("Công cụ kiểm tra dữ liệu trùng lặp với license system...")
    print("Danh sách các endpoint:")
    print("  GET  /health - Kiểm tra trạng thái")
    print("  POST /create-license - Tạo license key mới")
    print("  POST /validate-license - Kiểm tra license key")
    print("  GET  /list-licenses - Liệt kê tất cả license keys")
    print("  DELETE /remove-license - Xóa license key")
    print("  POST /upload-file - Tải lên tệp văn bản (cần license)")
    print("  POST /export-data - Xuất dữ liệu")
    print("\nServer starting on http://localhost:5000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)

import requests
import os
from typing import Dict, Optional
import sys
sys.stdout.reconfigure(encoding="utf-8")

def read_domain_from_file(file_path: str) -> Optional[str]:
    """Read the server domain from a file."""
    try:
        with open(file_path, 'r') as f:
            domain = f.read().strip()
            if domain:
                return domain
            return None
    except:
        return None

class DuplicateCheckerClient:
    def __init__(self, server_url: str = "http://localhost:5000"):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
    
    def check_server_health(self) -> bool:
        """Check if the server is running and healthy."""
        try:
            response = self.session.get(f"{self.server_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def upload_file(self, file_path: str) -> Optional[Dict]:
        """
        Upload a text file to check for duplicates.
        Each line in the file is treated as a separate data item.
        """
        try:
            if not os.path.exists(file_path):
                print(f"Error: File '{file_path}' not found")
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
            else:
                print(f"Error: Server returned status {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error connecting to server: {e}")
            return None


def print_results(result: Dict):
    """Pretty print the results from the server."""
    if result and 'statistics' in result:
        stats = result['statistics']
        print("\n" + "="*50)
        print("Kết quả kiểm tra trùng lặp")
        print("="*50)
        print(f"Tổng số lượt xử lý: {stats['total_processed']}")
        print(f"Số mục mới được lưu: {stats['success']}")
        print(f"Số mục trùng lặp: {stats['duplicates']}")
        print(f"Tỷ lệ thành công: {stats['success']/stats['total_processed']*100:.1f}%")
        print("="*50)
    else:
        print("Không có kết quả hợp lệ để hiển thị")

def main():
    domain = read_domain_from_file('domain.txt')

    """Main function to demonstrate the client usage."""
    client = DuplicateCheckerClient(server_url=domain if domain else "http://localhost:5000")

    print("Công cụ kiểm tra dữ liệu trùng lặp - Máy Khách")
    print("============================")
    
    # Check if server is running
    if not client.check_server_health():
        print("❌ Server hiện không khả dụng!")
        return

    print("✅ Server đang hoạt động!")

    while True:
        print("Lựa chọn:")
        print("0. Thoát")
        print("1. Upload file")

        choice = input("\nLựa chọn:").strip()
        
        if choice == '1':
            file_path = input("Nhập đường dẫn tệp văn bản cần kiểm tra: (Mặc định: 'data.txt')").strip()
            if not file_path:
                file_path = 'data.txt'
            result = client.upload_file(file_path)
            print_results(result)
        
        elif choice == '0':
            print("Goodbye!")
            break
        else:
            print("Lựa chọn không hợp lệ.")

if __name__ == '__main__':
    main()
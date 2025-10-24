"""
ADB 명령어 래퍼 클래스
Android Debug Bridge를 통한 디바이스 관리 및 파일 시스템 접근
"""

import subprocess
import threading
import time
from typing import List, Dict, Optional, Callable
import os


class ADBManager:
    """ADB 명령어를 실행하고 디바이스와 상호작용하는 클래스"""
    
    def __init__(self):
        self.devices = []
        self.current_device = None
        
    def check_adb_available(self) -> bool:
        """ADB가 시스템에 설치되어 있는지 확인"""
        try:
            result = subprocess.run(['adb', 'version'], 
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def get_connected_devices(self) -> List[Dict[str, str]]:
        """연결된 디바이스 목록을 가져옴"""
        try:
            result = subprocess.run(['adb', 'devices'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return []
            
            devices = []
            lines = result.stdout.strip().split('\n')[1:]  # 첫 번째 줄은 헤더
            
            for line in lines:
                if line.strip() and '\t' in line:
                    device_id, status = line.strip().split('\t')
                    if status == 'device':
                        devices.append({
                            'id': device_id,
                            'status': status,
                            'name': self._get_device_name(device_id)
                        })
            
            self.devices = devices
            return devices
            
        except subprocess.TimeoutExpired:
            return []
        except Exception as e:
            print(f"디바이스 목록 가져오기 실패: {e}")
            return []
    
    def _get_device_name(self, device_id: str) -> str:
        """디바이스 이름을 가져옴"""
        try:
            result = subprocess.run(['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return f"Device {device_id[:8]}"
    
    def set_current_device(self, device_id: str) -> bool:
        """현재 작업할 디바이스를 설정"""
        if any(device['id'] == device_id for device in self.devices):
            self.current_device = device_id
            return True
        return False
    
    def get_file_list(self, path: str = "/") -> List[Dict[str, str]]:
        """지정된 경로의 파일 목록을 가져옴"""
        if not self.current_device:
            return []
        
        try:
            # ls -la 명령어로 상세 정보 가져오기
            result = subprocess.run(['adb', '-s', self.current_device, 'shell', 'ls', '-la', path],
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                return []
            
            files = []
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                if line.strip() and not line.startswith('total'):
                    parts = line.split()
                    if len(parts) >= 9:
                        # ls -la 출력 파싱
                        permissions = parts[0]
                        size = parts[4]
                        date = ' '.join(parts[5:8])
                        name = ' '.join(parts[8:])
                        
                        is_directory = permissions.startswith('d')
                        
                        files.append({
                            'name': name,
                            'path': os.path.join(path, name).replace('//', '/'),
                            'is_directory': is_directory,
                            'size': size,
                            'permissions': permissions,
                            'date': date
                        })
            
            return files
            
        except subprocess.TimeoutExpired:
            return []
        except Exception as e:
            print(f"파일 목록 가져오기 실패: {e}")
            return []
    
    def pull_file(self, remote_path: str, local_path: str, 
                  progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """디바이스에서 로컬로 파일을 다운로드"""
        if not self.current_device:
            return False
        
        try:
            # 파일 크기 확인
            size_result = subprocess.run(['adb', '-s', self.current_device, 'shell', 'stat', '-c', '%s', remote_path],
                                      capture_output=True, text=True, timeout=5)
            
            if size_result.returncode != 0:
                return False
            
            total_size = int(size_result.stdout.strip())
            
            # adb pull 실행
            result = subprocess.run(['adb', '-s', self.current_device, 'pull', remote_path, local_path],
                                  capture_output=True, text=True, timeout=300)  # 5분 타임아웃
            
            if result.returncode == 0:
                if progress_callback:
                    progress_callback(total_size, total_size)
                return True
            else:
                print(f"파일 다운로드 실패: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("파일 다운로드 타임아웃")
            return False
        except Exception as e:
            print(f"파일 다운로드 실패: {e}")
            return False
    
    def push_file(self, local_path: str, remote_path: str,
                  progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """로컬에서 디바이스로 파일을 업로드"""
        if not self.current_device:
            return False
        
        try:
            # 로컬 파일 크기 확인
            if not os.path.exists(local_path):
                return False
            
            local_size = os.path.getsize(local_path)
            
            # adb push 실행
            result = subprocess.run(['adb', '-s', self.current_device, 'push', local_path, remote_path],
                                  capture_output=True, text=True, timeout=300)  # 5분 타임아웃
            
            if result.returncode == 0:
                if progress_callback:
                    progress_callback(local_size, local_size)
                return True
            else:
                print(f"파일 업로드 실패: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("파일 업로드 타임아웃")
            return False
        except Exception as e:
            print(f"파일 업로드 실패: {e}")
            return False
    
    def create_directory(self, path: str) -> bool:
        """디바이스에 디렉토리 생성"""
        if not self.current_device:
            return False
        
        try:
            result = subprocess.run(['adb', '-s', self.current_device, 'shell', 'mkdir', '-p', path],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            print(f"디렉토리 생성 실패: {e}")
            return False
    
    def delete_file(self, path: str) -> bool:
        """디바이스에서 파일/디렉토리 삭제"""
        if not self.current_device:
            return False
        
        try:
            result = subprocess.run(['adb', '-s', self.current_device, 'shell', 'rm', '-rf', path],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            print(f"파일 삭제 실패: {e}")
            return False

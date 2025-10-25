"""
ADB 명령어 래퍼 클래스
Android Debug Bridge를 통한 디바이스 관리 및 파일 시스템 접근
"""

import subprocess
import threading
import time
import re
from typing import List, Dict, Optional, Callable, Tuple
import os
import shutil
import sys

class ADBManager:
    """ADB 명령어를 실행하고 디바이스와 상호작용하는 클래스"""
    
    def __init__(self):
        self.devices = []
        self.current_device = None
        self.adb_path = self.get_adb_path()
        
    def get_adb_path(self):
        """Find the path to the adb executable."""
        base_path = os.path.dirname(os.path.abspath(__file__))
        
        if sys.platform == 'darwin':
            exe_name = 'adb'
        elif sys.platform == 'win32':
            exe_name = 'adb.exe'
        elif sys.platform.startswith('linux'):
            exe_name = 'adb'
        else:
            return shutil.which('adb')

        path = os.path.join(base_path, exe_name)
        
        if os.path.exists(path):
            os.chmod(path, 0o755)
            return path
            
        # Fallback to PATH
        return shutil.which('adb')

    def check_adb_available(self) -> bool:
        """ADB가 시스템에 설치되어 있는지 확인"""
        return self.adb_path is not None
    
    def get_connected_devices(self) -> List[Dict[str, str]]:
        """연결된 디바이스 목록을 가져옴"""
        if not self.adb_path:
            return []
        try:
            result = subprocess.run([self.adb_path, 'devices'], 
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
        if not self.adb_path:
            return f"Device {device_id[:8]}"
        try:
            result = subprocess.run([self.adb_path, '-s', device_id, 'shell', 'getprop', 'ro.product.model'],
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
        if not self.current_device or not self.adb_path:
            print("❌ 현재 디바이스가 설정되지 않음")
            return []
        
        try:
            print(f"🔍 ADB 명령어 실행: adb -s {self.current_device} shell ls -la {path}")
            result = subprocess.run([self.adb_path, '-s', self.current_device, 'shell', 'ls', '-la', path],
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0:
                print(f"❌ ADB 명령어 실패: {result.stderr}")
                return []
            
            files = []
            lines = result.stdout.strip().split('\n')

            patterns = [
                # With group, YYYY-MM-DD HH:MM
                re.compile(r'^(?P<permissions>\S+)\s+(?P<links>\d+)\s+(?P<owner>\S+)\s+(?P<group>\S+)\s+(?P<size>\S+)\s+(?P<date>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(?P<name>.+)$'),
                # With group, Mmm DD HH:MM
                re.compile(r'^(?P<permissions>\S+)\s+(?P<links>\d+)\s+(?P<owner>\S+)\s+(?P<group>\S+)\s+(?P<size>\S+)\s+(?P<date>\w{3}\s+\d{1,2}\s+\d{2}:\d{2})\s+(?P<name>.+)$'),
                # With group, Mmm DD YYYY
                re.compile(r'^(?P<permissions>\S+)\s+(?P<links>\d+)\s+(?P<owner>\S+)\s+(?P<group>\S+)\s+(?P<size>\S+)\s+(?P<date>\w{3}\s+\d{1,2}\s+\d{4})\s+(?P<name>.+)$'),
                # Without group, YYYY-MM-DD HH:MM
                re.compile(r'^(?P<permissions>\S+)\s+(?P<links>\d+)\s+(?P<owner>\S+)\s+(?P<size>\S+)\s+(?P<date>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(?P<name>.+)$'),
            ]
            
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('total'):
                    match = None
                    for pattern in patterns:
                        match = pattern.match(line)
                        if match:
                            break
                    
                    if match:
                        data = match.groupdict()
                        permissions = data['permissions']
                        name_part = data['name']
                        
                        if ' -> ' in name_part:
                            name = name_part.split(' -> ')[0].strip()
                        else:
                            name = name_part.strip()
                        
                        if name in ['.', '..']:
                            continue
                        
                        is_directory = permissions.startswith('d')
                        is_link = permissions.startswith('l')
                        
                        files.append({
                            'name': name,
                            'path': os.path.join(path, name).replace('//', '/'),
                            'is_directory': is_directory,
                            'is_link': is_link,
                            'size': data['size'],
                            'permissions': permissions,
                            'date': data['date'],
                            'owner': data['owner'],
                            'group': data.get('group', '')
                        })
                    else:
                        print(f"⚠️ 파싱 실패: {line}")
            
            return files
            
        except subprocess.TimeoutExpired:
            print("⏰ ADB 명령어 타임아웃")
            return []
        except Exception as e:
            print(f"❌ 파일 목록 가져오기 실패: {e}")
            return []
    
    def pull_file(self, remote_path: str, local_path: str, 
                  progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """디바이스에서 로컬로 파일을 다운로드"""
        if not self.current_device or not self.adb_path:
            return False
        
        try:
            # Get file size first
            size_result = subprocess.run([self.adb_path, '-s', self.current_device, 'shell', 'stat', '-c', '%s', remote_path],
                                      capture_output=True, text=True, timeout=5)
            if size_result.returncode != 0:
                total_size = -1
            else:
                total_size = int(size_result.stdout.strip())

            # Use Popen to capture output in real-time
            process = subprocess.Popen(
                [self.adb_path, '-s', self.current_device, 'pull', '-p', remote_path, local_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            if progress_callback:
                for line in iter(process.stdout.readline, ''):
                    match = re.search(r'[[\s*(\d+)%\\]]', line)
                    if match:
                        percentage = int(match.group(1))
                        if total_size > 0:
                            transferred = int(total_size * percentage / 100)
                            progress_callback(transferred, total_size)
                        else:
                            progress_callback(percentage, 100)

            return_code = process.wait()
            if return_code != 0:
                stderr = process.stderr.read()
                print(f"파일 다운로드 실패: {stderr}")
                return False

            if progress_callback and total_size > 0:
                progress_callback(total_size, total_size)
            return True
                
        except Exception as e:
            print(f"파일 다운로드 실패: {e}")
            return False
    
    def push_file(self, local_path: str, remote_path: str,
                  progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """로컬에서 디바이스로 파일을 업로드"""
        if not self.current_device or not self.adb_path:
            return False
        
        try:
            if not os.path.exists(local_path):
                return False
            
            local_size = os.path.getsize(local_path)

            process = subprocess.Popen(
                [self.adb_path, '-s', self.current_device, 'push', '-p', local_path, remote_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            if progress_callback:
                for line in iter(process.stdout.readline, ''):
                    match = re.search(r'[[\s*(\d+)%\\]]', line)
                    if match:
                        percentage = int(match.group(1))
                        transferred = int(local_size * percentage / 100)
                        progress_callback(transferred, local_size)

            return_code = process.wait()
            if return_code != 0:
                stderr = process.stderr.read()
                print(f"파일 업로드 실패: {stderr}")
                return False

            if progress_callback:
                progress_callback(local_size, local_size)
            return True
                
        except Exception as e:
            print(f"파일 업로드 실패: {e}")
            return False
    
    def create_directory(self, path: str) -> bool:
        """디바이스에 디렉토리 생성"""
        if not self.current_device or not self.adb_path:
            return False
        
        try:
            result = subprocess.run([self.adb_path, '-s', self.current_device, 'shell', 'mkdir', '-p', path],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            print(f"디렉토리 생성 실패: {e}")
            return False
    
    def rename_file(self, old_path: str, new_path: str) -> bool:
        """디바이스에서 파일/디렉토리 이름변경"""
        if not self.current_device or not self.adb_path:
            return False
        
        try:
            result = subprocess.run([self.adb_path, '-s', self.current_device, 'shell', 'mv', old_path, new_path],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            print(f"파일 이름변경 실패: {e}")
            return False
    
    def get_link_target(self, link_path: str) -> Optional[str]:
        """심볼릭 링크의 타겟 경로를 가져옴"""
        if not self.current_device or not self.adb_path:
            return None
        
        try:
            result = subprocess.run([self.adb_path, '-s', self.current_device, 'shell', 'readlink', link_path],
                                  capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                target = result.stdout.strip()
                print(f"🔗 링크 타겟: {link_path} -> {target}")
                return target
            else:
                print(f"❌ 링크 타겟 읽기 실패: {result.stderr}")
                return None
        except Exception as e:
            print(f"❌ 링크 타겟 읽기 오류: {e}")
            return None
    
    def is_directory(self, path: str) -> bool:
        """경로가 디렉토리인지 확인"""
        if not self.current_device or not self.adb_path:
            return False
        
        try:
            result = subprocess.run([self.adb_path, '-s', self.current_device, 'shell', 'test', '-d', path],
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            print(f"❌ 디렉토리 확인 오류: {e}")
            return False
    
    def is_link(self, path: str) -> bool:
        """경로가 심볼릭 링크인지 확인"""
        if not self.current_device or not self.adb_path:
            return False
        
        try:
            result = subprocess.run([self.adb_path, '-s', self.current_device, 'shell', 'test', '-L', path],
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            print(f"❌ 링크 확인 오류: {e}")
            return False
    
    def delete_file(self, path: str) -> bool:
        """디바이스에서 파일/디렉토리 삭제"""
        if not self.current_device or not self.adb_path:
            return False
        
        try:
            result = subprocess.run([self.adb_path, '-s', self.current_device, 'shell', 'rm', '-rf', path],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            print(f"파일 삭제 실패: {e}")
            return False

    def pair_device(self, ip_address: str, pairing_code: str) -> Tuple[bool, str]:
        """ADB 페어링을 시도"""
        if not self.adb_path:
            return False, "ADB executable not found."
        try:
            # adb pair 명령어 실행
            process = subprocess.Popen([self.adb_path, 'pair', ip_address],
                                     stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     text=True)
            
            # 페어링 코드 입력
            stdout, stderr = process.communicate(input=f"{pairing_code}\n", timeout=15)
            
            if process.returncode == 0 and "Successfully paired" in stdout:
                return True, stdout.strip()
            else:
                error_message = stderr.strip() if stderr else stdout.strip()
                return False, error_message

        except subprocess.TimeoutExpired:
            return False, "페어링 시간이 초과되었습니다."
        except Exception as e:
            return False, f"페어링 중 오류 발생: {e}"

    def restart_server(self) -> Tuple[bool, str]:
        """Kills and starts the ADB server."""
        if not self.adb_path:
            return False, "ADB executable not found."
        try:
            # Kill the server, ignore errors if it's not running
            subprocess.run([self.adb_path, 'kill-server'], capture_output=True, text=True, timeout=10)
            time.sleep(1) # Give it a moment to die

            # Start the server
            start_result = subprocess.run([self.adb_path, 'start-server'], capture_output=True, text=True, timeout=10)
            
            if start_result.returncode == 0:
                return True, "ADB server restarted successfully."
            else:
                error_message = start_result.stderr.strip() if start_result.stderr else "Unknown error."
                return False, f"Failed to start ADB server: {error_message}"

        except Exception as e:
            return False, f"An error occurred while restarting ADB server: {e}"

    def connect_device(self, ip_address: str) -> Tuple[bool, str]:
        """Connect to a device via IP address."""
        if not self.adb_path:
            return False, "ADB executable not found."
        try:
            result = subprocess.run([self.adb_path, 'connect', ip_address],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and "connected" in result.stdout:
                return True, result.stdout.strip()
            else:
                return False, result.stderr.strip() if result.stderr else result.stdout.strip()
        except Exception as e:
            return False, str(e)

    def discover_pairing_services(self) -> List[Dict[str, str]]:
        """Discover ADB pairing services on the network using mDNS."""
        if not self.adb_path:
            return []
        try:
            result = subprocess.run([self.adb_path, 'mdns', 'services'],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return []
            
            services = []
            lines = result.stdout.strip().split('\n')
            
            for line in lines:
                if '_adb-tls-pairing._tcp.' in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        name = parts[0]
                        address_port = parts[2]
                        if ':' in address_port:
                            ip, port = address_port.rsplit(':', 1)
                            services.append({'name': name, 'ip': ip, 'port': port})
            return services
            
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []
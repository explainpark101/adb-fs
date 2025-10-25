"""
ADB 명령어 래퍼 클래스
Android Debug Bridge를 통한 디바이스 관리 및 파일 시스템 접근
"""

import subprocess
import threading
import time
import re
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
            print("❌ 현재 디바이스가 설정되지 않음")
            return []
        
        try:
            print(f"🔍 ADB 명령어 실행: adb -s {self.current_device} shell ls -la {path}")
            # ls -la 명령어로 상세 정보 가져오기
            result = subprocess.run(['adb', '-s', self.current_device, 'shell', 'ls', '-la', path],
                                  capture_output=True, text=True, timeout=10)
            
            print(f"📊 ADB 명령어 결과: returncode={result.returncode}")
            print(f"📝 stdout 길이: {len(result.stdout)}")
            print(f"⚠️ stderr: {result.stderr}")
            
            if result.returncode != 0:
                print(f"❌ ADB 명령어 실패: {result.stderr}")
                return []
            
            files = []
            lines = result.stdout.strip().split('\n')
            print(f"📋 파싱할 줄 수: {len(lines)}")
            
            for i, line in enumerate(lines):
                if line.strip() and not line.startswith('total'):
                    print(f"🔍 파싱 중인 줄 {i}: {line[:50]}...")
                    
                    # 정규표현식으로 ls -la 출력 파싱
                    # 형식: permissions links owner group size month day time name
                    # 예: drwxr-xr-x  2 user user 4096 Dec 25 10:30 folder_name
                    # 예: lrwxrwxrwx  1 user user    8 Dec 25 10:30 link_name -> target
                    
                    # Android ls -la 출력 형식에 맞는 패턴
                    # 형식: permissions links owner group size YYYY-MM-DD HH:MM name
                    # 예: drwxr-xr-x   34 root   root       4096 2025-08-01 15:51 .
                    pattern = r'^(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(.+)$'
                    match = re.match(pattern, line)
                    
                    if match:
                        permissions = match.group(1)
                        links = match.group(2)
                        owner = match.group(3)
                        group = match.group(4)
                        size = match.group(5)
                        date = match.group(6)
                        name_part = match.group(7)
                        
                        # 심볼릭 링크 처리 (-> 제거)
                        if ' -> ' in name_part:
                            name = name_part.split(' -> ')[0].strip()
                        else:
                            name = name_part.strip()
                        
                        # . 및 .. 디렉토리 제외
                        if name in ['.', '..']:
                            continue
                        
                        is_directory = permissions.startswith('d')
                        is_link = permissions.startswith('l')
                        
                        files.append({
                            'name': name,
                            'path': os.path.join(path, name).replace('//', '/'),
                            'is_directory': is_directory,
                            'is_link': is_link,
                            'size': size,
                            'permissions': permissions,
                            'date': date,
                            'owner': owner,
                            'group': group
                        })
                        print(f"✅ 파일 추가: {name} ({'폴더' if is_directory else '파일'})")
                    else:
                        print(f"⚠️ 파싱 실패: {line}")
            
            print(f"📁 총 {len(files)}개 파일/폴더 발견")
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
    
    def rename_file(self, old_path: str, new_path: str) -> bool:
        """디바이스에서 파일/디렉토리 이름변경"""
        if not self.current_device:
            return False
        
        try:
            result = subprocess.run(['adb', '-s', self.current_device, 'shell', 'mv', old_path, new_path],
                                  capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            print(f"파일 이름변경 실패: {e}")
            return False
    
    def get_link_target(self, link_path: str) -> Optional[str]:
        """심볼릭 링크의 타겟 경로를 가져옴"""
        if not self.current_device:
            return None
        
        try:
            result = subprocess.run(['adb', '-s', self.current_device, 'shell', 'readlink', link_path],
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
        if not self.current_device:
            return False
        
        try:
            result = subprocess.run(['adb', '-s', self.current_device, 'shell', 'test', '-d', path],
                                  capture_output=True, text=True, timeout=5)
            return result.returncode == 0
        except Exception as e:
            print(f"❌ 디렉토리 확인 오류: {e}")
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

    def pair_device(self, ip_address: str, pairing_code: str) -> (bool, str):
        """ADB 페어링을 시도"""
        try:
            # adb pair 명령어 실행
            process = subprocess.Popen(['adb', 'pair', ip_address],
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

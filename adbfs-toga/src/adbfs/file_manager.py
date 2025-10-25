"""
파일 전송 관리 클래스
파일 다운로드/업로드 진행률 추적 및 상태 관리
"""

import os
import threading
import time
from typing import Callable, Optional, Dict, List, Any
from .adb_manager import ADBManager

class FileManager:
    """파일 전송을 관리하고 진행률을 추적하는 클래스"""
    
    def __init__(self, adb_manager: ADBManager):
        self.adb_manager = adb_manager
        self.transfer_threads = {}
        self.transfer_status = {}
        
    def download_file(self, remote_path: str, local_path: str, 
                     progress_callback: Optional[Callable[[int, int, str], None]] = None,
                     status_callback: Optional[Callable[[str], None]] = None) -> bool:
        """파일을 디바이스에서 로컬로 다운로드"""
        
        def progress_wrapper(transferred: int, total: int):
            if progress_callback:
                progress_callback(transferred, total, "다운로드 중...")
        
        def status_wrapper(message: str):
            if status_callback:
                status_callback(message)
        
        # 로컬 디렉토리 생성
        local_dir = os.path.dirname(local_path)
        if local_dir and not os.path.exists(local_dir):
            os.makedirs(local_dir, exist_ok=True)
        
        status_wrapper(f"다운로드 시작: {os.path.basename(remote_path)}")
        
        # 파일 전송 실행
        success = self.adb_manager.pull_file(remote_path, local_path, progress_wrapper)
        
        if success:
            status_wrapper(f"다운로드 완료: {local_path}")
        else:
            status_wrapper(f"다운로드 실패: {remote_path}")
        
        return success
    
    def upload_file(self, local_path: str, remote_path: str,
                   progress_callback: Optional[Callable[[int, int, str], None]] = None,
                   status_callback: Optional[Callable[[str], None]] = None) -> bool:
        """파일을 로컬에서 디바이스로 업로드"""
        
        def progress_wrapper(transferred: int, total: int):
            if progress_callback:
                progress_callback(transferred, total, "업로드 중...")
        
        def status_wrapper(message: str):
            if status_callback:
                status_callback(message)
        
        # 로컬 파일 존재 확인
        if not os.path.exists(local_path):
            status_wrapper(f"로컬 파일이 존재하지 않음: {local_path}")
            return False
        
        # 원격 디렉토리 생성
        remote_dir = os.path.dirname(remote_path)
        if remote_dir:
            self.adb_manager.create_directory(remote_dir)
        
        status_wrapper(f"업로드 시작: {os.path.basename(local_path)}")
        
        # 파일 전송 실행
        success = self.adb_manager.push_file(local_path, remote_path, progress_wrapper)
        
        if success:
            status_wrapper(f"업로드 완료: {remote_path}")
        else:
            status_wrapper(f"업로드 실패: {local_path}")
        
        return success
    
    def download_file_async(self, remote_path: str, local_path: str,
                           progress_callback: Optional[Callable[[int, int, str], None]] = None,
                           status_callback: Optional[Callable[[str], None]] = None,
                           completion_callback: Optional[Callable[[bool], None]] = None) -> str:
        """비동기 파일 다운로드"""
        
        def download_worker():
            success = self.download_file(remote_path, local_path, progress_callback, status_callback)
            if completion_callback:
                completion_callback(success)
            # 전송 완료 후 스레드 ID 제거
            thread_id = threading.current_thread().ident
            if thread_id in self.transfer_threads:
                del self.transfer_threads[thread_id]
        
        thread = threading.Thread(target=download_worker, daemon=True)
        thread.start()
        
        self.transfer_threads[thread.ident] = {
            'type': 'download',
            'remote_path': remote_path,
            'local_path': local_path,
            'thread': thread
        }
        
        return str(thread.ident)
    
    def upload_file_async(self, local_path: str, remote_path: str,
                         progress_callback: Optional[Callable[[int, int, str], None]] = None,
                         status_callback: Optional[Callable[[str], None]] = None,
                         completion_callback: Optional[Callable[[bool], None]] = None) -> str:
        """비동기 파일 업로드"""
        
        def upload_worker():
            success = self.upload_file(local_path, remote_path, progress_callback, status_callback)
            if completion_callback:
                completion_callback(success)
            # 전송 완료 후 스레드 ID 제거
            thread_id = threading.current_thread().ident
            if thread_id in self.transfer_threads:
                del self.transfer_threads[thread_id]
        
        thread = threading.Thread(target=upload_worker, daemon=True)
        thread.start()
        
        self.transfer_threads[thread.ident] = {
            'type': 'upload',
            'remote_path': remote_path,
            'local_path': local_path,
            'thread': thread
        }
        
        return str(thread.ident)
    
    def cancel_transfer(self, thread_id: str) -> bool:
        """파일 전송 취소"""
        try:
            thread_id_int = int(thread_id)
            if thread_id_int in self.transfer_threads:
                # 스레드는 강제 종료할 수 없으므로 상태만 업데이트
                self.transfer_status[thread_id] = 'cancelled'
                return True
        except ValueError:
            pass
        return False
    
    def get_transfer_status(self, thread_id: str) -> Dict[str, Any]:
        """파일 전송 상태 조회"""
        try:
            thread_id_int = int(thread_id)
            if thread_id_int in self.transfer_threads:
                thread_info = self.transfer_threads[thread_id_int]
                return {
                    'type': thread_info['type'],
                    'remote_path': thread_info['remote_path'],
                    'local_path': thread_info['local_path'],
                    'is_alive': thread_info['thread'].is_alive(),
                    'status': self.transfer_status.get(thread_id, 'running')
                }
        except ValueError:
            pass
        return {}
    
    def get_active_transfers(self) -> List[Dict[str, Any]]:
        """활성 전송 목록 조회"""
        active_transfers = []
        for thread_id, info in self.transfer_threads.items():
            if info['thread'].is_alive():
                active_transfers.append({
                    'thread_id': str(thread_id),
                    'type': info['type'],
                    'remote_path': info['remote_path'],
                    'local_path': info['local_path']
                })
        return active_transfers
    
    def format_file_size(self, size_bytes: int) -> str:
        """파일 크기를 읽기 쉬운 형태로 변환"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """파일 정보 조회"""
        if os.path.exists(file_path):
            stat = os.stat(file_path)
            return {
                'exists': True,
                'size': stat.st_size,
                'size_formatted': self.format_file_size(stat.st_size),
                'modified': stat.st_mtime,
                'is_directory': os.path.isdir(file_path)
            }
        return {'exists': False}

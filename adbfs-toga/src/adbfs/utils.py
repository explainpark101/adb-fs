"""
유틸리티 함수들
공통적으로 사용되는 헬퍼 함수들
"""

import os
import re
from typing import List, Optional, Dict, Any


def sanitize_filename(filename: str) -> str:
    """파일명에서 특수문자를 제거하여 안전한 파일명으로 변환"""
    # Windows에서 사용할 수 없는 문자들 제거
    invalid_chars = r'[<>:"/\\|?*]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # 연속된 언더스코어를 하나로 변환
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # 앞뒤 공백 및 언더스코어 제거
    sanitized = sanitized.strip('_ ')
    
    # 빈 문자열인 경우 기본값 반환
    if not sanitized:
        return "unnamed_file"
    
    return sanitized


def get_safe_path(path: str) -> str:
    """경로를 안전하게 정규화"""
    # 경로 정규화
    normalized = os.path.normpath(path)
    
    # 상위 디렉토리 접근 방지
    if '..' in normalized:
        normalized = normalized.replace('..', '')
    
    return normalized


def create_directory_if_not_exists(path: str) -> bool:
    """디렉토리가 존재하지 않으면 생성"""
    try:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        print(f"디렉토리 생성 실패: {e}")
        return False


def get_file_extension(filename: str) -> str:
    """파일 확장자 추출"""
    _, ext = os.path.splitext(filename)
    return ext.lower()


def is_image_file(filename: str) -> bool:
    """이미지 파일인지 확인"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    return get_file_extension(filename) in image_extensions


def is_video_file(filename: str) -> bool:
    """비디오 파일인지 확인"""
    video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'}
    return get_file_extension(filename) in video_extensions


def is_audio_file(filename: str) -> bool:
    """오디오 파일인지 확인"""
    audio_extensions = {'.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'}
    return get_file_extension(filename) in audio_extensions


def get_file_type_icon(filename: str) -> str:
    """파일 타입에 따른 아이콘 반환"""
    if is_image_file(filename):
        return "🖼️"
    elif is_video_file(filename):
        return "🎥"
    elif is_audio_file(filename):
        return "🎵"
    elif get_file_extension(filename) in {'.txt', '.md', '.log'}:
        return "📄"
    elif get_file_extension(filename) in {'.zip', '.rar', '.7z', '.tar', '.gz'}:
        return "📦"
    elif get_file_extension(filename) in {'.pdf', '.doc', '.docx'}:
        return "📋"
    else:
        return "📁"


def format_timestamp(timestamp: float) -> str:
    """타임스탬프를 읽기 쉬운 날짜/시간 형태로 변환"""
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def parse_ls_output(line: str) -> Optional[Dict[str, Any]]:
    """ls -la 출력을 파싱하여 파일 정보 추출"""
    parts = line.split()
    if len(parts) < 9:
        return None
    
    try:
        permissions = parts[0]
        size = int(parts[4]) if parts[4].isdigit() else 0
        date = ' '.join(parts[5:8])
        name = ' '.join(parts[8:])
        
        is_directory = permissions.startswith('d')
        is_link = permissions.startswith('l')
        
        return {
            'name': name,
            'permissions': permissions,
            'size': size,
            'date': date,
            'is_directory': is_directory,
            'is_link': is_link
        }
    except (ValueError, IndexError):
        return None


def get_human_readable_size(size_bytes: int) -> str:
    """바이트 크기를 사람이 읽기 쉬운 형태로 변환"""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def validate_path(path: str) -> bool:
    """경로가 유효한지 확인"""
    try:
        # 경로 정규화
        normalized = os.path.normpath(path)
        
        # 빈 경로나 루트만 있는 경우는 유효하지 않음
        if not normalized or normalized == '.':
            return False
        
        # 상위 디렉토리 접근 시도 감지
        if '..' in normalized:
            return False
        
        return True
    except Exception:
        return False


def get_relative_path(base_path: str, full_path: str) -> str:
    """기준 경로에 대한 상대 경로 계산"""
    try:
        return os.path.relpath(full_path, base_path)
    except ValueError:
        return full_path


def is_hidden_file(filename: str) -> bool:
    """숨김 파일인지 확인"""
    return filename.startswith('.')


def get_file_category(filename: str) -> str:
    """파일 카테고리 반환"""
    ext = get_file_extension(filename)
    
    if is_image_file(filename):
        return "이미지"
    elif is_video_file(filename):
        return "비디오"
    elif is_audio_file(filename):
        return "오디오"
    elif ext in {'.txt', '.md', '.log', '.json', '.xml', '.csv'}:
        return "문서"
    elif ext in {'.zip', '.rar', '.7z', '.tar', '.gz'}:
        return "압축파일"
    elif ext in {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'}:
        return "오피스"
    elif ext in {'.apk', '.exe', '.dmg', '.deb', '.rpm'}:
        return "실행파일"
    else:
        return "기타"

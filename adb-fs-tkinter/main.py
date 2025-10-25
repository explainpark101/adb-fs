"""
ADB File System Manager
tkinter를 사용한 Android 디바이스 파일 관리 GUI 애플리케이션
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
import os
import threading
from typing import Optional, Dict, Any, List
from enum import Enum

from adb_manager import ADBManager
from file_manager import FileManager
from utils import sanitize_filename, get_human_readable_size, get_file_type_icon


class LogLevel(Enum):
    """로그 레벨 정의"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3


class MainApplication:
    """메인 GUI 애플리케이션 클래스"""
    
    def __init__(self, root):
        print("Initializing MainApplication...")
        self.root = root
        self.root.title("ADB File System Manager")
        self.root.geometry("1000x700")
        
        # ADB 및 파일 매니저 초기화
        print("Initializing ADBManager...")
        self.adb_manager = ADBManager()
        print("Initializing FileManager...")
        self.file_manager = FileManager(self.adb_manager)
        print("FileManager initialized")
        
        # 현재 상태
        self.current_device = None
        self.current_remote_path = "/"
        self.current_local_path = os.path.expanduser("~/Downloads")
        
        # 정렬 상태 관리
        self.local_sort_column = None
        self.local_sort_reverse = False
        self.remote_sort_column = None
        self.remote_sort_reverse = False
        
        # 로그 레벨 설정 (기본값: INFO)
        self.log_level = LogLevel.INFO
        
        # GUI 구성요소
        self.setup_ui()
        
        # 초기 디바이스 검색
        self.refresh_devices()
    
        # 초기 로컬 파일 목록 로드
        self.refresh_local_file_list()
    
    def setup_ui(self):
        """UI 구성요소 설정"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 상단 컨트롤 패널
        self.setup_control_panel(main_frame)
        
        # 중간 파일 탐색기 영역 (분할 뷰)
        self.setup_split_file_explorer(main_frame)
        
        # 하단 로그 영역
        self.setup_log_area(main_frame)
    
    def setup_control_panel(self, parent):
        """상단 컨트롤 패널 설정"""
        control_frame = ttk.LabelFrame(parent, text="디바이스 및 경로 설정", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 디바이스 선택
        device_frame = ttk.Frame(control_frame)
        device_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(device_frame, text="디바이스:").pack(side=tk.LEFT)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(device_frame, textvariable=self.device_var, 
                                       state="readonly", width=30)
        self.device_combo.pack(side=tk.LEFT, padx=(5, 10))
        self.device_combo.bind('<<ComboboxSelected>>', self.on_device_selected)
        
        ttk.Button(device_frame, text="새로고침", 
                  command=self.refresh_devices).pack(side=tk.LEFT)
        
        ttk.Button(device_frame, text="페어링",
                command=self.pair_device).pack(side=tk.LEFT, padx=(5, 0))
        
        # 경로 설정
        path_frame = ttk.Frame(control_frame)
        path_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(path_frame, text="로컬 경로:").pack(side=tk.LEFT)
        self.local_path_var = tk.StringVar(value=self.current_local_path)
        local_path_entry = ttk.Entry(path_frame, textvariable=self.local_path_var, width=40)
        local_path_entry.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(path_frame, text="찾아보기", 
                  command=self.browse_local_path).pack(side=tk.LEFT)
        
        # 원격 경로
        remote_path_frame = ttk.Frame(control_frame)
        remote_path_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(remote_path_frame, text="원격 경로:").pack(side=tk.LEFT)
        self.remote_path_var = tk.StringVar(value=self.current_remote_path)
        remote_path_entry = ttk.Entry(remote_path_frame, textvariable=self.remote_path_var, width=40)
        remote_path_entry.pack(side=tk.LEFT, padx=(5, 5))
        ttk.Button(remote_path_frame, text="이동", 
                  command=self.navigate_remote_path).pack(side=tk.LEFT)

    def pair_device(self):
        """ADB 페어링을 위한 다이얼로그 및 로직"""
        dialog = tk.Toplevel(self.root)
        dialog.title("ADB 페어링")
        dialog.geometry("400x200")

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # IP 주소 및 포트
        ip_frame = ttk.Frame(main_frame)
        ip_frame.pack(fill=tk.X, pady=5)
        ttk.Label(ip_frame, text="IP 주소:포트", width=15).pack(side=tk.LEFT)
        ip_entry = ttk.Entry(ip_frame, width=30)
        ip_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # 페어링 코드
        code_frame = ttk.Frame(main_frame)
        code_frame.pack(fill=tk.X, pady=5)
        ttk.Label(code_frame, text="페어링 코드", width=15).pack(side=tk.LEFT)
        code_entry = ttk.Entry(code_frame, width=30)
        code_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        def do_pair():
            ip_address = ip_entry.get()
            pairing_code = code_entry.get()

            if not ip_address or not pairing_code:
                messagebox.showerror("오류", "IP 주소와 페어링 코드를 모두 입력하세요.", parent=dialog)
                return

            self.log_message(f"페어링 시도: {ip_address}")

            def pair_worker():
                success, message = self.adb_manager.pair_device(ip_address, pairing_code)
                
                def update_ui():
                    if success:
                        self.log_message(f"✅ 페어링 성공: {ip_address}")
                        messagebox.showinfo("성공", f"페어링에 성공했습니다.\n{message}", parent=dialog)
                        self.refresh_devices()
                        dialog.destroy()
                    else:
                        self.log_message(f"❌ 페어링 실패: {message}")
                        messagebox.showerror("실패", f"페어링에 실패했습니다.\n{message}", parent=dialog)
            
            threading.Thread(target=pair_worker, daemon=True).start()

        # 버튼
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        ttk.Button(button_frame, text="페어링", command=do_pair).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="취소", command=dialog.destroy).pack(side=tk.RIGHT, padx=5)    
    def setup_split_file_explorer(self, parent):
        """분할 파일 탐색기 영역 설정"""
        explorer_frame = ttk.LabelFrame(parent, text="파일 탐색기", padding=10)
        explorer_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 로컬 뷰 토글 체크박스 (split view 밖에 위치)
        toggle_frame = ttk.Frame(explorer_frame)
        toggle_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.show_local_var = tk.BooleanVar(value=True)
        self.show_local_check = ttk.Checkbutton(toggle_frame, text="로컬 디렉토리 표시", 
                                               variable=self.show_local_var,
                                               command=self.toggle_local_view)
        self.show_local_check.pack(side=tk.LEFT)
        
        # 분할 패널 생성
        self.paned_window = ttk.PanedWindow(explorer_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)
        
        # 왼쪽 패널 (로컬 파일 시스템)
        self.setup_local_file_panel(self.paned_window)
        
        # 오른쪽 패널 (원격 파일 시스템)
        self.setup_remote_file_panel(self.paned_window)
        
        # 분할 비율 설정 (기본 50:50)
        self.paned_window.sashpos(0, 500)
    
    def setup_local_file_panel(self, parent):
        """로컬 파일 시스템 패널 설정"""
        # 로컬 패널 프레임
        self.local_frame = ttk.LabelFrame(parent, text="로컬 파일 시스템", padding=5)
        parent.add(self.local_frame, weight=1)
        
        # 로컬 파일 리스트
        self.local_list_frame = ttk.Frame(self.local_frame)
        self.local_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 로컬 트리뷰 생성
        columns = ('name', 'type', 'size', 'date')
        self.local_file_tree = ttk.Treeview(self.local_list_frame, columns=columns, show='headings', height=15)
        
        # 컬럼 설정 및 헤더 클릭 이벤트 바인딩
        self.local_file_tree.heading('name', text='이름', command=lambda: self.sort_local_tree('name'))
        self.local_file_tree.heading('type', text='타입', command=lambda: self.sort_local_tree('type'))
        self.local_file_tree.heading('size', text='크기', command=lambda: self.sort_local_tree('size'))
        self.local_file_tree.heading('date', text='날짜', command=lambda: self.sort_local_tree('date'))
        
        # 컬럼 너비 설정
        self.local_file_tree.column('name', width=200)
        self.local_file_tree.column('type', width=80)
        self.local_file_tree.column('size', width=80)
        self.local_file_tree.column('date', width=120)
        
        # 스크롤바
        local_scrollbar = ttk.Scrollbar(self.local_list_frame, orient=tk.VERTICAL, command=self.local_file_tree.yview)
        self.local_file_tree.configure(yscrollcommand=local_scrollbar.set)
        
        # 배치
        self.local_file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        local_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 이벤트 바인딩
        self.local_file_tree.bind('<Double-1>', self.on_local_file_double_click)
        self.local_file_tree.bind('<Return>', self.on_local_file_double_click)  # Enter 키
        self.local_file_tree.bind('<Button-3>', self.on_local_file_right_click)
        self.local_file_tree.bind('<KeyPress>', self.on_local_key_press)  # 키보드 이벤트
        self.local_file_tree.bind('<Key>', self.on_local_key_press)  # 키보드 이벤트 (추가)
        self.local_file_tree.bind('<F2>', lambda e: self.rename_selected_local_file())  # F2 키
        self.local_file_tree.bind('<Delete>', lambda e: self.delete_selected_local_file())  # Delete 키
        self.local_file_tree.bind('<Command-Delete>', lambda e: self.delete_selected_local_file())  # Cmd+Delete (macOS)
        self.local_file_tree.bind('<Command-BackSpace>', lambda e: self.delete_selected_local_file())  # Cmd+BackSpace (macOS)
        self.local_file_tree.focus_set()  # 포커스 설정
        
        # 로컬 컨트롤 버튼
        local_button_frame = ttk.Frame(self.local_frame)
        local_button_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(local_button_frame, text="새로고침", 
                  command=self.refresh_local_file_list).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(local_button_frame, text="새폴더", 
                  command=self.create_local_directory).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(local_button_frame, text="삭제", 
                  command=self.delete_selected_local_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(local_button_frame, text="이름변경", 
                  command=self.rename_selected_local_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(local_button_frame, text="업로드", 
                  command=self.upload_selected_local_file).pack(side=tk.LEFT)
    
    def setup_remote_file_panel(self, parent):
        """원격 파일 시스템 패널 설정"""
        # 원격 패널 프레임
        remote_frame = ttk.LabelFrame(parent, text="원격 파일 시스템", padding=5)
        parent.add(remote_frame, weight=1)
        
        # 원격 파일 리스트
        self.remote_list_frame = ttk.Frame(remote_frame)
        self.remote_list_frame.pack(fill=tk.BOTH, expand=True)
        
        # 원격 트리뷰 생성
        columns = ('name', 'type', 'size', 'date')
        self.remote_file_tree = ttk.Treeview(self.remote_list_frame, columns=columns, show='headings', height=15)
        
        # 컬럼 설정 및 헤더 클릭 이벤트 바인딩
        self.remote_file_tree.heading('name', text='이름', command=lambda: self.sort_remote_tree('name'))
        self.remote_file_tree.heading('type', text='타입', command=lambda: self.sort_remote_tree('type'))
        self.remote_file_tree.heading('size', text='크기', command=lambda: self.sort_remote_tree('size'))
        self.remote_file_tree.heading('date', text='날짜', command=lambda: self.sort_remote_tree('date'))
        
        # 컬럼 너비 설정
        self.remote_file_tree.column('name', width=200)
        self.remote_file_tree.column('type', width=80)
        self.remote_file_tree.column('size', width=80)
        self.remote_file_tree.column('date', width=120)
        
        # 스크롤바
        remote_scrollbar = ttk.Scrollbar(self.remote_list_frame, orient=tk.VERTICAL, command=self.remote_file_tree.yview)
        self.remote_file_tree.configure(yscrollcommand=remote_scrollbar.set)
        
        # 배치
        self.remote_file_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        remote_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 이벤트 바인딩
        self.remote_file_tree.bind('<Double-1>', self.on_remote_file_double_click)
        self.remote_file_tree.bind('<Return>', self.on_remote_file_double_click)  # Enter 키
        self.remote_file_tree.bind('<Button-3>', self.on_remote_file_right_click)
        self.remote_file_tree.bind('<KeyPress>', self.on_remote_key_press)  # 키보드 이벤트
        self.remote_file_tree.bind('<Key>', self.on_remote_key_press)  # 키보드 이벤트 (추가)
        self.remote_file_tree.bind('<F2>', lambda e: self.rename_selected_remote_file())  # F2 키
        self.remote_file_tree.bind('<Delete>', lambda e: self.delete_selected_remote_file())  # Delete 키
        self.remote_file_tree.bind('<Command-Delete>', lambda e: self.delete_selected_remote_file())  # Cmd+Delete (macOS)
        self.remote_file_tree.bind('<Command-BackSpace>', lambda e: self.delete_selected_remote_file())  # Cmd+BackSpace (macOS)
        self.remote_file_tree.focus_set()  # 포커스 설정
        
        # 원격 컨트롤 버튼
        remote_button_frame = ttk.Frame(remote_frame)
        remote_button_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Button(remote_button_frame, text="새로고침", 
                  command=self.refresh_remote_file_list).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(remote_button_frame, text="새폴더", 
                  command=self.create_remote_directory).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(remote_button_frame, text="삭제", 
                  command=self.delete_selected_remote_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(remote_button_frame, text="이름변경", 
                  command=self.rename_selected_remote_file).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(remote_button_frame, text="다운로드", 
                  command=self.download_selected_remote_file).pack(side=tk.LEFT)
    
    def setup_log_area(self, parent):
        """하단 로그 영역 설정"""
        log_frame = ttk.LabelFrame(parent, text="로그", padding=5)
        log_frame.pack(fill=tk.X)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 진행률 표시
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(log_frame, variable=self.progress_var, 
                                           maximum=100, length=300)
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
    
    def log_message(self, message: str, level: LogLevel = LogLevel.INFO):
        """로그 메시지 출력"""
        # 로그 레벨 필터링
        if level.value < self.log_level.value:
            return
        
        # 레벨에 따른 접두사 추가
        level_prefix = {
            LogLevel.DEBUG: "[DEBUG]",
            LogLevel.INFO: "[INFO]",
            LogLevel.WARNING: "[WARNING]",
            LogLevel.ERROR: "[ERROR]"
        }
        
        prefix = level_prefix.get(level, "[INFO]")
        formatted_message = f"{prefix} {message}"
        
        self.log_text.insert(tk.END, f"{formatted_message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def set_log_level(self, level: LogLevel):
        """로그 레벨 설정"""
        self.log_level = level
        self.log_message(f"로그 레벨이 {level.name}로 설정되었습니다", LogLevel.INFO)
    
    def refresh_devices(self):
        """디바이스 목록 새로고침"""
        self.log_message("디바이스 검색 중...")
        
        def refresh_worker():
            devices = self.adb_manager.get_connected_devices()
            
            def update_ui():
                self.device_combo['values'] = [f"{d['name']} ({d['id']})" for d in devices]
                if devices:
                    self.device_combo.current(0)
                    self.on_device_selected()
                    self.log_message(f"{len(devices)}개 디바이스 발견")
                else:
                    self.log_message("연결된 디바이스가 없습니다")
            
            self.root.after(0, update_ui)
        
        threading.Thread(target=refresh_worker, daemon=True).start()
    
    def on_device_selected(self, event=None):
        """디바이스 선택 이벤트"""
        selection = self.device_combo.get()
        if selection:
            # 디바이스 ID 추출
            device_id = selection.split('(')[-1].rstrip(')')
            self.current_device = device_id
            self.adb_manager.set_current_device(device_id)
            self.log_message(f"📱 디바이스 선택: {selection}")
            self.log_message(f"🔗 디바이스 ID: {device_id}")
            
            # 디바이스 연결 상태 확인
            if self.adb_manager.set_current_device(device_id):
                self.log_message("✅ 디바이스 연결 성공")
                self.refresh_remote_file_list()
            else:
                self.log_message("❌ 디바이스 연결 실패")
        else:
            self.log_message("⚠️ 디바이스를 선택해주세요")
    
    def browse_local_path(self):
        """로컬 경로 선택"""
        path = filedialog.askdirectory(initialdir=self.current_local_path)
        if path:
            self.current_local_path = path
            self.local_path_var.set(path)
            self.log_message(f"로컬 경로 설정: {path}")
    
    def navigate_remote_path(self):
        """원격 경로 이동"""
        new_path = self.remote_path_var.get()
        if new_path and new_path != self.current_remote_path:
            self.current_remote_path = new_path
            self.refresh_remote_file_list()
            self.log_message(f"원격 경로 이동: {new_path}")
    
    def refresh_remote_file_list(self):
        """원격 파일 목록 새로고침"""
        if not self.current_device:
            self.log_message("❌ 디바이스가 선택되지 않았습니다")
            return
        
        self.log_message(f"🔄 원격 파일 목록 로딩 시작: {self.current_remote_path}")
        self.log_message(f"📱 현재 디바이스: {self.current_device}")
        
        def load_files_worker():
            try:
                self.log_message("🔍 ADB 명령어 실행 중...")
                files = self.adb_manager.get_file_list(self.current_remote_path)
                self.log_message(f"📋 ADB 응답: {len(files)}개 파일 발견")
                
                def update_ui():
                    try:
                        # 기존 항목 삭제
                        for item in self.remote_file_tree.get_children():
                            self.remote_file_tree.delete(item)
                        
                        # 상위 폴더 항목 추가 (루트가 아닌 경우에만)
                        if self.current_remote_path != "/":
                            self.remote_file_tree.insert('', 0, values=("⬆️ ..", "상위폴더", "-", ""))
                        
                        if not files:
                            self.log_message("⚠️ 파일 목록이 비어있습니다")
                            return
                        
                        # 새 항목 추가
                        for file_info in files:
                            try:
                                name = file_info['name']
                                
                                # 파일 타입 결정
                                if file_info.get('is_directory', False):
                                    file_type = "폴더"
                                    icon = "📁"
                                elif file_info.get('is_link', False):
                                    file_type = "링크"
                                    icon = "🔗"
                                else:
                                    file_type = "파일"
                                    icon = get_file_type_icon(name)
                                
                                # 크기 처리
                                try:
                                    if file_info['size'].isdigit():
                                        size = get_human_readable_size(int(file_info['size']))
                                    else:
                                        size = file_info['size']
                                except (ValueError, TypeError):
                                    size = file_info['size']
                                
                                date = file_info['date']
                                
                                # 표시 이름 생성
                                display_name = f"{icon} {name}"
                                
                                self.remote_file_tree.insert('', tk.END, values=(display_name, file_type, size, date))
                                
                            except Exception as e:
                                self.log_message(f"⚠️ 파일 정보 처리 오류: {str(e)}")
                                continue
                        
                        self.log_message(f"✅ {len(files)}개 원격 항목 로딩 완료")
                        
                    except Exception as e:
                        self.log_message(f"❌ UI 업데이트 오류: {str(e)}")
                
                self.root.after(0, update_ui)
                
            except Exception as e:
                self.log_message(f"❌ 파일 목록 로딩 실패: {str(e)}")
                def error_ui():
                    self.log_message("💡 해결 방법:")
                    self.log_message("   1. 디바이스가 USB로 연결되어 있는지 확인")
                    self.log_message("   2. USB 디버깅이 활성화되어 있는지 확인")
                    self.log_message("   3. ADB가 설치되어 있는지 확인")
                self.root.after(0, error_ui)
        
        threading.Thread(target=load_files_worker, daemon=True).start()
    
    def on_remote_file_double_click(self, event):
        """원격 파일 더블클릭 이벤트"""
        selection = self.remote_file_tree.selection()
        if not selection:
            return
            
        try:
            item = self.remote_file_tree.item(selection[0])
            values = item['values']
            if not values or len(values) < 2:
                return
                
            # 아이콘과 파일명 분리 (더 안전한 방법)
            display_name = values[0]
            if ' ' in display_name:
                # 아이콘과 파일명이 공백으로 구분된 경우
                name = display_name.split(' ', 1)[1]
            else:
                # 아이콘이 없는 경우
                name = display_name
                
            file_type = values[1]
            
            # 상위 폴더 항목 처리
            if name == ".." and file_type == "상위폴더":
                self.go_up_remote_directory()
                return
            
            # 폴더인 경우 이동
            if file_type == "폴더":
                # 경로 생성 (더 안전한 방법)
                if self.current_remote_path.endswith('/'):
                    new_path = f"{self.current_remote_path}{name}"
                else:
                    new_path = f"{self.current_remote_path}/{name}"
                
                # 경로 정규화
                new_path = new_path.replace('\\', '/')
                
                # 현재 경로와 다른 경우에만 이동
                if new_path != self.current_remote_path:
                    self.current_remote_path = new_path
                    self.remote_path_var.set(new_path)
                    self.log_message(f"폴더 이동: {new_path}")
                    self.refresh_remote_file_list()
                else:
                    self.log_message("이미 해당 폴더에 있습니다")
            elif file_type == "링크":
                # 링크인 경우 타겟으로 이동
                link_path = os.path.join(self.current_remote_path, name).replace('\\', '/')
                target = self.adb_manager.get_link_target(link_path)
                
                if target:
                    # 절대 경로인지 상대 경로인지 확인
                    if target.startswith('/'):
                        # 절대 경로
                        new_path = target
                    else:
                        # 상대 경로 - 현재 경로 기준으로 해석
                        if self.current_remote_path.endswith('/'):
                            new_path = f"{self.current_remote_path}{target}"
                        else:
                            new_path = f"{self.current_remote_path}/{target}"
                    
                    # 경로 정규화
                    new_path = new_path.replace('\\', '/')
                    
                    # 타겟이 디렉토리인지 확인
                    if self.adb_manager.is_directory(new_path):
                        self.current_remote_path = new_path
                        self.remote_path_var.set(new_path)
                        self.log_message(f"🔗 링크 타겟 이동: {new_path}")
                        self.refresh_remote_file_list()
                    else:
                        # 타겟이 파일인 경우 다운로드 후 열기
                        self.log_message(f"🔗 링크 타겟 파일: {new_path}")
                        self.download_and_open_file_from_path(new_path)
                else:
                    self.log_message(f"❌ 링크 타겟을 읽을 수 없습니다: {name}")
            else:
                # 파일인 경우 다운로드 후 열기
                self.download_and_open_file(name)
                
        except Exception as e:
            self.log_message(f"폴더 이동 중 오류 발생: {str(e)}")
    
    def on_remote_file_right_click(self, event):
        """원격 파일 우클릭 이벤트 (컨텍스트 메뉴)"""
        # TODO: 컨텍스트 메뉴 구현
        pass
    
    def on_remote_key_press(self, event):
        """원격 파일 키보드 이벤트"""
        import platform
        
        # 디버깅을 위한 로그
        self.log_message(f"🔍 원격 키 이벤트: {event.keysym}, state: {event.state}", LogLevel.DEBUG)
        
        # 엔터 키 - 원격 스토리지에 포커스 이동
        if event.keysym == 'Return':
            self.log_message("🎯 엔터 키 감지 - 원격 스토리지 포커스", LogLevel.DEBUG)
            self.remote_file_tree.focus_set()
            return
        
        # F2 키 - 이름변경
        if event.keysym == 'F2':
            self.log_message("📝 F2 키 감지 - 원격 이름변경", LogLevel.DEBUG)
            self.rename_selected_remote_file()
            return
        
        # 삭제 키 조합
        if platform.system() == 'Darwin':  # macOS
            # Cmd + Delete 또는 Cmd + BackSpace
            if (event.state & 0x4) and (event.keysym in ['Delete', 'BackSpace']):
                self.log_message("🗑️ Cmd+Delete 키 감지 - 원격 삭제", LogLevel.DEBUG)
                self.delete_selected_remote_file()
                return
        else:  # Windows/Linux
            # Delete 키만
            if event.keysym == 'Delete':
                self.log_message("🗑️ Delete 키 감지 - 원격 삭제", LogLevel.DEBUG)
                self.delete_selected_remote_file()
                return
    
    def on_local_file_double_click(self, event):
        """로컬 파일 더블클릭 이벤트"""
        selection = self.local_file_tree.selection()
        if not selection:
            return
            
        try:
            item = self.local_file_tree.item(selection[0])
            values = item['values']
            if not values or len(values) < 2:
                return
                
            # 아이콘과 파일명 분리
            display_name = values[0]
            if ' ' in display_name:
                name = display_name.split(' ', 1)[1]
            else:
                name = display_name
                
            file_type = values[1]
            
            # 상위 폴더 항목 처리
            if name == ".." and file_type == "상위폴더":
                self.go_up_local_directory()
                return
                
                # 폴더인 경우 이동
            if file_type == "폴더":
                new_path = os.path.join(self.current_local_path, name)
                if os.path.isdir(new_path):
                    self.current_local_path = new_path
                    self.local_path_var.set(new_path)
                    self.log_message(f"로컬 폴더 이동: {new_path}")
                    self.refresh_local_file_list()
                else:
                    self.log_message("폴더가 존재하지 않습니다")
            else:
                # 파일인 경우 열기
                self.open_local_file(name)
                
        except Exception as e:
            self.log_message(f"로컬 폴더 이동 중 오류 발생: {str(e)}")
    
    def on_local_file_right_click(self, event):
        """로컬 파일 우클릭 이벤트 (컨텍스트 메뉴)"""
        # TODO: 컨텍스트 메뉴 구현
        pass
    
    def on_local_key_press(self, event):
        """로컬 파일 키보드 이벤트"""
        import platform
        
        # 디버깅을 위한 로그
        self.log_message(f"🔍 키 이벤트: {event.keysym}, state: {event.state}", LogLevel.DEBUG)
        
        # 엔터 키 - 로컬 스토리지에 포커스 이동
        if event.keysym == 'Return':
            self.log_message("🎯 엔터 키 감지 - 로컬 스토리지 포커스", LogLevel.DEBUG)
            self.local_file_tree.focus_set()
            return
        
        # F2 키 - 이름변경
        if event.keysym == 'F2':
            self.log_message("📝 F2 키 감지 - 이름변경", LogLevel.DEBUG)
            self.rename_selected_local_file()
            return
        
        # 삭제 키 조합
        if platform.system() == 'Darwin':  # macOS
            # Cmd + Delete 또는 Cmd + BackSpace
            if (event.state & 0x4) and (event.keysym in ['Delete', 'BackSpace']):
                self.log_message("🗑️ Cmd+Delete 키 감지 - 삭제", LogLevel.DEBUG)
                self.delete_selected_local_file()
                return
        else:  # Windows/Linux
            # Delete 키만
            if event.keysym == 'Delete':
                self.log_message("🗑️ Delete 키 감지 - 삭제", LogLevel.DEBUG)
                self.delete_selected_local_file()
                return
    
    def refresh_local_file_list(self):
        """로컬 파일 목록 새로고침"""
        self.log_message(f"로컬 파일 목록 로딩: {self.current_local_path}")
        
        try:
            # 기존 항목 삭제
            for item in self.local_file_tree.get_children():
                self.local_file_tree.delete(item)
            
            # 새 항목 추가
            if os.path.exists(self.current_local_path):
                # 상위 폴더 항목 추가 (루트가 아닌 경우에만)
                parent_path = os.path.dirname(self.current_local_path)
                if parent_path and parent_path != self.current_local_path:
                    self.local_file_tree.insert('', 0, values=("⬆️ ..", "상위폴더", "-", ""))
                
                items = os.listdir(self.current_local_path)
                items.sort()  # 정렬
                
                for item_name in items:
                    item_path = os.path.join(self.current_local_path, item_name)
                    
                    # 파일 정보 가져오기
                    try:
                        stat = os.stat(item_path)
                        is_directory = os.path.isdir(item_path)
                        
                        if is_directory:
                            file_type = "폴더"
                            icon = "📁"
                            size = "-"
                        else:
                            file_type = "파일"
                            icon = get_file_type_icon(item_name)
                            size = get_human_readable_size(stat.st_size)
                        
                        # 날짜 포맷
                        import datetime
                        date = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                        
                        # 표시 이름 생성
                        display_name = f"{icon} {item_name}"
                        
                        self.local_file_tree.insert('', tk.END, values=(display_name, file_type, size, date))
                        
                    except (OSError, IOError) as e:
                        # 접근할 수 없는 파일/폴더는 건너뛰기
                        continue
                
                self.log_message(f"{len(items)}개 로컬 항목 로딩 완료")
            else:
                self.log_message("로컬 경로가 존재하지 않습니다")
                
        except Exception as e:
            self.log_message(f"로컬 파일 목록 로딩 실패: {str(e)}")
    
    def go_up_remote_directory(self):
        """원격 상위 디렉토리로 이동"""
        if self.current_remote_path != "/":
            parent_path = os.path.dirname(self.current_remote_path)
            if not parent_path:
                parent_path = "/"
            self.current_remote_path = parent_path
            self.remote_path_var.set(parent_path)
            self.refresh_remote_file_list()
            self.log_message(f"원격 상위 폴더로 이동: {parent_path}")
    
    def go_up_local_directory(self):
        """로컬 상위 디렉토리로 이동"""
        parent_path = os.path.dirname(self.current_local_path)
        if parent_path and parent_path != self.current_local_path:
            self.current_local_path = parent_path
            self.local_path_var.set(parent_path)
            self.refresh_local_file_list()
            self.log_message(f"로컬 상위 폴더로 이동: {parent_path}")
    
    def toggle_local_view(self):
        """로컬 뷰 토글"""
        if self.show_local_var.get():
            # 로컬 패널을 표시하고 50:50 비율로 설정
            self.paned_window.sashpos(0, 500)
            self.refresh_local_file_list()
        else:
            # 로컬 패널을 숨기고 원격 패널만 크게 표시
            # sashpos를 0으로 설정하여 로컬 패널을 완전히 숨김
            self.paned_window.sashpos(0, 0)
    
    def sort_local_tree(self, column):
        """로컬 트리뷰 정렬"""
        # 같은 컬럼을 클릭하면 정렬 순서 반전, 다른 컬럼이면 오름차순으로 시작
        if self.local_sort_column == column:
            self.local_sort_reverse = not self.local_sort_reverse
        else:
            self.local_sort_column = column
            self.local_sort_reverse = False
        
        # 트리뷰 데이터 가져오기
        items = []
        parent_items = []  # ".." 항목들
        other_items = []  # 일반 파일/폴더들
        
        for item in self.local_file_tree.get_children():
            values = self.local_file_tree.item(item)['values']
            if values[0].startswith('⬆️ ..') or values[0] == '..':
                parent_items.append((item, values))
            else:
                other_items.append((item, values))
        
        # 정렬 함수
        def sort_key(item_data):
            item, values = item_data
            if column == 'name':
                # 이름은 문자열로 정렬 (대소문자 구분 없음)
                return values[0].lower()
            elif column == 'type':
                return values[1]
            elif column == 'size':
                # 크기는 숫자로 정렬 (KB, MB 등 단위 고려)
                size_str = values[2]
                if size_str == '-':
                    return 0
                try:
                    # 숫자 부분만 추출
                    if 'KB' in size_str:
                        return float(size_str.replace('KB', '')) * 1024
                    elif 'MB' in size_str:
                        return float(size_str.replace('MB', '')) * 1024 * 1024
                    elif 'GB' in size_str:
                        return float(size_str.replace('GB', '')) * 1024 * 1024 * 1024
                    else:
                        return float(size_str)
                except:
                    return 0
            elif column == 'date':
                return values[3]
            return values[0]
        
        # 일반 항목들만 정렬
        other_items.sort(key=sort_key, reverse=self.local_sort_reverse)
        
        # 최종 리스트: ".." 항목들 + 정렬된 일반 항목들
        items = parent_items + other_items
        
        # 트리뷰 업데이트
        for item in self.local_file_tree.get_children():
            self.local_file_tree.delete(item)
        
        for item, values in items:
            self.local_file_tree.insert('', 'end', values=values)
    
    def sort_remote_tree(self, column):
        """원격 트리뷰 정렬"""
        # 같은 컬럼을 클릭하면 정렬 순서 반전, 다른 컬럼이면 오름차순으로 시작
        if self.remote_sort_column == column:
            self.remote_sort_reverse = not self.remote_sort_reverse
        else:
            self.remote_sort_column = column
            self.remote_sort_reverse = False
        
        # 트리뷰 데이터 가져오기
        items = []
        parent_items = []  # ".." 항목들
        other_items = []  # 일반 파일/폴더들
        
        for item in self.remote_file_tree.get_children():
            values = self.remote_file_tree.item(item)['values']
            if values[0].startswith('⬆️ ..') or values[0] == '..':
                parent_items.append((item, values))
            else:
                other_items.append((item, values))
        
        # 정렬 함수
        def sort_key(item_data):
            item, values = item_data
            if column == 'name':
                # 이름은 문자열로 정렬 (대소문자 구분 없음)
                return values[0].lower()
            elif column == 'type':
                return values[1]
            elif column == 'size':
                # 크기는 숫자로 정렬 (KB, MB 등 단위 고려)
                size_str = values[2]
                if size_str == '-':
                    return 0
                try:
                    # 숫자 부분만 추출
                    if 'KB' in size_str:
                        return float(size_str.replace('KB', '')) * 1024
                    elif 'MB' in size_str:
                        return float(size_str.replace('MB', '')) * 1024 * 1024
                    elif 'GB' in size_str:
                        return float(size_str.replace('GB', '')) * 1024 * 1024 * 1024
                    else:
                        return float(size_str)
                except:
                    return 0
            elif column == 'date':
                return values[3]
            return values[0]
        
        # 일반 항목들만 정렬
        other_items.sort(key=sort_key, reverse=self.remote_sort_reverse)
        
        # 최종 리스트: ".." 항목들 + 정렬된 일반 항목들
        items = parent_items + other_items
        
        # 트리뷰 업데이트
        for item in self.remote_file_tree.get_children():
            self.remote_file_tree.delete(item)
        
        for item, values in items:
            self.remote_file_tree.insert('', 'end', values=values)
    
    def download_selected_remote_file(self):
        """선택된 원격 파일 다운로드"""
        selection = self.remote_file_tree.selection()
        if not selection:
            messagebox.showwarning("경고", "다운로드할 파일을 선택하세요")
            return
        
        item = self.remote_file_tree.item(selection[0])
        values = item['values']
        if values and values[1] not in ["폴더", "링크"]:  # 폴더나 링크가 아닌 경우만
            name = values[0].split(' ', 1)[1]  # 아이콘 제거
            remote_path = os.path.join(self.current_remote_path, name).replace('\\', '/')
            local_path = os.path.join(self.current_local_path, sanitize_filename(name))
            
            self.log_message(f"다운로드 시작: {name}")
            
            def progress_callback(transferred, total, status):
                if total > 0:
                    progress = (transferred / total) * 100
                    self.progress_var.set(progress)
                    self.log_message(f"{status}: {progress:.1f}%")
            
            def status_callback(message):
                self.log_message(message)
            
            def completion_callback(success):
                if success:
                    self.progress_var.set(100)
                    self.log_message("다운로드 완료!")
                    self.refresh_local_file_list()  # 로컬 파일 목록 새로고침
                else:
                    self.log_message("다운로드 실패!")
                self.progress_var.set(0)
            
            self.file_manager.download_file_async(
                remote_path, local_path, 
                progress_callback, status_callback, completion_callback
            )
        else:
            messagebox.showwarning("경고", "폴더나 링크는 다운로드할 수 없습니다")
    
    def upload_file(self):
        """파일 업로드"""
        file_path = filedialog.askopenfilename(initialdir=self.current_local_path)
        if file_path:
            filename = os.path.basename(file_path)
            remote_path = os.path.join(self.current_remote_path, filename).replace('\\', '/')
            
            self.log_message(f"업로드 시작: {filename}")
            
            def progress_callback(transferred, total, status):
                if total > 0:
                    progress = (transferred / total) * 100
                    self.progress_var.set(progress)
                    self.log_message(f"{status}: {progress:.1f}%")
            
            def status_callback(message):
                self.log_message(message)
            
            def completion_callback(success):
                if success:
                    self.progress_var.set(100)
                    self.log_message("업로드 완료!")
                    self.refresh_remote_file_list()  # 파일 목록 새로고침
                else:
                    self.log_message("업로드 실패!")
                self.progress_var.set(0)
            
            self.file_manager.upload_file_async(
                file_path, remote_path,
                progress_callback, status_callback, completion_callback
            )
    
    def upload_selected_local_file(self):
        """선택된 로컬 파일 업로드"""
        selection = self.local_file_tree.selection()
        if not selection:
            messagebox.showwarning("경고", "업로드할 파일을 선택하세요")
            return
        
        item = self.local_file_tree.item(selection[0])
        values = item['values']
        if values and values[1] == "파일":  # 파일인 경우만
            name = values[0].split(' ', 1)[1]  # 아이콘 제거
            local_path = os.path.join(self.current_local_path, name)
            remote_path = os.path.join(self.current_remote_path, name).replace('\\', '/')
            
            self.log_message(f"업로드 시작: {name}")
            
            def progress_callback(transferred, total, status):
                if total > 0:
                    progress = (transferred / total) * 100
                    self.progress_var.set(progress)
                    self.log_message(f"{status}: {progress:.1f}%")
            
            def status_callback(message):
                self.log_message(message)
            
            def completion_callback(success):
                if success:
                    self.progress_var.set(100)
                    self.log_message("업로드 완료!")
                    self.refresh_remote_file_list()  # 원격 파일 목록 새로고침
                else:
                    self.log_message("업로드 실패!")
                self.progress_var.set(0)
            
            self.file_manager.upload_file_async(
                local_path, remote_path,
                progress_callback, status_callback, completion_callback
            )
        else:
            messagebox.showwarning("경고", "폴더는 업로드할 수 없습니다")
    
    def download_and_open_file(self, filename):
        """원격 파일 다운로드 후 열기"""
        remote_path = os.path.join(self.current_remote_path, filename).replace('\\', '/')
        local_path = os.path.join(self.current_local_path, sanitize_filename(filename))
        
        self.log_message(f"📥 파일 다운로드 시작: {filename}")
        
        def progress_callback(transferred, total, status):
            if total > 0:
                progress = (transferred / total) * 100
                self.progress_var.set(progress)
                self.log_message(f"{status}: {progress:.1f}%")
        
        def status_callback(message):
            self.log_message(message)
        
        def completion_callback(success):
            if success:
                self.progress_var.set(100)
                self.log_message("✅ 다운로드 완료!")
                self.refresh_local_file_list()  # 로컬 파일 목록 새로고침
                
                # 파일 열기
                try:
                    import subprocess
                    import platform
                    
                    if platform.system() == 'Darwin':  # macOS
                        subprocess.run(['open', local_path])
                    elif platform.system() == 'Windows':
                        os.startfile(local_path)
                    else:  # Linux
                        subprocess.run(['xdg-open', local_path])
                    
                    self.log_message(f"📂 파일 열기: {local_path}")
                except Exception as e:
                    self.log_message(f"⚠️ 파일 열기 실패: {str(e)}")
            else:
                self.log_message("❌ 다운로드 실패!")
            self.progress_var.set(0)
        
        self.file_manager.download_file_async(
            remote_path, local_path,
            progress_callback, status_callback, completion_callback
        )
    
    def download_and_open_file_from_path(self, remote_path):
        """원격 경로에서 파일 다운로드 후 열기"""
        filename = os.path.basename(remote_path)
        local_path = os.path.join(self.current_local_path, sanitize_filename(filename))
        
        self.log_message(f"📥 링크 타겟 파일 다운로드 시작: {filename}")
        
        def progress_callback(transferred, total, status):
            if total > 0:
                progress = (transferred / total) * 100
                self.progress_var.set(progress)
                self.log_message(f"{status}: {progress:.1f}%")
        
        def status_callback(message):
            self.log_message(message)
        
        def completion_callback(success):
            if success:
                self.progress_var.set(100)
                self.log_message("✅ 링크 타겟 다운로드 완료!")
                self.refresh_local_file_list()  # 로컬 파일 목록 새로고침
                
                # 파일 열기
                try:
                    import subprocess
                    import platform
                    
                    if platform.system() == 'Darwin':  # macOS
                        subprocess.run(['open', local_path])
                    elif platform.system() == 'Windows':
                        os.startfile(local_path)
                    else:  # Linux
                        subprocess.run(['xdg-open', local_path])
                    
                    self.log_message(f"📂 링크 타겟 파일 열기: {local_path}")
                except Exception as e:
                    self.log_message(f"⚠️ 파일 열기 실패: {str(e)}")
            else:
                self.log_message("❌ 링크 타겟 다운로드 실패!")
            self.progress_var.set(0)
        
        self.file_manager.download_file_async(
            remote_path, local_path,
            progress_callback, status_callback, completion_callback
        )
    
    def create_local_directory(self):
        """로컬 폴더 생성"""
        folder_name = simpledialog.askstring("새 폴더", "폴더 이름을 입력하세요:")
        if folder_name:
            folder_path = os.path.join(self.current_local_path, folder_name)
            try:
                os.makedirs(folder_path, exist_ok=True)
                self.log_message(f"📁 로컬 폴더 생성: {folder_path}")
                self.refresh_local_file_list()
            except Exception as e:
                self.log_message(f"❌ 폴더 생성 실패: {str(e)}")
                messagebox.showerror("오류", f"폴더 생성에 실패했습니다: {str(e)}")
    
    def delete_selected_local_file(self):
        """선택된 로컬 파일/폴더 삭제"""
        selection = self.local_file_tree.selection()
        if not selection:
            messagebox.showwarning("경고", "삭제할 파일/폴더를 선택하세요")
            return
        
        item = self.local_file_tree.item(selection[0])
        values = item['values']
        if values:
            name = values[0].split(' ', 1)[1]  # 아이콘 제거
            file_path = os.path.join(self.current_local_path, name)
            
            if messagebox.askyesno("확인", f"'{name}'을(를) 삭제하시겠습니까?"):
                try:
                    import shutil
                    if os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                        self.log_message(f"📁 폴더 삭제: {name}")
                    else:
                        os.remove(file_path)
                        self.log_message(f"📄 파일 삭제: {name}")
                    self.refresh_local_file_list()
                except Exception as e:
                    self.log_message(f"❌ 삭제 실패: {str(e)}")
                    messagebox.showerror("오류", f"삭제에 실패했습니다: {str(e)}")
    
    def rename_selected_local_file(self):
        """선택된 로컬 파일/폴더 이름변경"""
        selection = self.local_file_tree.selection()
        if not selection:
            messagebox.showwarning("경고", "이름을 변경할 파일/폴더를 선택하세요")
            return
        
        item = self.local_file_tree.item(selection[0])
        values = item['values']
        if values:
            old_name = values[0].split(' ', 1)[1]  # 아이콘 제거
            old_path = os.path.join(self.current_local_path, old_name)
            
            new_name = simpledialog.askstring("이름변경", f"새 이름을 입력하세요:", initialvalue=old_name)
            if new_name and new_name != old_name:
                new_path = os.path.join(self.current_local_path, new_name)
                try:
                    os.rename(old_path, new_path)
                    self.log_message(f"📝 이름변경: {old_name} → {new_name}")
                    self.refresh_local_file_list()
                except Exception as e:
                    self.log_message(f"❌ 이름변경 실패: {str(e)}")
                    messagebox.showerror("오류", f"이름변경에 실패했습니다: {str(e)}")
    
    def open_local_file(self, filename):
        """로컬 파일 열기"""
        file_path = os.path.join(self.current_local_path, filename)
        
        if os.path.exists(file_path):
            try:
                import subprocess
                import platform
                
                if platform.system() == 'Darwin':  # macOS
                    subprocess.run(['open', file_path])
                elif platform.system() == 'Windows':
                    os.startfile(file_path)
                else:  # Linux
                    subprocess.run(['xdg-open', file_path])
                
                self.log_message(f"📂 파일 열기: {file_path}")
            except Exception as e:
                self.log_message(f"⚠️ 파일 열기 실패: {str(e)}")
        else:
            self.log_message(f"❌ 파일이 존재하지 않습니다: {file_path}")
    
    def create_remote_directory(self):
        """원격 폴더 생성"""
        folder_name = simpledialog.askstring("새 폴더", "폴더 이름을 입력하세요:")
        if folder_name:
            folder_path = os.path.join(self.current_remote_path, folder_name).replace('\\', '/')
            if self.adb_manager.create_directory(folder_path):
                self.log_message(f"📁 원격 폴더 생성: {folder_path}")
                self.refresh_remote_file_list()
            else:
                self.log_message(f"❌ 폴더 생성 실패: {folder_path}")
                messagebox.showerror("오류", "폴더 생성에 실패했습니다")
    
    def delete_selected_remote_file(self):
        """선택된 원격 파일/폴더 삭제"""
        selection = self.remote_file_tree.selection()
        if not selection:
            messagebox.showwarning("경고", "삭제할 파일/폴더를 선택하세요")
            return
        
        item = self.remote_file_tree.item(selection[0])
        values = item['values']
        if values:
            name = values[0].split(' ', 1)[1]  # 아이콘 제거
            file_path = os.path.join(self.current_remote_path, name).replace('\\', '/')
            
            if messagebox.askyesno("확인", f"'{name}'을(를) 삭제하시겠습니까?"):
                if self.adb_manager.delete_file(file_path):
                    self.log_message(f"삭제 완료: {name}")
                    self.refresh_remote_file_list()
                else:
                    self.log_message(f"삭제 실패: {name}")
                    messagebox.showerror("오류", "파일 삭제에 실패했습니다")
    
    def rename_selected_remote_file(self):
        """선택된 원격 파일/폴더 이름변경"""
        selection = self.remote_file_tree.selection()
        if not selection:
            messagebox.showwarning("경고", "이름을 변경할 파일/폴더를 선택하세요")
            return
        
        item = self.remote_file_tree.item(selection[0])
        values = item['values']
        if values:
            old_name = values[0].split(' ', 1)[1]  # 아이콘 제거
            old_path = os.path.join(self.current_remote_path, old_name).replace('\\', '/')
            
            new_name = simpledialog.askstring("이름변경", f"새 이름을 입력하세요:", initialvalue=old_name)
            if new_name and new_name != old_name:
                new_path = os.path.join(self.current_remote_path, new_name).replace('\\', '/')
                if self.adb_manager.rename_file(old_path, new_path):
                    self.log_message(f"📝 이름변경: {old_name} → {new_name}")
                    self.refresh_remote_file_list()
                else:
                    self.log_message(f"❌ 이름변경 실패: {old_name}")
                    messagebox.showerror("오류", "이름변경에 실패했습니다")


def main():
    """메인 함수"""
    print("Running root")
    root = tk.Tk()
    print("Running app...")
    app = MainApplication(root)
    
    # ADB 가용성 확인
    print("Checking ADB availability...")
    if not app.adb_manager.check_adb_available():
        messagebox.showerror("오류", "ADB가 설치되지 않았거나 PATH에 없습니다.\nAndroid SDK Platform Tools를 설치하세요.")
        return
    
    root.mainloop()


if __name__ == "__main__":
    main()

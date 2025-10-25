# ADB File System Manager

Android 디바이스의 파일 시스템을 로컬에서 관리할 수 있는 GUI 애플리케이션입니다. tkinter를 사용한 직관적인 인터페이스로 adb 명령어를 통해 파일을 다운로드하고 업로드할 수 있습니다.

## 주요 기능

- **디바이스 연결 관리**: 연결된 adb 디바이스 목록 표시 및 상태 확인
- **파일 시스템 탐색**: 디바이스의 파일 및 폴더 구조를 트리뷰로 표시
- **파일 전송**: 로컬과 디바이스 간 파일 다운로드/업로드
- **진행률 표시**: 파일 전송 진행률을 실시간으로 표시
- **에러 처리**: 명확한 에러 메시지와 사용자 피드백

## 스크린샷

![ADB File System Manager](screenshot.png)

## 설치 및 실행

### 필요 조건

- Python 3.9 이상
- Android Debug Bridge (adb) 설치 및 PATH 설정
- USB 디버깅이 활성화된 Android 디바이스

### 설치 방법

```bash
# 프로젝트 클론
git clone <repository-url>
cd adb-fs/adbfs-toga
chmod +x build.sh
./build.sh
```

### adb 설정

1. Android SDK Platform Tools 설치
2. adb를 PATH에 추가
3. 디바이스에서 USB 디버깅 활성화
4. 디바이스 연결 후 `adb devices`로 연결 확인

## 사용 방법

### 1. 디바이스 연결
- USB 케이블로 Android 디바이스 연결
- 애플리케이션 실행 시 자동으로 디바이스 검색
- 연결된 디바이스가 목록에 표시됨

### 2. 파일 탐색
- 디바이스 선택 후 파일 시스템 탐색
- 폴더를 더블클릭하여 하위 디렉토리 진입
- 파일을 선택하여 다운로드 준비

### 3. 파일 전송
- **다운로드**: 디바이스 파일을 로컬로 복사
- **업로드**: 로컬 파일을 디바이스로 복사
- 진행률 표시바로 전송 상태 확인

## 프로젝트 구조

```
adb-fs/
├── main.py              # 메인 GUI 애플리케이션
├── adb_manager.py       # adb 명령어 래퍼
├── file_manager.py      # 파일 전송 로직
├── utils.py            # 유틸리티 함수
├── pyproject.toml      # 프로젝트 설정
├── .todo              # 실행계획
├── .mdc               # 프로젝트 문서
└── README.md          # 프로젝트 설명
```

## 기술 스택

- **Python 3.9+**: 메인 개발 언어
- **tkinter**: GUI 프레임워크 (Python 표준 라이브러리)
- **subprocess**: adb 명령어 실행
- **threading**: 비동기 파일 전송 처리

## 문제 해결

### 일반적인 문제

1. **디바이스가 인식되지 않음**
   - USB 디버깅 활성화 확인
   - USB 드라이버 설치 확인
   - adb 서버 재시작

2. **파일 전송 실패**
   - 디바이스 저장 공간 확인
   - 파일 권한 확인
   - USB 연결 상태 확인

3. **GUI 응답 없음**
   - 대용량 파일 전송 시 정상적인 현상
   - 진행률 표시바로 상태 확인

## 라이선스

MIT License

## 기여 방법

1. Fork 프로젝트
2. Feature 브랜치 생성
3. 변경사항 커밋
4. Pull Request 생성

## 연락처

프로젝트 관련 문의사항이 있으시면 이슈를 등록해주세요.

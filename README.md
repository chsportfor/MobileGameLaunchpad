# MobileGameLauncher

PC 게임과 Steam 게임을 한곳에서 등록하고 실행하는 Windows 데스크톱 런처입니다.

## 기능

- 하나의 등록 창에서 PC 게임과 Steam 게임 추가
- Steam 상점 링크, 게임 ID, Steam 바로가기 인식
- 게임 검색 및 개별 실행
- 체크한 게임 한 번에 실행
- 게임별 설정 수정 및 등록 삭제
- Windows 작업 스케줄러를 이용한 관리자 실행 설정
- 기존 등록된 관리자 실행 작업의 실행 경로 조회

관리자 실행 설정은 Windows 권한 정책을 변경하지 않습니다. 빌드한 실행 파일은 실행 시 관리자 권한을 요청합니다.

## 개발 환경

- Windows
- Python 3.14

```powershell
py -3.14 -m pip install -r requirements.txt
py -3.14 MobileGamePlayOnce.py
```

처음 실행할 때 게임 목록은 비어 있습니다. 게임 등록 시 실행 파일 옆에 `custom_programs.json`이 생성됩니다. 이 파일에는 개인 게임 경로와 Windows 작업 이름이 저장되므로 Git에서 제외합니다. 빈 설정 예시는 `custom_programs.example.json`입니다.

## 실행 파일 빌드

앱을 종료하고 `build.bat`를 실행하세요. 같은 폴더에 `MobileGameLaunchpad.exe`가 생성되며, 중간 빌드 파일은 Windows 임시 폴더에 저장됩니다.

빌드한 실행 파일은 Python을 설치하지 않은 Windows PC에서도 실행할 수 있습니다. 게임 및 Steam은 해당 PC에 별도로 설치되어 있어야 합니다.

## 파일 구성

| 파일 | 용도 |
| --- | --- |
| `MobileGamePlayOnce.py` | 앱 소스 |
| `MobileGamePlayOnce.spec` | PyInstaller 빌드 설정 |
| `requirements.txt` | Python 의존성 |
| `build.bat` | 실행 파일 빌드 |
| `icon.ico` | 앱 아이콘 |
| `사용안내.md` | 사용 방법 |

실행 파일과 개인 설정은 저장소에 포함하지 않습니다.

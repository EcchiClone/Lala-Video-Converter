# pyinstaller.exe -F -w --onefile --icon=icon.ico --add-data "icon.png;." "Lala Video Converter.py"
# dos창 없이, 한 파일로 실행파일을 만드는 커맨드, -w는 콘솔창 표시 안하는 옵션
# --add-data 로, 윈도우 상단에 뜰 아이콘을 빌드에 포함

import os, sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, scrolledtext
import subprocess
import threading
import re
from queue import Queue
log_queue = Queue()

current_process = None  # 현재 실행 중인 프로세스를 참조하기 위한 변수
is_converting = False  # 변환 작업 진행 중 플래그
current_converting_file = None  # 현재 변환 중인 파일의 경로를 저장하는 변수

file_types = [
    ("Video files", "*.mp4;*.MP4;*.avi;*.AVI;*.mov;*.MOV;*.mkv;*.MKV;*.wmv;*.WMV;*.flv;*.FLV")
]
supported_extensions = (".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv")

# FFMPEG 및 7z 다운로드 관련은 추후 업데이트... 너무 번거로움.
# Todo After: 7z 없는 경우 다운로드해서 사용하기.
# import requests
# import shutil
# def extract_with_7z(archive_path, target_dir):
#     try:
#         subprocess.check_call(['7z', 'x', archive_path, '-o' + target_dir])
#         update_progress_log("ffmpeg 압축 해제 완료.")
#     except subprocess.CalledProcessError as e:
#         update_progress_log(f"압축 해제 실패: {e}")

# def check_ffmpeg():
#     ffmpeg_exe = os.path.join(os.getcwd(), "ffmpeg", "ffmpeg.exe")
#     ffprobe_exe = os.path.join(os.getcwd(), "ffmpeg", "ffprobe.exe")
#     if not (os.path.isfile(ffmpeg_exe) and os.path.isfile(ffprobe_exe)):
#         response = messagebox.askyesno("ffmpeg 설치 필요", "ffmpeg가 설치되어 있지 않습니다. 다운로드하시겠습니까? (약 1분~2분 소요)")
#         if response:
#             download_ffmpeg()
#             return True
#         else:
#             messagebox.showerror("에러", "ffmpeg가 필요한 작업입니다. 프로그램을 종료합니다.")
#             sys.exit()
#     else: start_button["state"] = "normal"


# def download_ffmpeg(version="ffmpeg-release-essentials"):
#     ffmpeg_url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.7z"
#     target_dir = f"./{version}/"
#     target_path = f"{version}.7z"

#     # 압축 파일 다운로드
#     update_progress_log("ffmpeg 다운로드 시작...")
#     response = requests.get(ffmpeg_url, stream=True)
#     with open(target_path, "wb") as f:
#         total_length = response.headers.get('content-length')

#         if total_length is None:  # no content length header
#             f.write(response.content)
#         else:
#             dl = 0
#             total_length = int(total_length)
#             for data in response.iter_content(chunk_size=4096):
#                 dl += len(data)
#                 f.write(data)
#                 done = int(50 * dl / total_length)
#                 update_progress_log(f"다운로드 진행중: [{'#' * done}{'.' * (50-done)}]")
    
#     # 다운로드 완료 후 압축 해제
#     update_progress_log("ffmpeg 압축 해제 중...")
#     extract_with_7z(target_path, target_dir)
#     update_progress_log("ffmpeg 압축 해제 완료.")

#     # 필요한 파일만 ./ffmpeg 폴더로 이동
#     ffmpeg_bin_path = os.path.join(target_dir, "ffmpeg-4.3.1-2020-10-01-essentials_build", "bin")
#     shutil.move(os.path.join(ffmpeg_bin_path, "ffmpeg.exe"), "./ffmpeg/")
#     shutil.move(os.path.join(ffmpeg_bin_path, "ffprobe.exe"), "./ffmpeg/")

#     # 불필요한 파일 및 폴더 삭제
#     shutil.rmtree(target_dir)
#     os.remove(target_path)

#     update_progress_log("ffmpeg 설정 완료.")
#     start_button["state"] = "normal"

def get_video_duration(file_path, log_widget, entire_pregress):
    try:
        command = ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                   '-show_entries', 'stream=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
        duration_str = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT, encoding='utf-8').strip()
        duration = float(duration_str)
        return duration
    except subprocess.CalledProcessError as e:
        # FFprobe 호출 실패 시 로그에 오류 메시지 추가
        last_line_error_msg = e.output.rstrip().replace('\\n','\n').split('\n')[-1]
        update_progress_log(f"[에러] {entire_pregress} {file_path}: {last_line_error_msg}", log_widget)
        return 0
    except Exception as e:
        last_line_error_msg = str(e).rstrip().replace('\\n','\n').split('\n')[-1]
        update_progress_log(f"[에러] {entire_pregress} {file_path}: {last_line_error_msg}", log_widget)
        return 0
    
# FFmpeg 변환 과정에서 진행도를 추적
def track_conversion_progress(current_process, log_widget, file_name, total_duration):
    # 변환 과정의 로그를 처리하면서 진행도 업데이트
    while True:
        line = current_process.stderr.readline()
        if not line:
            break
        progress = parse_progress(line)
        if progress:
            current_seconds = sum(x * float(t) for x, t in zip([3600, 60, 1], progress.split(":")))
            # 변환된 초 단위 시간을 통해 진행도를 계산하고 업데이트.
            update_text_progress(log_widget, file_name, current_seconds, total_duration)

# 진행도 파싱
def parse_progress(line):
    match = re.search("time=(\d+:\d+:\d+\.\d+)", line)
    if match:
        return match.group(1)
    return None

# 진행도를 업데이트
def update_text_progress(log_widget, file_name, current_seconds, total_duration):
    # 기존 로그를 유지하며, 진행도만 업데이트.
    log_widget.config(state='normal')
    # 마지막 라인을 확인하고, 진행도 정보가 포함된 라인이면 업데이트.
    last_line = log_widget.get("end-2l", "end-1l")
    if "% " in last_line:
        log_widget.delete("end-2l", "end-1l")

    progress_percentage = current_seconds / total_duration * 100
    progress_bar = "#" * int(progress_percentage / 4) + "-" * (25 - int(progress_percentage / 4))
    progress_text = f"[{progress_bar}] {progress_percentage:.2f}% \n"
    log_widget.insert(tk.END, progress_text)
    log_widget.config(state='disabled')
    log_widget.see(tk.END)

def validate_crf(P):
    # 입력 값이 숫자이거나 비어있는 경우에만 허용
    if P.isdigit() or P == "":
        return True
    else:
        return False
    
def on_crf_focusout(event):
    try:
        crf_value = int(crf_entry.get())
        if not 18 <= crf_value <= 40:
            raise ValueError("CRF 값이 범위를 벗어났습니다.")
    except ValueError:
        if crf_value < 18:
            update_progress_log(f"[경고] 입력된 CRF 값({crf_value})이 너무 낮습니다.")
            crf_value = 18
        if crf_value > 40:
            update_progress_log(f"[경고] 입력된 CRF 값({crf_value})이 너무 높습니다.")
            crf_value = 40
        crf_entry.delete(0, tk.END)
        crf_entry.insert(0, str(crf_value))
    update_progress_log(f"- 선택된 CRF 값: {crf_value}")
    
def update_video_count():
    folder_path = source_folder.get()
    if not folder_path:
        video_count_var.set("동영상 0개를 찾았습니다.")
        return
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(tuple(ext.lower() for ext in supported_extensions))]
    video_count_var.set(f"동영상 {len(files)}개를 찾았습니다.")
    
def choose_source_file():
    file_selected = filedialog.askopenfilename(filetypes=file_types)
    if file_selected:
        source_file.set(file_selected)
        source_file_label.config(state='normal')
        source_file_label.delete(0, tk.END)
        source_file_label.insert(0, file_selected)
        source_file_label.config(state='readonly')
        video_count_var.set("동영상 1개를 찾았습니다.")
        
        # 소스 폴더 선택 취소
        source_folder.set("")
        source_folder_label.config(state='normal')
        source_folder_label.delete(0, tk.END)
        source_folder_label.config(state='readonly')

        # 대상 폴더가 정해져 있지 않은 경우에만 소스 파일과 동일한 경로를 대상 폴더로 설정
        if not destination_folder.get():
            file_folder = os.path.dirname(file_selected)
            destination_folder.set(file_folder)
            destination_folder_label.config(state='normal')
            destination_folder_label.delete(0, tk.END)
            destination_folder_label.insert(0, file_folder)
            destination_folder_label.config(state='readonly')
            open_folder_button["state"] = "normal"  # 대상 폴더가 설정되었으므로 "대상 폴더 열기" 버튼 활성화

def choose_source_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        source_folder.set(folder_selected)
        source_folder_label.config(state='normal')
        source_folder_label.delete(0, tk.END)
        source_folder_label.insert(0, folder_selected)
        source_folder_label.config(state='readonly')
        update_video_count()

        # 소스 파일 선택 취소
        source_file.set("")
        source_file_label.config(state='normal')
        source_file_label.delete(0, tk.END)
        source_file_label.config(state='readonly')

        # 대상 폴더가 공란일 경우 소스 폴더와 동일한 폴더로 설정하고 '대상 폴더 열기' 버튼 활성화
        if not destination_folder.get():
            destination_folder.set(folder_selected)
            destination_folder_label.config(state='normal')
            destination_folder_label.delete(0, tk.END)
            destination_folder_label.insert(0, folder_selected)
            destination_folder_label.config(state='readonly')
            open_folder_button["state"] = "normal"


def choose_destination_folder():
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        destination_folder.set(folder_selected)  # StringVar 업데이트
        destination_folder_label.config(state='normal')  # Entry를 일시적으로 편집 가능 상태로 변경
        destination_folder_label.delete(0, tk.END)  # 기존의 텍스트 삭제
        destination_folder_label.insert(0, folder_selected)  # 새 경로 삽입
        destination_folder_label.config(state='readonly')  # Entry를 다시 읽기 전용 상태로 변경
        open_folder_button["state"] = "normal"  # "대상 폴더 열기" 버튼 활성화

def convert_videos():
    global current_process, is_converting, current_converting_file
    crf_value = crf_entry.get().strip()
    overwrite = overwrite_var.get()
    destination = destination_folder.get()

    # 초기 메시지가 아닌 실제 경로인지 확인
    def is_valid_path(path):
        return path and not path.startswith("#")

    # 입력값 검증
    if not crf_value.isdigit() or not 18 <= int(crf_value) <= 40:
        crf_value = "23"
        crf_entry.delete(0, tk.END)
        crf_entry.insert(0, "23")

    if not destination or (not is_valid_path(source_file.get()) and not is_valid_path(source_folder.get())):
        messagebox.showerror("오류", "소스와 대상 폴더를 모두 지정해주세요.")
        enable_ui_elements()
        return

    if not os.path.exists(destination):
        try:
            os.makedirs(destination)
        except OSError as e:
            messagebox.showerror("오류", f"대상 폴더 생성 오류: {e}")
            enable_ui_elements()
            return

    files_to_convert = []
    if is_valid_path(source_file.get()):
        files_to_convert.append(source_file.get())
    elif is_valid_path(source_folder.get()):
        folder_path = source_folder.get()
        files_to_convert.extend([os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(tuple(ext.lower() for ext in supported_extensions))])

    if not files_to_convert:
        messagebox.showerror("오류", "변환할 파일을 찾을 수 없습니다.")
        enable_ui_elements()
        return

    is_converting = True
    success_count = 0
    
    entire_progress_count = 0
    entire_progress_end = len(files_to_convert)

    for file_path in files_to_convert:
        entire_progress_count += 1
        entire_pregress = f"({entire_progress_count}/{entire_progress_end})"
        file_name = os.path.basename(file_path)
        dest_file_path = os.path.join(destination, os.path.splitext(file_name)[0] + f"_crf{crf_value}" + os.path.splitext(file_name)[1])
        current_converting_file = dest_file_path
        
        if not is_converting:
            # update_progress_log("[중지] 동영상 변환을 중지했습니다.")
            break

        if not overwrite and os.path.exists(dest_file_path):
            update_progress_log(f"[실패] {file_name}: 대상 폴더에 같은 이름의 파일이 이미 존재합니다.")
            continue
        
        total_duration = get_video_duration(file_path, progress_log, entire_pregress)
        if total_duration <= 0:
            update_progress_log(f"[중지] {file_name}: 유효하지 않은 동영상 길이입니다.", progress_log)
            continue

        command = ["ffmpeg", "-i", file_path, "-crf", crf_value, "-preset", "veryfast", dest_file_path]
        if overwrite:
            command.insert(1, "-y")
        
        update_progress_log(f"[시작] {entire_pregress} {file_name} 변환 시작" + ("(덮어쓰기)" if overwrite and os.path.exists(dest_file_path) else ""))

        current_process = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)

        track_conversion_progress(current_process, progress_log, file_name, total_duration)
        
        # # FFmpeg 출력에서 진행도 파싱
        # 기존 로그를 유지하며, 진행도만 업데이트.
        progress_log.config(state='normal')
        progress_log.delete("end-2l", "end-1l")
        progress_log.config(state='disabled')
        
        if current_process.wait() == 0:
            update_progress_log(f" └[완료] {file_name} 변환을 완료하였습니다.\n")
            success_count += 1
        else:
            update_progress_log(f" └[중지] {file_name} 변환 실패 또는 중지되었습니다.")
            if not is_converting and os.path.exists(dest_file_path):
                os.remove(dest_file_path)
                update_progress_log(f"   └[삭제] 변환 작업중인 파일을 삭제했습니다.\n")

    if is_converting:
        update_progress_log(f"<종료> 총 {success_count}개의 동영상 변환이 완료되었습니다.\n")
    else:
        update_progress_log("<종료> 변환 작업이 중지되었습니다.\n")
    
    is_converting = False
    current_converting_file = None
    enable_ui_elements()

def parse_ffmpeg_progress(line):
    # `time=00:00:01.23` 형식의 시간 정보를 찾아서 반환하는 함수
    match = re.search("time=(\d+:\d+:\d+\.\d+)", line)
    if match:
        return match.group(1)
    return None

def stop_conversion():
    global current_process
    global is_converting
    is_converting = False
    if current_process:
        current_process.terminate()  # 현재 프로세스 종료
    enable_ui_elements()

def finish_conversion_process(success_count=0, was_cancelled=False):
    global is_converting
    is_converting = False
    if was_cancelled:
        update_progress_log("[중지] 변환 작업이 중지되었습니다.")
    else:
        update_progress_log(f"[완료] 총 {success_count}개의 동영상 변환이 완료되었습니다.")
    enable_ui_elements()

def enable_ui_elements():
    # UI 요소 활성화하는 함수
    source_file_button["state"] = "normal"
    source_folder_button["state"] = "normal"
    destination_button["state"] = "normal"
    start_button["state"] = "normal"
    overwrite_checkbutton["state"] = "normal"
    crf_entry["state"] = "normal"
    # 변환 중지 버튼은 변환 진행 시에만 활성화
    stop_button["state"] = "disabled"

def update_progress_log(message, overwrite=False):
    # 로그 메시지를 Text 위젯에 추가
    # overwrite 파라미터는 메시지를 덮어쓸지 여부를 결정.
    progress_log.config(state='normal')
    if overwrite:
        progress_log.delete("end-2l", "end-1l")  # 마지막 라인 삭제
    progress_log.insert('end', message + '\n')
    progress_log.config(state='disabled')
    progress_log.see('end')

def start_conversion_thread():
    # 변환 시작 시 UI 요소 비활성화
    source_file_button["state"] = "disabled"
    source_folder_button["state"] = "disabled"
    destination_button["state"] = "disabled"
    start_button["state"] = "disabled"
    stop_button["state"] = "normal"
    overwrite_checkbutton["state"] = "disabled"
    crf_entry["state"] = "disabled"
    
    conversion_thread = threading.Thread(target=convert_videos)
    conversion_thread.start()
    
def open_destination_folder():
    destination_path = destination_folder.get()
    if not destination_path:
        messagebox.showwarning("경고", "대상 폴더가 선택되지 않았습니다.")
    else:
        try:
            os.startfile(destination_path)  # 대상 폴더 열기
        except AttributeError:
            # os.startfile이 지원되지 않는 플랫폼의 경우 (예: macOS, Linux)
            import subprocess
            subprocess.Popen(['open', destination_path],creationflags=subprocess.CREATE_NO_WINDOW)  # macOS
            # subprocess.Popen(['xdg-open', destination_path])  # Linux
        except Exception as e:
            messagebox.showerror("오류", f"폴더를 여는 동안 오류가 발생했습니다: {e}")


          
root = tk.Tk()
root.title("Lala Video Converter")

# PyInstaller가 생성한 임시 폴더에서 리소스 파일의 경로를 구성
if getattr(sys, 'frozen', False):
    application_path = sys._MEIPASS
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

icon_path = os.path.join(application_path, 'icon.png')
root.tk.call('wm', 'iconphoto', root._w, tk.PhotoImage(file=icon_path))

root.geometry("500x320")
root.resizable(False,False)

# Validation command
vcmd = (root.register(validate_crf), '%P')

source_file = tk.StringVar()
source_folder = tk.StringVar()
destination_folder = tk.StringVar()
video_count_var = tk.StringVar(value="동영상 0개를 찾았습니다.")
crf_value = tk.StringVar(value="23")  # 기본값 설정

# 소스 파일 선택 UI 설정
source_file_frame = tk.Frame(root)
source_file_frame.pack(fill="x", padx=5, pady=5)

source_file_label = tk.Entry(source_file_frame, state='normal', width=50, relief="sunken", textvariable=source_file)
source_file_label.insert(0, "# 변환할 동영상의 파일 또는")  # 초기 텍스트 삽입
source_file_label.config(state='readonly')  # 다시 읽기 전용으로 설정
source_file_label.pack(side="left", expand=True)
source_file_button = tk.Button(source_file_frame, text="소스 파일 선택", command=choose_source_file)
source_file_button.pack(side="left", padx=5)

# 소스 폴더 선택 UI 설정
source_folder_frame = tk.Frame(root)
source_folder_frame.pack(fill="x", padx=5, pady=5)

source_folder_label = tk.Entry(source_folder_frame, state='normal', width=50, relief="sunken", textvariable=source_folder)
source_folder_label.insert(0, "# 변환할 동영상들이 들어있는 소스폴더를 선택하세요")  # 초기 텍스트 삽입
source_folder_label.config(state='readonly')  # 다시 읽기 전용으로 설정
source_folder_label.pack(side="left", expand=True)
source_folder_button = tk.Button(source_folder_frame, text="소스 폴더 선택", command=choose_source_folder)
source_folder_button.pack(side="left", padx=5)

destination_frame = tk.Frame(root)
destination_frame.pack(fill="x", padx=5, pady=5)

destination_folder_label = tk.Entry(destination_frame, state='readonly', width=50, relief="sunken", textvariable=destination_folder)
destination_folder_label.pack(side="left", expand=True)
destination_button = tk.Button(destination_frame, text="저장 폴더 선택", command=choose_destination_folder)
destination_button.pack(side="left", padx=5)

crf_frame = tk.Frame(root)
crf_frame.pack(fill="x", padx=5, pady=5)

tk.Label(crf_frame, text="crf [18 ~ 40](낮을수록 높은 품질, 23 전후가 무난)").pack(side="left", padx=5)
crf_entry = tk.Entry(crf_frame, validate='key', validatecommand=vcmd, textvariable=crf_value)
crf_entry.bind("<FocusOut>", on_crf_focusout)
crf_entry.pack(side="right")

conversion_frame = tk.Frame(root)
conversion_frame.pack(fill="x", padx=5, pady=5)

video_count_label = tk.Label(conversion_frame, textvariable=video_count_var)
video_count_label.pack(side="left", padx=5)

overwrite_var = tk.BooleanVar()  # 체크박스 상태를 저장할 변수
overwrite_checkbutton = tk.Checkbutton(conversion_frame, text="덮어쓰기", variable=overwrite_var)
overwrite_checkbutton.pack(side="left", padx=5)

start_button = tk.Button(conversion_frame, text="변환 시작", command=start_conversion_thread)
# FFMPEG 다운로드 구현 시 disabled
# start_button["state"] = "disabled"
start_button.pack(side="left", padx=5)

# "변환 중지" 버튼 추가
stop_button = tk.Button(conversion_frame, text="변환 중지", command=stop_conversion)
stop_button["state"] = "disabled"
stop_button.pack(side="left", padx=5)

open_folder_button = tk.Button(conversion_frame, text="대상 폴더 열기", command=open_destination_folder)
open_folder_button["state"] = "disabled"
open_folder_button.pack(side="right", padx=5)

progress_frame = tk.Frame(root)
progress_frame.pack(fill="both", expand=True, padx=10, pady=5)

progress_log = tk.Text(progress_frame, state='disabled', height=10, bg='#f0f0f0')
progress_log.pack(fill="both", expand=True)

# FFMPEG 다운로드 관련 추후 업데이트
# if not check_ffmpeg():
#     sys.exit()

root.mainloop()

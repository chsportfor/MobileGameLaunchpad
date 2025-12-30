import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame
import subprocess
from tkinter import filedialog, messagebox, BooleanVar, Listbox

import os
import sys
import json
import threading

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CONFIG_FILE = "custom_programs.json"
custom_programs = []
program_widgets = []

def register_task(task_name, full_command):
    result = subprocess.run([
        "schtasks", "/create",
        "/tn", task_name,
        "/tr", full_command,
        "/sc", "ONCE",
        "/st", "00:00",
        "/rl", "HIGHEST",
        "/f"
    ], shell=True, capture_output=True, text=True)
    
    if result.returncode != 0:
        messagebox.showerror("작업 등록 실패", result.stderr)
        return False
    return True

def delete_task(task_name):
    subprocess.run(["schtasks", "/delete", "/tn", task_name, "/f"], shell=True)

def load_custom_programs():
    global custom_programs
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                custom_programs = []
                for item in data:
                    program_data = None
                    if isinstance(item, dict):
                        enabled_var = BooleanVar(value=item.get("enabled", True))
                        program_data = {
                            "name": item["name"],
                            "command": item["command"],
                            "is_exception": item["is_exception"],
                            "enabled_var": enabled_var
                        }
                    elif isinstance(item, list) and len(item) >= 3:
                        enabled_var = BooleanVar(value=True)
                        program_data = {
                            "name": item[0],
                            "command": item[1],
                            "is_exception": item[2],
                            "enabled_var": enabled_var
                        }
                    
                    if program_data:
                        custom_programs.append(program_data)

            except (json.JSONDecodeError, IndexError):
                messagebox.showerror("오류", f"{CONFIG_FILE} 파일이 손상되었거나 형식이 올바르지 않습니다.")
    
    refresh_program_list()
    save_custom_programs()


def save_custom_programs():
    data_to_save = []
    for item in custom_programs:
        data_to_save.append({
            "name": item["name"],
            "command": item["command"],
            "is_exception": item["is_exception"],
            "enabled": item["enabled_var"].get()
        })
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=2)

def refresh_program_list():
    for widget in program_frame.winfo_children():
        widget.destroy()

    for item in custom_programs:
        frame = ttk.Frame(program_frame)
        frame.pack(fill='x', padx=20, pady=2)
        
        cb = ttk.Checkbutton(frame, variable=item["enabled_var"], command=save_custom_programs, bootstyle="round-toggle")
        cb.pack(side="left")
        
        label = ttk.Label(frame, text=item["name"], anchor="w")
        label.pack(side="left", fill="x", expand=True, padx=10)
        label.bind("<Button-1>", lambda e, var=item["enabled_var"]: var.set(not var.get()))

        run_button = ttk.Button(frame, text="실행", command=lambda i=item: run_single_program(i), bootstyle="outline-secondary", width=10)
        run_button.pack(side="right", padx=(5, 0))


def add_program():
    def select_path():
        file_path = filedialog.askopenfilename(title="실행할 프로그램 선택")
        if file_path:
            path_var.set(f'"{file_path}"')

    def toggle_steam_mode():
        if steam_var.get():
            path_label.config(text="AppID:")
            browse_button.grid_remove()
            path_var.set("")
        else:
            path_label.config(text="경로 및 인자:")
            browse_button.grid(row=1, column=2, padx=5, pady=5)

    def confirm_add():
        name = name_entry.get().strip()
        path_value = path_var.get().strip()
        is_steam_game = steam_var.get()
        use_exception = uac_var.get()

        if not name or not path_value:
            messagebox.showwarning("입력 오류", "이름과 경로/AppID를 모두 입력해야 합니다.")
            return

        command = ""
        if is_steam_game:
            if not path_value.isdigit():
                messagebox.showwarning("입력 오류", "AppID는 숫자여야 합니다.")
                return
            command = f"start steam://rungameid/{path_value}"
        else:
            command = path_value

        task_name_val = None
        if use_exception:
            task_name_val = f"{name}"
            command_for_task = f'cmd /c "{command}"' if is_steam_game else command
            if not register_task(task_name_val, command_for_task):
                return
        
        enabled_var = BooleanVar(value=True)
        new_program = {
            "name": name,
            "command": task_name_val if use_exception else command,
            "is_exception": use_exception,
            "enabled_var": enabled_var
        }
        custom_programs.append(new_program)
        save_custom_programs()
        refresh_program_list()
        add_window.destroy()

    add_window = ttk.Toplevel(title="프로그램 추가")
    add_window.geometry("500x230")
    add_window.resizable(False, False)
    add_window.transient(root)
    add_window.iconbitmap(resource_path('Controller.ico'))

    frame = ttk.Frame(add_window, padding=(15, 15))
    frame.pack(fill='both', expand=True)
    frame.grid_columnconfigure(0, minsize=90)

    ttk.Label(frame, text="이름:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
    name_entry = ttk.Entry(frame, width=40)
    name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w", columnspan=2)

    path_label = ttk.Label(frame, text="경로 및 인자:")
    path_label.grid(row=1, column=0, sticky="e", padx=5, pady=5)
    path_var = ttk.StringVar()
    path_entry = ttk.Entry(frame, textvariable=path_var, width=40)
    path_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")
    browse_button = ttk.Button(frame, text="찾아보기", command=select_path, bootstyle="secondary")
    browse_button.grid(row=1, column=2, padx=5, pady=5)
    
    steam_var = BooleanVar()
    ttk.Checkbutton(frame, text="스팀 게임", variable=steam_var, command=toggle_steam_mode).grid(row=2, column=1, sticky="w", padx=5, pady=(10, 0))

    uac_var = BooleanVar()
    uac_checkbox = ttk.Checkbutton(frame, text="관리자 권한 실행 메시지 끄기", variable=uac_var)
    uac_checkbox.grid(row=3, column=1, columnspan=2, sticky="w", padx=5, pady=5)

    ttk.Button(frame, text="추가", command=confirm_add, bootstyle="primary").grid(row=4, column=1, pady=10)

def delete_program():
    if not custom_programs:
        messagebox.showinfo("삭제", "삭제할 프로그램이 없습니다.")
        return

    delete_window = ttk.Toplevel(title="프로그램 삭제")
    delete_window.geometry("350x400")
    delete_window.resizable(False, False)
    delete_window.transient(root)
    delete_window.iconbitmap(resource_path('Controller.ico'))

    ttk.Label(delete_window, text="삭제할 항목 옆의 'X' 버튼을 누르세요:", padding=(0, 10, 0, 0)).pack()

    scroll_frame = ScrolledFrame(delete_window, autohide=True)
    scroll_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

    def delete_item(item_to_delete, row_widget):
        confirm = messagebox.askyesno(
            "삭제 확인", 
            f"'{item_to_delete['name']}' 항목을 정말로 삭제하시겠습니까?"
        )
        if confirm:
            if item_to_delete["is_exception"]:
                delete_task(item_to_delete["command"])
            
            custom_programs.remove(item_to_delete)
            save_custom_programs()
            refresh_program_list()
            row_widget.destroy()

    for item in custom_programs:
        row_frame = ttk.Frame(scroll_frame)
        row_frame.pack(fill='x', expand=True, pady=3, padx=3)

        delete_button = ttk.Button(
            row_frame,
            text="X",
            bootstyle="danger",
            width=2,
            command=lambda i=item, rf=row_frame: delete_item(i, rf)
        )
        delete_button.pack(side=RIGHT, padx=(5,0))

        name_label = ttk.Label(row_frame, text=item["name"], anchor=W)
        name_label.pack(side=LEFT, fill=X, expand=True)

    close_button = ttk.Button(delete_window, text="닫기", command=delete_window.destroy, bootstyle="secondary")
    close_button.pack(pady=10)

def run_single_program(item):
    def threaded_run():
        if item["is_exception"]:
            subprocess.Popen(["schtasks", "/run", "/tn", item["command"]], shell=True)
        else:
            subprocess.Popen(item["command"], shell=True)
    threading.Thread(target=threaded_run).start()

def run_all():
    def threaded_run():
        save_custom_programs() 
        for item in custom_programs:
            if item["enabled_var"].get():
                if item["is_exception"]:
                    subprocess.Popen(["schtasks", "/run", "/tn", item["command"]], shell=True)
                else:
                    subprocess.Popen(item["command"], shell=True)
    threading.Thread(target=threaded_run).start()

# GUI
root = ttk.Window(themename="litera")
root.title("MobileGame Launchpad")
root.iconbitmap(resource_path('Controller.ico'))

def center_window(win, width=450, height=550):
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    win.geometry(f"{width}x{height}+{x}+{y}")

center_window(root)
root.minsize(450, 300)


top_frame = ttk.Frame(root, padding=(0, 10))
top_frame.pack(fill='x', padx=20)
top_frame.grid_columnconfigure((0, 1), weight=1)

ttk.Button(top_frame, text="프로그램 추가", command=add_program, bootstyle="primary").grid(row=0, column=0, sticky=EW, padx=(0,5))
ttk.Button(top_frame, text="프로그램 삭제", command=delete_program, bootstyle="danger").grid(row=0, column=1, sticky=EW, padx=(5,0))


separator = ttk.Separator(root, orient=HORIZONTAL)
separator.pack(fill='x', padx=20, pady=10)


list_header_frame = ttk.Frame(root)
list_header_frame.pack(fill=X, padx=20)
ttk.Label(list_header_frame, text="게임 리스트", font=("-size 11 -weight bold")).pack(side=LEFT)


program_frame = ttk.Frame(root)
program_frame.pack(fill="both", expand=True, pady=(5,0))

ttk.Button(root, text="체크한 게임 전체 실행", command=run_all, bootstyle="success").pack(fill='x', padx=20, pady=20)

load_custom_programs()
root.mainloop()
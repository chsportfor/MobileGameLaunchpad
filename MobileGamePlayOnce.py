"""A small, local game library. Existing custom_programs.json remains compatible."""
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import uuid
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
from tkinter import filedialog, messagebox
import customtkinter as ctk

BASE = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
RESOURCES = Path(getattr(sys, '_MEIPASS', BASE))
CONFIG_FILE = BASE / 'custom_programs.json'
BG, PANEL, BORDER = '#10141D', '#1A2130', '#2B3548'
TEXT, MUTED, ACCENT = '#F1F5FC', '#9BAAC2', '#768CFF'
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def steam_id(value):
    value = value.strip()
    patterns = (r'(\d+)', r'(?:start\s+)?steam://(?:rungameid|run)/(\d+)/?',
                r'https?://store\.steampowered\.com/app/(\d+)(?:/[^\s]*)?(?:\?[^\s]*)?')
    for pattern in patterns:
        match = re.fullmatch(pattern, value, re.IGNORECASE)
        if match and int(match[1]) > 0:
            return match[1]
    return None


def target_of(game):
    return game.get('raw_path') or game.get('command', '')


def is_steam(game):
    return not game.get('is_exception') and steam_id(target_of(game)) is not None


def load_programs(path=CONFIG_FILE):
    if not Path(path).exists():
        return []
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data, list):
        raise ValueError('게임 목록 파일의 형식이 올바르지 않습니다.')
    result = []
    for item in data:
        if isinstance(item, list) and len(item) >= 3:
            item = dict(name=item[0], command=item[1], is_exception=item[2],
                        enabled=item[3] if len(item) > 3 else True)
        if not isinstance(item, dict) or not item.get('name') or not item.get('command'):
            raise ValueError('이름 또는 실행 정보가 없는 항목이 있습니다.')
        result.append(dict(item, enabled=item.get('enabled', True)))
    return result


def save_programs(games, path=CONFIG_FILE):
    path = Path(path)
    temporary = path.with_suffix('.json.tmp')
    try:
        temporary.write_text(json.dumps(games, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def task_command(*args):
    result = subprocess.run(['schtasks', *args], capture_output=True, text=True,
                            errors='replace', creationflags=NO_WINDOW)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result


def register_task(task_name, executable):
    # No triggers: the task runs only when the user launches this game.
    xml = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><ExecutionTimeLimit>PT0S</ExecutionTimeLimit></Settings>
  <Actions Context="Author"><Exec><Command>{escape(executable)}</Command><WorkingDirectory>{escape(str(Path(executable).parent))}</WorkingDirectory></Exec></Actions>
</Task>'''
    with tempfile.NamedTemporaryFile(suffix='.xml', delete=False) as file:
        filename = file.name
    try:
        Path(filename).write_text(xml, encoding='utf-16')
        task_command('/create', '/tn', task_name, '/xml', filename, '/f')
    finally:
        Path(filename).unlink(missing_ok=True)


def scheduled_game_path(task_name):
    xml = task_command('/query', '/tn', task_name, '/xml').stdout
    command = ET.fromstring(xml).find('.//{*}Actions/{*}Exec/{*}Command')
    if command is None or not command.text:
        raise ValueError('등록된 작업에서 실행 파일 경로를 찾지 못했습니다.')
    return command.text.strip().strip('"')


def launch_game(game):
    if game.get('is_exception'):
        task_command('/run', '/tn', game['command'])
    elif is_steam(game):
        os.startfile('steam://rungameid/' + steam_id(target_of(game)))
    else:
        target = target_of(game).strip().strip('"')
        if Path(target).is_file():
            os.startfile(target, cwd=str(Path(target).resolve().parent))
        elif game.get('kind') == 'pc':
            raise FileNotFoundError('실행 파일을 찾지 못했습니다. 설정에서 파일을 다시 선택해 주세요.')
        else:
            # Preserve old manually entered commands, including emulator arguments.
            subprocess.Popen(game['command'], shell=True, creationflags=NO_WINDOW)


def font(size=13, bold=False):
    return ctk.CTkFont(family='맑은 고딕', size=size, weight='bold' if bold else 'normal')


def label(parent, text, size=13, color=TEXT, bold=False, **kwargs):
    return ctk.CTkLabel(parent, text=text, font=font(size, bold), text_color=color, **kwargs)


def button(parent, text, command, primary=False, **kwargs):
    return ctk.CTkButton(parent, text=text, command=command, font=font(13, True),
                        height=38, corner_radius=9, fg_color=ACCENT if primary else BORDER,
                        hover_color='#8C9FFF' if primary else '#3C4961', **kwargs)


class Launchpad(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('MobileGame · 내 게임 라이브러리')
        self.geometry('820x780')
        self.minsize(720, 580)
        self.configure(fg_color=BG)
        self.games = []
        self.load_failed = False
        self.editor = None
        self.busy = False
        try:
            self.iconbitmap(str(RESOURCES / 'icon.ico'))
        except Exception:
            pass
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=30, pady=(28, 20))
        button(header, '+  게임 등록', self.open_editor, True, width=128).pack(side='right')
        label(header, '게임 목록', 24, bold=True).pack(anchor='w')
        toolbar = ctk.CTkFrame(self, fg_color='transparent')
        toolbar.pack(fill='x', padx=30, pady=(0, 12))
        self.count = label(toolbar, '', color=MUTED)
        self.count.pack(side='left')
        self.search = ctk.CTkEntry(toolbar, placeholder_text='게임 이름 검색', width=220,
                                   height=36, fg_color=PANEL, border_color=BORDER, font=font())
        self.search.pack(side='right')
        self.search.bind('<KeyRelease>', lambda _: self.refresh())
        footer = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0)
        footer.pack(side='bottom', fill='x')
        self.run_button = button(footer, '선택한 게임 실행', self.run_selected, True, width=200)
        self.run_button.pack(side='right', padx=26, pady=22)
        self.selection = label(footer, '', 15, bold=True)
        self.selection.pack(anchor='w', padx=30, pady=(20, 0))
        self.status = label(footer, '체크한 게임만 함께 실행합니다.', 12, MUTED)
        self.status.pack(anchor='w', padx=30, pady=(2, 18))
        self.list = ctk.CTkScrollableFrame(self, fg_color='transparent')
        self.list.pack(fill='both', expand=True, padx=24, pady=(0, 16))
        try:
            self.games = load_programs()
        except Exception as exc:
            self.load_failed = True
            self.after(100, lambda error=str(exc): messagebox.showerror('목록 불러오기 실패', error + '\n기존 파일 보호를 위해 저장을 중지했습니다.', parent=self))
        self.refresh()

    def commit(self, games, rebuild=True):
        if self.load_failed:
            messagebox.showerror('저장할 수 없음', '기존 목록 파일을 복구한 뒤 다시 실행해 주세요.', parent=self)
            return False
        try:
            save_programs(games)
        except Exception as exc:
            messagebox.showerror('저장 실패', str(exc), parent=self)
            return False
        self.games = games
        if rebuild:
            self.refresh()
        else:
            self.update_selection()
        return True

    def update_selection(self):
        selected = sum(bool(g.get('enabled', True)) for g in self.games)
        self.selection.configure(text=f'{selected}개 게임 선택됨')
        self.run_button.configure(text=f'선택한 {selected}개 실행', state='normal' if selected and not self.busy else 'disabled')

    def refresh(self):
        for child in self.list.winfo_children():
            child.destroy()
        self.update_selection()
        self.count.configure(text=f'전체 {len(self.games)}개  ·  Steam {sum(is_steam(g) for g in self.games)}개')
        query = self.search.get().strip().casefold()
        visible = [g for g in self.games if query in g['name'].casefold()]
        if not visible:
            label(self.list, '검색 결과가 없습니다' if self.games else '첫 게임을 등록해 보세요', 20, bold=True).pack(pady=(90, 12))
            label(self.list, '다른 이름으로 검색해 주세요.' if self.games else 'PC 게임과 Steam 게임 모두 위의 게임 등록에서 추가할 수 있어요.', color=MUTED).pack()
        for game in visible:
            card = ctk.CTkFrame(self.list, fg_color=PANEL, border_color=BORDER, border_width=1, corner_radius=14)
            card.pack(fill='x', pady=(0, 10))
            var = ctk.BooleanVar(value=game.get('enabled', True))
            ctk.CTkCheckBox(card, text='', width=24, variable=var, fg_color=ACCENT,
                            command=lambda g=game, v=var: self.toggle(g, v)).pack(side='left', padx=(18, 14))
            button(card, '실행', lambda g=game: self.run_games([g]), True, width=68).pack(side='right', padx=(8, 16))
            button(card, '설정', lambda g=game: self.open_editor(g), width=58).pack(side='right')
            info = ctk.CTkFrame(card, fg_color='transparent')
            info.pack(side='left', fill='x', expand=True, pady=16)
            title = game['name'] if len(game['name']) <= 24 else game['name'][:23] + '…'
            label(info, title, 15, bold=True, anchor='w').pack(fill='x')
            detail = 'Steam  ·  Steam으로 실행' if is_steam(game) else ('PC 게임  ·  관리자 실행 설정됨' if game.get('is_exception') else 'PC 게임  ·  일반 실행')
            label(info, detail, 12, MUTED, anchor='w').pack(fill='x')

    def toggle(self, game, variable):
        previous = game.get('enabled', True)
        game['enabled'] = variable.get()
        if not self.commit(self.games, rebuild=False):
            game['enabled'] = previous
            variable.set(previous)

    def run_selected(self):
        self.run_games([g for g in self.games if g.get('enabled', True)])

    def run_games(self, games):
        if self.busy:
            return
        self.busy = True
        self.update_selection()
        errors = []
        def step(index=0):
            if index == len(games):
                self.busy = False
                self.update_selection()
                self.status.configure(text=f'{len(games) - len(errors)}개 게임에 실행 요청을 보냈습니다.')
                if errors:
                    messagebox.showerror('실행 확인이 필요합니다', '\n\n'.join(errors), parent=self)
                return
            game = games[index]
            self.status.configure(text=game['name'] + ' 실행 요청 중…')
            try:
                launch_game(game)
            except Exception as exc:
                errors.append(game['name'] + '\n' + str(exc))
            self.after(150, lambda: step(index + 1))
        self.after(10, step)

    def open_editor(self, game=None):
        if self.editor and self.editor.winfo_exists():
            self.editor.focus()
            return
        self.editor = GameEditor(self, game)


class GameEditor(ctk.CTkToplevel):
    def __init__(self, app, game=None):
        super().__init__(app)
        self.app, self.game = app, game
        self.title('게임 설정' if game else '게임 등록')
        self.geometry('610x670')
        self.minsize(590, 650)
        self.configure(fg_color=BG)
        self.transient(app)
        self.after(250, self.apply_icon)
        self.grab_set()
        self.mode = ctk.StringVar(value='Steam' if game and is_steam(game) else 'PC 게임')
        self.name = ctk.StringVar(value=game['name'] if game else '')
        initial = target_of(game) if game else ''
        self.path_lookup_failed = False
        if game and game.get('is_exception'):
            initial = game.get('raw_path', '')
            if not initial:
                try:
                    initial = scheduled_game_path(game['command'])
                except (OSError, RuntimeError, ValueError, ET.ParseError):
                    self.path_lookup_failed = True
        self.original_path = initial.strip().strip('"')
        self.pc_value = initial if self.mode.get() == 'PC 게임' else ''
        self.steam_value = initial if self.mode.get() == 'Steam' else ''
        self.path = ctk.StringVar(value=initial)
        self.admin = ctk.BooleanVar(value=bool(game and game.get('is_exception')))
        self.previous_mode = self.mode.get()
        body = ctk.CTkFrame(self, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=28, pady=24)
        label(body, '게임 설정' if game else '어떤 게임을 추가할까요?', 24, bold=True).pack(anchor='w')
        label(body, '게임 종류를 선택하면 알맞은 입력 화면이 나타납니다.', color=MUTED).pack(anchor='w', pady=(4, 18))
        ctk.CTkSegmentedButton(body, values=['PC 게임', 'Steam'], variable=self.mode,
                               command=self.change_mode, height=40, font=font(14, True),
                               selected_color=ACCENT, fg_color=BORDER,
                               unselected_color=PANEL, unselected_hover_color=BORDER).pack(fill='x', pady=(0, 16))
        label(body, '게임 이름', bold=True).pack(anchor='w')
        ctk.CTkEntry(body, textvariable=self.name, height=40, font=font(), fg_color=PANEL, border_color=BORDER,
                    placeholder_text='라이브러리에 표시할 이름').pack(fill='x', pady=(5, 14))
        self.path_label = label(body, '', bold=True)
        self.path_label.pack(anchor='w')
        row = ctk.CTkFrame(body, fg_color='transparent')
        row.pack(fill='x', pady=(5, 8))
        self.browse = button(row, '파일 선택', self.select_file, width=90)
        self.entry = ctk.CTkEntry(row, textvariable=self.path, height=40, font=font(), fg_color=PANEL, border_color=BORDER)
        self.entry.pack(side='left', fill='x', expand=True)
        self.help = label(body, '', 12, MUTED, justify='left', anchor='w', wraplength=530)
        self.help.pack(fill='x', pady=(0, 14))
        self.options = ctk.CTkFrame(body, fg_color=PANEL, corner_radius=12)
        self.options.pack(fill='x')
        self.feedback = label(body, '', 12, '#AEBBFF', justify='left', anchor='w', wraplength=530)
        self.feedback.pack(fill='x', pady=(12, 8))
        actions = ctk.CTkFrame(self, fg_color='transparent')
        actions.pack(fill='x', padx=28, pady=(0, 24))
        if game:
            button(actions, '등록 삭제', self.delete, width=90, text_color='#FFA6B4').pack(side='left')
        button(actions, '저장' if game else '라이브러리에 추가', self.save, True, width=150).pack(side='right')
        button(actions, '취소', self.destroy, width=70).pack(side='right', padx=8)
        self.path.trace_add('write', self.detect)
        self.render_mode()
        self.detect()

    def apply_icon(self):
        if self.winfo_exists():
            try:
                self.iconbitmap(str(RESOURCES / 'icon.ico'))
            except Exception:
                pass

    def change_mode(self, value):
        if self.previous_mode == 'PC 게임':
            self.pc_value = self.path.get()
        else:
            self.steam_value = self.path.get()
        self.previous_mode = value
        self.path.set(self.steam_value if value == 'Steam' else self.pc_value)
        self.render_mode()
        self.detect()

    def render_mode(self):
        for child in self.options.winfo_children():
            child.destroy()
        steam = self.mode.get() == 'Steam'
        self.path_label.configure(text='Steam 상점 링크 또는 게임 ID' if steam else '게임 실행 파일')
        if steam:
            self.browse.pack_forget()
            self.help.configure(text='Steam 상점에서 게임 페이지 주소를 복사해 붙여넣으세요.\n예: https://store.steampowered.com/app/3557620/ 또는 3557620')
            label(self.options, 'Steam이 게임을 실행합니다', 14, bold=True).pack(anchor='w', padx=16, pady=(14, 4))
            label(self.options, 'Steam 설치 및 로그인이 필요합니다.\n관리자 실행 설정은 따로 하지 않아도 됩니다.', 12, MUTED, justify='left').pack(anchor='w', padx=16, pady=(0, 14))
        else:
            self.browse.pack(side='right', padx=(8, 0))
            self.help.configure(text='파일 선택으로 .exe 또는 바로가기를 고르세요.\nSteam 링크를 붙여넣으면 Steam 등록 화면으로 자동 전환됩니다.')
            ctk.CTkSwitch(self.options, text='관리자 권한으로 실행', variable=self.admin,
                          font=font(14, True), progress_color=ACCENT).pack(anchor='w', padx=16, pady=(16, 8))
            label(self.options, '권한 확인 창이 반복되는 게임만 켜 주세요.\n저장할 때 Windows 실행 작업을 등록합니다.\n최초 설정에는 관리자 권한이 필요합니다.', 12, MUTED, justify='left').pack(anchor='w', padx=16, pady=(0, 14))

    def detect(self, *_):
        value = self.path.get().strip()
        appid = steam_id(value)
        if appid and self.mode.get() != 'Steam':
            self.pc_value = ''
            self.steam_value = value
            self.mode.set('Steam')
            self.previous_mode = 'Steam'
            self.render_mode()
        if self.mode.get() == 'Steam':
            self.feedback.configure(text=f'Steam 게임 ID {appid} 인식됨 · 저장 후 Steam으로 실행합니다.' if appid else ('Steam 상점 링크 또는 숫자로 된 게임 ID를 확인해 주세요.' if value else '링크를 넣으면 게임 ID를 자동으로 확인합니다.'))
        else:
            self.feedback.configure(text='기존 작업의 경로를 읽지 못했습니다. 파일 선택으로 지정해 주세요.\n경로를 바꾸지 않고 저장하면 기존 실행 설정을 유지합니다.' if self.path_lookup_failed and not value else '')

    def select_file(self):
        filename = filedialog.askopenfilename(parent=self, title='게임 실행 파일 선택',
                    filetypes=[('게임 실행 파일 및 바로가기', '*.exe *.lnk *.url'), ('모든 파일', '*.*')])
        if not filename:
            return
        if filename.lower().endswith('.url'):
            content = Path(filename).read_text(encoding='utf-8-sig', errors='replace')
            match = re.search(r'^URL=(.+)$', content, re.MULTILINE | re.IGNORECASE)
            if match and steam_id(match[1]):
                self.path.set(match[1].strip())
            else:
                messagebox.showerror('Steam 바로가기 확인', 'Steam 게임 바로가기를 선택해 주세요.', parent=self)
                return
        else:
            self.path.set(filename)
        if not self.name.get().strip():
            self.name.set(Path(filename).stem)

    def save(self):
        name, value = self.name.get().strip(), self.path.get().strip().strip('"')
        steam = self.mode.get() == 'Steam'
        admin = self.admin.get() and not steam
        old = self.game
        if not name:
            self.feedback.configure(text='게임 이름을 입력해 주세요.')
            return
        if any(g is not old and g['name'].casefold() == name.casefold() for g in self.app.games):
            self.feedback.configure(text='이미 등록된 이름입니다. 다른 이름을 입력해 주세요.')
            return
        item = dict(old or {}, name=name, enabled=old.get('enabled', True) if old else True)
        new_task = None
        keep_task = old and old.get('is_exception') and admin and value == self.original_path
        keep_legacy = old and not old.get('kind') and not old.get('is_exception') and not steam and value == target_of(old).strip().strip('"')
        try:
            if steam:
                appid = steam_id(value)
                if not appid:
                    raise ValueError('올바른 Steam 상점 링크 또는 게임 ID를 입력해 주세요.')
                item.update(command='steam://rungameid/' + appid, raw_path='steam://rungameid/' + appid,
                            kind='steam', is_exception=False)
            elif keep_task:
                if value:
                    item['raw_path'] = value
            elif keep_legacy:
                if admin:
                    raise ValueError('관리자 설정을 하려면 파일 선택으로 .exe 파일을 지정해 주세요.')
            else:
                if not Path(value).is_file():
                    raise ValueError('파일 선택으로 실행할 게임 파일을 지정해 주세요.')
                value = str(Path(value).resolve())
                if Path(value).suffix.lower() not in ('.exe', '.lnk'):
                    raise ValueError('.exe 또는 .lnk 파일을 선택해 주세요.')
                if admin:
                    if Path(value).suffix.lower() != '.exe':
                        raise ValueError('관리자 실행에는 바로가기 대신 실제 .exe 파일을 선택해 주세요.')
                    if not ctypes.windll.shell32.IsUserAnAdmin():
                        raise ValueError('런처를 닫고 마우스 오른쪽 버튼 → 관리자 권한으로 실행한 뒤 설정해 주세요.')
                    new_task = 'MobileGame_' + uuid.uuid4().hex
                    register_task(new_task, value)
                item.update(command=new_task or value, raw_path=value, kind='pc', is_exception=admin)
            games = [item if g is old else g for g in self.app.games] if old else self.app.games + [item]
            if not self.app.commit(games):
                if new_task:
                    task_command('/delete', '/tn', new_task, '/f')
                return
        except Exception as exc:
            self.feedback.configure(text=str(exc))
            return
        self.cleanup_owned_task(old, item)
        self.destroy()

    def cleanup_owned_task(self, old, new=None):
        if old and old.get('is_exception') and old['command'].startswith('MobileGame_') and (not new or new.get('command') != old['command']):
            try:
                task_command('/delete', '/tn', old['command'], '/f')
            except Exception as exc:
                messagebox.showwarning('이전 실행 작업 정리 필요', '게임 목록은 저장되었습니다. 이전 Windows 작업은 남아 있습니다.\n' + str(exc), parent=self)

    def delete(self):
        if messagebox.askyesno('게임 등록 삭제', f'“{self.game["name"]}”을 목록에서 삭제할까요?\n설치된 게임 파일은 유지됩니다.', parent=self):
            if self.app.commit([g for g in self.app.games if g is not self.game]):
                self.cleanup_owned_task(self.game)
                self.destroy()


def main():
    # Use Windows' executable-based identity, matching ordinary pinned shortcuts.
    # A process-only custom AppUserModelID splits the window from its pinned EXE.
    ctk.set_appearance_mode('dark')
    ctk.set_default_color_theme('blue')
    Launchpad().mainloop()


if __name__ == '__main__':
    main()

"""
病院アンケートシステム メインアプリケーション
管理者モード・回答者モードの切り替え画面を提供する。
起動時に共有フォルダへの接続を確認する。
"""

import os
import shutil
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import src.config as config
from src.config import APP_TITLE, APP_VERSION
from src.data_manager import check_version_outdated, ensure_data_layout, get_update_exe_path
from src.gui_admin import AdminLoginDialog, AdminPanel
from src.gui_aggregate import AggregatePanel
from src.gui_response import ResponsePanel
from src.logger import write_access_log


class HospitalSurveyApp:
    """メインアプリケーションクラス。"""

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"{APP_TITLE} v{APP_VERSION}")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        self._current_panel: tk.Widget | None = None

        style = ttk.Style()
        style.configure("Title.TLabel", font=("", 20, "bold"))
        style.configure("Big.TButton", font=("", 12), padding=10)
        style.configure("Status.TLabel", font=("", 9))
        style.configure("Small.TButton", font=("", 8))

        self._check_data_connection()

    def _check_data_connection(self) -> None:
        """共有フォルダへの接続を確認し、問題があれば設定画面を表示する。"""
        data_dir = config.get_data_dir()

        if os.path.isdir(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            self._after_connect()
        else:
            self._show_connection_setup()

    def _after_connect(self) -> None:
        """接続確立後の初期化（データ構成・ログ・更新チェック）を行う。"""
        try:
            ensure_data_layout()
        except Exception:
            pass
        try:
            write_access_log()
        except Exception:
            pass
        self._show_home()
        self._check_version()

    def _check_version(self) -> None:
        """共有フォルダの最新バージョンと比較し、古ければ自動更新を試みる。"""
        try:
            outdated, latest, note = check_version_outdated()
        except Exception:
            return
        if not outdated:
            return

        update_exe = get_update_exe_path()
        if update_exe and getattr(sys, "frozen", False):
            msg = (
                f"新しいバージョンが利用可能です。\n\n"
                f"使用中: {APP_VERSION}\n最新: {latest}\n"
            )
            if note:
                msg += f"\n{note}"
            msg += "\n\n自動更新しますか？"
            if messagebox.askyesno("更新のお知らせ", msg):
                self._perform_auto_update(update_exe)
                return

        msg = (
            f"新しいバージョンがあります。\n\n"
            f"使用中: {APP_VERSION}\n最新: {latest}\n"
        )
        if note:
            msg += f"\n{note}"
        msg += "\n\n管理者から最新版（exe）を入手してください。"
        messagebox.showwarning("更新のお知らせ", msg)

    def _perform_auto_update(self, source_exe: str) -> None:
        """共有フォルダのexeで自身を更新し、再起動する。"""
        current_exe = sys.executable
        current_dir = os.path.dirname(current_exe)
        exe_name = os.path.basename(current_exe)

        bat_path = os.path.join(current_dir, "_update.bat")
        bat_content = (
            "@echo off\r\n"
            "timeout /t 2 /nobreak > nul\r\n"
            f'copy /Y "{source_exe}" "{current_exe}"\r\n'
            f'start "" "{current_exe}"\r\n'
            f'del "%~f0"\r\n'
        )
        try:
            with open(bat_path, "w", encoding="mbcs") as f:
                f.write(bat_content)
            CREATE_NO_WINDOW = 0x08000000
            subprocess.Popen(
                ["cmd", "/c", bat_path],
                creationflags=CREATE_NO_WINDOW,
            )
            self.root.destroy()
            sys.exit(0)
        except Exception as e:
            messagebox.showerror(
                "更新エラー",
                f"自動更新に失敗しました。\n{e}\n\n管理者から最新版を入手してください。",
            )

    def _show_connection_setup(self) -> None:
        """共有フォルダ設定画面を表示する。"""
        self._clear_panel()

        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)
        self._current_panel = frame

        center = ttk.Frame(frame)
        center.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        ttk.Label(
            center, text="共有フォルダの接続設定", font=("", 16, "bold")
        ).pack(pady=(0, 10))

        ttk.Label(
            center,
            text="データの保存先となる共有フォルダを指定してください。\n"
            "（例: \\\\server\\share\\hospital_survey\\data）",
            justify=tk.CENTER,
        ).pack(pady=(0, 20))

        path_frame = ttk.Frame(center)
        path_frame.pack(pady=5)

        self._path_var = tk.StringVar(value=config.DATA_DIR)
        ttk.Entry(path_frame, textvariable=self._path_var, width=50).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(path_frame, text="参照...", command=self._browse_folder).pack(
            side=tk.LEFT
        )

        self._status_label = ttk.Label(center, text="", foreground="red")
        self._status_label.pack(pady=5)

        ttk.Button(
            center, text="接続テスト＆保存", command=self._test_and_save_connection
        ).pack(pady=10)

        ttk.Button(
            center,
            text="ローカルモードで起動（exe同階層のdataフォルダ）",
            command=self._use_local_mode,
        ).pack(pady=5)

    def _browse_folder(self) -> None:
        path = filedialog.askdirectory(title="共有フォルダを選択")
        if path:
            self._path_var.set(path)

    def _test_and_save_connection(self) -> None:
        path = self._path_var.get().strip()
        if not path:
            self._status_label.config(text="パスを入力してください。", foreground="red")
            return

        if not os.path.isdir(path):
            self._status_label.config(
                text="指定されたフォルダが見つかりません。パスを確認してください。",
                foreground="red",
            )
            return

        # 書き込みテスト
        test_file = os.path.join(path, ".connection_test")
        try:
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except OSError:
            self._status_label.config(
                text="フォルダへの書き込み権限がありません。", foreground="red"
            )
            return

        # 設定を保存
        config.set_data_dir(path)

        self._status_label.config(text="接続成功！", foreground="green")
        self.root.after(500, self._after_connect)

    def _use_local_mode(self) -> None:
        local_dir = os.path.join(config.APP_DIR, "data")
        os.makedirs(local_dir, exist_ok=True)
        config.set_data_dir(local_dir)
        self._after_connect()

    def _clear_panel(self) -> None:
        if self._current_panel is not None:
            self._current_panel.destroy()
            self._current_panel = None

    def _show_home(self) -> None:
        self._clear_panel()

        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)
        self._current_panel = frame

        # 右上に管理者モードボタン（小さく配置）
        top_bar = ttk.Frame(frame)
        top_bar.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(
            top_bar,
            text="管理者モード",
            style="Small.TButton",
            command=self._show_admin_login,
        ).pack(side=tk.RIGHT)

        # 中央コンテンツ
        center = ttk.Frame(frame)
        center.place(relx=0.5, rely=0.45, anchor=tk.CENTER)

        ttk.Label(center, text=APP_TITLE, style="Title.TLabel").pack(pady=(0, 30))

        ttk.Button(
            center,
            text="アンケートに回答する",
            style="Big.TButton",
            command=self._show_response,
            width=30,
        ).pack(pady=10)

        ttk.Button(center, text="終了", command=self.root.quit, width=30).pack(
            pady=(30, 0)
        )

    def _show_response(self) -> None:
        self._clear_panel()
        panel = ResponsePanel(self.root, back_callback=self._show_home)
        panel.pack(fill=tk.BOTH, expand=True)
        self._current_panel = panel

    def _show_admin_login(self) -> None:
        AdminLoginDialog(self.root, on_success=self._show_admin)

    def _show_admin(self) -> None:
        self._clear_panel()
        panel = _AdminWithAggregate(self.root, back_callback=self._show_home)
        panel.pack(fill=tk.BOTH, expand=True)
        self._current_panel = panel

    def run(self) -> None:
        self.root.mainloop()


class _AdminWithAggregate(ttk.Frame):
    """管理者モード＋集計機能を統合したパネル。"""

    def __init__(self, parent: tk.Widget, back_callback):
        super().__init__(parent)
        self.back_callback = back_callback

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        admin_panel = AdminPanel(notebook, back_callback=back_callback)
        notebook.add(admin_panel, text="アンケート管理")

        agg_panel = AggregatePanel(notebook, back_callback=back_callback)
        notebook.add(agg_panel, text="集計・出力")


def main() -> None:
    app = HospitalSurveyApp()
    app.run()


if __name__ == "__main__":
    main()

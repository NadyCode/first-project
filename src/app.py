"""
病院アンケートシステム メインアプリケーション
管理者モード・回答者モードの切り替え画面を提供する。
起動時に共有フォルダへの接続を確認する。
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import src.config as config
from src.config import APP_TITLE, APP_VERSION
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

        self._check_data_connection()

    def _check_data_connection(self) -> None:
        """共有フォルダへの接続を確認し、問題があれば設定画面を表示する。"""
        data_dir = config.get_data_dir()

        if os.path.isdir(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            try:
                write_access_log()
            except Exception:
                pass
            self._show_home()
        else:
            self._show_connection_setup()

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
        settings = config.load_local_settings()
        settings["shared_data_dir"] = path
        config.save_local_settings(settings)
        config.reload_paths()

        try:
            write_access_log()
        except Exception:
            pass

        self._status_label.config(text="接続成功！", foreground="green")
        self.root.after(500, self._show_home)

    def _use_local_mode(self) -> None:
        local_dir = os.path.join(config.APP_DIR, "data")
        os.makedirs(local_dir, exist_ok=True)

        settings = config.load_local_settings()
        settings["shared_data_dir"] = local_dir
        config.save_local_settings(settings)
        config.reload_paths()

        try:
            write_access_log()
        except Exception:
            pass

        self._show_home()

    def _clear_panel(self) -> None:
        if self._current_panel is not None:
            self._current_panel.destroy()
            self._current_panel = None

    def _show_home(self) -> None:
        self._clear_panel()

        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)
        self._current_panel = frame

        center = ttk.Frame(frame)
        center.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        ttk.Label(center, text=APP_TITLE, style="Title.TLabel").pack(pady=(0, 10))
        ttk.Label(center, text=f"Version {APP_VERSION}").pack(pady=(0, 5))

        # 接続先表示
        ttk.Label(
            center,
            text=f"データ: {config.DATA_DIR}",
            style="Status.TLabel",
            foreground="gray",
        ).pack(pady=(0, 25))

        ttk.Button(
            center,
            text="アンケートに回答する",
            style="Big.TButton",
            command=self._show_response,
            width=30,
        ).pack(pady=10)

        ttk.Button(
            center,
            text="管理者モード（作成・集計）",
            style="Big.TButton",
            command=self._show_admin_login,
            width=30,
        ).pack(pady=10)

        btn_frame = ttk.Frame(center)
        btn_frame.pack(pady=(30, 0))

        ttk.Button(
            btn_frame, text="接続先変更", command=self._show_connection_setup
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(btn_frame, text="終了", command=self.root.quit).pack(
            side=tk.LEFT, padx=5
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

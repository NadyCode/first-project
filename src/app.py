"""
病院アンケートシステム メインアプリケーション
管理者モード・回答者モードの切り替え画面を提供する。
"""

import os
import tkinter as tk
from tkinter import ttk

from src.config import APP_TITLE, APP_VERSION, DATA_DIR
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

        # データフォルダの存在確認
        os.makedirs(DATA_DIR, exist_ok=True)

        # 起動ログ記録
        try:
            write_access_log()
        except Exception:
            pass  # ログ記録失敗はアプリ起動を妨げない

        # 現在表示中のパネル
        self._current_panel: tk.Widget | None = None

        # スタイル設定
        style = ttk.Style()
        style.configure("Title.TLabel", font=("", 20, "bold"))
        style.configure("Big.TButton", font=("", 12), padding=10)

        self._show_home()

    def _clear_panel(self) -> None:
        """現在のパネルをクリアする。"""
        if self._current_panel is not None:
            self._current_panel.destroy()
            self._current_panel = None

    def _show_home(self) -> None:
        """ホーム画面を表示する。"""
        self._clear_panel()

        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.BOTH, expand=True)
        self._current_panel = frame

        # タイトル
        center = ttk.Frame(frame)
        center.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        ttk.Label(center, text=APP_TITLE, style="Title.TLabel").pack(pady=(0, 10))
        ttk.Label(center, text=f"Version {APP_VERSION}").pack(pady=(0, 30))

        # モード選択ボタン
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

        ttk.Button(
            center,
            text="終了",
            command=self.root.quit,
            width=30,
        ).pack(pady=(30, 0))

    def _show_response(self) -> None:
        """回答者モードを表示する。"""
        self._clear_panel()
        panel = ResponsePanel(self.root, back_callback=self._show_home)
        panel.pack(fill=tk.BOTH, expand=True)
        self._current_panel = panel

    def _show_admin_login(self) -> None:
        """管理者ログインダイアログを表示する。"""
        AdminLoginDialog(self.root, on_success=self._show_admin)

    def _show_admin(self) -> None:
        """管理者モードを表示する（認証後）。"""
        self._clear_panel()
        panel = _AdminWithAggregate(self.root, back_callback=self._show_home)
        panel.pack(fill=tk.BOTH, expand=True)
        self._current_panel = panel

    def run(self) -> None:
        """アプリケーションを実行する。"""
        self.root.mainloop()


class _AdminWithAggregate(ttk.Frame):
    """管理者モード＋集計機能を統合したパネル。"""

    def __init__(self, parent: tk.Widget, back_callback):
        super().__init__(parent)
        self.back_callback = back_callback

        # 上部にモード切替タブ
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        # 管理者タブ
        admin_panel = AdminPanel(notebook, back_callback=back_callback)
        notebook.add(admin_panel, text="アンケート管理")

        # 集計タブ
        agg_panel = AggregatePanel(notebook, back_callback=back_callback)
        notebook.add(agg_panel, text="集計・出力")


def main() -> None:
    """エントリポイント。"""
    app = HospitalSurveyApp()
    app.run()


if __name__ == "__main__":
    main()

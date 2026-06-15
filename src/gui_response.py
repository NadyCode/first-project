"""
回答者モード画面モジュール
部署・氏名の連動選択、設問への回答、バリデーションを行う。
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from src.data_manager import (
    get_respondents,
    load_master_users,
    load_survey_config,
    save_answer,
)
from src.logger import write_action_log


class ResponsePanel(ttk.Frame):
    """回答者モードのメインパネル。"""

    def __init__(self, parent: tk.Widget, back_callback: Callable[[], None]):
        super().__init__(parent)
        self.back_callback = back_callback
        self._config = load_survey_config()
        self._departments = load_master_users()
        self._answer_widgets: dict[int, tk.Widget] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        # ヘッダー
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(header, text="アンケート回答", font=("", 16, "bold")).pack(
            side=tk.LEFT
        )
        ttk.Button(header, text="戻る", command=self.back_callback).pack(side=tk.RIGHT)

        # スクロール可能エリア
        canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)

        self.scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # マウスホイールスクロール対応
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # アンケートタイトル・説明
        title = self._config.get("title", "")
        desc = self._config.get("description", "")
        if title:
            ttk.Label(
                self.scroll_frame, text=title, font=("", 14, "bold")
            ).pack(anchor=tk.W, padx=10, pady=(10, 2))
        if desc:
            ttk.Label(
                self.scroll_frame, text=desc, wraplength=600
            ).pack(anchor=tk.W, padx=10, pady=(0, 10))

        # 参照ファイルリンク
        refs = self._config.get("reference_files", [])
        if refs:
            ref_frame = ttk.LabelFrame(
                self.scroll_frame, text="参照資料", padding=5
            )
            ref_frame.pack(fill=tk.X, padx=10, pady=5)
            for ref_path in refs:
                fname = os.path.basename(ref_path)
                link = ttk.Label(
                    ref_frame, text=f"📄 {fname}", foreground="blue", cursor="hand2"
                )
                link.pack(anchor=tk.W)
                link.bind(
                    "<Button-1>",
                    lambda e, p=ref_path: self._open_file(p),
                )

        # 部署・氏名選択
        id_frame = ttk.LabelFrame(self.scroll_frame, text="回答者情報", padding=10)
        id_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(id_frame, text="部署:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.dept_var = tk.StringVar()
        dept_list = sorted(self._departments.keys())
        self.dept_combo = ttk.Combobox(
            id_frame,
            textvariable=self.dept_var,
            values=dept_list,
            state="readonly",
            width=20,
        )
        self.dept_combo.grid(row=0, column=1, padx=5, pady=3)
        self.dept_combo.bind("<<ComboboxSelected>>", self._on_dept_selected)

        ttk.Label(id_frame, text="氏名:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.name_var = tk.StringVar()
        self.name_combo = ttk.Combobox(
            id_frame,
            textvariable=self.name_var,
            state="readonly",
            width=20,
        )
        self.name_combo.grid(row=0, column=3, padx=5, pady=3)
        self.name_combo.bind("<<ComboboxSelected>>", self._on_name_selected)

        self._already_answered_label = ttk.Label(
            id_frame, text="", foreground="orange"
        )
        self._already_answered_label.grid(row=1, column=0, columnspan=4, sticky=tk.W, padx=5)

        self._respondents = get_respondents()
        self._submission_allowed = True

        # 設問表示
        questions = self._config.get("questions", [])
        if not questions:
            ttk.Label(
                self.scroll_frame,
                text="現在、回答可能なアンケートはありません。",
                font=("", 12),
            ).pack(pady=20)
            return

        for q in questions:
            self._build_question_widget(q)

        # 送信ボタン
        ttk.Button(
            self.scroll_frame,
            text="回答を送信",
            command=self._submit,
        ).pack(pady=20)

    def _on_dept_selected(self, event=None) -> None:
        """部署選択時に氏名リストを連動更新する。"""
        dept = self.dept_var.get()
        names = self._departments.get(dept, [])
        self.name_combo["values"] = sorted(names)
        self.name_var.set("")
        self._already_answered_label.config(text="")
        self._submission_allowed = True

    def _on_name_selected(self, event=None) -> None:
        """氏名選択時に回答済みかどうかを確認する。"""
        dept = self.dept_var.get()
        name = self.name_var.get()
        if not dept or not name:
            return

        if (dept, name) in self._respondents:
            self._submission_allowed = False
            self._already_answered_label.config(text="※ 回答済みです")
            result = messagebox.askyesno(
                "回答済み",
                f"{name} さんは既に回答済みです。\n修正しますか？",
            )
            if result:
                self._submission_allowed = True
                self._already_answered_label.config(
                    text="※ 回答済み（修正モード）", foreground="blue"
                )
            else:
                self._already_answered_label.config(
                    text="※ 回答済みです", foreground="orange"
                )
        else:
            self._submission_allowed = True
            self._already_answered_label.config(text="")

    def _build_question_widget(self, q: dict) -> None:
        """設問タイプに応じたウィジェットを生成する。"""
        q_id = q["id"]
        required_mark = " *" if q.get("required") else ""

        frame = ttk.LabelFrame(
            self.scroll_frame,
            text=f"Q{q_id}{required_mark}",
            padding=10,
        )
        frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame, text=q["text"], wraplength=550).pack(anchor=tk.W, pady=(0, 5))

        if q["type"] == "single_choice":
            var = tk.StringVar()
            for choice in q.get("choices", []):
                ttk.Radiobutton(frame, text=choice, variable=var, value=choice).pack(
                    anchor=tk.W, padx=10
                )
            self._answer_widgets[q_id] = var

        elif q["type"] == "free_text":
            text_widget = tk.Text(frame, width=60, height=4)
            text_widget.pack(anchor=tk.W, padx=10)
            self._answer_widgets[q_id] = text_widget

    def _validate(self) -> list[str]:
        """入力バリデーション。エラーメッセージのリストを返す。"""
        errors: list[str] = []

        if not self.dept_var.get():
            errors.append("部署を選択してください。")
        if not self.name_var.get():
            errors.append("氏名を選択してください。")

        for q in self._config.get("questions", []):
            if not q.get("required"):
                continue
            q_id = q["id"]
            widget = self._answer_widgets.get(q_id)
            if widget is None:
                continue
            if isinstance(widget, tk.StringVar):
                if not widget.get():
                    errors.append(f"Q{q_id}: 回答を選択してください。")
            elif isinstance(widget, tk.Text):
                if not widget.get("1.0", tk.END).strip():
                    errors.append(f"Q{q_id}: 回答を入力してください。")

        return errors

    def _submit(self) -> None:
        """回答を送信する。"""
        if not self._submission_allowed:
            messagebox.showinfo(
                "送信不可", "回答済みのため送信できません。\n修正する場合は氏名を再度選択してください。"
            )
            return

        errors = self._validate()
        if errors:
            messagebox.showwarning("入力エラー", "\n".join(errors))
            return

        department = self.dept_var.get()
        name = self.name_var.get()

        answers: dict[int, str] = {}
        for q in self._config.get("questions", []):
            q_id = q["id"]
            widget = self._answer_widgets.get(q_id)
            if widget is None:
                continue
            if isinstance(widget, tk.StringVar):
                answers[q_id] = widget.get()
            elif isinstance(widget, tk.Text):
                answers[q_id] = widget.get("1.0", tk.END).strip()

        save_answer(department, name, answers)
        write_action_log(f"回答送信: {department}/{name}")
        messagebox.showinfo("送信完了", "回答を送信しました。ご協力ありがとうございます。")
        self.back_callback()

    @staticmethod
    def _open_file(path: str) -> None:
        """ローカルファイルをOSデフォルトアプリで開く。"""
        if not os.path.exists(path):
            messagebox.showerror("エラー", f"ファイルが見つかりません:\n{path}")
            return
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("エラー", f"ファイルを開けません:\n{e}")

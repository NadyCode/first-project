"""
回答者モード画面モジュール
アンケート選択、部署・氏名の連動選択、設問への回答、
期限・匿名・条件分岐・必須バリデーションに対応する。
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from src.data_manager import (
    get_survey_respondents,
    is_survey_open,
    list_active_surveys,
    load_master_users,
    load_survey,
    question_is_visible,
    save_survey_answer,
    survey_open_reason,
)
from src.logger import write_action_log

_RADIO_UNSELECTED = "__unselected__"


class ResponsePanel(ttk.Frame):
    """回答者モードのメインパネル。アンケート選択→回答フォーム。"""

    def __init__(self, parent: tk.Widget, back_callback: Callable[[], None]):
        super().__init__(parent)
        self.back_callback = back_callback
        self._departments = load_master_users()
        self._survey: dict | None = None
        self._answer_widgets: dict[int, object] = {}
        self._question_frames: dict[int, tk.Widget] = {}
        self._select_active_survey()

    # ------------------------------------------------------------------
    # アンケート選択
    # ------------------------------------------------------------------
    def _select_active_survey(self) -> None:
        active = list_active_surveys()
        if len(active) == 0:
            self._show_no_survey()
        elif len(active) == 1:
            self._survey = active[0]
            self._build_form()
        else:
            self._show_survey_chooser(active)

    def _show_no_survey(self) -> None:
        self._clear()
        header = self._make_header("アンケート回答")
        center = ttk.Frame(self)
        center.pack(expand=True)
        ttk.Label(
            center,
            text="現在、回答可能なアンケートはありません。",
            font=("", 13),
        ).pack(pady=40)

    def _show_survey_chooser(self, surveys: list[dict]) -> None:
        self._clear()
        self._make_header("アンケートを選択してください")
        center = ttk.Frame(self)
        center.pack(expand=True, fill=tk.BOTH, padx=40, pady=20)
        for s in surveys:
            text = s.get("title") or "(無題)"
            if s.get("end_date"):
                text += f"（締切: {s['end_date']}）"
            ttk.Button(
                center,
                text=text,
                width=50,
                command=lambda sid=s["id"]: self._open_survey(sid),
            ).pack(pady=6)

    def _open_survey(self, survey_id: str) -> None:
        self._survey = load_survey(survey_id)
        self._build_form()

    # ------------------------------------------------------------------
    # 共通
    # ------------------------------------------------------------------
    def _clear(self) -> None:
        for child in self.winfo_children():
            child.destroy()

    def _make_header(self, title: str) -> ttk.Frame:
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(header, text=title, font=("", 16, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="戻る", command=self.back_callback).pack(side=tk.RIGHT)
        return header

    # ------------------------------------------------------------------
    # 回答フォーム
    # ------------------------------------------------------------------
    def _build_form(self) -> None:
        self._clear()
        assert self._survey is not None
        survey = self._survey
        self._answer_widgets = {}
        self._question_frames = {}
        self._anonymous = bool(survey.get("anonymous"))

        # 期限の再確認（選択から時間が経過したケース対策）
        if not is_survey_open(survey):
            self._make_header("アンケート回答")
            ttk.Label(
                self, text=survey_open_reason(survey), font=("", 12), foreground="red"
            ).pack(pady=40)
            return

        title = survey.get("title", "")
        self._make_header(title or "アンケート回答")

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

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # 説明文
        desc = survey.get("description", "")
        if desc:
            ttk.Label(self.scroll_frame, text=desc, wraplength=600).pack(
                anchor=tk.W, padx=10, pady=(10, 5)
            )
        if survey.get("end_date"):
            ttk.Label(
                self.scroll_frame,
                text=f"回答締切: {survey['end_date']}",
                foreground="gray",
            ).pack(anchor=tk.W, padx=10)
        if self._anonymous:
            ttk.Label(
                self.scroll_frame,
                text="※ このアンケートは匿名です（氏名は記録されません）",
                foreground="blue",
            ).pack(anchor=tk.W, padx=10, pady=(5, 0))

        # 参照ファイル
        refs = survey.get("reference_files", [])
        if refs:
            ref_frame = ttk.LabelFrame(self.scroll_frame, text="参照資料", padding=5)
            ref_frame.pack(fill=tk.X, padx=10, pady=5)
            for ref_path in refs:
                fname = os.path.basename(ref_path)
                link = ttk.Label(
                    ref_frame, text=f"📄 {fname}", foreground="blue", cursor="hand2"
                )
                link.pack(anchor=tk.W)
                link.bind("<Button-1>", lambda e, p=ref_path: self._open_file(p))

        # 回答者情報
        id_frame = ttk.LabelFrame(self.scroll_frame, text="回答者情報", padding=10)
        id_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(id_frame, text="部署:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.dept_var = tk.StringVar()
        self.dept_combo = ttk.Combobox(
            id_frame,
            textvariable=self.dept_var,
            values=sorted(self._departments.keys()),
            state="readonly",
            width=20,
        )
        self.dept_combo.grid(row=0, column=1, padx=5, pady=3)
        self.dept_combo.bind("<<ComboboxSelected>>", self._on_dept_selected)

        self._submission_allowed = True
        if not self._anonymous:
            ttk.Label(id_frame, text="氏名:").grid(row=0, column=2, sticky=tk.W, padx=5)
            self.name_var = tk.StringVar()
            self.name_combo = ttk.Combobox(
                id_frame, textvariable=self.name_var, state="readonly", width=20
            )
            self.name_combo.grid(row=0, column=3, padx=5, pady=3)
            self.name_combo.bind("<<ComboboxSelected>>", self._on_name_selected)
            self._already_label = ttk.Label(id_frame, text="", foreground="orange")
            self._already_label.grid(row=1, column=0, columnspan=4, sticky=tk.W, padx=5)
            self._respondents = get_survey_respondents(survey["id"])
        else:
            self.name_var = tk.StringVar()
            self._respondents = set()

        # 設問
        questions = survey.get("questions", [])
        if not questions:
            ttk.Label(
                self.scroll_frame, text="設問が登録されていません。", font=("", 12)
            ).pack(pady=20)
            return

        q_container = ttk.Frame(self.scroll_frame)
        q_container.pack(fill=tk.X, padx=0, pady=0)
        q_container.columnconfigure(0, weight=1)
        for i, q in enumerate(questions):
            self._build_question_widget(q_container, q, i)

        self._refresh_visibility()

        ttk.Button(self.scroll_frame, text="回答を送信", command=self._submit).pack(
            pady=20
        )

    def _on_dept_selected(self, event=None) -> None:
        dept = self.dept_var.get()
        names = self._departments.get(dept, [])
        if not self._anonymous:
            self.name_combo["values"] = sorted(names)
            self.name_var.set("")
            self._already_label.config(text="")
            self._submission_allowed = True

    def _on_name_selected(self, event=None) -> None:
        dept = self.dept_var.get()
        name = self.name_var.get()
        if not dept or not name:
            return
        if (dept, name) in self._respondents:
            self._submission_allowed = False
            self._already_label.config(text="※ 回答済みです", foreground="orange")
            if messagebox.askyesno(
                "回答済み", f"{name} さんは既に回答済みです。\n修正しますか？"
            ):
                self._submission_allowed = True
                self._already_label.config(
                    text="※ 回答済み（修正モード）", foreground="blue"
                )
        else:
            self._submission_allowed = True
            self._already_label.config(text="")

    def _build_question_widget(self, container: tk.Widget, q: dict, row: int) -> None:
        q_id = q["id"]
        required_mark = " *" if q.get("required") else ""
        frame = ttk.LabelFrame(container, text=f"Q{q_id}{required_mark}", padding=10)
        frame.grid(row=row, column=0, sticky="ew", padx=10, pady=5)
        self._question_frames[q_id] = frame

        ttk.Label(frame, text=q["text"], wraplength=550).pack(anchor=tk.W, pady=(0, 5))

        if q["type"] == "single_choice":
            var = tk.StringVar(value=_RADIO_UNSELECTED)
            for choice in q.get("choices", []):
                ttk.Radiobutton(
                    frame,
                    text=choice,
                    variable=var,
                    value=choice,
                    command=self._refresh_visibility,
                ).pack(anchor=tk.W, padx=10)
            self._answer_widgets[q_id] = var
        elif q["type"] == "free_text":
            text_widget = tk.Text(frame, width=60, height=4)
            text_widget.pack(anchor=tk.W, padx=10)
            self._answer_widgets[q_id] = text_widget

    def _collect_answers(self) -> dict[int, str]:
        answers: dict[int, str] = {}
        for q_id, widget in self._answer_widgets.items():
            if isinstance(widget, tk.StringVar):
                val = widget.get()
                answers[q_id] = "" if val == _RADIO_UNSELECTED else val
            elif isinstance(widget, tk.Text):
                answers[q_id] = widget.get("1.0", tk.END).strip()
        return answers

    def _refresh_visibility(self) -> None:
        """条件分岐に従って設問の表示/非表示を切り替える。"""
        answers = self._collect_answers()
        for q in self._survey.get("questions", []):
            frame = self._question_frames.get(q["id"])
            if frame is None:
                continue
            if question_is_visible(q, answers):
                frame.grid()
            else:
                frame.grid_remove()

    def _validate(self) -> list[str]:
        errors: list[str] = []
        if not self.dept_var.get():
            errors.append("部署を選択してください。")
        if not self._anonymous and not self.name_var.get():
            errors.append("氏名を選択してください。")

        answers = self._collect_answers()
        for q in self._survey.get("questions", []):
            if not q.get("required"):
                continue
            if not question_is_visible(q, answers):
                continue  # 非表示の設問は必須対象外
            q_id = q["id"]
            val = answers.get(q_id, "")
            if not val:
                errors.append(f"Q{q_id}: 回答してください。")
        return errors

    def _submit(self) -> None:
        if not self._anonymous and not self._submission_allowed:
            messagebox.showinfo(
                "送信不可",
                "回答済みのため送信できません。\n修正する場合は氏名を再度選択してください。",
            )
            return

        errors = self._validate()
        if errors:
            messagebox.showwarning("入力エラー", "\n".join(errors))
            return

        department = self.dept_var.get()
        name = self.name_var.get()
        answers = self._collect_answers()
        # 非表示設問は記録しない
        visible_answers = {
            q["id"]: answers.get(q["id"], "")
            for q in self._survey.get("questions", [])
            if question_is_visible(q, answers)
        }

        save_survey_answer(
            self._survey["id"], department, name, visible_answers, anonymous=self._anonymous
        )
        who = "匿名" if self._anonymous else f"{department}/{name}"
        write_action_log(f"回答送信[{self._survey['id']}]: {who}")
        messagebox.showinfo("送信完了", "回答を送信しました。ご協力ありがとうございます。")
        self.back_callback()

    @staticmethod
    def _open_file(path: str) -> None:
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

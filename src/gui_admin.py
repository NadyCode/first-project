"""
管理者モード画面モジュール
アンケートの作成・編集、パスワード設定、職員マスター管理を行う。
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

from src.data_manager import (
    hash_password,
    load_master_users,
    load_survey_config,
    save_master_users,
    save_survey_config,
)
from src.logger import write_action_log


class AdminLoginDialog(tk.Toplevel):
    """管理者パスワード入力ダイアログ。"""

    def __init__(self, parent: tk.Widget, on_success: Callable[[], None]):
        super().__init__(parent)
        self.title("管理者認証")
        self.resizable(False, False)
        self.grab_set()
        self.on_success = on_success

        self._config = load_survey_config()

        frame = ttk.Frame(self, padding=20)
        frame.pack()

        ttk.Label(frame, text="管理者パスワードを入力してください:").pack(pady=(0, 10))
        self.pw_var = tk.StringVar()
        pw_entry = ttk.Entry(frame, textvariable=self.pw_var, show="*", width=30)
        pw_entry.pack(pady=(0, 10))
        pw_entry.focus_set()
        pw_entry.bind("<Return>", lambda _: self._verify())

        ttk.Button(frame, text="ログイン", command=self._verify).pack()

        # パスワード未設定の場合は直接通す
        if not self._config.get("admin_password_hash"):
            self.destroy()
            self.on_success()

    def _verify(self) -> None:
        pw = self.pw_var.get()
        stored = self._config.get("admin_password_hash", "")
        if not stored or hash_password(pw) == stored:
            write_action_log("管理者ログイン成功")
            self.destroy()
            self.on_success()
        else:
            messagebox.showerror("認証エラー", "パスワードが正しくありません。", parent=self)


class AdminPanel(ttk.Frame):
    """管理者モードのメインパネル。"""

    def __init__(self, parent: tk.Widget, back_callback: Callable[[], None]):
        super().__init__(parent)
        self.back_callback = back_callback
        self._config = load_survey_config()
        self._build_ui()

    def _build_ui(self) -> None:
        # ヘッダー
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(header, text="管理者モード", font=("", 16, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="戻る", command=self.back_callback).pack(side=tk.RIGHT)

        # タブ
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # タブ1: アンケート設定
        self.survey_tab = ttk.Frame(notebook)
        notebook.add(self.survey_tab, text="アンケート設定")
        self._build_survey_tab()

        # タブ2: 設問編集
        self.questions_tab = ttk.Frame(notebook)
        notebook.add(self.questions_tab, text="設問編集")
        self._build_questions_tab()

        # タブ3: 職員マスター管理
        self.master_tab = ttk.Frame(notebook)
        notebook.add(self.master_tab, text="職員マスター")
        self._build_master_tab()

        # タブ4: パスワード設定
        self.pw_tab = ttk.Frame(notebook)
        notebook.add(self.pw_tab, text="パスワード設定")
        self._build_password_tab()

    # ------------------------------------------------------------------
    # アンケート基本設定タブ
    # ------------------------------------------------------------------
    def _build_survey_tab(self) -> None:
        frame = ttk.LabelFrame(self.survey_tab, text="基本情報", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(frame, text="タイトル:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.title_var = tk.StringVar(value=self._config.get("title", ""))
        ttk.Entry(frame, textvariable=self.title_var, width=60).grid(
            row=0, column=1, sticky=tk.W, pady=2
        )

        ttk.Label(frame, text="説明文:").grid(row=1, column=0, sticky=tk.NW, pady=2)
        self.desc_text = tk.Text(frame, width=60, height=4)
        self.desc_text.grid(row=1, column=1, sticky=tk.W, pady=2)
        self.desc_text.insert("1.0", self._config.get("description", ""))

        # 参照ファイル
        ref_frame = ttk.LabelFrame(self.survey_tab, text="参照ファイル（PDF等）", padding=10)
        ref_frame.pack(fill=tk.X, padx=10, pady=5)

        self.ref_listbox = tk.Listbox(ref_frame, height=4, width=70)
        self.ref_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        for ref in self._config.get("reference_files", []):
            self.ref_listbox.insert(tk.END, ref)

        btn_frame = ttk.Frame(ref_frame)
        btn_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="追加", command=self._add_reference).pack(pady=2)
        ttk.Button(btn_frame, text="削除", command=self._remove_reference).pack(pady=2)

        # 保存ボタン
        ttk.Button(
            self.survey_tab, text="基本情報を保存", command=self._save_survey_info
        ).pack(pady=10)

    def _add_reference(self) -> None:
        path = filedialog.askopenfilename(
            title="参照ファイルを選択",
            filetypes=[("PDF", "*.pdf"), ("すべて", "*.*")],
        )
        if path:
            self.ref_listbox.insert(tk.END, path)

    def _remove_reference(self) -> None:
        sel = self.ref_listbox.curselection()
        if sel:
            self.ref_listbox.delete(sel[0])

    def _save_survey_info(self) -> None:
        self._config["title"] = self.title_var.get().strip()
        self._config["description"] = self.desc_text.get("1.0", tk.END).strip()
        refs = list(self.ref_listbox.get(0, tk.END))
        self._config["reference_files"] = refs
        save_survey_config(self._config)
        write_action_log("アンケート基本情報保存")
        messagebox.showinfo("保存完了", "アンケートの基本情報を保存しました。")

    # ------------------------------------------------------------------
    # 設問編集タブ
    # ------------------------------------------------------------------
    def _build_questions_tab(self) -> None:
        # 設問一覧
        list_frame = ttk.Frame(self.questions_tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.q_tree = ttk.Treeview(
            list_frame,
            columns=("id", "type", "required", "text"),
            show="headings",
            height=8,
        )
        self.q_tree.heading("id", text="ID")
        self.q_tree.heading("type", text="タイプ")
        self.q_tree.heading("required", text="必須")
        self.q_tree.heading("text", text="設問文")
        self.q_tree.column("id", width=40)
        self.q_tree.column("type", width=100)
        self.q_tree.column("required", width=50)
        self.q_tree.column("text", width=400)
        self.q_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.q_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.q_tree.configure(yscrollcommand=scrollbar.set)

        self._refresh_question_list()

        # 操作ボタン
        btn_frame = ttk.Frame(self.questions_tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="設問を追加", command=self._add_question).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="設問を編集", command=self._edit_question).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(btn_frame, text="設問を削除", command=self._delete_question).pack(
            side=tk.LEFT, padx=5
        )

    def _refresh_question_list(self) -> None:
        for item in self.q_tree.get_children():
            self.q_tree.delete(item)
        for q in self._config.get("questions", []):
            type_label = {"single_choice": "単一選択", "free_text": "自由記述"}.get(
                q["type"], q["type"]
            )
            required = "○" if q.get("required") else ""
            self.q_tree.insert("", tk.END, values=(q["id"], type_label, required, q["text"]))

    def _add_question(self) -> None:
        QuestionEditDialog(self, self._config, question=None, on_save=self._on_question_saved)

    def _edit_question(self) -> None:
        sel = self.q_tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "編集する設問を選択してください。")
            return
        q_id = int(self.q_tree.item(sel[0])["values"][0])
        question = next(
            (q for q in self._config["questions"] if q["id"] == q_id), None
        )
        if question:
            QuestionEditDialog(
                self, self._config, question=question, on_save=self._on_question_saved
            )

    def _delete_question(self) -> None:
        sel = self.q_tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "削除する設問を選択してください。")
            return
        q_id = int(self.q_tree.item(sel[0])["values"][0])
        if messagebox.askyesno("確認", f"設問ID {q_id} を削除しますか？"):
            self._config["questions"] = [
                q for q in self._config["questions"] if q["id"] != q_id
            ]
            save_survey_config(self._config)
            write_action_log(f"設問削除: ID={q_id}")
            self._refresh_question_list()

    def _on_question_saved(self) -> None:
        save_survey_config(self._config)
        self._refresh_question_list()

    # ------------------------------------------------------------------
    # 職員マスター管理タブ
    # ------------------------------------------------------------------
    def _build_master_tab(self) -> None:
        self._departments = load_master_users()

        # 一覧表示
        list_frame = ttk.Frame(self.master_tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.m_tree = ttk.Treeview(
            list_frame, columns=("dept", "name"), show="headings", height=10
        )
        self.m_tree.heading("dept", text="部署")
        self.m_tree.heading("name", text="氏名")
        self.m_tree.column("dept", width=150)
        self.m_tree.column("name", width=200)
        self.m_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.m_tree.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.m_tree.configure(yscrollcommand=scrollbar.set)

        self._refresh_master_list()

        # 入力フォーム
        form_frame = ttk.LabelFrame(self.master_tab, text="職員追加", padding=10)
        form_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(form_frame, text="部署:").grid(row=0, column=0, sticky=tk.W)
        self.new_dept_var = tk.StringVar()
        dept_combo = ttk.Combobox(
            form_frame,
            textvariable=self.new_dept_var,
            values=list(self._departments.keys()),
            width=20,
        )
        dept_combo.grid(row=0, column=1, padx=5)

        ttk.Label(form_frame, text="氏名:").grid(row=0, column=2, sticky=tk.W)
        self.new_name_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.new_name_var, width=20).grid(
            row=0, column=3, padx=5
        )

        ttk.Button(form_frame, text="追加", command=self._add_staff).grid(
            row=0, column=4, padx=5
        )
        ttk.Button(
            self.master_tab, text="選択した職員を削除", command=self._delete_staff
        ).pack(pady=5)

    def _refresh_master_list(self) -> None:
        for item in self.m_tree.get_children():
            self.m_tree.delete(item)
        for dept, names in self._departments.items():
            for name in names:
                self.m_tree.insert("", tk.END, values=(dept, name))

    def _add_staff(self) -> None:
        dept = self.new_dept_var.get().strip()
        name = self.new_name_var.get().strip()
        if not dept or not name:
            messagebox.showwarning("入力不足", "部署と氏名を入力してください。")
            return
        self._departments.setdefault(dept, []).append(name)
        save_master_users(self._departments)
        write_action_log(f"職員追加: {dept}/{name}")
        self._refresh_master_list()
        self.new_name_var.set("")

    def _delete_staff(self) -> None:
        sel = self.m_tree.selection()
        if not sel:
            messagebox.showwarning("選択なし", "削除する職員を選択してください。")
            return
        values = self.m_tree.item(sel[0])["values"]
        dept, name = str(values[0]), str(values[1])
        if messagebox.askyesno("確認", f"{dept} / {name} を削除しますか？"):
            if dept in self._departments and name in self._departments[dept]:
                self._departments[dept].remove(name)
                if not self._departments[dept]:
                    del self._departments[dept]
            save_master_users(self._departments)
            write_action_log(f"職員削除: {dept}/{name}")
            self._refresh_master_list()

    # ------------------------------------------------------------------
    # パスワード設定タブ
    # ------------------------------------------------------------------
    def _build_password_tab(self) -> None:
        frame = ttk.LabelFrame(self.pw_tab, text="管理者パスワード設定", padding=20)
        frame.pack(padx=20, pady=20)

        has_pw = bool(self._config.get("admin_password_hash"))
        status = "設定済み" if has_pw else "未設定"
        ttk.Label(frame, text=f"現在の状態: {status}").grid(
            row=0, column=0, columnspan=2, pady=5
        )

        if has_pw:
            ttk.Label(frame, text="現在のパスワード:").grid(row=1, column=0, sticky=tk.W)
            self.current_pw_var = tk.StringVar()
            ttk.Entry(frame, textvariable=self.current_pw_var, show="*", width=30).grid(
                row=1, column=1, pady=2
            )
        else:
            self.current_pw_var = tk.StringVar()

        ttk.Label(frame, text="新しいパスワード:").grid(row=2, column=0, sticky=tk.W)
        self.new_pw_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.new_pw_var, show="*", width=30).grid(
            row=2, column=1, pady=2
        )

        ttk.Label(frame, text="新しいパスワード(確認):").grid(row=3, column=0, sticky=tk.W)
        self.confirm_pw_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.confirm_pw_var, show="*", width=30).grid(
            row=3, column=1, pady=2
        )

        ttk.Button(frame, text="パスワードを設定", command=self._set_password).grid(
            row=4, column=0, columnspan=2, pady=10
        )

        ttk.Button(frame, text="パスワードを解除", command=self._clear_password).grid(
            row=5, column=0, columnspan=2
        )

    def _set_password(self) -> None:
        stored = self._config.get("admin_password_hash", "")
        if stored:
            if hash_password(self.current_pw_var.get()) != stored:
                messagebox.showerror("エラー", "現在のパスワードが正しくありません。")
                return
        new_pw = self.new_pw_var.get()
        confirm = self.confirm_pw_var.get()
        if not new_pw:
            messagebox.showwarning("入力不足", "新しいパスワードを入力してください。")
            return
        if new_pw != confirm:
            messagebox.showerror("エラー", "パスワードが一致しません。")
            return
        self._config["admin_password_hash"] = hash_password(new_pw)
        save_survey_config(self._config)
        write_action_log("管理者パスワード変更")
        messagebox.showinfo("完了", "パスワードを設定しました。")

    def _clear_password(self) -> None:
        stored = self._config.get("admin_password_hash", "")
        if stored:
            if hash_password(self.current_pw_var.get()) != stored:
                messagebox.showerror("エラー", "現在のパスワードが正しくありません。")
                return
        self._config["admin_password_hash"] = ""
        save_survey_config(self._config)
        write_action_log("管理者パスワード解除")
        messagebox.showinfo("完了", "パスワードを解除しました。")


class QuestionEditDialog(tk.Toplevel):
    """設問の追加・編集ダイアログ。"""

    def __init__(
        self,
        parent: tk.Widget,
        config: dict[str, Any],
        question: dict[str, Any] | None,
        on_save: Callable[[], None],
    ):
        super().__init__(parent)
        self.title("設問編集" if question else "設問追加")
        self.resizable(False, False)
        self.grab_set()

        self._config = config
        self._question = question
        self._on_save = on_save
        self._is_new = question is None

        frame = ttk.Frame(self, padding=15)
        frame.pack()

        # 設問タイプ
        ttk.Label(frame, text="タイプ:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.type_var = tk.StringVar(
            value=question["type"] if question else "single_choice"
        )
        type_combo = ttk.Combobox(
            frame,
            textvariable=self.type_var,
            values=["single_choice", "free_text"],
            state="readonly",
            width=20,
        )
        type_combo.grid(row=0, column=1, sticky=tk.W, pady=3)
        type_combo.bind("<<ComboboxSelected>>", self._on_type_change)

        # 必須
        self.required_var = tk.BooleanVar(
            value=question.get("required", True) if question else True
        )
        ttk.Checkbutton(frame, text="必須", variable=self.required_var).grid(
            row=0, column=2, padx=10
        )

        # 設問文
        ttk.Label(frame, text="設問文:").grid(row=1, column=0, sticky=tk.NW, pady=3)
        self.text_entry = tk.Text(frame, width=50, height=3)
        self.text_entry.grid(row=1, column=1, columnspan=2, pady=3)
        if question:
            self.text_entry.insert("1.0", question.get("text", ""))

        # 選択肢（single_choiceの場合）
        self.choices_label = ttk.Label(frame, text="選択肢（改行区切り）:")
        self.choices_label.grid(row=2, column=0, sticky=tk.NW, pady=3)
        self.choices_text = tk.Text(frame, width=50, height=5)
        self.choices_text.grid(row=2, column=1, columnspan=2, pady=3)
        if question and question.get("choices"):
            self.choices_text.insert("1.0", "\n".join(question["choices"]))

        self._on_type_change()

        # 保存ボタン
        ttk.Button(frame, text="保存", command=self._save).grid(
            row=3, column=1, pady=10
        )

    def _on_type_change(self, event=None) -> None:
        is_choice = self.type_var.get() == "single_choice"
        state = tk.NORMAL if is_choice else tk.DISABLED
        self.choices_text.configure(state=state)

    def _save(self) -> None:
        q_type = self.type_var.get()
        text = self.text_entry.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("入力不足", "設問文を入力してください。", parent=self)
            return

        choices = []
        if q_type == "single_choice":
            raw = self.choices_text.get("1.0", tk.END).strip()
            choices = [c.strip() for c in raw.split("\n") if c.strip()]
            if len(choices) < 2:
                messagebox.showwarning(
                    "入力不足", "選択肢を2つ以上入力してください。", parent=self
                )
                return

        if self._is_new:
            existing_ids = [q["id"] for q in self._config["questions"]]
            new_id = max(existing_ids) + 1 if existing_ids else 1
            new_q: dict[str, Any] = {
                "id": new_id,
                "type": q_type,
                "required": self.required_var.get(),
                "text": text,
            }
            if choices:
                new_q["choices"] = choices
            self._config["questions"].append(new_q)
            write_action_log(f"設問追加: ID={new_id}")
        else:
            self._question["type"] = q_type
            self._question["required"] = self.required_var.get()
            self._question["text"] = text
            if choices:
                self._question["choices"] = choices
            elif "choices" in self._question:
                del self._question["choices"]
            write_action_log(f"設問編集: ID={self._question['id']}")

        self._on_save()
        self.destroy()

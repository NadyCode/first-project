"""
管理者モード画面モジュール
複数アンケートの作成・編集・公開管理、設問編集（並び替え・条件分岐）、
期限・匿名設定、職員マスター管理、グローバルパスワード、バージョン管理を行う。
"""

import datetime as _dt
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Callable

import src.config as config
from src.data_manager import (
    archive_survey,
    create_survey,
    delete_survey,
    get_admin_password_hash,
    hash_password,
    list_surveys,
    load_master_users,
    load_survey,
    load_survey_answers,
    load_version_info,
    save_master_users,
    save_survey,
    save_version_info,
    set_admin_password,
    unarchive_survey,
)
from src.logger import write_action_log


def _valid_date(value: str) -> bool:
    """空文字または YYYY-MM-DD 形式なら True。"""
    value = value.strip()
    if not value:
        return True
    try:
        _dt.datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


class AdminLoginDialog(tk.Toplevel):
    """管理者パスワード入力ダイアログ（グローバルパスワード）。"""

    def __init__(self, parent: tk.Widget, on_success: Callable[[], None]):
        super().__init__(parent)
        self.title("管理者認証")
        self.resizable(False, False)
        self.grab_set()
        self.on_success = on_success
        self._stored = get_admin_password_hash()

        if not self._stored:
            self.destroy()
            self.on_success()
            return

        frame = ttk.Frame(self, padding=20)
        frame.pack()
        ttk.Label(frame, text="管理者パスワードを入力してください:").pack(pady=(0, 10))
        self.pw_var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=self.pw_var, show="*", width=30)
        entry.pack(pady=(0, 10))
        entry.focus_set()
        entry.bind("<Return>", lambda _: self._verify())
        ttk.Button(frame, text="ログイン", command=self._verify).pack()

    def _verify(self) -> None:
        if hash_password(self.pw_var.get()) == self._stored:
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
        self._current_id: str | None = None
        surveys = list_surveys()
        if surveys:
            self._current_id = surveys[0]["id"]
        self._build_ui()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self._notebook = notebook

        self.list_tab = ttk.Frame(notebook)
        notebook.add(self.list_tab, text="アンケート一覧")
        self._build_list_tab()

        self.basic_tab = ttk.Frame(notebook)
        notebook.add(self.basic_tab, text="基本設定")

        self.questions_tab = ttk.Frame(notebook)
        notebook.add(self.questions_tab, text="設問編集")

        self.master_tab = ttk.Frame(notebook)
        notebook.add(self.master_tab, text="職員マスター")
        self._build_master_tab()

        self.pw_tab = ttk.Frame(notebook)
        notebook.add(self.pw_tab, text="パスワード設定")
        self._build_password_tab()

        self.version_tab = ttk.Frame(notebook)
        notebook.add(self.version_tab, text="バージョン管理")
        self._build_version_tab()

        self._refresh_current()

    # ------------------------------------------------------------------
    # アンケート一覧タブ
    # ------------------------------------------------------------------
    def _build_list_tab(self) -> None:
        toolbar = ttk.Frame(self.list_tab)
        toolbar.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(toolbar, text="アンケート一覧", font=("", 13, "bold")).pack(side=tk.LEFT)
        ttk.Button(toolbar, text="新規作成", command=self._create_survey).pack(
            side=tk.RIGHT, padx=2
        )

        self.s_tree = ttk.Treeview(
            self.list_tab,
            columns=("title", "status", "period", "anon", "count"),
            show="headings",
            height=10,
        )
        for col, txt, w in [
            ("title", "タイトル", 220),
            ("status", "状態", 70),
            ("period", "回答期間", 180),
            ("anon", "匿名", 50),
            ("count", "回答数", 60),
        ]:
            self.s_tree.heading(col, text=txt)
            self.s_tree.column(col, width=w)
        self.s_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.s_tree.bind("<<TreeviewSelect>>", self._on_survey_selected)

        btns = ttk.Frame(self.list_tab)
        btns.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btns, text="この内容を編集", command=self._edit_selected).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="公開/非公開を切替", command=self._toggle_archive).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btns, text="削除", command=self._delete_selected).pack(
            side=tk.LEFT, padx=2
        )

        self._refresh_survey_list()

    def _refresh_survey_list(self) -> None:
        for item in self.s_tree.get_children():
            self.s_tree.delete(item)
        for s in list_surveys():
            status = "公開中" if s.get("status") == "active" else "非公開"
            start = s.get("start_date", "") or "—"
            end = s.get("end_date", "") or "—"
            period = f"{start} 〜 {end}"
            anon = "○" if s.get("anonymous") else ""
            count = len(load_survey_answers(s["id"]))
            self.s_tree.insert(
                "", tk.END, iid=s["id"],
                values=(s.get("title", ""), status, period, anon, count),
            )
        if self._current_id and self.s_tree.exists(self._current_id):
            self.s_tree.selection_set(self._current_id)

    def _selected_survey_id(self) -> str | None:
        sel = self.s_tree.selection()
        return sel[0] if sel else None

    def _on_survey_selected(self, event=None) -> None:
        sid = self._selected_survey_id()
        if sid:
            self._current_id = sid

    def _create_survey(self) -> None:
        sid = create_survey()
        write_action_log(f"アンケート新規作成: {sid}")
        self._current_id = sid
        self._refresh_survey_list()
        self._refresh_current()
        messagebox.showinfo("作成完了", "新しいアンケートを作成しました。「基本設定」で内容を編集してください。")

    def _edit_selected(self) -> None:
        sid = self._selected_survey_id()
        if not sid:
            messagebox.showwarning("選択なし", "アンケートを選択してください。")
            return
        self._current_id = sid
        self._refresh_current()
        self._notebook.select(self.basic_tab)

    def _toggle_archive(self) -> None:
        sid = self._selected_survey_id()
        if not sid:
            messagebox.showwarning("選択なし", "アンケートを選択してください。")
            return
        cfg = load_survey(sid)
        if cfg.get("status") == "active":
            archive_survey(sid)
            write_action_log(f"アンケート非公開: {sid}")
        else:
            unarchive_survey(sid)
            write_action_log(f"アンケート公開: {sid}")
        self._refresh_survey_list()

    def _delete_selected(self) -> None:
        sid = self._selected_survey_id()
        if not sid:
            messagebox.showwarning("選択なし", "アンケートを選択してください。")
            return
        cfg = load_survey(sid)
        if messagebox.askyesno(
            "確認",
            f"「{cfg.get('title', '')}」を回答データごと完全に削除します。\nよろしいですか？",
        ):
            delete_survey(sid)
            write_action_log(f"アンケート削除: {sid}")
            if self._current_id == sid:
                remaining = list_surveys()
                self._current_id = remaining[0]["id"] if remaining else None
            self._refresh_survey_list()
            self._refresh_current()

    # ------------------------------------------------------------------
    # 現在の編集対象を各タブへ反映
    # ------------------------------------------------------------------
    def _refresh_current(self) -> None:
        self._build_basic_tab()
        self._build_questions_tab()

    def _current_survey(self) -> dict[str, Any] | None:
        if not self._current_id:
            return None
        return load_survey(self._current_id)

    # ------------------------------------------------------------------
    # 基本設定タブ
    # ------------------------------------------------------------------
    def _build_basic_tab(self) -> None:
        for child in self.basic_tab.winfo_children():
            child.destroy()

        cfg = self._current_survey()
        if cfg is None:
            ttk.Label(
                self.basic_tab,
                text="編集するアンケートがありません。\n「アンケート一覧」で新規作成してください。",
                font=("", 12),
            ).pack(pady=40)
            return

        ttk.Label(
            self.basic_tab, text=f"編集中: {cfg.get('title', '')}", font=("", 11, "bold")
        ).pack(anchor=tk.W, padx=10, pady=(8, 2))

        frame = ttk.LabelFrame(self.basic_tab, text="基本情報", padding=10)
        frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame, text="タイトル:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.title_var = tk.StringVar(value=cfg.get("title", ""))
        ttk.Entry(frame, textvariable=self.title_var, width=55).grid(
            row=0, column=1, columnspan=3, sticky=tk.W, pady=2
        )

        ttk.Label(frame, text="説明文:").grid(row=1, column=0, sticky=tk.NW, pady=2)
        self.desc_text = tk.Text(frame, width=55, height=3)
        self.desc_text.grid(row=1, column=1, columnspan=3, sticky=tk.W, pady=2)
        self.desc_text.insert("1.0", cfg.get("description", ""))

        ttk.Label(frame, text="回答開始日:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.start_var = tk.StringVar(value=cfg.get("start_date", ""))
        ttk.Entry(frame, textvariable=self.start_var, width=15).grid(
            row=2, column=1, sticky=tk.W, pady=2
        )
        ttk.Label(frame, text="回答終了日:").grid(row=2, column=2, sticky=tk.W, pady=2)
        self.end_var = tk.StringVar(value=cfg.get("end_date", ""))
        ttk.Entry(frame, textvariable=self.end_var, width=15).grid(
            row=2, column=3, sticky=tk.W, pady=2
        )
        ttk.Label(
            frame, text="（空欄=制限なし / 形式: 2026-01-31）", foreground="gray"
        ).grid(row=3, column=1, columnspan=3, sticky=tk.W)

        self.anon_var = tk.BooleanVar(value=cfg.get("anonymous", False))
        ttk.Checkbutton(
            frame, text="匿名アンケートにする（氏名を記録しない）", variable=self.anon_var
        ).grid(row=4, column=0, columnspan=4, sticky=tk.W, pady=4)

        # 参照ファイル
        ref_frame = ttk.LabelFrame(self.basic_tab, text="参照ファイル（PDF等）", padding=10)
        ref_frame.pack(fill=tk.X, padx=10, pady=5)
        self.ref_listbox = tk.Listbox(ref_frame, height=3, width=65)
        self.ref_listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        for ref in cfg.get("reference_files", []):
            self.ref_listbox.insert(tk.END, ref)
        rbtn = ttk.Frame(ref_frame)
        rbtn.pack(side=tk.RIGHT, padx=5)
        ttk.Button(rbtn, text="追加", command=self._add_reference).pack(pady=2)
        ttk.Button(rbtn, text="削除", command=self._remove_reference).pack(pady=2)

        ttk.Button(self.basic_tab, text="基本情報を保存", command=self._save_basic).pack(
            pady=10
        )

    def _add_reference(self) -> None:
        path = filedialog.askopenfilename(
            title="参照ファイルを選択", filetypes=[("PDF", "*.pdf"), ("すべて", "*.*")]
        )
        if path:
            self.ref_listbox.insert(tk.END, path)

    def _remove_reference(self) -> None:
        sel = self.ref_listbox.curselection()
        if sel:
            self.ref_listbox.delete(sel[0])

    def _save_basic(self) -> None:
        if not _valid_date(self.start_var.get()) or not _valid_date(self.end_var.get()):
            messagebox.showerror("入力エラー", "日付は YYYY-MM-DD 形式で入力してください。")
            return
        cfg = self._current_survey()
        if cfg is None:
            return
        cfg["title"] = self.title_var.get().strip()
        cfg["description"] = self.desc_text.get("1.0", tk.END).strip()
        cfg["start_date"] = self.start_var.get().strip()
        cfg["end_date"] = self.end_var.get().strip()
        cfg["anonymous"] = self.anon_var.get()
        cfg["reference_files"] = list(self.ref_listbox.get(0, tk.END))
        save_survey(cfg)
        write_action_log(f"アンケート基本情報保存: {cfg['id']}")
        self._refresh_survey_list()
        messagebox.showinfo("保存完了", "基本情報を保存しました。")

    # ------------------------------------------------------------------
    # 設問編集タブ
    # ------------------------------------------------------------------
    def _build_questions_tab(self) -> None:
        for child in self.questions_tab.winfo_children():
            child.destroy()

        cfg = self._current_survey()
        if cfg is None:
            ttk.Label(
                self.questions_tab,
                text="編集するアンケートがありません。",
                font=("", 12),
            ).pack(pady=40)
            return

        list_frame = ttk.Frame(self.questions_tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.q_tree = ttk.Treeview(
            list_frame,
            columns=("id", "type", "required", "cond", "text"),
            show="headings",
            height=8,
        )
        for col, txt, w in [
            ("id", "ID", 40),
            ("type", "タイプ", 90),
            ("required", "必須", 45),
            ("cond", "条件", 110),
            ("text", "設問文", 330),
        ]:
            self.q_tree.heading(col, text=txt)
            self.q_tree.column(col, width=w)
        self.q_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.q_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.q_tree.configure(yscrollcommand=scrollbar.set)
        self._refresh_question_list()

        btn_frame = ttk.Frame(self.questions_tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame, text="設問を追加", command=self._add_question).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="編集", command=self._edit_question).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="削除", command=self._delete_question).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="▲ 上へ", command=lambda: self._move_question(-1)).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(btn_frame, text="▼ 下へ", command=lambda: self._move_question(1)).pack(
            side=tk.LEFT, padx=2
        )

    def _refresh_question_list(self) -> None:
        for item in self.q_tree.get_children():
            self.q_tree.delete(item)
        cfg = self._current_survey()
        if cfg is None:
            return
        id_to_text = {q["id"]: q["text"] for q in cfg.get("questions", [])}
        for idx, q in enumerate(cfg.get("questions", [])):
            type_label = {"single_choice": "単一選択", "free_text": "自由記述"}.get(
                q["type"], q["type"]
            )
            required = "○" if q.get("required") else ""
            cond = q.get("condition")
            if cond and cond.get("question_id"):
                tgt = cond["question_id"]
                cond_text = f"Q{tgt}=「{cond.get('equals', '')}」"
            else:
                cond_text = ""
            self.q_tree.insert(
                "", tk.END, iid=str(idx),
                values=(q["id"], type_label, required, cond_text, q["text"]),
            )

    def _selected_question_index(self) -> int | None:
        sel = self.q_tree.selection()
        return int(sel[0]) if sel else None

    def _add_question(self) -> None:
        cfg = self._current_survey()
        if cfg is None:
            return
        QuestionEditDialog(self, cfg, question=None, on_save=self._on_question_saved)

    def _edit_question(self) -> None:
        idx = self._selected_question_index()
        if idx is None:
            messagebox.showwarning("選択なし", "編集する設問を選択してください。")
            return
        cfg = self._current_survey()
        question = cfg["questions"][idx]
        QuestionEditDialog(self, cfg, question=question, on_save=self._on_question_saved)

    def _delete_question(self) -> None:
        idx = self._selected_question_index()
        if idx is None:
            messagebox.showwarning("選択なし", "削除する設問を選択してください。")
            return
        cfg = self._current_survey()
        q_id = cfg["questions"][idx]["id"]
        if messagebox.askyesno("確認", f"設問ID {q_id} を削除しますか？"):
            del cfg["questions"][idx]
            save_survey(cfg)
            write_action_log(f"設問削除[{cfg['id']}]: ID={q_id}")
            self._refresh_question_list()

    def _move_question(self, direction: int) -> None:
        idx = self._selected_question_index()
        if idx is None:
            messagebox.showwarning("選択なし", "並び替える設問を選択してください。")
            return
        cfg = self._current_survey()
        questions = cfg["questions"]
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(questions):
            return
        questions[idx], questions[new_idx] = questions[new_idx], questions[idx]
        save_survey(cfg)
        write_action_log(f"設問並び替え[{cfg['id']}]")
        self._refresh_question_list()
        self.q_tree.selection_set(str(new_idx))

    def _on_question_saved(self, cfg: dict[str, Any]) -> None:
        save_survey(cfg)
        self._refresh_question_list()

    # ------------------------------------------------------------------
    # 職員マスター管理タブ
    # ------------------------------------------------------------------
    def _build_master_tab(self) -> None:
        self._departments = load_master_users()

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
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.m_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.m_tree.configure(yscrollcommand=scrollbar.set)
        self._refresh_master_list()

        form_frame = ttk.LabelFrame(self.master_tab, text="職員追加", padding=10)
        form_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(form_frame, text="部署:").grid(row=0, column=0, sticky=tk.W)
        self.new_dept_var = tk.StringVar()
        ttk.Combobox(
            form_frame, textvariable=self.new_dept_var,
            values=list(self._departments.keys()), width=20,
        ).grid(row=0, column=1, padx=5)
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
    # パスワード設定タブ（グローバル）
    # ------------------------------------------------------------------
    def _build_password_tab(self) -> None:
        frame = ttk.LabelFrame(self.pw_tab, text="管理者パスワード設定", padding=20)
        frame.pack(padx=20, pady=20)

        has_pw = bool(get_admin_password_hash())
        ttk.Label(
            frame, text=f"現在の状態: {'設定済み' if has_pw else '未設定'}"
        ).grid(row=0, column=0, columnspan=2, pady=5)

        self.current_pw_var = tk.StringVar()
        if has_pw:
            ttk.Label(frame, text="現在のパスワード:").grid(row=1, column=0, sticky=tk.W)
            ttk.Entry(frame, textvariable=self.current_pw_var, show="*", width=30).grid(
                row=1, column=1, pady=2
            )

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

    def _check_current_pw(self) -> bool:
        stored = get_admin_password_hash()
        if stored and hash_password(self.current_pw_var.get()) != stored:
            messagebox.showerror("エラー", "現在のパスワードが正しくありません。")
            return False
        return True

    def _set_password(self) -> None:
        if not self._check_current_pw():
            return
        new_pw = self.new_pw_var.get()
        if not new_pw:
            messagebox.showwarning("入力不足", "新しいパスワードを入力してください。")
            return
        if new_pw != self.confirm_pw_var.get():
            messagebox.showerror("エラー", "パスワードが一致しません。")
            return
        set_admin_password(new_pw)
        write_action_log("管理者パスワード変更")
        messagebox.showinfo("完了", "パスワードを設定しました。")
        self._build_password_tab_refresh()

    def _clear_password(self) -> None:
        if not self._check_current_pw():
            return
        set_admin_password("")
        write_action_log("管理者パスワード解除")
        messagebox.showinfo("完了", "パスワードを解除しました。")
        self._build_password_tab_refresh()

    def _build_password_tab_refresh(self) -> None:
        for child in self.pw_tab.winfo_children():
            child.destroy()
        self._build_password_tab()

    # ------------------------------------------------------------------
    # バージョン管理タブ
    # ------------------------------------------------------------------
    def _build_version_tab(self) -> None:
        frame = ttk.LabelFrame(
            self.version_tab, text="バージョン管理（更新チェック用）", padding=20
        )
        frame.pack(padx=20, pady=20, fill=tk.X)

        ttk.Label(
            frame, text=f"このアプリのバージョン: {config.APP_VERSION}"
        ).grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=2)

        info = load_version_info()
        ttk.Label(
            frame,
            text=f"共有フォルダの最新バージョン: {info.get('latest_version', '') or '未設定'}",
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=2)

        ttk.Label(
            frame,
            text="最新のexeを共有フォルダに配置したら、ここに最新バージョンを登録してください。\n"
            "古いバージョンで起動した端末に更新を促します。",
            foreground="gray",
            justify=tk.LEFT,
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 10))

        ttk.Label(frame, text="最新バージョン:").grid(row=3, column=0, sticky=tk.W)
        self.latest_ver_var = tk.StringVar(value=info.get("latest_version", ""))
        ttk.Entry(frame, textvariable=self.latest_ver_var, width=20).grid(
            row=3, column=1, sticky=tk.W, pady=2
        )

        ttk.Label(frame, text="更新メモ:").grid(row=4, column=0, sticky=tk.NW)
        self.ver_note_text = tk.Text(frame, width=45, height=3)
        self.ver_note_text.grid(row=4, column=1, sticky=tk.W, pady=2)
        self.ver_note_text.insert("1.0", info.get("note", ""))

        ttk.Button(frame, text="登録", command=self._save_version).grid(
            row=5, column=0, columnspan=2, pady=10
        )

    def _save_version(self) -> None:
        latest = self.latest_ver_var.get().strip()
        if not latest:
            messagebox.showwarning("入力不足", "最新バージョンを入力してください。")
            return
        save_version_info(latest, self.ver_note_text.get("1.0", tk.END).strip())
        write_action_log(f"最新バージョン登録: {latest}")
        messagebox.showinfo("完了", "最新バージョン情報を登録しました。")


class QuestionEditDialog(tk.Toplevel):
    """設問の追加・編集ダイアログ（条件分岐対応）。"""

    def __init__(
        self,
        parent: tk.Widget,
        survey_cfg: dict[str, Any],
        question: dict[str, Any] | None,
        on_save: Callable[[dict[str, Any]], None],
    ):
        super().__init__(parent)
        self.title("設問編集" if question else "設問追加")
        self.resizable(False, False)
        self.grab_set()

        self._cfg = survey_cfg
        self._question = question
        self._on_save = on_save
        self._is_new = question is None

        frame = ttk.Frame(self, padding=15)
        frame.pack()

        ttk.Label(frame, text="タイプ:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.type_var = tk.StringVar(
            value=question["type"] if question else "single_choice"
        )
        type_combo = ttk.Combobox(
            frame, textvariable=self.type_var,
            values=["single_choice", "free_text"], state="readonly", width=20,
        )
        type_combo.grid(row=0, column=1, sticky=tk.W, pady=3)
        type_combo.bind("<<ComboboxSelected>>", self._on_type_change)

        self.required_var = tk.BooleanVar(
            value=question.get("required", True) if question else True
        )
        ttk.Checkbutton(frame, text="必須", variable=self.required_var).grid(
            row=0, column=2, padx=10
        )

        ttk.Label(frame, text="設問文:").grid(row=1, column=0, sticky=tk.NW, pady=3)
        self.text_entry = tk.Text(frame, width=50, height=3)
        self.text_entry.grid(row=1, column=1, columnspan=2, pady=3)
        if question:
            self.text_entry.insert("1.0", question.get("text", ""))

        self.choices_label = ttk.Label(frame, text="選択肢（改行区切り）:")
        self.choices_label.grid(row=2, column=0, sticky=tk.NW, pady=3)
        self.choices_text = tk.Text(frame, width=50, height=5)
        self.choices_text.grid(row=2, column=1, columnspan=2, pady=3)
        if question and question.get("choices"):
            self.choices_text.insert("1.0", "\n".join(question["choices"]))

        # 条件分岐設定
        cond_frame = ttk.LabelFrame(frame, text="表示条件（条件分岐）", padding=8)
        cond_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 3))

        ttk.Label(cond_frame, text="次の設問が…").grid(row=0, column=0, sticky=tk.W)
        self._candidates = self._build_candidates()
        cand_labels = ["（条件なし）"] + [
            f"Q{q['id']}: {q['text'][:20]}" for q in self._candidates
        ]
        self.cond_q_var = tk.StringVar(value=cand_labels[0])
        self.cond_q_combo = ttk.Combobox(
            cond_frame, textvariable=self.cond_q_var, values=cand_labels,
            state="readonly", width=28,
        )
        self.cond_q_combo.grid(row=0, column=1, padx=5)
        self.cond_q_combo.bind("<<ComboboxSelected>>", self._on_cond_q_change)

        ttk.Label(cond_frame, text="次の値の時に表示:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.cond_val_var = tk.StringVar()
        self.cond_val_combo = ttk.Combobox(
            cond_frame, textvariable=self.cond_val_var, values=[], state="readonly", width=28
        )
        self.cond_val_combo.grid(row=1, column=1, padx=5, pady=3)

        # 既存条件の復元
        if question and question.get("condition") and question["condition"].get("question_id"):
            tgt_id = question["condition"]["question_id"]
            for i, q in enumerate(self._candidates):
                if q["id"] == tgt_id:
                    self.cond_q_var.set(cand_labels[i + 1])
                    self._on_cond_q_change()
                    self.cond_val_var.set(question["condition"].get("equals", ""))
                    break

        self._on_type_change()

        ttk.Button(frame, text="保存", command=self._save).grid(row=4, column=1, pady=10)

    def _build_candidates(self) -> list[dict[str, Any]]:
        """条件の参照先候補（自分以外の単一選択設問）。"""
        result = []
        for q in self._cfg.get("questions", []):
            if q["type"] != "single_choice":
                continue
            if self._question is not None and q["id"] == self._question["id"]:
                continue
            result.append(q)
        return result

    def _on_cond_q_change(self, event=None) -> None:
        label = self.cond_q_var.get()
        if label.startswith("（条件なし"):
            self.cond_val_combo["values"] = []
            self.cond_val_var.set("")
            return
        # "Q{id}: ..." から id を取得
        try:
            qid = int(label.split(":")[0].replace("Q", "").strip())
        except ValueError:
            return
        target = next((q for q in self._candidates if q["id"] == qid), None)
        if target:
            self.cond_val_combo["values"] = target.get("choices", [])

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

        # 条件分岐
        condition = None
        label = self.cond_q_var.get()
        if not label.startswith("（条件なし"):
            try:
                qid = int(label.split(":")[0].replace("Q", "").strip())
            except ValueError:
                qid = None
            val = self.cond_val_var.get()
            if qid and val:
                condition = {"question_id": qid, "equals": val}

        if self._is_new:
            existing_ids = [q["id"] for q in self._cfg["questions"]]
            new_id = max(existing_ids) + 1 if existing_ids else 1
            new_q: dict[str, Any] = {
                "id": new_id, "type": q_type,
                "required": self.required_var.get(), "text": text,
            }
            if choices:
                new_q["choices"] = choices
            if condition:
                new_q["condition"] = condition
            self._cfg["questions"].append(new_q)
            write_action_log(f"設問追加[{self._cfg['id']}]: ID={new_id}")
        else:
            self._question["type"] = q_type
            self._question["required"] = self.required_var.get()
            self._question["text"] = text
            if choices:
                self._question["choices"] = choices
            elif "choices" in self._question:
                del self._question["choices"]
            if condition:
                self._question["condition"] = condition
            elif "condition" in self._question:
                del self._question["condition"]
            write_action_log(f"設問編集[{self._cfg['id']}]: ID={self._question['id']}")

        self._on_save(self._cfg)
        self.destroy()

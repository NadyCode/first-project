"""
集計・出力モード画面モジュール
回答データの集計、未回答者抽出、CSV出力を行う。
"""

import csv
import os
import tkinter as tk
from collections import Counter
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from src.data_manager import (
    get_all_staff,
    get_respondents,
    load_answers,
    load_survey_config,
)
from src.logger import write_action_log


class AggregatePanel(ttk.Frame):
    """集計・出力モードのメインパネル。"""

    def __init__(self, parent: tk.Widget, back_callback: Callable[[], None]):
        super().__init__(parent)
        self.back_callback = back_callback
        self._config = load_survey_config()
        self._answers = load_answers()
        self._build_ui()

    def _build_ui(self) -> None:
        # ヘッダー
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(header, text="集計・出力", font=("", 16, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="戻る", command=self.back_callback).pack(side=tk.RIGHT)

        # タブ
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # タブ1: 集計結果
        agg_tab = ttk.Frame(notebook)
        notebook.add(agg_tab, text="集計結果")
        self._build_aggregate_tab(agg_tab)

        # タブ2: 未回答者一覧
        unanswered_tab = ttk.Frame(notebook)
        notebook.add(unanswered_tab, text="未回答者一覧")
        self._build_unanswered_tab(unanswered_tab)

        # タブ3: 回答一覧（ローデータ）
        raw_tab = ttk.Frame(notebook)
        notebook.add(raw_tab, text="回答一覧")
        self._build_raw_tab(raw_tab)

    # ------------------------------------------------------------------
    # 集計結果タブ
    # ------------------------------------------------------------------
    def _build_aggregate_tab(self, parent: ttk.Frame) -> None:
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(
            info_frame, text=f"総回答数: {len(self._answers)}件", font=("", 12)
        ).pack(side=tk.LEFT)

        ttk.Button(
            info_frame, text="集計結果をCSV出力", command=self._export_aggregate_csv
        ).pack(side=tk.RIGHT)

        # スクロール可能エリア
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        questions = self._config.get("questions", [])
        for q in questions:
            q_id = q["id"]
            q_key = f"q{q_id}"

            frame = ttk.LabelFrame(scroll_frame, text=f"Q{q_id}: {q['text']}", padding=10)
            frame.pack(fill=tk.X, padx=5, pady=5)

            if q["type"] == "single_choice":
                counter = Counter()
                for ans in self._answers:
                    val = ans.get(q_key, "").strip()
                    if val:
                        counter[val] += 1

                total = sum(counter.values())
                for choice in q.get("choices", []):
                    count = counter.get(choice, 0)
                    pct = (count / total * 100) if total > 0 else 0
                    row_frame = ttk.Frame(frame)
                    row_frame.pack(fill=tk.X, pady=1)
                    ttk.Label(row_frame, text=f"{choice}:", width=15, anchor=tk.W).pack(
                        side=tk.LEFT
                    )
                    ttk.Label(row_frame, text=f"{count}件 ({pct:.1f}%)").pack(
                        side=tk.LEFT
                    )
                    # プログレスバー
                    bar = ttk.Progressbar(
                        row_frame, length=200, maximum=100, value=pct
                    )
                    bar.pack(side=tk.LEFT, padx=10)

            elif q["type"] == "free_text":
                text_answers = []
                for ans in self._answers:
                    val = ans.get(q_key, "").strip()
                    if val:
                        text_answers.append(val)
                ttk.Label(frame, text=f"回答数: {len(text_answers)}件").pack(anchor=tk.W)
                if text_answers:
                    text_widget = tk.Text(frame, width=70, height=min(len(text_answers) * 2, 10))
                    text_widget.pack(anchor=tk.W, pady=5)
                    for i, t in enumerate(text_answers, 1):
                        text_widget.insert(tk.END, f"{i}. {t}\n")
                    text_widget.configure(state=tk.DISABLED)

    def _export_aggregate_csv(self) -> None:
        """集計結果をCSV出力する。"""
        path = filedialog.asksaveasfilename(
            title="集計結果を保存",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="aggregate_result.csv",
        )
        if not path:
            return

        questions = self._config.get("questions", [])
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)

            for q in questions:
                q_id = q["id"]
                q_key = f"q{q_id}"
                writer.writerow([f"Q{q_id}", q["text"]])

                if q["type"] == "single_choice":
                    counter = Counter()
                    for ans in self._answers:
                        val = ans.get(q_key, "").strip()
                        if val:
                            counter[val] += 1
                    total = sum(counter.values())
                    writer.writerow(["選択肢", "回答数", "割合(%)"])
                    for choice in q.get("choices", []):
                        count = counter.get(choice, 0)
                        pct = (count / total * 100) if total > 0 else 0
                        writer.writerow([choice, count, f"{pct:.1f}"])

                elif q["type"] == "free_text":
                    writer.writerow(["回答内容"])
                    for ans in self._answers:
                        val = ans.get(q_key, "").strip()
                        if val:
                            writer.writerow([val])

                writer.writerow([])  # 空行

        write_action_log("集計結果CSV出力")
        messagebox.showinfo("出力完了", f"集計結果を保存しました:\n{path}")

    # ------------------------------------------------------------------
    # 未回答者一覧タブ
    # ------------------------------------------------------------------
    def _build_unanswered_tab(self, parent: ttk.Frame) -> None:
        all_staff = get_all_staff()
        respondents = get_respondents()

        answered = [(d, n) for d, n in all_staff if (d, n) in respondents]
        unanswered = [(d, n) for d, n in all_staff if (d, n) not in respondents]

        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(
            info_frame,
            text=f"全職員: {len(all_staff)}名 / 回答済み: {len(answered)}名 / 未回答: {len(unanswered)}名",
            font=("", 11),
        ).pack(side=tk.LEFT)

        ttk.Button(
            info_frame, text="未回答者リストをCSV出力", command=lambda: self._export_unanswered_csv(unanswered)
        ).pack(side=tk.RIGHT)

        # 未回答者一覧
        tree = ttk.Treeview(
            parent, columns=("dept", "name", "status"), show="headings", height=15
        )
        tree.heading("dept", text="部署")
        tree.heading("name", text="氏名")
        tree.heading("status", text="状態")
        tree.column("dept", width=150)
        tree.column("name", width=200)
        tree.column("status", width=100)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        # 未回答者を先に表示
        for dept, name in unanswered:
            tree.insert("", tk.END, values=(dept, name, "未回答"), tags=("unanswered",))
        for dept, name in answered:
            tree.insert("", tk.END, values=(dept, name, "回答済み"), tags=("answered",))

        tree.tag_configure("unanswered", foreground="red")
        tree.tag_configure("answered", foreground="green")

    def _export_unanswered_csv(self, unanswered: list[tuple[str, str]]) -> None:
        """未回答者リストをCSV出力する。"""
        path = filedialog.asksaveasfilename(
            title="未回答者リストを保存",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="unanswered_list.csv",
        )
        if not path:
            return

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["部署", "氏名"])
            for dept, name in unanswered:
                writer.writerow([dept, name])

        write_action_log("未回答者リストCSV出力")
        messagebox.showinfo("出力完了", f"未回答者リストを保存しました:\n{path}")

    # ------------------------------------------------------------------
    # 回答一覧（ローデータ）タブ
    # ------------------------------------------------------------------
    def _build_raw_tab(self, parent: ttk.Frame) -> None:
        info_frame = ttk.Frame(parent)
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(info_frame, text=f"全回答: {len(self._answers)}件").pack(side=tk.LEFT)

        ttk.Button(
            info_frame, text="回答データをCSV出力", command=self._export_raw_csv
        ).pack(side=tk.RIGHT)

        if not self._answers:
            ttk.Label(parent, text="回答データがありません。", font=("", 12)).pack(
                pady=20
            )
            return

        # 列名を取得
        columns = list(self._answers[0].keys())
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        v_scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=v_scroll.set)

        h_scroll = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(xscrollcommand=h_scroll.set)
        h_scroll.pack(fill=tk.X, padx=10)

        for row in self._answers:
            values = [row.get(col, "") for col in columns]
            tree.insert("", tk.END, values=values)

    def _export_raw_csv(self) -> None:
        """回答ローデータをCSV出力する。"""
        path = filedialog.asksaveasfilename(
            title="回答データを保存",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="answers_export.csv",
        )
        if not path:
            return

        if not self._answers:
            messagebox.showwarning("データなし", "出力する回答データがありません。")
            return

        columns = list(self._answers[0].keys())
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(self._answers)

        write_action_log("回答データCSV出力")
        messagebox.showinfo("出力完了", f"回答データを保存しました:\n{path}")

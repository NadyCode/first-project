"""
集計・出力モード画面モジュール
アンケート選択、回答データの集計（棒/円グラフ、部署フィルタ）、
部署別回答率グラフ、未回答者抽出、バックアップ、CSV出力を行う。
"""

import csv
import math
import tkinter as tk
from collections import Counter
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from src.data_manager import (
    backup_survey_answers,
    get_all_staff,
    get_survey_respondents,
    list_surveys,
    load_master_users,
    load_survey,
    load_survey_answers,
)
from src.logger import write_action_log

PIE_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
]
ALL_DEPTS = "全部署"


class PieChart(tk.Canvas):
    """tkinter Canvas上に円グラフを描画するウィジェット。"""

    def __init__(self, parent: tk.Widget, data: dict[str, int], size: int = 220):
        super().__init__(parent, width=size + 200, height=size + 20, highlightthickness=0)
        self._draw(data, size)

    def _draw(self, data: dict[str, int], size: int) -> None:
        total = sum(data.values())
        if total == 0:
            self.create_text(size // 2, size // 2, text="データなし", font=("", 11))
            return
        cx, cy = size // 2 + 10, size // 2 + 10
        r = size // 2 - 5
        start_angle = 90.0
        legend_x, legend_y = size + 20, 15

        for i, (label, count) in enumerate(data.items()):
            color = PIE_COLORS[i % len(PIE_COLORS)]
            extent = -(count / total) * 360
            pct = count / total * 100
            if count > 0:
                self.create_arc(
                    cx - r, cy - r, cx + r, cy + r,
                    start=start_angle, extent=extent,
                    fill=color, outline="white", width=2,
                )
                mid = math.radians(start_angle + extent / 2)
                if pct >= 5:
                    lx = cx + (r * 0.6) * math.cos(mid)
                    ly = cy - (r * 0.6) * math.sin(mid)
                    self.create_text(lx, ly, text=f"{pct:.0f}%", font=("", 8, "bold"), fill="white")
                start_angle += extent
            self.create_rectangle(
                legend_x, legend_y, legend_x + 12, legend_y + 12, fill=color, outline=""
            )
            self.create_text(
                legend_x + 18, legend_y + 6,
                text=f"{label} ({count}件, {pct:.1f}%)", anchor=tk.W, font=("", 9),
            )
            legend_y += 20


class AggregatePanel(ttk.Frame):
    """集計・出力モードのメインパネル。"""

    def __init__(self, parent: tk.Widget, back_callback: Callable[[], None]):
        super().__init__(parent)
        self.back_callback = back_callback
        self._chart_mode = tk.StringVar(value="bar")
        self._dept_filter = tk.StringVar(value=ALL_DEPTS)

        surveys = list_surveys()
        self._survey_map = {self._survey_label(s): s["id"] for s in surveys}
        self._current_id = surveys[0]["id"] if surveys else None

        self._build_header()
        self._content = ttk.Frame(self)
        self._content.pack(fill=tk.BOTH, expand=True)
        self._reload()

    @staticmethod
    def _survey_label(s: dict) -> str:
        status = "公開中" if s.get("status") == "active" else "非公開"
        return f"{s.get('title', '(無題)')} [{status}]"

    def _build_header(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(header, text="集計・出力", font=("", 16, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="戻る", command=self.back_callback).pack(side=tk.RIGHT)

        ttk.Label(header, text="アンケート:").pack(side=tk.LEFT, padx=(20, 2))
        self._survey_combo = ttk.Combobox(
            header, values=list(self._survey_map.keys()), state="readonly", width=35
        )
        self._survey_combo.pack(side=tk.LEFT)
        if self._current_id:
            for label, sid in self._survey_map.items():
                if sid == self._current_id:
                    self._survey_combo.set(label)
                    break
        self._survey_combo.bind("<<ComboboxSelected>>", self._on_survey_change)

    def _on_survey_change(self, event=None) -> None:
        label = self._survey_combo.get()
        self._current_id = self._survey_map.get(label)
        self._dept_filter.set(ALL_DEPTS)
        self._reload()

    def _reload(self) -> None:
        for child in self._content.winfo_children():
            child.destroy()

        if not self._current_id:
            ttk.Label(
                self._content, text="アンケートがありません。", font=("", 12)
            ).pack(pady=40)
            return

        self._survey = load_survey(self._current_id)
        self._answers = load_survey_answers(self._current_id)

        notebook = ttk.Notebook(self._content)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        agg_tab = ttk.Frame(notebook)
        notebook.add(agg_tab, text="集計結果")
        self._build_aggregate_tab(agg_tab)

        rate_tab = ttk.Frame(notebook)
        notebook.add(rate_tab, text="部署別回答率")
        self._build_rate_tab(rate_tab)

        unanswered_tab = ttk.Frame(notebook)
        notebook.add(unanswered_tab, text="未回答者一覧")
        self._build_unanswered_tab(unanswered_tab)

        raw_tab = ttk.Frame(notebook)
        notebook.add(raw_tab, text="回答一覧")
        self._build_raw_tab(raw_tab)

    def _filtered_answers(self) -> list[dict[str, str]]:
        dept = self._dept_filter.get()
        if dept == ALL_DEPTS:
            return self._answers
        return [a for a in self._answers if (a.get("department") or "").strip() == dept]

    # ------------------------------------------------------------------
    # 集計結果タブ
    # ------------------------------------------------------------------
    def _build_aggregate_tab(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, padx=10, pady=5)

        self._count_label = ttk.Label(toolbar, font=("", 12))
        self._count_label.pack(side=tk.LEFT)

        ttk.Button(
            toolbar, text="集計結果をCSV出力", command=self._export_aggregate_csv
        ).pack(side=tk.RIGHT)

        chart_frame = ttk.LabelFrame(toolbar, text="表示形式", padding=2)
        chart_frame.pack(side=tk.RIGHT, padx=10)
        ttk.Radiobutton(
            chart_frame, text="棒グラフ", variable=self._chart_mode, value="bar",
            command=self._refresh_charts,
        ).pack(side=tk.LEFT, padx=3)
        ttk.Radiobutton(
            chart_frame, text="円グラフ", variable=self._chart_mode, value="pie",
            command=self._refresh_charts,
        ).pack(side=tk.LEFT, padx=3)

        # 部署フィルタ
        filter_frame = ttk.LabelFrame(toolbar, text="部署フィルタ", padding=2)
        filter_frame.pack(side=tk.RIGHT, padx=10)
        depts = sorted({(a.get("department") or "").strip() for a in self._answers if a.get("department")})
        combo = ttk.Combobox(
            filter_frame, textvariable=self._dept_filter,
            values=[ALL_DEPTS] + depts, state="readonly", width=15,
        )
        combo.pack(side=tk.LEFT)
        combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_charts())

        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        self._scroll_frame = ttk.Frame(canvas)
        self._scroll_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self._scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._render_charts()

    def _refresh_charts(self) -> None:
        for child in self._scroll_frame.winfo_children():
            child.destroy()
        self._render_charts()

    def _render_charts(self) -> None:
        answers = self._filtered_answers()
        self._count_label.config(text=f"対象回答数: {len(answers)}件")
        mode = self._chart_mode.get()

        for q in self._survey.get("questions", []):
            q_id = q["id"]
            q_key = f"q{q_id}"
            frame = ttk.LabelFrame(
                self._scroll_frame, text=f"Q{q_id}: {q['text']}", padding=10
            )
            frame.pack(fill=tk.X, padx=5, pady=5)

            if q["type"] == "single_choice":
                counter = Counter()
                for ans in answers:
                    val = (ans.get(q_key) or "").strip()
                    if val:
                        counter[val] += 1
                total = sum(counter.values())
                ordered = {c: counter.get(c, 0) for c in q.get("choices", [])}

                if mode == "pie":
                    PieChart(frame, ordered).pack(anchor=tk.W, pady=5)
                else:
                    for choice in q.get("choices", []):
                        count = counter.get(choice, 0)
                        pct = (count / total * 100) if total > 0 else 0
                        row = ttk.Frame(frame)
                        row.pack(fill=tk.X, pady=1)
                        ttk.Label(row, text=f"{choice}:", width=15, anchor=tk.W).pack(side=tk.LEFT)
                        ttk.Label(row, text=f"{count}件 ({pct:.1f}%)").pack(side=tk.LEFT)
                        ttk.Progressbar(row, length=200, maximum=100, value=pct).pack(
                            side=tk.LEFT, padx=10
                        )

            elif q["type"] == "free_text":
                texts = [(a.get(q_key) or "").strip() for a in answers if (a.get(q_key) or "").strip()]
                ttk.Label(frame, text=f"回答数: {len(texts)}件").pack(anchor=tk.W)
                if texts:
                    tw = tk.Text(frame, width=70, height=min(len(texts) * 2, 10))
                    tw.pack(anchor=tk.W, pady=5)
                    for i, t in enumerate(texts, 1):
                        tw.insert(tk.END, f"{i}. {t}\n")
                    tw.configure(state=tk.DISABLED)

    def _export_aggregate_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="集計結果を保存", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], initialfile="aggregate_result.csv",
        )
        if not path:
            return
        answers = self._filtered_answers()
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["アンケート", self._survey.get("title", "")])
            writer.writerow(["部署フィルタ", self._dept_filter.get()])
            writer.writerow(["対象回答数", len(answers)])
            writer.writerow([])
            for q in self._survey.get("questions", []):
                q_id, q_key = q["id"], f"q{q['id']}"
                writer.writerow([f"Q{q_id}", q["text"]])
                if q["type"] == "single_choice":
                    counter = Counter()
                    for ans in answers:
                        val = (ans.get(q_key) or "").strip()
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
                    for ans in answers:
                        val = (ans.get(q_key) or "").strip()
                        if val:
                            writer.writerow([val])
                writer.writerow([])
        write_action_log("集計結果CSV出力")
        messagebox.showinfo("出力完了", f"集計結果を保存しました:\n{path}")

    # ------------------------------------------------------------------
    # 部署別回答率タブ
    # ------------------------------------------------------------------
    def _build_rate_tab(self, parent: ttk.Frame) -> None:
        if self._survey.get("anonymous"):
            ttk.Label(
                parent,
                text="匿名アンケートのため、部署別回答率は集計できません。",
                font=("", 12), foreground="gray",
            ).pack(pady=40)
            return

        all_staff = get_all_staff()
        respondents = get_survey_respondents(self._current_id)

        # 部署ごとの全数と回答数
        dept_total: Counter = Counter()
        for dept, _ in all_staff:
            dept_total[dept] += 1
        dept_answered: Counter = Counter()
        for dept, name in respondents:
            if dept in dept_total:
                dept_answered[dept] += 1

        ttk.Label(
            parent, text="部署別の回答率", font=("", 13, "bold")
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        sframe = ttk.Frame(canvas)
        sframe.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=sframe, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for dept in sorted(dept_total.keys()):
            total = dept_total[dept]
            answered = dept_answered.get(dept, 0)
            pct = (answered / total * 100) if total > 0 else 0
            row = ttk.Frame(sframe)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"{dept}", width=14, anchor=tk.W).pack(side=tk.LEFT)
            ttk.Progressbar(row, length=250, maximum=100, value=pct).pack(side=tk.LEFT, padx=5)
            ttk.Label(row, text=f"{answered}/{total} ({pct:.0f}%)").pack(side=tk.LEFT, padx=5)

        # 全体回答率
        total_all = sum(dept_total.values())
        answered_all = len(respondents)
        pct_all = (answered_all / total_all * 100) if total_all > 0 else 0
        ttk.Separator(sframe, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)
        ttk.Label(
            sframe,
            text=f"全体: {answered_all}/{total_all} ({pct_all:.1f}%)",
            font=("", 11, "bold"),
        ).pack(anchor=tk.W)

    # ------------------------------------------------------------------
    # 未回答者一覧タブ
    # ------------------------------------------------------------------
    def _build_unanswered_tab(self, parent: ttk.Frame) -> None:
        if self._survey.get("anonymous"):
            ttk.Label(
                parent,
                text="匿名アンケートのため、未回答者の抽出はできません。",
                font=("", 12), foreground="gray",
            ).pack(pady=40)
            return

        all_staff = get_all_staff()
        respondents = get_survey_respondents(self._current_id)
        answered = [(d, n) for d, n in all_staff if (d, n) in respondents]
        unanswered = [(d, n) for d, n in all_staff if (d, n) not in respondents]

        info = ttk.Frame(parent)
        info.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(
            info,
            text=f"全職員: {len(all_staff)}名 / 回答済み: {len(answered)}名 / 未回答: {len(unanswered)}名",
            font=("", 11),
        ).pack(side=tk.LEFT)
        ttk.Button(
            info, text="未回答者リストをCSV出力",
            command=lambda: self._export_unanswered_csv(unanswered),
        ).pack(side=tk.RIGHT)

        tree = ttk.Treeview(parent, columns=("dept", "name", "status"), show="headings", height=15)
        for col, txt, w in [("dept", "部署", 150), ("name", "氏名", 200), ("status", "状態", 100)]:
            tree.heading(col, text=txt)
            tree.column(col, width=w)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        for dept, name in unanswered:
            tree.insert("", tk.END, values=(dept, name, "未回答"), tags=("u",))
        for dept, name in answered:
            tree.insert("", tk.END, values=(dept, name, "回答済み"), tags=("a",))
        tree.tag_configure("u", foreground="red")
        tree.tag_configure("a", foreground="green")

    def _export_unanswered_csv(self, unanswered: list[tuple[str, str]]) -> None:
        path = filedialog.asksaveasfilename(
            title="未回答者リストを保存", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], initialfile="unanswered_list.csv",
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
    # 回答一覧タブ
    # ------------------------------------------------------------------
    def _build_raw_tab(self, parent: ttk.Frame) -> None:
        info = ttk.Frame(parent)
        info.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(info, text=f"全回答: {len(self._answers)}件").pack(side=tk.LEFT)
        ttk.Button(info, text="バックアップ作成", command=self._make_backup).pack(
            side=tk.RIGHT, padx=2
        )
        ttk.Button(info, text="回答データをCSV出力", command=self._export_raw_csv).pack(
            side=tk.RIGHT, padx=2
        )

        if not self._answers:
            ttk.Label(parent, text="回答データがありません。", font=("", 12)).pack(pady=20)
            return

        columns = list(self._answers[0].keys())
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        v = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=v.set)
        h = ttk.Scrollbar(parent, orient=tk.HORIZONTAL, command=tree.xview)
        tree.configure(xscrollcommand=h.set)
        h.pack(fill=tk.X, padx=10)
        for row in self._answers:
            tree.insert("", tk.END, values=[row.get(c, "") for c in columns])

    def _make_backup(self) -> None:
        path = backup_survey_answers(self._current_id)
        if path:
            write_action_log(f"回答バックアップ作成: {self._current_id}")
            messagebox.showinfo("完了", f"バックアップを作成しました:\n{path}")
        else:
            messagebox.showwarning("データなし", "バックアップ対象の回答がありません。")

    def _export_raw_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="回答データを保存", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")], initialfile="answers_export.csv",
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

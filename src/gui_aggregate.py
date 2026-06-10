"""
集計・出力モード画面モジュール
回答データの集計、未回答者抽出、CSV出力を行う。
棒グラフ・円グラフの切り替え表示に対応。
"""

import csv
import math
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

# 円グラフ用カラーパレット
PIE_COLORS = [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
]


class PieChart(tk.Canvas):
    """tkinter Canvas上に円グラフを描画するウィジェット。"""

    def __init__(self, parent: tk.Widget, data: dict[str, int], size: int = 220):
        super().__init__(parent, width=size + 180, height=size + 20, highlightthickness=0)
        self._draw(data, size)

    def _draw(self, data: dict[str, int], size: int) -> None:
        total = sum(data.values())
        if total == 0:
            self.create_text(
                size // 2, size // 2, text="データなし", font=("", 11)
            )
            return

        cx, cy = size // 2 + 10, size // 2 + 10
        r = size // 2 - 5
        start_angle = 90.0  # 12時方向から開始

        legend_x = size + 20
        legend_y = 15

        for i, (label, count) in enumerate(data.items()):
            color = PIE_COLORS[i % len(PIE_COLORS)]
            extent = -(count / total) * 360
            pct = count / total * 100

            self.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=start_angle, extent=extent,
                fill=color, outline="white", width=2,
            )

            # ラベルを扇形の中央に配置
            mid_angle = math.radians(start_angle + extent / 2)
            lx = cx + (r * 0.6) * math.cos(mid_angle)
            ly = cy - (r * 0.6) * math.sin(mid_angle)
            if pct >= 5:
                self.create_text(lx, ly, text=f"{pct:.0f}%", font=("", 8, "bold"), fill="white")

            start_angle += extent

            # 凡例
            self.create_rectangle(
                legend_x, legend_y, legend_x + 12, legend_y + 12, fill=color, outline=""
            )
            self.create_text(
                legend_x + 18, legend_y + 6,
                text=f"{label} ({count}件, {pct:.1f}%)",
                anchor=tk.W, font=("", 9),
            )
            legend_y += 20


class AggregatePanel(ttk.Frame):
    """集計・出力モードのメインパネル。"""

    def __init__(self, parent: tk.Widget, back_callback: Callable[[], None]):
        super().__init__(parent)
        self.back_callback = back_callback
        self._config = load_survey_config()
        self._answers = load_answers()
        self._chart_mode = tk.StringVar(value="bar")
        self._build_ui()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(header, text="集計・出力", font=("", 16, "bold")).pack(side=tk.LEFT)
        ttk.Button(header, text="戻る", command=self.back_callback).pack(side=tk.RIGHT)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        agg_tab = ttk.Frame(notebook)
        notebook.add(agg_tab, text="集計結果")
        self._build_aggregate_tab(agg_tab)

        unanswered_tab = ttk.Frame(notebook)
        notebook.add(unanswered_tab, text="未回答者一覧")
        self._build_unanswered_tab(unanswered_tab)

        raw_tab = ttk.Frame(notebook)
        notebook.add(raw_tab, text="回答一覧")
        self._build_raw_tab(raw_tab)

    # ------------------------------------------------------------------
    # 集計結果タブ
    # ------------------------------------------------------------------
    def _build_aggregate_tab(self, parent: ttk.Frame) -> None:
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(toolbar, text=f"総回答数: {len(self._answers)}件", font=("", 12)).pack(
            side=tk.LEFT
        )

        ttk.Button(
            toolbar, text="集計結果をCSV出力", command=self._export_aggregate_csv
        ).pack(side=tk.RIGHT)

        # グラフ切替
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

        # スクロール可能エリア
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

        self._agg_canvas = canvas
        self._render_charts()

    def _refresh_charts(self) -> None:
        for child in self._scroll_frame.winfo_children():
            child.destroy()
        self._render_charts()

    def _render_charts(self) -> None:
        questions = self._config.get("questions", [])
        mode = self._chart_mode.get()

        for q in questions:
            q_id = q["id"]
            q_key = f"q{q_id}"

            frame = ttk.LabelFrame(
                self._scroll_frame, text=f"Q{q_id}: {q['text']}", padding=10
            )
            frame.pack(fill=tk.X, padx=5, pady=5)

            if q["type"] == "single_choice":
                counter = Counter()
                for ans in self._answers:
                    val = ans.get(q_key, "").strip()
                    if val:
                        counter[val] += 1

                total = sum(counter.values())
                ordered = {c: counter.get(c, 0) for c in q.get("choices", [])}

                if mode == "pie":
                    pie = PieChart(frame, ordered)
                    pie.pack(anchor=tk.W, pady=5)
                else:
                    for choice in q.get("choices", []):
                        count = counter.get(choice, 0)
                        pct = (count / total * 100) if total > 0 else 0
                        row_frame = ttk.Frame(frame)
                        row_frame.pack(fill=tk.X, pady=1)
                        ttk.Label(
                            row_frame, text=f"{choice}:", width=15, anchor=tk.W
                        ).pack(side=tk.LEFT)
                        ttk.Label(
                            row_frame, text=f"{count}件 ({pct:.1f}%)"
                        ).pack(side=tk.LEFT)
                        bar = ttk.Progressbar(
                            row_frame, length=200, maximum=100, value=pct
                        )
                        bar.pack(side=tk.LEFT, padx=10)

            elif q["type"] == "free_text":
                text_answers = [
                    ans.get(q_key, "").strip()
                    for ans in self._answers
                    if ans.get(q_key, "").strip()
                ]
                ttk.Label(frame, text=f"回答数: {len(text_answers)}件").pack(anchor=tk.W)
                if text_answers:
                    tw = tk.Text(
                        frame, width=70, height=min(len(text_answers) * 2, 10)
                    )
                    tw.pack(anchor=tk.W, pady=5)
                    for i, t in enumerate(text_answers, 1):
                        tw.insert(tk.END, f"{i}. {t}\n")
                    tw.configure(state=tk.DISABLED)

    def _export_aggregate_csv(self) -> None:
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

                writer.writerow([])

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
            info_frame,
            text="未回答者リストをCSV出力",
            command=lambda: self._export_unanswered_csv(unanswered),
        ).pack(side=tk.RIGHT)

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

        for dept, name in unanswered:
            tree.insert("", tk.END, values=(dept, name, "未回答"), tags=("unanswered",))
        for dept, name in answered:
            tree.insert("", tk.END, values=(dept, name, "回答済み"), tags=("answered",))

        tree.tag_configure("unanswered", foreground="red")
        tree.tag_configure("answered", foreground="green")

    def _export_unanswered_csv(self, unanswered: list[tuple[str, str]]) -> None:
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

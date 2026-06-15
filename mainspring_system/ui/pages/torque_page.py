"""
力矩曲线页面
展示力矩曲线、衰减过快区段标红、风险预警
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.mechanics import AnalysisResult
from core.storage import DesignReportGenerator
from ui.widgets.chart_canvas import TorqueChart, BarChart


class TorquePage(ttk.Frame):
    """力矩曲线页面"""

    def __init__(self, master, app=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.analysis_result = None

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        main_container = ttk.Frame(self, padding=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(title_frame, text="力矩曲线分析",
                  font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        self.temp_label = ttk.Label(title_frame, text="温度: 20°C",
                                    foreground='#666')
        self.temp_label.pack(side=tk.LEFT, padx=(20, 0))

        btn_frame = ttk.Frame(title_frame)
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="导出设计报告",
                   command=self._on_export_report).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_frame, text="保存为档案",
                   command=self._on_save_as_archive).pack(side=tk.RIGHT, padx=2)

        content = ttk.Frame(main_container)
        content.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.Frame(content)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_panel = ttk.Frame(content, width=280)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_panel.pack_propagate(False)

        chart_frame = ttk.LabelFrame(left_panel, text="力矩曲线图", padding=5)
        chart_frame.pack(fill=tk.BOTH, expand=True)

        self.torque_chart = TorqueChart(chart_frame, height=350)
        self.torque_chart.pack(fill=tk.BOTH, expand=True)

        legend_info = ttk.Frame(chart_frame)
        legend_info.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(legend_info, text="红色区域: 力矩衰减过快区段",
                  foreground='#d62728', font=('Arial', 9)).pack(side=tk.LEFT)

        self._build_stats_panel(right_panel)
        self._build_risk_panel(right_panel)
        self._build_case_check_panel(right_panel)

        bottom_panel = ttk.LabelFrame(main_container, text="温度影响分析", padding=10)
        bottom_panel.pack(fill=tk.X, pady=(10, 0))

        self._build_temp_effect_panel(bottom_panel)

    def _build_stats_panel(self, parent):
        """构建统计数据面板"""
        frame = ttk.LabelFrame(parent, text="关键指标", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        self.stats_labels = {}
        stats = [
            ("满弦力矩", "max_torque", "g·cm", '#d62728'),
            ("末端力矩", "min_torque", "g·cm", '#ff7f0e'),
            ("平均力矩", "avg_torque", "g·cm", '#1f77b4'),
            ("力矩衰减率", "decay_rate", "%", '#9467bd'),
            ("总圈数", "total_turns", "圈", '#2ca02c'),
            ("总储能", "total_energy", "mJ", '#8c564b'),
            ("动储估计", "reserve", "小时", '#e377c2'),
        ]

        for i, (label, key, unit, color) in enumerate(stats):
            ttk.Label(frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=3)

            val_frame = ttk.Frame(frame)
            val_frame.grid(row=i, column=1, sticky=tk.E, pady=3, padx=(10, 0))

            val_label = ttk.Label(val_frame, text="-", foreground=color,
                                  font=('Arial', 10, 'bold'))
            val_label.pack(side=tk.RIGHT)
            ttk.Label(val_frame, text=f" {unit}").pack(side=tk.RIGHT)

            self.stats_labels[key] = val_label

        frame.columnconfigure(1, weight=1)

    def _build_risk_panel(self, parent):
        """构建风险预警面板"""
        frame = ttk.LabelFrame(parent, text="风险预警", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        self.risk_listbox = tk.Listbox(frame, height=5, fg='#d62728',
                                       activestyle='none', relief=tk.FLAT)
        self.risk_listbox.pack(fill=tk.X)

        self.risk_listbox.insert(tk.END, "暂无风险预警")
        self.risk_listbox.itemconfig(0, fg='#2ca02c')

    def _build_case_check_panel(self, parent):
        """构建条盒校验面板"""
        frame = ttk.LabelFrame(parent, text="条盒容积校验", padding=10)
        frame.pack(fill=tk.X)

        self.case_labels = {}
        items = [
            ("径向间隙", "radial_gap", "mm"),
            ("估计圈数", "turns", "圈"),
            ("装填系数", "fill_ratio", "%"),
            ("安全状态", "safe", ""),
        ]

        for i, (label, key, unit) in enumerate(items):
            ttk.Label(frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=2)

            val_frame = ttk.Frame(frame)
            val_frame.grid(row=i, column=1, sticky=tk.E, pady=2, padx=(10, 0))

            val_label = ttk.Label(val_frame, text="-", foreground='#1f77b4')
            val_label.pack(side=tk.RIGHT)
            if unit:
                ttk.Label(val_frame, text=f" {unit}").pack(side=tk.RIGHT)

            self.case_labels[key] = val_label

        frame.columnconfigure(1, weight=1)

    def _build_temp_effect_panel(self, parent):
        """构建温度影响面板"""
        self.temp_chart = BarChart(parent, height=120)
        self.temp_chart.pack(fill=tk.X)

        self.temp_chart.set_title("不同温度下的动力储备")
        self.temp_chart.set_ylabel("小时")

    def set_analysis_result(self, result: AnalysisResult):
        """设置分析结果并更新显示"""
        self.analysis_result = result

        self._update_chart()
        self._update_stats()
        self._update_risks()
        self._update_case_check()
        self._update_temp_effects()

    def _update_chart(self):
        """更新曲线图"""
        if not self.analysis_result:
            return

        curve = self.analysis_result.torque_curve
        decay_segments = self.analysis_result.decay_segments

        self.torque_chart.set_data(
            [curve],
            curve_names=["输出力矩"],
            curve_colors=['#1f77b4'],
            decay_segments=decay_segments
        )
        self.torque_chart.set_title("发条力矩曲线 (满弦 → 放尽)")

    def _update_stats(self):
        """更新统计数据"""
        if not self.analysis_result:
            return

        r = self.analysis_result

        self.stats_labels["max_torque"].config(text=f"{r.max_torque:.2f}")
        self.stats_labels["min_torque"].config(text=f"{r.min_torque:.2f}")
        self.stats_labels["avg_torque"].config(text=f"{r.avg_torque:.2f}")

        decay_rate = (r.max_torque - r.min_torque) / r.max_torque * 100 if r.max_torque > 0 else 0
        self.stats_labels["decay_rate"].config(text=f"{decay_rate:.1f}")

        self.stats_labels["total_turns"].config(text=f"{r.total_turns:.2f}")
        self.stats_labels["total_energy"].config(text=f"{r.total_energy:.2f}")

        from core.mechanics import TorqueCalculator
        reserve = TorqueCalculator.estimate_power_reserve(
            r.torque_curve, min_torque=r.max_torque * 0.3
        )
        self.stats_labels["reserve"].config(text=f"{reserve:.1f}")

        if self.app and hasattr(self.app, 'current_temp'):
            self.temp_label.config(text=f"温度: {self.app.current_temp}°C")

    def _update_risks(self):
        """更新风险预警"""
        if not self.analysis_result:
            return

        warnings = self.analysis_result.risk_warnings

        self.risk_listbox.delete(0, tk.END)

        if not warnings:
            self.risk_listbox.insert(tk.END, "✓ 未发现明显风险")
            self.risk_listbox.itemconfig(0, fg='#2ca02c')
        else:
            for i, warning in enumerate(warnings):
                self.risk_listbox.insert(tk.END, "⚠ " + warning)
                if "高风险" in warning:
                    self.risk_listbox.itemconfig(i, fg='#d62728')
                else:
                    self.risk_listbox.itemconfig(i, fg='#ff7f0e')

    def _update_case_check(self):
        """更新条盒校验"""
        if not self.analysis_result:
            return

        cc = self.analysis_result.case_check

        self.case_labels["radial_gap"].config(text=f"{cc['radial_gap']:.3f}")
        self.case_labels["turns"].config(text=f"{cc['estimated_turns']:.1f}")
        self.case_labels["fill_ratio"].config(text=f"{cc['fill_ratio'] * 100:.1f}")

        if cc["safe"]:
            self.case_labels["safe"].config(text="安全", foreground='#2ca02c')
        else:
            self.case_labels["safe"].config(text="危险", foreground='#d62728')

    def _update_temp_effects(self):
        """更新温度影响图表"""
        if not self.analysis_result:
            return

        temp_effects = self.analysis_result.temp_effects

        temps = sorted(temp_effects.keys())
        reserve_values = []
        labels = []

        for t in temps:
            info = temp_effects[t]
            reserve_values.append(info["power_reserve_hours"])
            labels.append(f"{t}°C")

        colors = []
        for t in temps:
            if t < 0:
                colors.append('#1f77b4')
            elif t < 20:
                colors.append('#2ca02c')
            elif t < 40:
                colors.append('#ff7f0e')
            else:
                colors.append('#d62728')

        self.temp_chart.set_data(reserve_values, labels, colors)

    def _on_export_report(self):
        """导出设计报告"""
        if not self.analysis_result:
            messagebox.showinfo("提示", "请先执行分析")
            return

        default_name = f"发条设计报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        filepath = filedialog.asksaveasfilename(
            title="导出设计报告",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )

        if not filepath:
            return

        try:
            compensation_result = None
            if self.app and hasattr(self.app, 'compensation_page'):
                comp_page = self.app.compensation_page
                if hasattr(comp_page, 'current_compensation') and comp_page.current_compensation:
                    compensation_result = comp_page.current_compensation

            DesignReportGenerator.generate_text_report(
                self.analysis_result,
                compensation_result=compensation_result,
                filepath=filepath
            )

            messagebox.showinfo("成功", f"设计报告已导出到:\n{filepath}")
        except Exception as e:
            messagebox.showerror("错误", f"导出失败: {str(e)}")

    def _on_save_as_archive(self):
        """保存为档案"""
        if not self.analysis_result:
            messagebox.showinfo("提示", "请先执行分析")
            return

        if self.app and hasattr(self.app, 'archive_page'):
            self.app.show_page("archive")
            archive_page = self.app.archive_page
            archive_page._on_create_from_analysis()

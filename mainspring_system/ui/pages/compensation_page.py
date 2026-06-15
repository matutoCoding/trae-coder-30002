"""
均力补偿页面
计算宝塔轮或均力装置补偿后的等力矩效果
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.mechanics import (
    AnalysisResult,
    CompensationCalculator,
    CompensationResult
)
from ui.widgets.chart_canvas import TorqueChart, BarChart


class CompensationPage(ttk.Frame):
    """均力补偿页面"""

    def __init__(self, master, app=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.analysis_result = None
        self.compensation_results = {}
        self.selected_compensations = []
        self.current_compensation = None

        self._build_ui()

    def _build_ui(self):
        """构建界面"""
        main_container = ttk.Frame(self, padding=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_container, text="均力补偿分析",
                  font=('Arial', 16, 'bold')).pack(anchor=tk.W, pady=(0, 10))

        content = ttk.Frame(main_container)
        content.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.Frame(content)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_panel = ttk.Frame(content, width=300)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right_panel.pack_propagate(False)

        chart_frame = ttk.LabelFrame(left_panel, text="补偿前后力矩曲线对比", padding=5)
        chart_frame.pack(fill=tk.BOTH, expand=True)

        self.torque_chart = TorqueChart(chart_frame, height=340)
        self.torque_chart.pack(fill=tk.BOTH, expand=True)

        bottom_left = ttk.Frame(left_panel)
        bottom_left.pack(fill=tk.X, pady=(10, 0))

        self._build_compensation_options(bottom_left)

        self._build_compensation_list(right_panel)
        self._build_comparison_panel(right_panel)

    def _build_compensation_options(self, parent):
        """构建补偿方式选择"""
        frame = ttk.LabelFrame(parent, text="补偿方式选择", padding=10)
        frame.pack(fill=tk.X)

        self.compensation_vars = {}

        options = [
            ("原始曲线 (对照)", "original", True),
            ("宝塔轮补偿 (5级)", "fusee_5", False),
            ("宝塔轮补偿 (8级)", "fusee_8", False),
            ("恒力装置", "constant_force", False),
            ("Stackfreed补偿", "stackfreed", False),
        ]

        for i, (label, key, default) in enumerate(options):
            var = tk.BooleanVar(value=default)
            cb = ttk.Checkbutton(frame, text=label, variable=var,
                                 command=self._on_compensation_change)
            cb.grid(row=i // 3, column=i % 3, sticky=tk.W, padx=5, pady=2)
            self.compensation_vars[key] = var

        ttk.Button(frame, text="应用补偿", command=self._apply_compensations).grid(
            row=0, column=3, rowspan=2, padx=20, sticky=tk.E)

        frame.columnconfigure(2, weight=1)

    def _build_compensation_list(self, parent):
        """构建补偿效果列表"""
        frame = ttk.LabelFrame(parent, text="补偿效果对比", padding=10)
        frame.pack(fill=tk.X, pady=(0, 10))

        self.effect_listbox = tk.Listbox(frame, height=8, relief=tk.FLAT)
        self.effect_listbox.pack(fill=tk.X)

        self.effect_listbox.insert(tk.END, "请选择补偿方式查看效果")

    def _build_comparison_panel(self, parent):
        """构建对比面板"""
        frame = ttk.LabelFrame(parent, text="补偿效果量化", padding=10)
        frame.pack(fill=tk.X)

        self.comparison_chart = BarChart(frame, height=150)
        self.comparison_chart.pack(fill=tk.X)

        self.comparison_chart.set_title("力矩标准差对比")
        self.comparison_chart.set_ylabel("标准差")

        detail_frame = ttk.Frame(frame)
        detail_frame.pack(fill=tk.X, pady=(10, 0))

        self.detail_labels = {}
        details = [
            ("原始力矩标准差", "std_before", "g·cm"),
            ("补偿后标准差", "std_after", "g·cm"),
            ("改善百分比", "improvement", "%"),
        ]

        for i, (label, key, unit) in enumerate(details):
            ttk.Label(detail_frame, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=3)
            val_frame = ttk.Frame(detail_frame)
            val_frame.grid(row=i, column=1, sticky=tk.E, pady=3)

            val_label = ttk.Label(val_frame, text="-", foreground='#1f77b4',
                                  font=('Arial', 10, 'bold'))
            val_label.pack(side=tk.RIGHT)
            ttk.Label(val_frame, text=f" {unit}").pack(side=tk.RIGHT)

            self.detail_labels[key] = val_label

        detail_frame.columnconfigure(1, weight=1)

    def set_analysis_result(self, result: AnalysisResult):
        """设置分析结果"""
        self.analysis_result = result
        self._calculate_all_compensations()
        self._apply_compensations()

    def _calculate_all_compensations(self):
        """计算所有补偿方式的效果"""
        if not self.analysis_result:
            return

        curve = self.analysis_result.torque_curve

        self.compensation_results = {}

        self.compensation_results["original"] = CompensationResult(
            name="原始曲线",
            original_curve=curve,
            compensated_curve=curve,
            torque_std_before=0,
            torque_std_after=self._calc_torque_std(curve),
            improvement_pct=0
        )

        self.compensation_results["fusee_5"] = \
            CompensationCalculator.calc_fusee_compensation(curve, 5)

        self.compensation_results["fusee_8"] = \
            CompensationCalculator.calc_fusee_compensation(curve, 8)

        self.compensation_results["constant_force"] = \
            CompensationCalculator.calc_constant_force_compensation(curve)

        self.compensation_results["stackfreed"] = \
            CompensationCalculator.calc_stackfreed_compensation(curve)

    def _calc_torque_std(self, curve):
        """计算力矩标准差"""
        if not curve:
            return 0
        torques = [p.torque for p in curve]
        mean = sum(torques) / len(torques)
        variance = sum((t - mean) ** 2 for t in torques) / len(torques)
        return variance ** 0.5

    def _on_compensation_change(self):
        """补偿方式改变"""
        pass

    def _apply_compensations(self):
        """应用选中的补偿方式"""
        if not self.analysis_result or not self.compensation_results:
            return

        selected_keys = []
        curves = []
        names = []
        colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']

        color_map = {
            "original": '#1f77b4',
            "fusee_5": '#ff7f0e',
            "fusee_8": '#2ca02c',
            "constant_force": '#d62728',
            "stackfreed": '#9467bd'
        }

        for key, var in self.compensation_vars.items():
            if var.get() and key in self.compensation_results:
                selected_keys.append(key)
                result = self.compensation_results[key]
                curves.append(result.compensated_curve)
                names.append(result.name)

        if not curves:
            return

        selected_colors = [color_map.get(k, '#333') for k in selected_keys]

        self.torque_chart.set_data(
            curves,
            curve_names=names,
            curve_colors=selected_colors,
            decay_segments=[]
        )
        self.torque_chart.set_title("补偿前后力矩曲线对比")

        self._update_effect_list(selected_keys)
        self._update_comparison(selected_keys)

        if selected_keys:
            best_key = "original"
            best_improvement = 0
            for key in selected_keys:
                if key != "original" and key in self.compensation_results:
                    result = self.compensation_results[key]
                    if result.improvement_pct > best_improvement:
                        best_improvement = result.improvement_pct
                        best_key = key
            if best_key in self.compensation_results:
                self.current_compensation = self.compensation_results[best_key]

    def _update_effect_list(self, selected_keys):
        """更新效果列表"""
        self.effect_listbox.delete(0, tk.END)

        for key in selected_keys:
            if key in self.compensation_results:
                result = self.compensation_results[key]
                if key == "original":
                    text = f"{result.name}: 标准差 {result.torque_std_after:.2f} g·cm"
                else:
                    text = f"{result.name}: 改善 {result.improvement_pct:.1f}%"
                self.effect_listbox.insert(tk.END, text)

        if not selected_keys:
            self.effect_listbox.insert(tk.END, "请选择补偿方式查看效果")

    def _update_comparison(self, selected_keys):
        """更新对比数据"""
        if not selected_keys:
            return

        std_values = []
        labels = []
        colors = []

        color_map = {
            "original": '#1f77b4',
            "fusee_5": '#ff7f0e',
            "fusee_8": '#2ca02c',
            "constant_force": '#d62728',
            "stackfreed": '#9467bd'
        }

        for key in selected_keys:
            if key in self.compensation_results:
                result = self.compensation_results[key]
                std_values.append(result.torque_std_after)
                labels.append(result.name)
                colors.append(color_map.get(key, '#333'))

        self.comparison_chart.set_data(std_values, labels, colors)

        if "original" in selected_keys:
            original_result = self.compensation_results["original"]
            self.detail_labels["std_before"].config(
                text=f"{original_result.torque_std_after:.2f}")
        else:
            self.detail_labels["std_before"].config(text="-")

        best_key = None
        best_improvement = -999
        for key in selected_keys:
            if key != "original" and key in self.compensation_results:
                result = self.compensation_results[key]
                if result.improvement_pct > best_improvement:
                    best_improvement = result.improvement_pct
                    best_key = key

        if best_key:
            result = self.compensation_results[best_key]
            self.detail_labels["std_after"].config(
                text=f"{result.torque_std_after:.2f}")
            self.detail_labels["improvement"].config(
                text=f"{result.improvement_pct:.1f}")
        else:
            self.detail_labels["std_after"].config(text="-")
            self.detail_labels["improvement"].config(text="-")

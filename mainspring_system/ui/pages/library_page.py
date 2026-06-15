"""
方案库页面
不同动储等级的发条配置方案库
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.storage import SpringSolution, DataStorage
from core.mechanics import (
    SpringParams,
    DesignOptimizer,
    perform_full_analysis,
    MaterialLibrary
)
from ui.widgets.chart_canvas import TorqueChart


class LibraryPage(ttk.Frame):
    """方案库页面"""

    def __init__(self, master, app=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.storage = None
        self.solutions = []
        self.selected_solution = None

        self._build_ui()

    def set_storage(self, storage: DataStorage):
        self.storage = storage
        self._refresh_solutions()
        self._load_categories()

    def _build_ui(self):
        """构建界面"""
        main_container = ttk.Frame(self, padding=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(title_frame, text="发条方案库",
                  font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        filter_frame = ttk.Frame(title_frame)
        filter_frame.pack(side=tk.RIGHT)

        ttk.Label(filter_frame, text="分类:").pack(side=tk.LEFT, padx=(0, 5))
        self.category_var = tk.StringVar(value="全部")
        self.category_combo = ttk.Combobox(filter_frame, textvariable=self.category_var,
                                            state='readonly', width=12)
        self.category_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.category_combo.bind('<<ComboboxSelected>>', lambda e: self._filter_solutions())

        ttk.Label(filter_frame, text="等级:").pack(side=tk.LEFT, padx=(0, 5))
        self.grade_var = tk.StringVar(value="全部")
        self.grade_combo = ttk.Combobox(filter_frame, textvariable=self.grade_var,
                                         values=["全部", "标准", "长动力", "超长动力"],
                                         state='readonly', width=12)
        self.grade_combo.pack(side=tk.LEFT)
        self.grade_combo.bind('<<ComboboxSelected>>', lambda e: self._filter_solutions())

        content = ttk.Frame(main_container)
        content.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.LabelFrame(content, text="方案列表", padding=5)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.config(width=300)
        left_panel.pack_propagate(False)

        search_frame = ttk.Frame(left_panel)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.search_entry.bind('<KeyRelease>', lambda e: self._filter_solutions())

        self.solution_listbox = tk.Listbox(left_panel, relief=tk.FLAT)
        self.solution_listbox.pack(fill=tk.BOTH, expand=True)
        self.solution_listbox.bind('<<ListboxSelect>>', self._on_select_solution)

        scrollbar = ttk.Scrollbar(left_panel, orient=tk.VERTICAL,
                                   command=self.solution_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.solution_listbox.config(yscrollcommand=scrollbar.set)

        btn_frame = ttk.Frame(left_panel)
        btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(btn_frame, text="应用方案", command=self._on_apply).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=1)
        ttk.Button(btn_frame, text="保存当前", command=self._on_save_current).pack(
            side=tk.LEFT, expand=True, fill=tk.X, padx=1)

        right_panel = ttk.Frame(content)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        detail_frame = ttk.LabelFrame(right_panel, text="方案详情", padding=10)
        detail_frame.pack(fill=tk.X)

        self._build_detail_info(detail_frame)

        chart_frame = ttk.LabelFrame(right_panel, text="预计力矩曲线", padding=5)
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.torque_chart = TorqueChart(chart_frame, height=260)
        self.torque_chart.pack(fill=tk.BOTH, expand=True)

        optimizer_frame = ttk.LabelFrame(main_container, text="智能设计 - 反推发条参数", padding=10)
        optimizer_frame.pack(fill=tk.X, pady=(10, 0))

        self._build_optimizer(optimizer_frame)

    def _build_detail_info(self, parent):
        """构建详情信息"""
        top_info = ttk.Frame(parent)
        top_info.pack(fill=tk.X)

        self.name_label = ttk.Label(top_info, text="请选择一个方案",
                                     font=('Arial', 12, 'bold'))
        self.name_label.pack(side=tk.LEFT)

        self.grade_label = ttk.Label(top_info, text="",
                                      foreground='white',
                                      font=('Arial', 9, 'bold'),
                                      padding=(8, 2))
        self.grade_label.pack(side=tk.RIGHT)

        self.desc_label = ttk.Label(parent, text="", foreground='#666',
                                     wraplength=500, justify=tk.LEFT)
        self.desc_label.pack(anchor=tk.W, pady=(5, 10))

        params_frame = ttk.Frame(parent)
        params_frame.pack(fill=tk.X)

        self.param_labels = {}
        params = [
            ("料厚", "thickness", "mm"),
            ("宽度", "width", "mm"),
            ("长度", "length", "mm"),
            ("条盒内径", "case_inner_dia", "mm"),
            ("条轴直径", "arbor_dia", "mm"),
            ("材料", "material", ""),
        ]

        for i, (label, key, unit) in enumerate(params):
            row = i // 3
            col = i % 3 * 2

            ttk.Label(params_frame, text=label + ":").grid(
                row=row, column=col, sticky=tk.W, padx=(0, 5), pady=3)

            val_frame = ttk.Frame(params_frame)
            val_frame.grid(row=row, column=col + 1, sticky=tk.W, padx=(0, 15), pady=3)

            val_label = ttk.Label(val_frame, text="-", foreground='#2ca02c',
                                  font=('Arial', 10, 'bold'))
            val_label.pack(side=tk.LEFT)
            if unit:
                ttk.Label(val_frame, text=f" {unit}").pack(side=tk.LEFT)

            self.param_labels[key] = val_label

        perf_frame = ttk.LabelFrame(parent, text="性能指标", padding=8)
        perf_frame.pack(fill=tk.X, pady=(10, 0))

        self.perf_labels = {}
        perfs = [
            ("满弦力矩", "max_torque", "g·cm"),
            ("末端力矩", "min_torque", "g·cm"),
            ("动储时长", "reserve_hours", "小时"),
            ("总圈数", "total_turns", "圈"),
        ]

        for i, (label, key, unit) in enumerate(perfs):
            ttk.Label(perf_frame, text=label + ":").grid(
                row=0, column=i * 2, sticky=tk.W, padx=(0, 5))

            val_frame = ttk.Frame(perf_frame)
            val_frame.grid(row=0, column=i * 2 + 1, sticky=tk.W, padx=(0, 15))

            val_label = ttk.Label(val_frame, text="-", foreground='#ff7f0e',
                                  font=('Arial', 10, 'bold'))
            val_label.pack(side=tk.LEFT)
            ttk.Label(val_frame, text=f" {unit}").pack(side=tk.LEFT)

            self.perf_labels[key] = val_label

    def _build_optimizer(self, parent):
        """构建设计优化器"""
        input_frame = ttk.Frame(parent)
        input_frame.pack(fill=tk.X)

        fields = [
            ("目标动储 (小时)", "target_reserve", "72"),
            ("条盒内径 (mm)", "case_dia", "10.0"),
            ("条轴直径 (mm)", "arbor_dia", "1.5"),
            ("目标力矩 (g·cm)", "target_torque", "30"),
        ]

        self.optimizer_entries = {}
        for label, key, default in fields:
            frame = ttk.Frame(input_frame)
            frame.pack(side=tk.LEFT, padx=(0, 15))

            ttk.Label(frame, text=label).pack(anchor=tk.W)
            entry = ttk.Entry(frame, width=12)
            entry.pack()
            entry.insert(0, default)
            self.optimizer_entries[key] = entry

        ttk.Label(input_frame, text="材料:").pack(side=tk.LEFT, padx=(10, 5))
        self.optimizer_material = tk.StringVar(value="镍铬钢")
        ttk.Combobox(input_frame, textvariable=self.optimizer_material,
                      values=MaterialLibrary.list_materials(),
                      state='readonly', width=12).pack(side=tk.LEFT)

        ttk.Button(input_frame, text="反推参数",
                   command=self._on_optimize).pack(side=tk.LEFT, padx=(20, 0))

        result_frame = ttk.Frame(parent)
        result_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(result_frame, text="推荐方案:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        self.optimizer_tree = ttk.Treeview(result_frame, height=4,
                                            columns=('thickness', 'width', 'length',
                                                     'reserve', 'torque', 'fill'),
                                            show='headings')

        self.optimizer_tree.heading('thickness', text='料厚(mm)')
        self.optimizer_tree.heading('width', text='宽度(mm)')
        self.optimizer_tree.heading('length', text='长度(mm)')
        self.optimizer_tree.heading('reserve', text='动储(小时)')
        self.optimizer_tree.heading('torque', text='力矩(g·cm)')
        self.optimizer_tree.heading('fill', text='装填率(%)')

        for col in ['thickness', 'width', 'length', 'reserve', 'torque', 'fill']:
            self.optimizer_tree.column(col, width=80, anchor=tk.CENTER)

        self.optimizer_tree.pack(fill=tk.X, pady=(5, 0))
        self.optimizer_tree.bind('<Double-1>', lambda e: self._on_optimizer_select())

        ttk.Label(parent, text="提示: 双击方案可应用到参数录入页面",
                  foreground='gray', font=('Arial', 9)).pack(anchor=tk.W, pady=(5, 0))

    def _load_categories(self):
        """加载分类"""
        if not self.storage:
            return

        categories = ["全部"] + self.storage.get_categories()
        self.category_combo.config(values=categories)

    def _refresh_solutions(self):
        """刷新方案列表"""
        if not self.storage:
            return

        self.solutions = self.storage.list_solutions()
        self._filter_solutions()

    def _filter_solutions(self):
        """过滤方案列表"""
        category = self.category_var.get() if hasattr(self, 'category_var') else "全部"
        grade = self.grade_var.get() if hasattr(self, 'grade_var') else "全部"
        search_text = self.search_entry.get().lower() if hasattr(self, 'search_entry') else ""

        self.solution_listbox.delete(0, tk.END)

        for solution in self.solutions:
            if category != "全部" and solution.category != category:
                continue
            if grade != "全部" and solution.reserve_grade != grade:
                continue

            if search_text:
                text = f"{solution.name} {solution.description} {solution.category}".lower()
                if search_text not in text:
                    continue

            display_text = f"  [{solution.reserve_grade}] {solution.name}"
            self.solution_listbox.insert(tk.END, display_text)

    def _on_select_solution(self, event):
        """选择方案"""
        selection = self.solution_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        filtered = self._get_filtered_solutions()

        if idx < len(filtered):
            self.selected_solution = filtered[idx]
            self._show_solution_detail()

    def _get_filtered_solutions(self):
        """获取过滤后的方案列表"""
        category = self.category_var.get()
        grade = self.grade_var.get()
        search_text = self.search_entry.get().lower()

        filtered = []
        for solution in self.solutions:
            if category != "全部" and solution.category != category:
                continue
            if grade != "全部" and solution.reserve_grade != grade:
                continue

            if search_text:
                text = f"{solution.name} {solution.description} {solution.category}".lower()
                if search_text not in text:
                    continue

            filtered.append(solution)

        return filtered

    def _show_solution_detail(self):
        """显示方案详情"""
        if not self.selected_solution:
            return

        s = self.selected_solution

        self.name_label.config(text=s.name)
        self.grade_label.config(text=s.reserve_grade)

        grade_colors = {
            "标准": "#1f77b4",
            "长动力": "#2ca02c",
            "超长动力": "#9467bd",
            "超短动力": "#ff7f0e",
        }
        color = grade_colors.get(s.reserve_grade, '#666')
        self.grade_label.config(background=color)

        self.desc_label.config(text=s.description or "-")

        params = s.params
        if params:
            self.param_labels["thickness"].config(text=str(params.get('thickness', '-')))
            self.param_labels["width"].config(text=str(params.get('width', '-')))
            self.param_labels["length"].config(text=str(params.get('length', '-')))
            self.param_labels["case_inner_dia"].config(text=str(params.get('case_inner_dia', '-')))
            self.param_labels["arbor_dia"].config(text=str(params.get('arbor_dia', '-')))
            self.param_labels["material"].config(text=str(params.get('material', '-')))

        perf = s.performance
        if perf:
            self.perf_labels["max_torque"].config(text=str(perf.get('max_torque', '-')))
            self.perf_labels["min_torque"].config(text=str(perf.get('min_torque', '-')))
            self.perf_labels["reserve_hours"].config(text=str(perf.get('reserve_hours', '-')))
            self.perf_labels["total_turns"].config(text=str(perf.get('total_turns', '-')))

        self._update_chart()

    def _update_chart(self):
        """更新曲线图"""
        if not self.selected_solution:
            return

        params_data = self.selected_solution.params
        if not params_data:
            return

        try:
            params = SpringParams.from_dict(params_data)
            result = perform_full_analysis(params)

            self.torque_chart.set_data(
                [result.torque_curve],
                curve_names=["预计力矩"],
                curve_colors=['#9467bd'],
                decay_segments=result.decay_segments
            )
            self.torque_chart.set_title(self.selected_solution.name + " 力矩曲线")
        except Exception as e:
            pass

    def _on_apply(self):
        """应用方案"""
        if not self.selected_solution:
            messagebox.showinfo("提示", "请先选择一个方案")
            return

        if self.app:
            params_data = self.selected_solution.params
            if params_data:
                params = SpringParams.from_dict(params_data)
                self.app.current_params = params
                self.app.perform_analysis()

                if hasattr(self.app, 'input_page'):
                    self.app.input_page.set_params(params)

                self.app.show_page("torque")

    def _on_save_current(self):
        """保存当前参数为方案"""
        if self.app and hasattr(self.app, 'current_params') and self.app.current_params:
            self.app.show_save_solution_dialog(self.app.current_params)
        else:
            messagebox.showinfo("提示", "请先在录入页面设置参数")

    def _on_optimize(self):
        """反推参数"""
        try:
            target_reserve = float(self.optimizer_entries["target_reserve"].get())
            case_dia = float(self.optimizer_entries["case_dia"].get())
            arbor_dia = float(self.optimizer_entries["arbor_dia"].get())
            target_torque = float(self.optimizer_entries["target_torque"].get())
            material = self.optimizer_material.get()
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数值")
            return

        solutions = DesignOptimizer.reverse_design(
            target_reserve_hours=target_reserve,
            case_inner_dia=case_dia,
            arbor_dia=arbor_dia,
            material=material,
            target_torque=target_torque
        )

        for item in self.optimizer_tree.get_children():
            self.optimizer_tree.delete(item)

        for sol in solutions:
            self.optimizer_tree.insert('', tk.END, values=(
                sol['thickness'],
                sol['width'],
                sol['length'],
                f"{sol['estimated_reserve_hours']:.1f}",
                f"{sol['max_torque']:.1f}",
                f"{sol['fill_ratio']:.1f}"
            ))

        self.optimizer_results = solutions

    def _on_optimizer_select(self):
        """选择反推结果"""
        selection = self.optimizer_tree.selection()
        if not selection:
            return

        idx = self.optimizer_tree.index(selection[0])
        if hasattr(self, 'optimizer_results') and idx < len(self.optimizer_results):
            sol = self.optimizer_results[idx]
            params = sol.get('params')
            if params and self.app:
                self.app.current_params = params
                self.app.perform_analysis()

                if hasattr(self.app, 'input_page'):
                    self.app.input_page.set_params(params)

                self.app.show_page("torque")

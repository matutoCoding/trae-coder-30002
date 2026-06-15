"""
发条录入页面
录入发条的料厚、长度、条盒内径等参数
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.mechanics import SpringParams, MaterialLibrary, SpringGeometry
from ui.widgets.chart_canvas import SpringCrossSection


class InputPage(ttk.Frame):
    """发条参数录入页面"""

    def __init__(self, master, app=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.params = SpringParams()

        self._build_ui()
        self._load_default_values()

    def _build_ui(self):
        """构建界面"""
        main_container = ttk.Frame(self, padding=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_container, text="发条参数录入",
                                font=('Arial', 16, 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, 15))

        content = ttk.Frame(main_container)
        content.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.LabelFrame(content, text="基础参数", padding=15)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        right_panel = ttk.LabelFrame(content, text="材料与环境", padding=15)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        self._build_basic_params(left_panel)
        self._build_material_params(right_panel)

        bottom_panel = ttk.Frame(main_container)
        bottom_panel.pack(fill=tk.X, pady=(15, 0))

        preview_frame = ttk.LabelFrame(bottom_panel, text="发条截面预览", padding=10)
        preview_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        self.preview_chart = SpringCrossSection(preview_frame, height=220)
        self.preview_chart.pack(fill=tk.BOTH, expand=True)

        quick_calc_frame = ttk.LabelFrame(bottom_panel, text="快速校验", padding=10)
        quick_calc_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))

        self._build_quick_calc(quick_calc_frame)

        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill=tk.X, pady=(15, 0))

        ttk.Button(button_frame, text="计算并分析", command=self._on_calculate,
                   style='Accent.TButton').pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="重置参数", command=self._on_reset).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="保存为方案", command=self._on_save_solution).pack(side=tk.RIGHT, padx=5)

    def _build_basic_params(self, parent):
        """构建基础参数输入区"""
        fields = [
            ("发条料厚 (mm)", "thickness", "0.05 - 0.30"),
            ("发条宽度 (mm)", "width", "0.5 - 3.0"),
            ("发条长度 (mm)", "length", "50 - 1000"),
            ("条盒内径 (mm)", "case_inner_dia", "5 - 30"),
            ("条轴直径 (mm)", "arbor_dia", "1 - 5"),
        ]

        self.entries = {}

        for i, (label, key, hint) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=i, column=0, sticky=tk.W, pady=5)

            frame = ttk.Frame(parent)
            frame.grid(row=i, column=1, sticky=tk.EW, pady=5, padx=(10, 0))

            entry = ttk.Entry(frame, width=15)
            entry.pack(side=tk.LEFT)
            entry.bind('<KeyRelease>', lambda e, k=key: self._on_param_change(k))

            ttk.Label(frame, text=hint, foreground='gray',
                      font=('Arial', 8)).pack(side=tk.LEFT, padx=(5, 0))

            self.entries[key] = entry

        parent.columnconfigure(1, weight=1)

    def _build_material_params(self, parent):
        """构建材料参数区"""
        ttk.Label(parent, text="发条材料:").grid(row=0, column=0, sticky=tk.W, pady=5)

        materials = MaterialLibrary.list_materials()
        self.material_var = tk.StringVar(value="镍铬钢")
        material_combo = ttk.Combobox(parent, textvariable=self.material_var,
                                       values=materials, state='readonly', width=15)
        material_combo.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        material_combo.bind('<<ComboboxSelected>>', self._on_material_change)

        ttk.Label(parent, text="参考温度 (°C):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.temp_entry = ttk.Entry(parent, width=15)
        self.temp_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        self.temp_entry.bind('<KeyRelease>', lambda e: self._on_param_change('temp'))

        info_frame = ttk.LabelFrame(parent, text="材料属性", padding=8)
        info_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(15, 0))

        self.material_info_labels = {}
        info_items = [
            ("弹性模量 (GPa)", "E_GPa"),
            ("温度系数 (/°C)", "temp_coeff"),
            ("密度 (g/cm³)", "density"),
            ("屈服强度 (MPa)", "yield_strength"),
        ]

        for i, (label, key) in enumerate(info_items):
            ttk.Label(info_frame, text=label).grid(row=i, column=0, sticky=tk.W, pady=3)
            val_label = ttk.Label(info_frame, text="-", foreground='#1f77b4')
            val_label.grid(row=i, column=1, sticky=tk.W, pady=3, padx=(10, 0))
            self.material_info_labels[key] = val_label

        parent.columnconfigure(1, weight=1)

    def _build_quick_calc(self, parent):
        """构建快速校验区"""
        self.quick_calc_labels = {}
        calc_items = [
            ("估计总圈数", "turns", "圈"),
            ("条盒装填系数", "fill_ratio", "%"),
            ("截面惯性矩", "inertia", "mm⁴"),
            ("满弦力矩(估算)", "max_torque", "g·cm"),
            ("动储时长(估算)", "reserve", "小时"),
        ]

        for i, (label, key, unit) in enumerate(calc_items):
            ttk.Label(parent, text=label + ":").grid(row=i, column=0, sticky=tk.W, pady=4)
            val_frame = ttk.Frame(parent)
            val_frame.grid(row=i, column=1, sticky=tk.W, pady=4, padx=(10, 0))

            val_label = ttk.Label(val_frame, text="-", foreground='#2ca02c',
                                  font=('Arial', 10, 'bold'))
            val_label.pack(side=tk.LEFT)
            ttk.Label(val_frame, text=f" {unit}").pack(side=tk.LEFT)

            self.quick_calc_labels[key] = val_label

        self.status_label = ttk.Label(parent, text="", foreground='#d62728',
                                      font=('Arial', 9))
        self.status_label.grid(row=len(calc_items), column=0, columnspan=2,
                               sticky=tk.W, pady=(10, 0))

        parent.columnconfigure(1, weight=1)

    def _load_default_values(self):
        """加载默认值"""
        defaults = {
            "thickness": "0.12",
            "width": "1.2",
            "length": "200.0",
            "case_inner_dia": "10.0",
            "arbor_dia": "1.5",
        }

        for key, val in defaults.items():
            self.entries[key].delete(0, tk.END)
            self.entries[key].insert(0, val)

        self.temp_entry.delete(0, tk.END)
        self.temp_entry.insert(0, "20")

        self._update_material_info()
        self._update_quick_calc()
        self._update_preview()

    def _get_params(self) -> SpringParams:
        """获取当前参数"""
        try:
            params = SpringParams()
            params.thickness = float(self.entries["thickness"].get())
            params.width = float(self.entries["width"].get())
            params.length = float(self.entries["length"].get())
            params.case_inner_dia = float(self.entries["case_inner_dia"].get())
            params.arbor_dia = float(self.entries["arbor_dia"].get())
            params.material = self.material_var.get()

            mat_info = MaterialLibrary.get_material(params.material)
            if mat_info:
                params.E_ref = mat_info["E_ref"]
                params.E_temp_coeff = mat_info["E_temp_coeff"]
                params.density = mat_info["density"]

            return params
        except ValueError:
            return None

    def _on_param_change(self, param_key):
        """参数变化时更新预览"""
        self._update_quick_calc()
        self._update_preview()

    def _on_material_change(self, event=None):
        """材料改变时更新"""
        self._update_material_info()
        self._update_quick_calc()
        self._update_preview()

    def _update_material_info(self):
        """更新材料属性显示"""
        material = self.material_var.get()
        mat_info = MaterialLibrary.get_material(material)

        if mat_info:
            self.material_info_labels["E_GPa"].config(
                text=f"{mat_info['E_ref'] / 1000:.1f}")
            self.material_info_labels["temp_coeff"].config(
                text=f"{mat_info['E_temp_coeff']:.5f}")
            self.material_info_labels["density"].config(
                text=f"{mat_info['density']:.2f}")
            self.material_info_labels["yield_strength"].config(
                text=f"{mat_info['yield_strength']:.0f}")

    def _update_quick_calc(self):
        """更新快速计算结果"""
        params = self._get_params()
        if not params:
            return

        try:
            turns = SpringGeometry.estimate_turns_by_length(
                params.length, params.case_inner_dia,
                params.arbor_dia, params.thickness
            )

            case_check = SpringGeometry.check_case_volume(params)

            I = SpringGeometry.calc_section_inertia(params.width, params.thickness)

            from core.mechanics import TorqueCalculator
            max_torque = TorqueCalculator.calc_max_torque(params,
                                                           float(self.temp_entry.get() or 20))

            reserve_hours = max_torque * 0.6 / 1.5 * 30 if max_torque > 0 else 0

            self.quick_calc_labels["turns"].config(text=f"{turns:.1f}")
            self.quick_calc_labels["fill_ratio"].config(
                text=f"{case_check['fill_ratio'] * 100:.1f}")
            self.quick_calc_labels["inertia"].config(text=f"{I:.4f}")
            self.quick_calc_labels["max_torque"].config(text=f"{max_torque:.1f}")
            self.quick_calc_labels["reserve"].config(text=f"{reserve_hours:.0f}")

            if case_check["warnings"]:
                self.status_label.config(text="⚠ " + case_check["warnings"][0])
            else:
                self.status_label.config(text="✓ 参数正常", foreground='#2ca02c')

        except Exception as e:
            pass

    def _update_preview(self):
        """更新预览图"""
        params = self._get_params()
        if params:
            self.preview_chart.set_params(params)

    def _on_calculate(self):
        """计算按钮事件"""
        params = self._get_params()
        if not params:
            messagebox.showerror("错误", "请输入有效的参数值")
            return

        if self.app:
            try:
                temp = float(self.temp_entry.get())
            except ValueError:
                temp = 20.0

            self.app.current_params = params
            self.app.current_temp = temp
            self.app.perform_analysis()
            self.app.show_page("torque")

    def _on_reset(self):
        """重置参数"""
        self._load_default_values()

    def _on_save_solution(self):
        """保存为方案"""
        params = self._get_params()
        if not params:
            messagebox.showerror("错误", "请输入有效的参数值")
            return

        if self.app:
            self.app.show_save_solution_dialog(params)

    def set_params(self, params: SpringParams):
        """设置参数"""
        self.entries["thickness"].delete(0, tk.END)
        self.entries["thickness"].insert(0, str(params.thickness))

        self.entries["width"].delete(0, tk.END)
        self.entries["width"].insert(0, str(params.width))

        self.entries["length"].delete(0, tk.END)
        self.entries["length"].insert(0, str(params.length))

        self.entries["case_inner_dia"].delete(0, tk.END)
        self.entries["case_inner_dia"].insert(0, str(params.case_inner_dia))

        self.entries["arbor_dia"].delete(0, tk.END)
        self.entries["arbor_dia"].insert(0, str(params.arbor_dia))

        self.material_var.set(params.material)

        self._update_material_info()
        self._update_quick_calc()
        self._update_preview()

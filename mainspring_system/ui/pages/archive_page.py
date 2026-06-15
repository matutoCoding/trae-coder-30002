"""
动储档案页面
记录每款机芯的力矩曲线与实测动储，建立档案
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.storage import MovementArchive, DataStorage, SpringSolution
from core.mechanics import SpringParams, perform_full_analysis, TorquePoint
from ui.widgets.chart_canvas import TorqueChart


class ArchivePage(ttk.Frame):
    """动储档案页面"""

    def __init__(self, master, app=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.storage = None
        self.archives = []
        self.selected_archive = None
        self.show_measured_curve = tk.BooleanVar(value=True)

        self._build_ui()

    def set_storage(self, storage: DataStorage):
        self.storage = storage
        self._refresh_archives()

    def _build_ui(self):
        """构建界面"""
        main_container = ttk.Frame(self, padding=10)
        main_container.pack(fill=tk.BOTH, expand=True)

        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(title_frame, text="动储档案管理",
                  font=('Arial', 16, 'bold')).pack(side=tk.LEFT)

        btn_frame = ttk.Frame(title_frame)
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="从当前分析生成",
                   command=self._on_create_from_analysis).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="新建档案",
                   command=self._on_new_archive).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="编辑档案",
                   command=self._on_edit_archive).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="删除档案",
                   command=self._on_delete_archive).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="沉淀为方案",
                   command=self._on_promote_to_solution).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="应用到分析",
                   command=self._on_apply_to_analysis).pack(side=tk.LEFT, padx=2)

        content = ttk.Frame(main_container)
        content.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.LabelFrame(content, text="机芯档案列表", padding=5)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.config(width=280)
        left_panel.pack_propagate(False)

        search_frame = ttk.Frame(left_panel)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(search_frame, text="搜索:").pack(side=tk.LEFT)
        self.search_entry = ttk.Entry(search_frame)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.search_entry.bind('<KeyRelease>', lambda e: self._filter_archives())

        self.archive_listbox = tk.Listbox(left_panel, relief=tk.FLAT)
        self.archive_listbox.pack(fill=tk.BOTH, expand=True)
        self.archive_listbox.bind('<<ListboxSelect>>', self._on_select_archive)

        scrollbar = ttk.Scrollbar(left_panel, orient=tk.VERTICAL,
                                   command=self.archive_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.archive_listbox.config(yscrollcommand=scrollbar.set)

        right_panel = ttk.Frame(content)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(right_panel)
        notebook.pack(fill=tk.BOTH, expand=True)

        self._build_detail_tab(notebook)
        self._build_comparison_tab(notebook)
        self._build_risks_tab(notebook)

        self.notebook = notebook

    def _build_detail_tab(self, notebook):
        """详情标签页"""
        tab = ttk.Frame(notebook, padding=5)
        notebook.add(tab, text="详情")

        detail_top = ttk.Frame(tab)
        detail_top.pack(fill=tk.X, pady=(0, 10))

        self._build_detail_info(detail_top)

        chart_frame = ttk.LabelFrame(tab, text="力矩曲线", padding=5)
        chart_frame.pack(fill=tk.BOTH, expand=True)

        chart_opt_frame = ttk.Frame(chart_frame)
        chart_opt_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Checkbutton(chart_opt_frame, text="显示实测点",
                         variable=self.show_measured_curve,
                         command=self._update_chart).pack(side=tk.LEFT)

        self.torque_chart = TorqueChart(chart_frame, height=260)
        self.torque_chart.pack(fill=tk.BOTH, expand=True)

        bottom_frame = ttk.LabelFrame(tab, text="实测数据记录", padding=10)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        self._build_measured_data(bottom_frame)

    def _build_comparison_tab(self, notebook):
        """实测对比标签页"""
        tab = ttk.Frame(notebook, padding=5)
        notebook.add(tab, text="实测对比")

        comp_chart_frame = ttk.LabelFrame(tab, text="计算 vs 实测 对比", padding=5)
        comp_chart_frame.pack(fill=tk.BOTH, expand=True)

        self.comparison_chart = TorqueChart(comp_chart_frame, height=300)
        self.comparison_chart.pack(fill=tk.BOTH, expand=True)

        comp_table_frame = ttk.LabelFrame(tab, text="偏差分析", padding=10)
        comp_table_frame.pack(fill=tk.X, pady=(10, 0))

        headers = ["指标", "计算值", "实测值", "偏差", "偏差率"]
        for i, h in enumerate(headers):
            ttk.Label(comp_table_frame, text=h,
                      font=('Arial', 10, 'bold'),
                      foreground='#333').grid(row=0, column=i, padx=15, pady=5, sticky=tk.W)

        self.comp_labels = {}
        comp_items = [
            ("满弦力矩 (g·cm)", "max_torque"),
            ("末端力矩 (g·cm)", "min_torque"),
            ("动储时长 (小时)", "reserve"),
        ]

        for i, (label, key) in enumerate(comp_items):
            ttk.Label(comp_table_frame, text=label).grid(
                row=i + 1, column=0, padx=15, pady=3, sticky=tk.W)

            calc_label = ttk.Label(comp_table_frame, text="-", foreground='#1f77b4')
            calc_label.grid(row=i + 1, column=1, padx=15, pady=3, sticky=tk.W)
            self.comp_labels[f"{key}_calc"] = calc_label

            meas_label = ttk.Label(comp_table_frame, text="-", foreground='#ff7f0e')
            meas_label.grid(row=i + 1, column=2, padx=15, pady=3, sticky=tk.W)
            self.comp_labels[f"{key}_meas"] = meas_label

            diff_label = ttk.Label(comp_table_frame, text="-")
            diff_label.grid(row=i + 1, column=3, padx=15, pady=3, sticky=tk.W)
            self.comp_labels[f"{key}_diff"] = diff_label

            pct_label = ttk.Label(comp_table_frame, text="-", font=('Arial', 10, 'bold'))
            pct_label.grid(row=i + 1, column=4, padx=15, pady=3, sticky=tk.W)
            self.comp_labels[f"{key}_pct"] = pct_label

        verdict_frame = ttk.Frame(tab)
        verdict_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Label(verdict_frame, text="模型吻合度评估:",
                  font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        self.verdict_label = ttk.Label(verdict_frame, text="-",
                                        font=('Arial', 11, 'bold'))
        self.verdict_label.pack(side=tk.LEFT, padx=(10, 0))

    def _build_risks_tab(self, notebook):
        """风险预警标签页"""
        tab = ttk.Frame(notebook, padding=5)
        notebook.add(tab, text="风险与校验")

        risk_frame = ttk.LabelFrame(tab, text="风险预警", padding=10)
        risk_frame.pack(fill=tk.X)

        self.risk_listbox = tk.Listbox(risk_frame, height=6, relief=tk.FLAT,
                                        fg='#d62728')
        self.risk_listbox.pack(fill=tk.X)

        case_frame = ttk.LabelFrame(tab, text="条盒容积校验", padding=10)
        case_frame.pack(fill=tk.X, pady=(10, 0))

        self.case_labels = {}
        case_items = [
            ("条盒内径", "case_inner_dia", "mm"),
            ("条轴直径", "arbor_dia", "mm"),
            ("可用径向空间", "radial_space", "mm"),
            ("理论圈数", "estimated_turns", "圈"),
            ("装填系数", "packing_factor", ""),
            ("容积利用率", "volume_utilization", "%"),
            ("状态", "status", ""),
        ]

        for i, (label, key, unit) in enumerate(case_items):
            row = i // 2
            col = i % 2
            f = ttk.Frame(case_frame)
            f.grid(row=row, column=col, sticky=tk.W, padx=15, pady=3)

            ttk.Label(f, text=f"{label}: ").pack(side=tk.LEFT)
            val_label = ttk.Label(f, text="-", foreground='#2ca02c',
                                  font=('Arial', 10, 'bold'))
            val_label.pack(side=tk.LEFT)
            if unit:
                ttk.Label(f, text=f" {unit}").pack(side=tk.LEFT)
            self.case_labels[key] = val_label

        note_frame = ttk.LabelFrame(tab, text="备注说明", padding=10)
        note_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.notes_display = tk.Text(note_frame, height=5, relief=tk.FLAT,
                                      state=tk.DISABLED, wrap=tk.WORD)
        self.notes_display.pack(fill=tk.BOTH, expand=True)

    def _build_detail_info(self, parent):
        """构建详情信息区"""
        info_frame = ttk.LabelFrame(parent, text="机芯信息", padding=10)
        info_frame.pack(fill=tk.X)

        self.name_label = ttk.Label(info_frame, text="未选择档案",
                                     font=('Arial', 12, 'bold'))
        self.name_label.grid(row=0, column=0, columnspan=4, sticky=tk.W, pady=(0, 8))

        info_items = [
            ("型号", "model", 0, 1),
            ("厂商", "manufacturer", 0, 3),
            ("创建时间", "created", 1, 1),
            ("更新时间", "updated", 1, 3),
        ]

        self.info_labels = {}
        for label, key, row, col in info_items:
            ttk.Label(info_frame, text=label + ":").grid(row=row + 2, column=col,
                                                           sticky=tk.W, pady=3)
            val_label = ttk.Label(info_frame, text="-", foreground='#1f77b4')
            val_label.grid(row=row + 2, column=col + 1, sticky=tk.W, pady=3, padx=(5, 15))
            self.info_labels[key] = val_label

        params_frame = ttk.LabelFrame(parent, text="发条参数", padding=10)
        params_frame.pack(fill=tk.X, pady=(10, 0))

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
            ttk.Label(params_frame, text=label + ":").grid(row=0, column=i * 2,
                                                            sticky=tk.W, padx=(0, 5))
            val_frame = ttk.Frame(params_frame)
            val_frame.grid(row=0, column=i * 2 + 1, sticky=tk.W, padx=(0, 15))

            val_label = ttk.Label(val_frame, text="-", foreground='#2ca02c',
                                  font=('Arial', 10, 'bold'))
            val_label.pack(side=tk.LEFT)
            if unit:
                ttk.Label(val_frame, text=f" {unit}").pack(side=tk.LEFT)

            self.param_labels[key] = val_label

    def _build_measured_data(self, parent):
        """构建实测数据区"""
        self.measured_labels = {}
        items = [
            ("实测动储时长", "measured_reserve", "小时"),
            ("实测满弦力矩", "measured_max_torque", "g·cm"),
            ("实测末端力矩", "measured_min_torque", "g·cm"),
        ]

        for i, (label, key, unit) in enumerate(items):
            ttk.Label(parent, text=label + ":").grid(row=0, column=i * 2,
                                                      sticky=tk.W, padx=(0, 5))
            val_frame = ttk.Frame(parent)
            val_frame.grid(row=0, column=i * 2 + 1, sticky=tk.W, padx=(0, 20))

            val_label = ttk.Label(val_frame, text="-", foreground='#9467bd',
                                  font=('Arial', 10, 'bold'))
            val_label.pack(side=tk.LEFT)
            ttk.Label(val_frame, text=f" {unit}").pack(side=tk.LEFT)

            self.measured_labels[key] = val_label

        ttk.Label(parent, text="备注:").grid(row=1, column=0, sticky=tk.NW, pady=(10, 0))
        self.notes_label = ttk.Label(parent, text="-", foreground='#666',
                                      wraplength=500, justify=tk.LEFT)
        self.notes_label.grid(row=1, column=1, columnspan=5, sticky=tk.W,
                              pady=(10, 0), padx=(5, 0))

    def _refresh_archives(self):
        """刷新档案列表"""
        if not self.storage:
            return

        self.archives = self.storage.list_archives()
        self._filter_archives()

    def _filter_archives(self):
        """过滤档案列表"""
        search_text = self.search_entry.get().lower() if hasattr(self, 'search_entry') else ""

        self.archive_listbox.delete(0, tk.END)

        for archive in self.archives:
            display_text = archive.name or archive.model or archive.id

            if search_text:
                text = f"{archive.name} {archive.model} {archive.manufacturer}".lower()
                if search_text not in text:
                    continue

            self.archive_listbox.insert(tk.END, f"  {display_text}")

    def _on_select_archive(self, event):
        """选择档案"""
        selection = self.archive_listbox.curselection()
        if not selection:
            return

        idx = selection[0]
        filtered_archives = self._get_filtered_archives()

        if idx < len(filtered_archives):
            self.selected_archive = filtered_archives[idx]
            self._show_archive_detail()
            self._show_comparison()
            self._show_risks_and_case()

    def _get_filtered_archives(self):
        """获取过滤后的档案列表"""
        search_text = self.search_entry.get().lower() if hasattr(self, 'search_entry') else ""

        if not search_text:
            return self.archives

        filtered = []
        for archive in self.archives:
            text = f"{archive.name} {archive.model} {archive.manufacturer}".lower()
            if search_text in text:
                filtered.append(archive)
        return filtered

    def _show_archive_detail(self):
        """显示档案详情"""
        if not self.selected_archive:
            return

        a = self.selected_archive

        self.name_label.config(text=a.name or "未命名机芯")
        self.info_labels["model"].config(text=a.model or "-")
        self.info_labels["manufacturer"].config(text=a.manufacturer or "-")
        self.info_labels["created"].config(text=a.created_at[:19] if a.created_at else "-")
        self.info_labels["updated"].config(text=a.updated_at[:19] if a.updated_at else "-")

        params = a.spring_params
        if params:
            self.param_labels["thickness"].config(text=f"{params.get('thickness', '-')}")
            self.param_labels["width"].config(text=f"{params.get('width', '-')}")
            self.param_labels["length"].config(text=f"{params.get('length', '-')}")
            self.param_labels["case_inner_dia"].config(text=f"{params.get('case_inner_dia', '-')}")
            self.param_labels["arbor_dia"].config(text=f"{params.get('arbor_dia', '-')}")
            self.param_labels["material"].config(text=params.get('material', '-'))

        self.measured_labels["measured_reserve"].config(
            text=f"{a.measured_reserve_hours:.1f}" if a.measured_reserve_hours else "-")
        self.measured_labels["measured_max_torque"].config(
            text=f"{a.measured_max_torque:.1f}" if a.measured_max_torque else "-")
        self.measured_labels["measured_min_torque"].config(
            text=f"{a.measured_min_torque:.1f}" if a.measured_min_torque else "-")

        self.notes_label.config(text=a.notes or "-")

        self._update_chart()

    def _update_chart(self):
        """更新曲线图"""
        if not self.selected_archive:
            return

        curve_data = self._get_curve_from_archive()
        decay_segments = [tuple(s) for s in self.selected_archive.decay_segments] if self.selected_archive.decay_segments else []

        curves = [curve_data]
        names = ["计算力矩"]
        colors = ['#1f77b4']

        if self.show_measured_curve.get() and self._has_measured_data():
            meas_points = self._get_measured_curve_points(curve_data)
            if meas_points:
                curves.append(meas_points)
                names.append("实测点")
                colors.append('#ff7f0e')

        self.torque_chart.set_data(
            curves,
            curve_names=names,
            curve_colors=colors,
            decay_segments=decay_segments,
            show_points=[False, True] if len(curves) > 1 else [False]
        )
        self.torque_chart.set_title(f"{self.selected_archive.name or '机芯'} 力矩曲线")

    def _get_curve_from_archive(self):
        """从档案获取力矩曲线"""
        a = self.selected_archive
        if a.torque_curve and len(a.torque_curve) > 0:
            points = []
            for p in a.torque_curve:
                if isinstance(p, dict):
                    points.append(TorquePoint(
                        turn=p.get('turn', 0),
                        angle=p.get('angle', 0),
                        torque=p.get('torque', 0),
                        radius_outer=p.get('radius_outer', 0),
                        radius_inner=p.get('radius_inner', 0),
                        turns_remaining=p.get('turns_remaining', 0)
                    ))
            return points

        if a.spring_params:
            params = SpringParams.from_dict(a.spring_params)
            result = perform_full_analysis(params)
            return result.torque_curve

        return []

    def _has_measured_data(self):
        """检查是否有实测数据"""
        a = self.selected_archive
        if not a:
            return False
        return a.measured_max_torque > 0 or a.measured_min_torque > 0 or a.measured_reserve_hours > 0

    def _get_measured_curve_points(self, calc_curve):
        """根据实测数据生成对比点"""
        if not calc_curve or len(calc_curve) == 0:
            return []

        a = self.selected_archive
        points = []

        if a.measured_max_torque > 0 and len(calc_curve) > 0:
            first = calc_curve[0]
            points.append(TorquePoint(
                turn=first.turn,
                angle=first.angle,
                torque=a.measured_max_torque,
                radius_outer=first.radius_outer,
                radius_inner=first.radius_inner,
                turns_remaining=first.turns_remaining
            ))

        if a.measured_min_torque > 0 and len(calc_curve) > 1:
            last = calc_curve[-1]
            points.append(TorquePoint(
                turn=last.turn,
                angle=last.angle,
                torque=a.measured_min_torque,
                radius_outer=last.radius_outer,
                radius_inner=last.radius_inner,
                turns_remaining=last.turns_remaining
            ))

        return points

    def _show_comparison(self):
        """显示实测对比"""
        if not self.selected_archive:
            return

        a = self.selected_archive
        summary = a.analysis_summary or {}

        calc_max = summary.get('max_torque', 0)
        calc_min = summary.get('min_torque', 0)
        calc_reserve = summary.get('reserve_hours', 0)

        meas_max = a.measured_max_torque
        meas_min = a.measured_min_torque
        meas_reserve = a.measured_reserve_hours

        self._set_comp_value("max_torque", calc_max, meas_max, "g·cm")
        self._set_comp_value("min_torque", calc_min, meas_min, "g·cm")
        self._set_comp_value("reserve", calc_reserve, meas_reserve, "h")

        deviations = a.get_calc_deviation()
        pcts = []
        if 'max_torque_deviation_pct' in deviations:
            pcts.append(abs(deviations['max_torque_deviation_pct']))
        if 'min_torque_deviation_pct' in deviations:
            pcts.append(abs(deviations['min_torque_deviation_pct']))
        if 'reserve_deviation_pct' in deviations:
            pcts.append(abs(deviations['reserve_deviation_pct']))

        if pcts:
            avg_pct = sum(pcts) / len(pcts)
            if avg_pct < 5:
                verdict = "优秀"
                color = '#2ca02c'
            elif avg_pct < 10:
                verdict = "良好"
                color = '#1f77b4'
            elif avg_pct < 20:
                verdict = "一般"
                color = '#ff7f0e'
            else:
                verdict = "偏差较大"
                color = '#d62728'
            self.verdict_label.config(text=f"{verdict} (平均偏差 {avg_pct:.1f}%)", foreground=color)
        else:
            self.verdict_label.config(text="数据不足，无法评估", foreground='#999')

        self._update_comparison_chart()

    def _set_comp_value(self, key, calc_val, meas_val, unit):
        """设置对比值"""
        self.comp_labels[f"{key}_calc"].config(text=f"{calc_val:.2f} {unit}" if calc_val else "-")
        self.comp_labels[f"{key}_meas"].config(text=f"{meas_val:.2f} {unit}" if meas_val else "-")

        if calc_val and meas_val:
            diff = meas_val - calc_val
            pct = diff / calc_val * 100
            self.comp_labels[f"{key}_diff"].config(text=f"{diff:+.2f} {unit}")

            pct_text = f"{pct:+.1f}%"
            color = '#2ca02c' if pct >= 0 else '#d62728'
            self.comp_labels[f"{key}_pct"].config(text=pct_text, foreground=color)
        else:
            self.comp_labels[f"{key}_diff"].config(text="-")
            self.comp_labels[f"{key}_pct"].config(text="-", foreground='#999')

    def _update_comparison_chart(self):
        """更新对比图"""
        if not self.selected_archive:
            return

        calc_curve = self._get_curve_from_archive()
        meas_points = self._get_measured_curve_points(calc_curve)

        curves = [calc_curve]
        names = ["计算曲线"]
        colors = ['#1f77b4']
        show_points = [False]

        if meas_points and len(meas_points) > 0:
            curves.append(meas_points)
            names.append("实测点")
            colors.append('#ff7f0e')
            show_points.append(True)

        decay_segments = [tuple(s) for s in self.selected_archive.decay_segments] if self.selected_archive.decay_segments else []

        self.comparison_chart.set_data(
            curves,
            curve_names=names,
            curve_colors=colors,
            decay_segments=decay_segments,
            show_points=show_points
        )
        self.comparison_chart.set_title("计算与实测力矩对比")

    def _show_risks_and_case(self):
        """显示风险和条盒校验"""
        if not self.selected_archive:
            return

        a = self.selected_archive

        self.risk_listbox.delete(0, tk.END)
        if a.risk_warnings:
            for warning in a.risk_warnings:
                self.risk_listbox.insert(tk.END, f"  ⚠ {warning}")
        else:
            self.risk_listbox.insert(tk.END, "  ✓ 暂无风险预警")
            self.risk_listbox.config(fg='#2ca02c')

        cc = a.case_check or {}
        for key in self.case_labels:
            val = cc.get(key, '-')
            if isinstance(val, float):
                text = f"{val:.2f}"
            else:
                text = str(val)
            self.case_labels[key].config(text=text)

        self.notes_display.config(state=tk.NORMAL)
        self.notes_display.delete('1.0', tk.END)
        self.notes_display.insert('1.0', a.notes or "无备注")
        self.notes_display.config(state=tk.DISABLED)

    def _on_create_from_analysis(self):
        """从当前分析结果生成档案"""
        if not self.app or not hasattr(self.app, 'analysis_result') or self.app.analysis_result is None:
            messagebox.showinfo("提示", "请先在力矩曲线页执行分析")
            return

        name = simpledialog.askstring("生成档案", "请输入机芯档案名称:",
                                      initialvalue=f"分析结果_{datetime.now().strftime('%m%d_%H%M')}")
        if not name:
            return

        result = self.app.analysis_result
        archive = MovementArchive.from_analysis(result, name=name)

        if self.storage and self.storage.save_archive(archive):
            messagebox.showinfo("成功", "档案已保存，包含完整的力矩曲线、风险预警和校验数据")
            self._refresh_archives()
        else:
            messagebox.showerror("错误", "保存失败")

    def _on_new_archive(self):
        """新建档案"""
        dialog = ArchiveEditDialog(self, title="新建机芯档案")
        self.wait_window(dialog)

        if dialog.result:
            if self.storage:
                self.storage.save_archive(dialog.result)
                self._refresh_archives()

    def _on_edit_archive(self):
        """编辑档案"""
        if not self.selected_archive:
            messagebox.showinfo("提示", "请先选择一个档案")
            return

        dialog = ArchiveEditDialog(self, title="编辑机芯档案",
                                    archive=self.selected_archive)
        self.wait_window(dialog)

        if dialog.result:
            orig = self.selected_archive
            updated = dialog.result

            updated.id = orig.id
            updated.created_at = orig.created_at
            updated.torque_curve = orig.torque_curve
            updated.analysis_summary = orig.analysis_summary
            updated.risk_warnings = orig.risk_warnings
            updated.case_check = orig.case_check
            updated.temp_effects = orig.temp_effects
            updated.decay_segments = orig.decay_segments
            updated.spring_params = orig.spring_params

            if self.storage:
                self.storage.save_archive(updated)
                self.selected_archive = updated
                self._refresh_archives()
                self._show_archive_detail()
                self._show_comparison()
                self._show_risks_and_case()

    def _on_delete_archive(self):
        """删除档案"""
        if not self.selected_archive:
            messagebox.showinfo("提示", "请先选择一个档案")
            return

        if messagebox.askyesno("确认删除",
                               f"确定要删除档案 \"{self.selected_archive.name}\" 吗？"):
            if self.storage:
                self.storage.delete_archive(self.selected_archive.id)
                self.selected_archive = None
                self._refresh_archives()

    def _on_promote_to_solution(self):
        """从档案沉淀为方案"""
        if not self.selected_archive:
            messagebox.showinfo("提示", "请先选择一个档案")
            return

        dialog = PromoteSolutionDialog(self, archive=self.selected_archive)
        self.wait_window(dialog)

        if dialog.result:
            if self.storage:
                self.storage.save_solution(dialog.result)
                messagebox.showinfo("成功", f"方案 \"{dialog.result.name}\" 已存入方案库")

    def _on_apply_to_analysis(self):
        """应用到分析"""
        if not self.selected_archive:
            messagebox.showinfo("提示", "请先选择一个档案")
            return

        params_data = self.selected_archive.spring_params
        if not params_data:
            messagebox.showinfo("提示", "该档案没有发条参数")
            return

        if self.app:
            params = SpringParams.from_dict(params_data)
            self.app.current_params = params
            self.app.perform_analysis()

            if hasattr(self.app, 'input_page'):
                self.app.input_page.set_params(params)

            self.app.show_page("torque")


class ArchiveEditDialog(tk.Toplevel):
    """档案编辑对话框"""

    def __init__(self, master, title="编辑档案", archive=None):
        super().__init__(master)
        self.title(title)
        self.result = None
        self.archive = archive

        self._build_ui()
        self._load_data()

        self.transient(master)
        self.grab_set()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w, h = 480, 560
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        """构建界面"""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="基本信息", font=('Arial', 11, 'bold')).pack(
            anchor=tk.W, pady=(0, 5))

        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X)

        self.entries = {}

        fields = [
            ("机芯名称", "name", True),
            ("型号", "model", False),
            ("制造厂商", "manufacturer", False),
        ]

        for label, key, required in fields:
            row = ttk.Frame(info_frame)
            row.pack(fill=tk.X, pady=3)

            lbl_text = label + (" *" if required else "")
            ttk.Label(row, text=lbl_text, width=12).pack(side=tk.LEFT)

            entry = ttk.Entry(row)
            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
            self.entries[key] = entry

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Label(main_frame, text="实测数据", font=('Arial', 11, 'bold')).pack(
            anchor=tk.W, pady=(0, 5))

        measured_frame = ttk.Frame(main_frame)
        measured_frame.pack(fill=tk.X)

        measured_fields = [
            ("实测动储 (小时)", "measured_reserve_hours"),
            ("满弦力矩 (g·cm)", "measured_max_torque"),
            ("末端力矩 (g·cm)", "measured_min_torque"),
        ]

        for label, key in measured_fields:
            row = ttk.Frame(measured_frame)
            row.pack(fill=tk.X, pady=3)

            ttk.Label(row, text=label, width=18).pack(side=tk.LEFT)
            entry = ttk.Entry(row, width=15)
            entry.pack(side=tk.LEFT)
            self.entries[key] = entry

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        ttk.Label(main_frame, text="标签 (逗号分隔)", font=('Arial', 10, 'bold')).pack(
            anchor=tk.W, pady=(0, 5))
        self.tags_entry = ttk.Entry(main_frame)
        self.tags_entry.pack(fill=tk.X)

        ttk.Label(main_frame, text="备注", font=('Arial', 11, 'bold')).pack(
            anchor=tk.W, pady=(10, 5))

        self.notes_text = tk.Text(main_frame, height=6, relief=tk.FLAT,
                                   highlightthickness=1,
                                   highlightbackground='#ccc')
        self.notes_text.pack(fill=tk.BOTH, expand=True)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15)

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="取消", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="保存", command=self._on_save).pack(side=tk.RIGHT, padx=5)

    def _load_data(self):
        """加载数据"""
        if not self.archive:
            return

        a = self.archive
        self.entries["name"].insert(0, a.name or "")
        self.entries["model"].insert(0, a.model or "")
        self.entries["manufacturer"].insert(0, a.manufacturer or "")
        self.entries["measured_reserve_hours"].insert(0, str(a.measured_reserve_hours or ""))
        self.entries["measured_max_torque"].insert(0, str(a.measured_max_torque or ""))
        self.entries["measured_min_torque"].insert(0, str(a.measured_min_torque or ""))
        self.tags_entry.insert(0, ", ".join(a.tags) if a.tags else "")
        self.notes_text.insert('1.0', a.notes or "")

    def _on_save(self):
        """保存"""
        name = self.entries["name"].get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入机芯名称")
            return

        archive = self.archive or MovementArchive()

        archive.name = name
        archive.model = self.entries["model"].get().strip()
        archive.manufacturer = self.entries["manufacturer"].get().strip()

        try:
            val = self.entries["measured_reserve_hours"].get().strip()
            archive.measured_reserve_hours = float(val) if val else 0.0
        except ValueError:
            pass

        try:
            val = self.entries["measured_max_torque"].get().strip()
            archive.measured_max_torque = float(val) if val else 0.0
        except ValueError:
            pass

        try:
            val = self.entries["measured_min_torque"].get().strip()
            archive.measured_min_torque = float(val) if val else 0.0
        except ValueError:
            pass

        tags_text = self.tags_entry.get().strip()
        if tags_text:
            archive.tags = [t.strip() for t in tags_text.split(',') if t.strip()]
        else:
            archive.tags = []

        archive.notes = self.notes_text.get('1.0', tk.END).strip()

        self.result = archive
        self.destroy()

    def _on_cancel(self):
        """取消"""
        self.result = None
        self.destroy()


class PromoteSolutionDialog(tk.Toplevel):
    """档案沉淀为方案对话框"""

    def __init__(self, master, archive):
        super().__init__(master)
        self.title("沉淀为方案")
        self.result = None
        self.archive = archive

        self._build_ui()

        self.transient(master)
        self.grab_set()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w, h = 420, 380
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        """构建界面"""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="从档案生成方案",
                  font=('Arial', 12, 'bold')).pack(anchor=tk.W, pady=(0, 10))

        self.entries = {}

        fields = [
            ("方案名称", "name", True),
            ("方案分类", "category", True),
            ("动储等级", "reserve_grade", True),
        ]

        for label, key, required in fields:
            row = ttk.Frame(main_frame)
            row.pack(fill=tk.X, pady=5)

            lbl_text = label + (" *" if required else "")
            ttk.Label(row, text=lbl_text, width=12).pack(side=tk.LEFT)

            if key == "category":
                combo = ttk.Combobox(row, values=[
                    "标准配置", "长动力", "紧凑型", "特殊应用", "新材料", "自定义"
                ], state='readonly')
                combo.set("自定义")
                combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.entries[key] = combo
            elif key == "reserve_grade":
                combo = ttk.Combobox(row, values=[
                    "标准", "长动力", "超长动力", "超短动力"
                ], state='readonly')
                combo.set("标准")
                combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.entries[key] = combo
            else:
                entry = ttk.Entry(row)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.entries[key] = entry

        self.entries["name"].insert(0, f"源自 {self.archive.name}" if self.archive.name else "新方案")

        ttk.Label(main_frame, text="方案描述",
                  font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(10, 5))
        self.desc_text = tk.Text(main_frame, height=4, relief=tk.FLAT,
                                  highlightthickness=1, highlightbackground='#ccc')
        self.desc_text.pack(fill=tk.X)

        summary = self.archive.analysis_summary or {}
        if summary:
            default_desc = (
                f"满弦力矩 {summary.get('max_torque', 0):.1f} g·cm，"
                f"末端力矩 {summary.get('min_torque', 0):.1f} g·cm，"
                f"总圈数 {summary.get('total_turns', 0):.1f} 圈。"
                f"源档案: {self.archive.name}"
            )
            self.desc_text.insert('1.0', default_desc)

        perf_frame = ttk.LabelFrame(main_frame, text="预计性能", padding=10)
        perf_frame.pack(fill=tk.X, pady=(10, 0))

        perf_text = (
            f"满弦力矩: {summary.get('max_torque', '-'):.1f} g·cm   "
            f"末端力矩: {summary.get('min_torque', '-'):.1f} g·cm\n"
            f"总圈数: {summary.get('total_turns', '-'):.1f} 圈   "
            f"动储: 约 {summary.get('reserve_hours', 0):.1f} 小时"
        ) if summary else "暂无性能数据"
        ttk.Label(perf_frame, text=perf_text, foreground='#2ca02c').pack(anchor=tk.W)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15)

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="取消", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="生成方案", command=self._on_save).pack(side=tk.RIGHT, padx=5)

    def _on_save(self):
        """保存"""
        name = self.entries["name"].get().strip()
        if not name:
            messagebox.showwarning("提示", "请输入方案名称")
            return

        category = self.entries["category"].get()
        reserve_grade = self.entries["reserve_grade"].get()
        description = self.desc_text.get('1.0', tk.END).strip()

        solution = SpringSolution.from_archive(
            self.archive,
            name=name,
            category=category,
            reserve_grade=reserve_grade
        )
        solution.description = description

        self.result = solution
        self.destroy()

    def _on_cancel(self):
        """取消"""
        self.result = None
        self.destroy()

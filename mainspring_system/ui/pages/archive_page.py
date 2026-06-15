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

from core.storage import MovementArchive, DataStorage
from core.mechanics import SpringParams, perform_full_analysis
from ui.widgets.chart_canvas import TorqueChart


class ArchivePage(ttk.Frame):
    """动储档案页面"""

    def __init__(self, master, app=None, **kwargs):
        super().__init__(master, **kwargs)
        self.app = app
        self.storage = None
        self.archives = []
        self.selected_archive = None

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

        ttk.Button(btn_frame, text="新建档案", command=self._on_new_archive).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="编辑档案", command=self._on_edit_archive).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="删除档案", command=self._on_delete_archive).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="应用到分析", command=self._on_apply_to_analysis).pack(side=tk.LEFT, padx=2)

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

        detail_top = ttk.Frame(right_panel)
        detail_top.pack(fill=tk.X, pady=(0, 10))

        self._build_detail_info(detail_top)

        chart_frame = ttk.LabelFrame(right_panel, text="力矩曲线", padding=5)
        chart_frame.pack(fill=tk.BOTH, expand=True)

        self.torque_chart = TorqueChart(chart_frame, height=280)
        self.torque_chart.pack(fill=tk.BOTH, expand=True)

        bottom_frame = ttk.LabelFrame(right_panel, text="实测数据记录", padding=10)
        bottom_frame.pack(fill=tk.X, pady=(10, 0))

        self._build_measured_data(bottom_frame)

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

        params_data = self.selected_archive.spring_params
        if not params_data:
            return

        try:
            params = SpringParams.from_dict(params_data)
            result = perform_full_analysis(params)

            self.torque_chart.set_data(
                [result.torque_curve],
                curve_names=["计算力矩"],
                curve_colors=['#1f77b4'],
                decay_segments=result.decay_segments
            )
            self.torque_chart.set_title(f"{self.selected_archive.name or '机芯'} 力矩曲线")
        except Exception as e:
            pass

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
            if self.storage:
                self.storage.save_archive(dialog.result)
                self._refresh_archives()
                self._show_archive_detail()

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
        w, h = 480, 520
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

        ttk.Label(main_frame, text="备注", font=('Arial', 11, 'bold')).pack(
            anchor=tk.W, pady=(0, 5))

        self.notes_text = tk.Text(main_frame, height=5, relief=tk.FLAT,
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

        archive.notes = self.notes_text.get('1.0', tk.END).strip()

        self.result = archive
        self.destroy()

    def _on_cancel(self):
        """取消"""
        self.result = None
        self.destroy()

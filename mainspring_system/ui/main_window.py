"""
主窗口
集成所有页面与导航
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mechanics import SpringParams, perform_full_analysis, AnalysisResult
from core.storage import DataStorage, SpringSolution

from ui.pages.input_page import InputPage
from ui.pages.torque_page import TorquePage
from ui.pages.compensation_page import CompensationPage
from ui.pages.archive_page import ArchivePage
from ui.pages.library_page import LibraryPage


class MainWindow(tk.Tk):
    """主窗口"""

    def __init__(self):
        super().__init__()

        self.title("发条动力储备分析系统 - 机械机芯设计工具")
        self.geometry("1200x800")
        self.minsize(1000, 650)

        self.current_params = SpringParams()
        self.current_temp = 20.0
        self.analysis_result = None

        self._init_storage()
        self._setup_style()
        self._build_ui()
        self._perform_initial_analysis()

    def _init_storage(self):
        """初始化数据存储"""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(base_dir, 'data')
        self.storage = DataStorage(data_dir)

    def _setup_style(self):
        """设置样式"""
        style = ttk.Style(self)

        try:
            style.theme_use('clam')
        except tk.TclError:
            pass

        style.configure('Sidebar.TFrame', background='#f0f0f0')
        style.configure('Sidebar.TButton',
                        padding=(20, 10),
                        font=('Arial', 10),
                        anchor='w')
        style.map('Sidebar.TButton',
                   background=[('active', '#e0e0e0'), ('pressed', '#d0d0d0')])

        style.configure('Accent.TButton',
                        background='#1f77b4',
                        foreground='white',
                        padding=(15, 8))
        style.map('Accent.TButton',
                   background=[('active', '#1565c0'), ('pressed', '#0d47a1')])

        style.configure('Title.TLabel',
                        font=('Arial', 14, 'bold'),
                        foreground='#333')

        style.configure('NavActive.TFrame', background='#1f77b4')

    def _build_ui(self):
        """构建主界面"""
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True)

        self._build_sidebar(main_container)
        self._build_content(main_container)
        self._build_statusbar()

    def _build_sidebar(self, parent):
        """构建侧边导航栏"""
        sidebar = ttk.Frame(parent, style='Sidebar.TFrame', width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        logo_frame = ttk.Frame(sidebar, style='Sidebar.TFrame', padding=20)
        logo_frame.pack(fill=tk.X)

        ttk.Label(logo_frame, text="⚙",
                  font=('Arial', 28),
                  background='#f0f0f0').pack()
        ttk.Label(logo_frame, text="发条分析系统",
                  font=('Arial', 12, 'bold'),
                  background='#f0f0f0',
                  foreground='#333').pack(pady=(5, 0))
        ttk.Label(logo_frame, text="动力储备·力矩均匀",
                  font=('Arial', 9),
                  background='#f0f0f0',
                  foreground='#888').pack()

        ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10)

        nav_frame = ttk.Frame(sidebar, style='Sidebar.TFrame', padding=(0, 10))
        nav_frame.pack(fill=tk.X)

        self.nav_buttons = {}
        nav_items = [
            ("input", "📝 发条录入", "输入发条参数"),
            ("torque", "📈 力矩曲线", "查看力矩衰减曲线"),
            ("compensation", "⚖ 均力补偿", "宝塔轮/恒力装置"),
            ("archive", "📋 动储档案", "机芯数据档案"),
            ("library", "📚 方案库", "发条配置方案库"),
        ]

        self.active_page_var = tk.StringVar(value="input")

        for page_id, label, hint in nav_items:
            btn_frame = ttk.Frame(nav_frame, style='Sidebar.TFrame')
            btn_frame.pack(fill=tk.X, pady=2)

            btn = tk.Button(btn_frame, text=label,
                            command=lambda pid=page_id: self.show_page(pid),
                            relief=tk.FLAT,
                            bg='#f0f0f0',
                            fg='#333',
                            font=('Arial', 10),
                            anchor='w',
                            padx=20, pady=8,
                            cursor='hand2')
            btn.pack(fill=tk.X)
            self.nav_buttons[page_id] = btn

        ttk.Separator(sidebar, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=10, pady=10)

        bottom_frame = ttk.Frame(sidebar, style='Sidebar.TFrame', padding=15)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        ttk.Label(bottom_frame, text="版本 1.0.0",
                  font=('Arial', 8),
                  background='#f0f0f0',
                  foreground='#aaa').pack(anchor=tk.W)

        self._update_nav_style()

    def _build_content(self, parent):
        """构建内容区"""
        content_frame = ttk.Frame(parent)
        content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.pages = {}

        self.input_page = InputPage(content_frame, app=self)
        self.torque_page = TorquePage(content_frame, app=self)
        self.compensation_page = CompensationPage(content_frame, app=self)
        self.archive_page = ArchivePage(content_frame, app=self)
        self.library_page = LibraryPage(content_frame, app=self)

        self.archive_page.set_storage(self.storage)
        self.library_page.set_storage(self.storage)

        self.pages = {
            "input": self.input_page,
            "torque": self.torque_page,
            "compensation": self.compensation_page,
            "archive": self.archive_page,
            "library": self.library_page,
        }

    def _build_statusbar(self):
        """构建状态栏"""
        statusbar = ttk.Frame(self, relief=tk.FLAT, padding=(10, 3))
        statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(statusbar, text="就绪", foreground='#666')
        self.status_label.pack(side=tk.LEFT)

        self.temp_status = ttk.Label(statusbar, text="温度: 20°C", foreground='#666')
        self.temp_status.pack(side=tk.RIGHT)

    def show_page(self, page_id):
        """显示指定页面"""
        if page_id not in self.pages:
            return

        for pid, page in self.pages.items():
            page.pack_forget()

        self.pages[page_id].pack(fill=tk.BOTH, expand=True)
        self.active_page_var.set(page_id)
        self._update_nav_style()

        if page_id == "torque" and self.analysis_result:
            self.torque_page.set_analysis_result(self.analysis_result)
        elif page_id == "compensation" and self.analysis_result:
            self.compensation_page.set_analysis_result(self.analysis_result)

    def _update_nav_style(self):
        """更新导航栏样式"""
        active = self.active_page_var.get()

        for page_id, btn in self.nav_buttons.items():
            if page_id == active:
                btn.config(bg='#1f77b4', fg='white')
            else:
                btn.config(bg='#f0f0f0', fg='#333')

    def perform_analysis(self):
        """执行分析"""
        if not self.current_params:
            return

        try:
            self.analysis_result = perform_full_analysis(
                self.current_params, self.current_temp
            )

            self.torque_page.set_analysis_result(self.analysis_result)
            self.compensation_page.set_analysis_result(self.analysis_result)

            self.status_label.config(text="分析完成")
            self.temp_status.config(text=f"温度: {self.current_temp}°C")

        except Exception as e:
            messagebox.showerror("分析错误", f"分析过程中发生错误: {str(e)}")

    def _perform_initial_analysis(self):
        """执行初始分析"""
        self.perform_analysis()

    def show_save_solution_dialog(self, params: SpringParams):
        """显示保存方案对话框"""
        dialog = SaveSolutionDialog(self, params=params, storage=self.storage)
        self.wait_window(dialog)

        if dialog.saved:
            self.library_page._refresh_solutions()
            messagebox.showinfo("成功", "方案已保存到方案库")


class SaveSolutionDialog(tk.Toplevel):
    """保存方案对话框"""

    def __init__(self, master, params: SpringParams, storage: DataStorage):
        super().__init__(master)
        self.title("保存为方案")
        self.params = params
        self.storage = storage
        self.saved = False

        self._build_ui()

        self.transient(master)
        self.grab_set()

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w, h = 420, 400
        x = (screen_w - w) // 2
        y = (screen_h - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        """构建界面"""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        fields = [
            ("方案名称 *", "name", ""),
            ("方案分类", "category", "标准配置"),
            ("动储等级", "grade", "标准"),
        ]

        self.entries = {}

        for label, key, default in fields:
            row = ttk.Frame(main_frame)
            row.pack(fill=tk.X, pady=5)

            ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)

            if key == "category":
                categories = ["标准配置", "长动力", "紧凑型", "特殊应用", "新材料", "其他"]
                var = tk.StringVar(value=default)
                combo = ttk.Combobox(row, textvariable=var,
                                      values=categories, state='readonly')
                combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.entries[key] = var
            elif key == "grade":
                grades = ["标准", "长动力", "超长动力", "超短动力"]
                var = tk.StringVar(value=default)
                combo = ttk.Combobox(row, textvariable=var,
                                      values=grades, state='readonly')
                combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.entries[key] = var
            else:
                entry = ttk.Entry(row)
                entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                self.entries[key] = entry

        ttk.Label(main_frame, text="方案描述:").pack(anchor=tk.W, pady=(10, 5))
        self.desc_text = tk.Text(main_frame, height=4, relief=tk.FLAT,
                                  highlightthickness=1,
                                  highlightbackground='#ccc')
        self.desc_text.pack(fill=tk.X)

        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=15)

        ttk.Label(main_frame, text="参数预览:", font=('Arial', 10, 'bold')).pack(anchor=tk.W)

        preview_frame = ttk.LabelFrame(main_frame, text="", padding=10)
        preview_frame.pack(fill=tk.X, pady=5)

        p = self.params
        preview_text = f"料厚: {p.thickness} mm | 宽度: {p.width} mm | 长度: {p.length} mm\n" \
                       f"条盒内径: {p.case_inner_dia} mm | 材料: {p.material}"
        ttk.Label(preview_frame, text=preview_text, foreground='#1f77b4').pack(anchor=tk.W)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=15)

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="取消", command=self._on_cancel).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="保存", command=self._on_save,
                   style='Accent.TButton').pack(side=tk.RIGHT, padx=5)

    def _on_save(self):
        """保存"""
        name = ""
        if isinstance(self.entries["name"], ttk.Entry):
            name = self.entries["name"].get().strip()

        if not name:
            messagebox.showwarning("提示", "请输入方案名称")
            return

        category = self.entries["category"].get()
        grade = self.entries["grade"].get()
        description = self.desc_text.get('1.0', tk.END).strip()

        solution = SpringSolution()
        solution.name = name
        solution.category = category
        solution.reserve_grade = grade
        solution.description = description
        solution.params = self.params.to_dict()

        from core.mechanics import perform_full_analysis
        result = perform_full_analysis(self.params)
        solution.performance = {
            "max_torque": round(result.max_torque, 1),
            "min_torque": round(result.min_torque, 1),
            "reserve_hours": 0,
            "total_turns": round(result.total_turns, 1),
        }

        from core.mechanics import TorqueCalculator
        reserve = TorqueCalculator.estimate_power_reserve(
            result.torque_curve, min_torque=result.max_torque * 0.3
        )
        solution.performance["reserve_hours"] = round(reserve, 1)

        solution.created_at = datetime.now().isoformat()

        self.storage.save_solution(solution)
        self.saved = True
        self.destroy()

    def _on_cancel(self):
        """取消"""
        self.saved = False
        self.destroy()

"""
图表绘制组件
使用 tkinter Canvas 绘制力矩曲线等图表
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Tuple, Optional, Dict
import math

try:
    from core.mechanics import TorquePoint
except ImportError:
    TorquePoint = None


class TorqueChart(tk.Canvas):
    """力矩曲线图组件"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(bg='white', highlightthickness=1,
                       highlightbackground='#ccc')

        self.curves = []
        self.decay_segments = []
        self.title = "力矩曲线图"
        self.x_label = "圈数"
        self.y_label = "力矩 (g·cm)"
        self.show_grid = True
        self.show_legend = True

        self._padding = {
            'left': 60,
            'right': 20,
            'top': 40,
            'bottom': 50
        }

        self._tooltip_window = None
        self._tooltip_label = None

        self.bind('<Configure>', self._on_resize)
        self.bind('<Motion>', self._on_mouse_move)
        self.bind('<Leave>', self._on_mouse_leave)

    def set_data(self, curves: List[List['TorquePoint']],
                 curve_names: List[str] = None,
                 curve_colors: List[str] = None,
                 decay_segments: List[Tuple[int, int]] = None):
        """设置数据"""
        self.curves = curves
        self.decay_segments = decay_segments or []

        if curve_names:
            self._curve_names = curve_names
        else:
            self._curve_names = [f"曲线{i + 1}" for i in range(len(curves))]

        if curve_colors:
            self._curve_colors = curve_colors
        else:
            default_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728',
                              '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
            self._curve_colors = default_colors[:len(curves)]

        self.draw()

    def set_title(self, title: str):
        self.title = title

    def set_labels(self, x_label: str, y_label: str):
        self.x_label = x_label
        self.y_label = y_label

    def _get_plot_area(self) -> Tuple[int, int, int, int]:
        """获取绘图区域坐标"""
        w = self.winfo_width()
        h = self.winfo_height()

        left = self._padding['left']
        right = w - self._padding['right']
        top = self._padding['top']
        bottom = h - self._padding['bottom']

        return left, right, top, bottom

    def _get_data_range(self) -> Tuple[float, float, float, float]:
        """获取数据范围"""
        min_x = float('inf')
        max_x = float('-inf')
        min_y = float('inf')
        max_y = float('-inf')

        for curve in self.curves:
            if not curve:
                continue
            for point in curve:
                x = point.turn
                y = point.torque
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)

        if min_x == float('inf'):
            return 0, 10, 0, 100

        if min_y > 0:
            min_y = 0

        range_x = max_x - min_x
        range_y = max_y - min_y

        if range_x == 0:
            range_x = 1
        if range_y == 0:
            range_y = 1

        min_x -= range_x * 0.05
        max_x += range_x * 0.05
        max_y += range_y * 0.1

        return min_x, max_x, min_y, max_y

    def _data_to_pixel(self, x: float, y: float) -> Tuple[int, int]:
        """数据坐标转像素坐标"""
        left, right, top, bottom = self._get_plot_area()
        min_x, max_x, min_y, max_y = self._get_data_range()

        px = left + (x - min_x) / (max_x - min_x) * (right - left)
        py = bottom - (y - min_y) / (max_y - min_y) * (bottom - top)

        return int(px), int(py)

    def _pixel_to_data(self, px: int, py: int) -> Tuple[float, float]:
        """像素坐标转数据坐标"""
        left, right, top, bottom = self._get_plot_area()
        min_x, max_x, min_y, max_y = self._get_data_range()

        x = min_x + (px - left) / (right - left) * (max_x - min_x)
        y = min_y + (bottom - py) / (bottom - top) * (max_y - min_y)

        return x, y

    def draw(self):
        """绘制图表"""
        self.delete('all')

        w = self.winfo_width()
        h = self.winfo_height()

        if w < 10 or h < 10:
            return

        self._draw_background()
        self._draw_grid()
        self._draw_decay_regions()
        self._draw_curves()
        self._draw_axes()
        self._draw_title()
        self._draw_legend()

    def _draw_background(self):
        """绘制背景"""
        left, right, top, bottom = self._get_plot_area()
        self.create_rectangle(left, top, right, bottom,
                              fill='#fafafa', outline='#ddd')

    def _draw_grid(self):
        """绘制网格"""
        if not self.show_grid:
            return

        left, right, top, bottom = self._get_plot_area()
        min_x, max_x, min_y, max_y = self._get_data_range()

        x_ticks = self._get_ticks(min_x, max_x, 8)
        y_ticks = self._get_ticks(min_y, max_y, 8)

        for y_val in y_ticks:
            _, py = self._data_to_pixel(0, y_val)
            if top <= py <= bottom:
                self.create_line(left, py, right, py,
                                 fill='#e8e8e8', dash=(2, 2))

        for x_val in x_ticks:
            px, _ = self._data_to_pixel(x_val, 0)
            if left <= px <= right:
                self.create_line(px, top, px, bottom,
                                 fill='#e8e8e8', dash=(2, 2))

    def _get_ticks(self, min_val: float, max_val: float, count: int) -> List[float]:
        """获取刻度值"""
        if max_val <= min_val:
            return [min_val]

        range_val = max_val - min_val
        step = range_val / count

        magnitude = 10 ** math.floor(math.log10(step))
        scaled_step = step / magnitude

        if scaled_step < 1.5:
            nice_step = 1 * magnitude
        elif scaled_step < 3:
            nice_step = 2 * magnitude
        elif scaled_step < 7:
            nice_step = 5 * magnitude
        else:
            nice_step = 10 * magnitude

        start = math.floor(min_val / nice_step) * nice_step
        ticks = []
        val = start
        while val <= max_val + nice_step:
            if val >= min_val:
                ticks.append(val)
            val += nice_step

        return ticks

    def _draw_decay_regions(self):
        """绘制衰减过快区域（标红）"""
        if not self.decay_segments or not self.curves:
            return

        curve = self.curves[0]
        if not curve:
            return

        left, right, top, bottom = self._get_plot_area()

        for start_idx, end_idx in self.decay_segments:
            if start_idx >= len(curve) or end_idx < 0:
                continue

            start_idx = max(0, start_idx)
            end_idx = min(len(curve) - 1, end_idx)

            x_start = curve[start_idx].turn
            x_end = curve[end_idx].turn

            px_start, _ = self._data_to_pixel(x_start, 0)
            px_end, _ = self._data_to_pixel(x_end, 0)

            px_start = max(left, px_start)
            px_end = min(right, px_end)

            self.create_rectangle(px_start, top, px_end, bottom,
                                  fill='#fff0f0', outline='', stipple='gray25')

            mid_x = (px_start + px_end) / 2
            self.create_text(mid_x, top + 15,
                             text="⚠ 衰减过快",
                             fill='#d62728', font=('Arial', 9))

    def _draw_curves(self):
        """绘制曲线"""
        for curve_idx, curve in enumerate(self.curves):
            if not curve or len(curve) < 2:
                continue

            color = self._curve_colors[curve_idx % len(self._curve_colors)]

            points = []
            for point in curve:
                px, py = self._data_to_pixel(point.turn, point.torque)
                points.extend([px, py])

            if len(points) >= 4:
                self.create_line(*points, fill=color, width=2,
                                 smooth=False, tags=f"curve_{curve_idx}")

    def _draw_axes(self):
        """绘制坐标轴"""
        left, right, top, bottom = self._get_plot_area()
        min_x, max_x, min_y, max_y = self._get_data_range()

        self.create_line(left, top, left, bottom, fill='#333', width=1)
        self.create_line(left, bottom, right, bottom, fill='#333', width=1)

        x_ticks = self._get_ticks(min_x, max_x, 8)
        y_ticks = self._get_ticks(min_y, max_y, 8)

        for x_val in x_ticks:
            px, _ = self._data_to_pixel(x_val, 0)
            if left <= px <= right:
                self.create_line(px, bottom, px, bottom + 5, fill='#333')
                self.create_text(px, bottom + 15, text=f"{x_val:.1f}",
                                 fill='#555', font=('Arial', 9))

        for y_val in y_ticks:
            _, py = self._data_to_pixel(0, y_val)
            if top <= py <= bottom:
                self.create_line(left - 5, py, left, py, fill='#333')
                self.create_text(left - 8, py, text=f"{y_val:.0f}",
                                 fill='#555', font=('Arial', 9), anchor='e')

        self.create_text((left + right) / 2, bottom + 35,
                         text=self.x_label, fill='#333', font=('Arial', 10))

        self.create_text(15, (top + bottom) / 2,
                         text=self.y_label, fill='#333', font=('Arial', 10),
                         angle=90)

    def _draw_title(self):
        """绘制标题"""
        w = self.winfo_width()
        self.create_text(w / 2, 20, text=self.title,
                         fill='#222', font=('Arial', 12, 'bold'))

    def _draw_legend(self):
        """绘制图例"""
        if not self.show_legend or not self.curves:
            return

        left, right, top, bottom = self._get_plot_area()

        legend_x = right - 10
        legend_y = top + 10

        for i in range(len(self.curves)):
            color = self._curve_colors[i % len(self._curve_colors)]
            name = self._curve_names[i] if i < len(self._curve_names) else f"曲线{i + 1}"

            text_w = len(name) * 12 + 30
            legend_x_item = legend_x - text_w

            self.create_rectangle(legend_x_item, legend_y + i * 22,
                                  legend_x_item + 20, legend_y + i * 22 + 12,
                                  fill=color, outline=color)

            self.create_text(legend_x_item + 25, legend_y + i * 22 + 6,
                             text=name, fill='#333', font=('Arial', 9), anchor='w')

    def _on_resize(self, event):
        """窗口大小改变时重绘"""
        self.draw()

    def _on_mouse_move(self, event):
        """鼠标移动事件"""
        if not self.curves:
            return

        left, right, top, bottom = self._get_plot_area()
        if not (left <= event.x <= right and top <= event.y <= bottom):
            self._hide_tooltip()
            return

        x_data, _ = self._pixel_to_data(event.x, event.y)

        closest_info = None
        min_dist = float('inf')

        for curve_idx, curve in enumerate(self.curves):
            if not curve:
                continue

            for i, point in enumerate(curve):
                dist = abs(point.turn - x_data)
                if dist < min_dist:
                    min_dist = dist
                    closest_info = (curve_idx, i, point)

        if closest_info and min_dist < 0.5:
            curve_idx, point_idx, point = closest_info
            self._show_tooltip(event.x, event.y, curve_idx, point)
        else:
            self._hide_tooltip()

    def _show_tooltip(self, x: int, y: int, curve_idx: int, point: 'TorquePoint'):
        """显示提示框"""
        if self._tooltip_window is None:
            self._tooltip_window = tk.Toplevel(self)
            self._tooltip_window.wm_overrideredirect(True)
            self._tooltip_window.configure(bg='#333')

            self._tooltip_label = tk.Label(
                self._tooltip_window,
                bg='#333', fg='white',
                font=('Arial', 9),
                padx=8, pady=4
            )
            self._tooltip_label.pack()

        curve_name = self._curve_names[curve_idx] if curve_idx < len(self._curve_names) else ""

        text = f"{curve_name}\n圈数: {point.turn:.2f}\n力矩: {point.torque:.2f} g·cm\n剩余圈数: {point.turns_remaining:.2f}"
        self._tooltip_label.config(text=text)

        self._tooltip_window.wm_geometry(f"+{self.winfo_rootx() + x + 10}+{self.winfo_rooty() + y + 10}")

    def _hide_tooltip(self):
        """隐藏提示框"""
        if self._tooltip_window:
            self._tooltip_window.destroy()
            self._tooltip_window = None
            self._tooltip_label = None

    def _on_mouse_leave(self, event):
        """鼠标离开事件"""
        self._hide_tooltip()


class BarChart(tk.Canvas):
    """柱状图组件"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(bg='white', highlightthickness=1,
                       highlightbackground='#ccc')

        self.data = []
        self.labels = []
        self.colors = []
        self.title = "柱状图"
        self.y_label = ""

        self._padding = {'left': 50, 'right': 20, 'top': 40, 'bottom': 50}

        self.bind('<Configure>', lambda e: self.draw())

    def set_data(self, values: List[float], labels: List[str],
                 colors: List[str] = None):
        self.data = values
        self.labels = labels
        self.colors = colors or ['#1f77b4'] * len(values)
        self.draw()

    def set_title(self, title: str):
        self.title = title
        self.draw()

    def set_ylabel(self, label: str):
        self.y_label = label
        self.draw()

    def draw(self):
        self.delete('all')

        w = self.winfo_width()
        h = self.winfo_height()

        if w < 10 or h < 10:
            return

        left = self._padding['left']
        right = w - self._padding['right']
        top = self._padding['top']
        bottom = h - self._padding['bottom']

        self.create_rectangle(left, top, right, bottom,
                              fill='#fafafa', outline='#ddd')

        if not self.data:
            return

        max_val = max(self.data) if self.data else 1
        if max_val <= 0:
            max_val = 1
        max_val *= 1.1

        n_bars = len(self.data)
        bar_width = (right - left) / (n_bars * 2 + 1)
        bar_gap = bar_width

        for i, (val, label) in enumerate(zip(self.data, self.labels)):
            bar_x = left + bar_gap + i * (bar_width + bar_gap)
            bar_height = (val / max_val) * (bottom - top)
            bar_y = bottom - bar_height

            color = self.colors[i % len(self.colors)]

            self.create_rectangle(bar_x, bar_y, bar_x + bar_width, bottom,
                                  fill=color, outline=color)

            self.create_text(bar_x + bar_width / 2, bottom + 20,
                             text=label, fill='#333', font=('Arial', 9))

            self.create_text(bar_x + bar_width / 2, bar_y - 10,
                             text=f"{val:.1f}", fill='#333', font=('Arial', 9))

        self.create_text(w / 2, 20, text=self.title,
                         fill='#222', font=('Arial', 12, 'bold'))

        if self.y_label:
            self.create_text(15, (top + bottom) / 2,
                             text=self.y_label, fill='#333',
                             font=('Arial', 10), angle=90)

        y_ticks = self._get_ticks(0, max_val, 5)
        for y_val in y_ticks:
            py = bottom - (y_val / max_val) * (bottom - top)
            if top <= py <= bottom:
                self.create_line(left - 5, py, left, py, fill='#333')
                self.create_text(left - 8, py, text=f"{y_val:.0f}",
                                 fill='#555', font=('Arial', 9), anchor='e')

    def _get_ticks(self, min_val, max_val, count):
        if max_val <= min_val:
            return [min_val]
        step = (max_val - min_val) / count
        return [min_val + i * step for i in range(count + 1)]


class SpringCrossSection(tk.Canvas):
    """发条截面示意图"""

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(bg='white', highlightthickness=1,
                       highlightbackground='#ccc')

        self.params = None
        self.bind('<Configure>', lambda e: self.draw())

    def set_params(self, params):
        self.params = params
        self.draw()

    def draw(self):
        self.delete('all')

        w = self.winfo_width()
        h = self.winfo_height()

        if w < 10 or h < 10 or self.params is None:
            return

        cx = w / 2
        cy = h / 2

        case_r = min(w, h) * 0.4
        case_inner_r = case_r * 0.9

        thickness_scale = case_inner_r * 0.02

        turns = min(15, max(3, int(self.params.length / 20)))

        self.create_oval(cx - case_r, cy - case_r,
                         cx + case_r, cy + case_r,
                         fill='#8B7355', outline='#5D4E37', width=3)

        self.create_oval(cx - case_inner_r, cy - case_inner_r,
                         cx + case_inner_r, cy + case_inner_r,
                         fill='#FFF8DC', outline='#CD853F')

        arbor_r = case_r * 0.15
        self.create_oval(cx - arbor_r, cy - arbor_r,
                         cx + arbor_r, cy + arbor_r,
                         fill='#696969', outline='#333')

        for i in range(turns):
            r_i = arbor_r + i * thickness_scale * 2 + thickness_scale
            r_o = r_i + thickness_scale

            color = self._get_spring_color(i, turns)

            start_angle = 0
            extent = 360

            self.create_arc(cx - r_o, cy - r_o, cx + r_o, cy + r_o,
                            start=start_angle, extent=extent,
                            style='arc', outline=color, width=int(thickness_scale))

        self.create_text(cx, 20, text="发条卷绕截面示意图",
                         fill='#333', font=('Arial', 10, 'bold'))

        info_text = f"条盒内径: {self.params.case_inner_dia:.1f} mm\n" \
                    f"发条长度: {self.params.length:.0f} mm\n" \
                    f"料厚: {self.params.thickness:.2f} mm\n" \
                    f"估计圈数: ~{turns}圈"
        self.create_text(w - 10, h / 2, text=info_text,
                         fill='#333', font=('Arial', 9), anchor='e')

    def _get_spring_color(self, index: int, total: int) -> str:
        ratio = index / max(1, total - 1)
        r = int(80 + ratio * 100)
        g = int(80 + ratio * 80)
        b = int(120 + ratio * 60)
        return f'#{r:02x}{g:02x}{b:02x}'

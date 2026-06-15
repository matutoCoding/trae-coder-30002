"""
发条动力储备分析系统
主程序入口
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import MainWindow


def main():
    """主函数"""
    app = MainWindow()

    try:
        app.iconify()
        app.deiconify()
    except Exception:
        pass

    app.show_page("input")
    app.mainloop()


if __name__ == "__main__":
    main()

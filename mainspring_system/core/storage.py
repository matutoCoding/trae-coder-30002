"""
数据持久化模块
管理机芯档案和方案库的本地存储
"""

import json
import os
import shutil
from datetime import datetime
from typing import List, Optional, Dict
from dataclasses import dataclass, field, asdict

from .mechanics import SpringParams, AnalysisResult


@dataclass
class MovementArchive:
    """机芯档案"""
    id: str = ""
    name: str = ""
    model: str = ""
    manufacturer: str = ""
    spring_params: dict = field(default_factory=dict)
    torque_curve: list = field(default_factory=list)
    measured_reserve_hours: float = 0.0
    measured_max_torque: float = 0.0
    measured_min_torque: float = 0.0
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'MovementArchive':
        archive = cls()
        for key, val in data.items():
            if hasattr(archive, key):
                setattr(archive, key, val)
        return archive


@dataclass
class SpringSolution:
    """发条方案"""
    id: str = ""
    name: str = ""
    category: str = ""
    reserve_grade: str = ""
    description: str = ""
    params: dict = field(default_factory=dict)
    performance: dict = field(default_factory=dict)
    application_scenarios: list = field(default_factory=list)
    reference_movements: list = field(default_factory=list)
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'SpringSolution':
        solution = cls()
        for key, val in data.items():
            if hasattr(solution, key):
                setattr(solution, key, val)
        return solution


class DataStorage:
    """数据存储管理器"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            self.data_dir = os.path.join(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))), 'data')
        else:
            self.data_dir = data_dir

        self.archives_file = os.path.join(self.data_dir, 'archives.json')
        self.solutions_file = os.path.join(self.data_dir, 'solutions.json')
        self.settings_file = os.path.join(self.data_dir, 'settings.json')

        self._ensure_data_dir()
        self._init_default_data()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir, exist_ok=True)

    def _init_default_data(self):
        """初始化默认数据"""
        if not os.path.exists(self.archives_file):
            self._save_json(self.archives_file, [])

        if not os.path.exists(self.solutions_file):
            default_solutions = self._get_default_solutions()
            self._save_json(self.solutions_file, default_solutions)

        if not os.path.exists(self.settings_file):
            default_settings = {
                "current_params": SpringParams().to_dict(),
                "theme": "light",
                "unit_system": "metric"
            }
            self._save_json(self.settings_file, default_settings)

    def _get_default_solutions(self) -> list:
        """获取默认方案库"""
        solutions = [
            {
                "id": "sol_standard_42h",
                "name": "标准42小时动储",
                "category": "标准配置",
                "reserve_grade": "标准",
                "description": "经典42小时动力储备配置，适用于大多数自动机械机芯",
                "params": {
                    "thickness": 0.12,
                    "width": 1.2,
                    "length": 200.0,
                    "case_inner_dia": 10.0,
                    "arbor_dia": 1.5,
                    "material": "镍铬钢"
                },
                "performance": {
                    "max_torque": 45.0,
                    "min_torque": 18.0,
                    "reserve_hours": 42.0,
                    "total_turns": 6.5
                },
                "application_scenarios": ["大三针", "日期显示", "基础自动机芯"],
                "reference_movements": ["ETA2824", "SW200", "MIYOTA9015"],
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "sol_long_72h",
                "name": "长动力72小时",
                "category": "长动力",
                "reserve_grade": "长动力",
                "description": "72小时长动力配置，三日链，适合周末不佩戴也能持续走时",
                "params": {
                    "thickness": 0.12,
                    "width": 1.4,
                    "length": 320.0,
                    "case_inner_dia": 12.0,
                    "arbor_dia": 1.8,
                    "material": "镍铬钢"
                },
                "performance": {
                    "max_torque": 55.0,
                    "min_torque": 20.0,
                    "reserve_hours": 72.0,
                    "total_turns": 8.5
                },
                "application_scenarios": ["三日链", "大三针", "正装表"],
                "reference_movements": ["PT5000", "SW300"],
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "sol_ultra_120h",
                "name": "超长动力120小时",
                "category": "长动力",
                "reserve_grade": "超长动力",
                "description": "120小时五日链超长动力，适合出差旅行使用",
                "params": {
                    "thickness": 0.10,
                    "width": 1.8,
                    "length": 520.0,
                    "case_inner_dia": 14.0,
                    "arbor_dia": 2.0,
                    "material": "钴基合金"
                },
                "performance": {
                    "max_torque": 60.0,
                    "min_torque": 22.0,
                    "reserve_hours": 120.0,
                    "total_turns": 11.0
                },
                "application_scenarios": ["五日链", "年历表", "复杂功能"],
                "reference_movements": ["Cal.3120", "ML115"],
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "sol_compact_36h",
                "name": "紧凑36小时",
                "category": "紧凑型",
                "reserve_grade": "标准",
                "description": "小尺寸条盒配置，适合女表或超薄机芯",
                "params": {
                    "thickness": 0.10,
                    "width": 0.9,
                    "length": 150.0,
                    "case_inner_dia": 8.0,
                    "arbor_dia": 1.2,
                    "material": "镍铬钢"
                },
                "performance": {
                    "max_torque": 32.0,
                    "min_torque": 12.0,
                    "reserve_hours": 36.0,
                    "total_turns": 5.8
                },
                "application_scenarios": ["女表", "超薄机芯", "两针表"],
                "reference_movements": ["ETA2671", "SW1000"],
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "sol_high_torque",
                "name": "高力矩配置",
                "category": "特殊应用",
                "reserve_grade": "标准",
                "description": "高力矩输出配置，适合复杂功能或大摆轮机芯",
                "params": {
                    "thickness": 0.16,
                    "width": 1.5,
                    "length": 250.0,
                    "case_inner_dia": 11.0,
                    "arbor_dia": 2.0,
                    "material": "钴基合金"
                },
                "performance": {
                    "max_torque": 85.0,
                    "min_torque": 35.0,
                    "reserve_hours": 40.0,
                    "total_turns": 5.0
                },
                "application_scenarios": ["计时码表", "大摆轮", "复杂功能"],
                "reference_movements": ["Valjoux7750", "SW500"],
                "created_at": datetime.now().isoformat()
            },
            {
                "id": "sol_silicone_80h",
                "name": "硅发条80小时",
                "category": "新材料",
                "reserve_grade": "长动力",
                "description": "采用硅材料发条，弹性优异，抗疲劳性能好",
                "params": {
                    "thickness": 0.08,
                    "width": 1.2,
                    "length": 350.0,
                    "case_inner_dia": 11.0,
                    "arbor_dia": 1.5,
                    "material": "硅硅"
                },
                "performance": {
                    "max_torque": 40.0,
                    "min_torque": 18.0,
                    "reserve_hours": 80.0,
                    "total_turns": 10.5
                },
                "application_scenarios": ["高端腕表", "硅材质", "高振频"],
                "reference_movements": ["Nivarox硅游丝"],
                "created_at": datetime.now().isoformat()
            }
        ]
        return solutions

    def _load_json(self, filepath: str):
        """加载JSON文件"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return []

    def _save_json(self, filepath: str, data):
        """保存JSON文件"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except IOError:
            return False

    # ===== 机芯档案 =====

    def list_archives(self) -> List[MovementArchive]:
        """获取所有机芯档案"""
        data = self._load_json(self.archives_file)
        return [MovementArchive.from_dict(item) for item in data]

    def get_archive(self, archive_id: str) -> Optional[MovementArchive]:
        """获取单个档案"""
        archives = self.list_archives()
        for a in archives:
            if a.id == archive_id:
                return a
        return None

    def save_archive(self, archive: MovementArchive) -> bool:
        """保存/更新档案"""
        archives = self.list_archives()

        if not archive.id:
            archive.id = f"arch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if not archive.created_at:
            archive.created_at = datetime.now().isoformat()
        archive.updated_at = datetime.now().isoformat()

        found = False
        for i, a in enumerate(archives):
            if a.id == archive.id:
                archives[i] = archive
                found = True
                break

        if not found:
            archives.append(archive)

        data = [a.to_dict() for a in archives]
        return self._save_json(self.archives_file, data)

    def delete_archive(self, archive_id: str) -> bool:
        """删除档案"""
        archives = self.list_archives()
        archives = [a for a in archives if a.id != archive_id]
        data = [a.to_dict() for a in archives]
        return self._save_json(self.archives_file, data)

    # ===== 方案库 =====

    def list_solutions(self, category: str = None) -> List[SpringSolution]:
        """获取方案列表"""
        data = self._load_json(self.solutions_file)
        solutions = [SpringSolution.from_dict(item) for item in data]

        if category and category != "全部":
            solutions = [s for s in solutions if s.category == category]

        return solutions

    def get_solution(self, solution_id: str) -> Optional[SpringSolution]:
        """获取单个方案"""
        solutions = self.list_solutions()
        for s in solutions:
            if s.id == solution_id:
                return s
        return None

    def save_solution(self, solution: SpringSolution) -> bool:
        """保存/更新方案"""
        solutions = self.list_solutions()

        if not solution.id:
            solution.id = f"sol_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if not solution.created_at:
            solution.created_at = datetime.now().isoformat()

        found = False
        for i, s in enumerate(solutions):
            if s.id == solution.id:
                solutions[i] = solution
                found = True
                break

        if not found:
            solutions.append(solution)

        data = [s.to_dict() for s in solutions]
        return self._save_json(self.solutions_file, data)

    def delete_solution(self, solution_id: str) -> bool:
        """删除方案"""
        solutions = self.list_solutions()
        solutions = [s for s in solutions if s.id != solution_id]
        data = [s.to_dict() for s in solutions]
        return self._save_json(self.solutions_file, data)

    def get_categories(self) -> List[str]:
        """获取方案分类"""
        solutions = self.list_solutions()
        categories = set()
        for s in solutions:
            if s.category:
                categories.add(s.category)
        return sorted(list(categories))

    def get_reserve_grades(self) -> List[str]:
        """获取动储等级"""
        return ["标准", "长动力", "超长动力", "超短动力"]

    # ===== 设置 =====

    def load_settings(self) -> dict:
        """加载设置"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def save_settings(self, settings: dict) -> bool:
        """保存设置"""
        return self._save_json(self.settings_file, settings)

    # ===== 数据导入导出 =====

    def export_archive(self, archive_id: str, filepath: str) -> bool:
        """导出单个档案"""
        archive = self.get_archive(archive_id)
        if archive:
            return self._save_json(filepath, archive.to_dict())
        return False

    def import_archive(self, filepath: str) -> bool:
        """导入档案"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if isinstance(data, list):
                archives = [MovementArchive.from_dict(item) for item in data]
                for a in archives:
                    self.save_archive(a)
            else:
                archive = MovementArchive.from_dict(data)
                self.save_archive(archive)
            return True
        except (json.JSONDecodeError, IOError):
            return False

    def backup_data(self, backup_dir: str = None) -> str:
        """备份所有数据"""
        if backup_dir is None:
            backup_dir = os.path.join(self.data_dir, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_path, exist_ok=True)

        if os.path.exists(self.archives_file):
            shutil.copy2(self.archives_file, os.path.join(backup_path, 'archives.json'))
        if os.path.exists(self.solutions_file):
            shutil.copy2(self.solutions_file, os.path.join(backup_path, 'solutions.json'))
        if os.path.exists(self.settings_file):
            shutil.copy2(self.settings_file, os.path.join(backup_path, 'settings.json'))

        return backup_path

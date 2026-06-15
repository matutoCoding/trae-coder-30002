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
    analysis_summary: dict = field(default_factory=dict)
    risk_warnings: list = field(default_factory=list)
    case_check: dict = field(default_factory=dict)
    temp_effects: dict = field(default_factory=dict)
    decay_segments: list = field(default_factory=list)
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

    @classmethod
    def from_analysis(cls, result, name: str = "", model: str = "") -> 'MovementArchive':
        """从分析结果创建档案"""
        from .mechanics import SpringParams
        archive = cls()
        archive.name = name or f"分析结果 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        archive.model = model
        archive.spring_params = result.params.to_dict() if hasattr(result.params, 'to_dict') else dict(result.params)
        archive.torque_curve = [
            {
                "turn": p.turn,
                "angle": p.angle,
                "torque": p.torque,
                "radius_outer": p.radius_outer,
                "radius_inner": p.radius_inner,
                "turns_remaining": p.turns_remaining
            }
            for p in result.torque_curve
        ]
        archive.analysis_summary = {
            "max_torque": result.max_torque,
            "min_torque": result.min_torque,
            "avg_torque": result.avg_torque,
            "total_turns": result.total_turns,
            "total_energy": result.total_energy,
            "decay_rate": (result.max_torque - result.min_torque) / result.max_torque * 100 if result.max_torque > 0 else 0,
            "reserve_hours": 0
        }

        try:
            from .mechanics import TorqueCalculator
            reserve = TorqueCalculator.estimate_power_reserve(
                result.torque_curve,
                min_torque=result.max_torque * 0.35
            )
            archive.analysis_summary["reserve_hours"] = round(reserve, 2)
        except Exception:
            pass
        archive.risk_warnings = list(result.risk_warnings)
        archive.case_check = dict(result.case_check) if result.case_check else {}
        archive.temp_effects = {}
        for temp, eff in result.temp_effects.items():
            archive.temp_effects[str(temp)] = dict(eff) if isinstance(eff, dict) else {"reserve_hours": eff}
        archive.decay_segments = [list(s) for s in result.decay_segments]
        return archive

    def get_calc_deviation(self) -> dict:
        """计算实测与理论的偏差"""
        deviation = {}
        summary = self.analysis_summary or {}

        if summary.get("max_torque", 0) > 0 and self.measured_max_torque > 0:
            deviation["max_torque_deviation_pct"] = round(
                (self.measured_max_torque - summary["max_torque"]) / summary["max_torque"] * 100, 2
            )

        if summary.get("min_torque", 0) > 0 and self.measured_min_torque > 0:
            deviation["min_torque_deviation_pct"] = round(
                (self.measured_min_torque - summary["min_torque"]) / summary["min_torque"] * 100, 2
            )

        calc_reserve = summary.get("reserve_hours", 0)
        if calc_reserve > 0 and self.measured_reserve_hours > 0:
            deviation["reserve_deviation_pct"] = round(
                (self.measured_reserve_hours - calc_reserve) / calc_reserve * 100, 2
            )

        return deviation


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

    @classmethod
    def from_archive(cls, archive: 'MovementArchive', name: str = "",
                     category: str = "自定义", reserve_grade: str = "标准") -> 'SpringSolution':
        """从机芯档案沉淀为方案"""
        solution = cls()
        solution.name = name or f"源自 {archive.name}"
        solution.category = category
        solution.reserve_grade = reserve_grade

        summary = archive.analysis_summary or {}
        solution.params = dict(archive.spring_params) if archive.spring_params else {}
        solution.performance = {
            "max_torque": round(summary.get("max_torque", 0), 1),
            "min_torque": round(summary.get("min_torque", 0), 1),
            "reserve_hours": round(summary.get("reserve_hours", 0), 1),
            "total_turns": round(summary.get("total_turns", 0), 1),
        }

        if archive.notes:
            solution.description = archive.notes

        if archive.tags:
            solution.application_scenarios = list(archive.tags)

        if archive.model:
            solution.reference_movements = [archive.model]

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


class DesignReportGenerator:
    """设计报告生成器"""

    @staticmethod
    def generate_text_report(result, compensation_result=None, filepath: str = None) -> str:
        """生成文本格式的设计报告"""
        from datetime import datetime

        lines = []
        lines.append("=" * 60)
        lines.append("       发条动力储备设计报告")
        lines.append("=" * 60)
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        lines.append("-" * 60)
        lines.append("一、输入参数")
        lines.append("-" * 60)
        p = result.params
        lines.append(f"  材料:       {p.material}")
        lines.append(f"  料厚:       {p.thickness} mm")
        lines.append(f"  料宽:       {p.width} mm")
        lines.append(f"  长度:       {p.length} mm")
        lines.append(f"  条盒内径:   {p.case_inner_dia} mm")
        lines.append(f"  条轴直径:   {p.arbor_dia} mm")
        lines.append(f"  弹性模量:   {p.E_ref} MPa (参考温度 {p.temp_ref}°C)")
        lines.append(f"  温度系数:   {p.E_temp_coeff} /°C")
        lines.append("")

        lines.append("-" * 60)
        lines.append("二、力矩特性")
        lines.append("-" * 60)
        lines.append(f"  满弦力矩:   {result.max_torque:.2f} g·cm")
        lines.append(f"  末端力矩:   {result.min_torque:.2f} g·cm")
        lines.append(f"  平均力矩:   {result.avg_torque:.2f} g·cm")
        decay_rate = (result.max_torque - result.min_torque) / result.max_torque * 100 if result.max_torque > 0 else 0
        lines.append(f"  力矩衰减率: {decay_rate:.1f}%")
        lines.append(f"  总圈数:     {result.total_turns:.1f} 圈")
        lines.append(f"  总能量:     {result.total_energy:.4f} J")
        lines.append("")

        lines.append("-" * 60)
        lines.append("三、条盒容积校验")
        lines.append("-" * 60)
        cc = result.case_check or {}
        lines.append(f"  条盒内径:       {cc.get('case_inner_dia', '-')} mm")
        lines.append(f"  条轴直径:       {cc.get('arbor_dia', '-')} mm")
        lines.append(f"  可用径向空间:   {cc.get('radial_space', '-')} mm")
        lines.append(f"  理论圈数:       {cc.get('estimated_turns', '-')} 圈")
        lines.append(f"  装填系数:       {cc.get('packing_factor', '-')}")
        lines.append(f"  容积利用率:     {cc.get('volume_utilization', '-')}%")
        lines.append(f"  状态:           {cc.get('status', '-')}")
        if cc.get('note'):
            lines.append(f"  说明:           {cc['note']}")
        lines.append("")

        lines.append("-" * 60)
        lines.append("四、温度影响分析")
        lines.append("-" * 60)
        lines.append(f"{'温度(°C)':<12} {'弹性模量(MPa)':<16} {'动储时长(h)':<14} {'变化率(%)':<10}")
        lines.append("-" * 56)
        for temp, eff in sorted(result.temp_effects.items(), key=lambda x: float(x[0])):
            if isinstance(eff, dict):
                E = eff.get('E', '-')
                reserve = eff.get('reserve_hours', '-')
                change = eff.get('change_pct', '-')
            else:
                E = '-'
                reserve = eff
                change = '-'
            lines.append(f"{temp:<12} {str(E):<16} {str(reserve):<14} {str(change):<10}")
        lines.append("")

        if compensation_result:
            lines.append("-" * 60)
            lines.append("五、均力补偿效果")
            lines.append("-" * 60)
            lines.append(f"  补偿方式:       {compensation_result.name}")
            lines.append(f"  补偿前标准差:   {compensation_result.torque_std_before:.3f} g·cm")
            lines.append(f"  补偿后标准差:   {compensation_result.torque_std_after:.3f} g·cm")
            lines.append(f"  改善幅度:       {compensation_result.improvement_pct:.1f}%")
            lines.append("")
            if compensation_result.params:
                lines.append(f"  补偿参数:")
                for k, v in compensation_result.params.items():
                    lines.append(f"    {k}: {v}")
            lines.append("")

        lines.append("-" * 60)
        lines.append("六、风险预警")
        lines.append("-" * 60)
        if result.risk_warnings:
            for i, warning in enumerate(result.risk_warnings, 1):
                lines.append(f"  [{i}] {warning}")
        else:
            lines.append("  暂无风险预警，设计参数在合理范围内。")
        lines.append("")

        if result.decay_segments:
            lines.append("-" * 60)
            lines.append("七、力矩衰减过快区段")
            lines.append("-" * 60)
            for i, seg in enumerate(result.decay_segments, 1):
                start_idx, end_idx = seg
                if 0 <= start_idx < len(result.torque_curve) and 0 <= end_idx < len(result.torque_curve):
                    start_turn = result.torque_curve[start_idx].turn
                    end_turn = result.torque_curve[end_idx].turn
                    start_torque = result.torque_curve[start_idx].torque
                    end_torque = result.torque_curve[end_idx].torque
                    lines.append(f"  区段 {i}: 第{start_turn:.1f}圈 ~ 第{end_turn:.1f}圈")
                    lines.append(f"          力矩 {start_torque:.2f} → {end_torque:.2f} g·cm")
            lines.append("")

        lines.append("=" * 60)
        lines.append("                    报告结束")
        lines.append("=" * 60)

        report_text = "\n".join(lines)

        if filepath:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report_text)

        return report_text

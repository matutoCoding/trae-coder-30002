"""
发条力学核心算法库
用于机械机芯发条动力储备的力矩计算与分析
"""

import math
import json
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Optional, Dict


@dataclass
class SpringParams:
    """发条参数"""
    thickness: float = 0.12
    width: float = 1.2
    length: float = 200.0
    case_inner_dia: float = 10.0
    arbor_dia: float = 1.5
    material: str = "镍铬钢"
    E_ref: float = 206000.0
    temp_ref: float = 20.0
    E_temp_coeff: float = -0.00025
    density: float = 7.85

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'SpringParams':
        params = cls()
        for key, val in data.items():
            if hasattr(params, key):
                setattr(params, key, val)
        return params


@dataclass
class TorquePoint:
    """力矩曲线上的点"""
    turn: float
    angle: float
    torque: float
    radius_outer: float
    radius_inner: float
    turns_remaining: float


@dataclass
class CompensationResult:
    """均力补偿结果"""
    name: str
    original_curve: List[TorquePoint]
    compensated_curve: List[TorquePoint]
    torque_std_before: float
    torque_std_after: float
    improvement_pct: float
    params: dict = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """分析结果"""
    params: SpringParams
    torque_curve: List[TorquePoint]
    max_torque: float
    min_torque: float
    avg_torque: float
    total_turns: float
    total_energy: float
    decay_segments: List[Tuple[int, int]]
    risk_warnings: List[str]
    case_check: dict
    temp_effects: Dict[float, dict]


class MaterialLibrary:
    """发条材料库"""
    MATERIALS = {
        "镍铬钢": {
            "E_ref": 206000.0,
            "E_temp_coeff": -0.00025,
            "density": 7.85,
            "yield_strength": 1600.0,
            "fatigue_limit": 700.0
        },
        "不锈钢": {
            "E_ref": 193000.0,
            "E_temp_coeff": -0.00023,
            "density": 7.75,
            "yield_strength": 1400.0,
            "fatigue_limit": 600.0
        },
        "钴基合金": {
            "E_ref": 210000.0,
            "E_temp_coeff": -0.00015,
            "density": 8.20,
            "yield_strength": 2000.0,
            "fatigue_limit": 900.0
        },
        "硅硅": {
            "E_ref": 130000.0,
            "E_temp_coeff": -0.00008,
            "density": 2.33,
            "yield_strength": 7000.0,
            "fatigue_limit": 3000.0
        },
        "碳钢": {
            "E_ref": 207000.0,
            "E_temp_coeff": -0.00028,
            "density": 7.85,
            "yield_strength": 1200.0,
            "fatigue_limit": 500.0
        }
    }

    @classmethod
    def get_material(cls, name: str) -> Optional[dict]:
        return cls.MATERIALS.get(name)

    @classmethod
    def list_materials(cls) -> List[str]:
        return list(cls.MATERIALS.keys())


class SpringGeometry:
    """发条几何计算"""

    @staticmethod
    def calc_section_inertia(width: float, thickness: float) -> float:
        """计算截面惯性矩 I = b*h^3/12"""
        return width * (thickness ** 3) / 12.0

    @staticmethod
    def calc_section_area(width: float, thickness: float) -> float:
        """计算截面积"""
        return width * thickness

    @staticmethod
    def estimate_turns_by_length(length: float, case_inner_dia: float,
                                  arbor_dia: float, thickness: float) -> float:
        """根据长度估算总圈数（近似）"""
        case_r = case_inner_dia / 2.0
        arbor_r = arbor_dia / 2.0
        avg_r = (case_r + arbor_r) / 2.0
        avg_circumference = 2 * math.pi * avg_r
        return length / avg_circumference

    @staticmethod
    def calc_winding_radii(wound_turns: float, total_turns: float,
                           case_inner_dia: float, arbor_dia: float,
                           thickness: float) -> Tuple[float, float]:
        """
        计算指定卷绕圈数时的内圈和外圈半径
        wound_turns: 已卷绕的圈数 (0 = 完全放松, total_turns = 满弦)
        返回: (内圈半径, 外圈半径)
        """
        case_r = case_inner_dia / 2.0
        arbor_r = arbor_dia / 2.0
        stack_height = thickness * total_turns

        if total_turns <= 0:
            return case_r - stack_height, case_r

        ratio = wound_turns / total_turns

        outer_r = case_r - ratio * (case_r - arbor_r - stack_height)
        inner_r = outer_r - stack_height

        inner_r = max(inner_r, arbor_r)
        outer_r = min(outer_r, case_r)

        return inner_r, outer_r

    @staticmethod
    def calc_spring_length_from_turns(total_turns: float, case_inner_dia: float,
                                       arbor_dia: float, thickness: float) -> float:
        """根据圈数计算所需发条长度"""
        case_r = case_inner_dia / 2.0
        arbor_r = arbor_dia / 2.0

        total_len = 0.0
        for i in range(int(total_turns) + 1):
            if i < total_turns:
                frac = total_turns - i
                if frac > 1:
                    frac = 1.0
                r = arbor_r + thickness * (i + frac / 2)
                total_len += 2 * math.pi * r * frac

        return total_len

    @staticmethod
    def check_case_volume(params: SpringParams) -> dict:
        """校验条盒容积与发条圈数匹配"""
        case_r = params.case_inner_dia / 2.0
        arbor_r = params.arbor_dia / 2.0
        gap = case_r - arbor_r

        est_turns = SpringGeometry.estimate_turns_by_length(
            params.length, params.case_inner_dia,
            params.arbor_dia, params.thickness
        )

        stack_height = est_turns * params.thickness
        fill_ratio = stack_height / gap

        critical_turns = gap / params.thickness
        max_length = SpringGeometry.calc_spring_length_from_turns(
            critical_turns * 0.95, params.case_inner_dia,
            params.arbor_dia, params.thickness
        )

        result = {
            "case_radius": case_r,
            "arbor_radius": arbor_r,
            "radial_gap": gap,
            "estimated_turns": est_turns,
            "stack_height": stack_height,
            "fill_ratio": fill_ratio,
            "max_turns_theoretical": critical_turns,
            "max_length_safe": max_length,
            "safe": True,
            "warnings": []
        }

        if fill_ratio > 0.95:
            result["safe"] = False
            result["warnings"].append("装填系数过高，可能导致堆叠咬死")
        elif fill_ratio > 0.85:
            result["warnings"].append("装填系数偏高，需注意发条质量")

        if fill_ratio < 0.5:
            result["warnings"].append("装填系数偏低，条盒空间未充分利用")

        if est_turns < 5:
            result["warnings"].append("圈数过少，动力储备可能不足")

        return result


class TorqueCalculator:
    """力矩计算器"""

    @staticmethod
    def calc_elastic_modulus(E_ref: float, temp_coeff: float,
                              temp: float, temp_ref: float = 20.0) -> float:
        """计算指定温度下的弹性模量"""
        delta_T = temp - temp_ref
        return E_ref * (1 + temp_coeff * delta_T)

    @staticmethod
    def calc_bending_stress(torque_Nmm: float, width: float,
                             thickness: float) -> float:
        """计算弯曲应力 (MPa)
        σ = M * y / I = M * (h/2) / (b*h³/12) = 6*M / (b*h²)
        """
        if width <= 0 or thickness <= 0:
            return 0.0
        return 6.0 * torque_Nmm / (width * thickness * thickness)

    @staticmethod
    def calc_max_torque(params: SpringParams, temp: float = 20.0) -> float:
        """计算满弦力矩（单位：g·cm）
        基于材料许用应力和安全系数计算
        """
        mat_info = MaterialLibrary.get_material(params.material)
        if mat_info:
            yield_strength = mat_info.get("yield_strength", 1600.0)
            safety_factor = 1.8
            allowable_stress = yield_strength / safety_factor
        else:
            allowable_stress = 800.0

        E = TorqueCalculator.calc_elastic_modulus(
            params.E_ref, params.E_temp_coeff, temp, params.temp_ref
        )

        thickness = params.thickness
        width = params.width

        max_torque_Nmm = allowable_stress * width * thickness * thickness / 6.0

        case_r = params.case_inner_dia / 2.0
        arbor_r = params.arbor_dia / 2.0
        avg_r = (case_r + arbor_r) / 2.0
        curvature_ratio = thickness / avg_r

        geometric_factor = 0.7 + 0.3 * (1 - curvature_ratio * 2)
        geometric_factor = max(0.5, min(geometric_factor, 1.0))

        max_torque_Nmm *= geometric_factor

        max_torque_gcm = max_torque_Nmm * 10.197

        return max_torque_gcm

    @staticmethod
    def generate_torque_curve(params: SpringParams, temp: float = 20.0,
                               num_points: int = 100) -> List[TorquePoint]:
        """生成力矩曲线（从满弦到放尽，力矩递减）
        x轴: 已释放圈数 (0 = 满弦, total_turns = 放尽)
        """
        total_turns = SpringGeometry.estimate_turns_by_length(
            params.length, params.case_inner_dia,
            params.arbor_dia, params.thickness
        )

        max_torque = TorqueCalculator.calc_max_torque(params, temp)

        E_ratio = TorqueCalculator.calc_elastic_modulus(
            params.E_ref, params.E_temp_coeff, temp, params.temp_ref
        ) / params.E_ref

        max_torque *= E_ratio

        min_torque_ratio = 0.35

        curve = []

        for i in range(num_points + 1):
            release_ratio = i / num_points
            released_turns = release_ratio * total_turns
            wound_turns = total_turns - released_turns

            linear_factor = 1.0 - release_ratio * (1 - min_torque_ratio)

            shape_factor = 0.15
            nonlinear = shape_factor * math.sin(math.pi * release_ratio)
            torque_factor = linear_factor + nonlinear

            torque = max_torque * torque_factor

            if release_ratio > 0.85:
                tail_factor = (1.0 - release_ratio) / 0.15
                tail_factor = max(0.0, tail_factor)
                torque = min_torque_ratio * max_torque + \
                         (torque - min_torque_ratio * max_torque) * tail_factor

            torque = max(0.0, torque)

            case_r = params.case_inner_dia / 2.0
            arbor_r = params.arbor_dia / 2.0
            stack_height = thickness = params.thickness * total_turns

            wound_ratio = wound_turns / total_turns if total_turns > 0 else 0
            outer_r = case_r - wound_ratio * (case_r - arbor_r - stack_height)
            inner_r = outer_r - stack_height

            if total_turns <= 0:
                inner_r = arbor_r
                outer_r = case_r

            point = TorquePoint(
                turn=released_turns,
                angle=released_turns * 360.0,
                torque=torque,
                radius_outer=outer_r,
                radius_inner=inner_r,
                turns_remaining=wound_turns
            )
            curve.append(point)

        return curve

    @staticmethod
    def analyze_decay_segments(curve: List[TorquePoint],
                                threshold_ratio: float = 0.15) -> List[Tuple[int, int]]:
        """识别力矩衰减过快的区段（标红区域）
        threshold_ratio: 单位圈数力矩衰减超过平均值的倍数
        """
        if len(curve) < 10:
            return []

        torques = [p.torque for p in curve]
        total_decay = torques[0] - torques[-1]
        total_turns = curve[-1].turn - curve[0].turn
        avg_decay_per_turn = total_decay / total_turns if total_turns > 0 else 0

        segments = []
        in_segment = False
        seg_start = 0

        window_size = max(3, len(curve) // 20)

        for i in range(window_size, len(curve)):
            window_decay = torques[i - window_size] - torques[i]
            window_turns = curve[i].turn - curve[i - window_size].turn
            decay_per_turn = window_decay / window_turns if window_turns > 0 else 0

            is_fast = decay_per_turn > avg_decay_per_turn * (1 + threshold_ratio)

            if is_fast and not in_segment:
                in_segment = True
                seg_start = i - window_size
            elif not is_fast and in_segment:
                in_segment = False
                if i - seg_start >= window_size * 2:
                    segments.append((seg_start, i))

        if in_segment and len(curve) - seg_start >= window_size * 2:
            segments.append((seg_start, len(curve) - 1))

        end_segment_start = int(len(curve) * 0.7)
        has_end_segment = any(s <= end_segment_start <= e for s, e in segments)
        if not has_end_segment:
            end_torque_ratio = torques[-1] / torques[0] if torques[0] > 0 else 0
            if end_torque_ratio < 0.5:
                segments.append((end_segment_start, len(curve) - 1))

        return segments

    @staticmethod
    def calc_total_energy(curve: List[TorquePoint]) -> float:
        """计算总储能（单位：mJ）
        力矩单位为 g·cm，转换为 mJ：1 g·cm = 9.80665 μJ = 0.00980665 mJ
        """
        energy_gcm = 0.0
        for i in range(1, len(curve)):
            avg_torque = (curve[i].torque + curve[i - 1].torque) / 2.0
            delta_angle = (curve[i].angle - curve[i - 1].angle) * math.pi / 180.0
            energy_gcm += avg_torque * delta_angle

        energy_mJ = energy_gcm * 9.80665 * 0.001
        return energy_mJ

    @staticmethod
    def estimate_power_reserve(curve: List[TorquePoint],
                                min_torque: float,
                                power_consumption: float = 1.5e-6) -> float:
        """
        估算动力储备时间（小时）
        power_consumption: 机芯功耗，单位 W，默认 1.5 微瓦
        min_torque: 维持走时的最小力矩 (g·cm)
        """
        energy_gcm = 0.0
        for i in range(1, len(curve)):
            if curve[i].torque < min_torque:
                break
            avg_torque = (curve[i].torque + curve[i - 1].torque) / 2.0
            delta_angle = (curve[i].angle - curve[i - 1].angle) * math.pi / 180.0
            energy_gcm += avg_torque * delta_angle

        energy_J = energy_gcm * 9.80665e-5

        if power_consumption > 0:
            reserve_seconds = energy_J / power_consumption
            return reserve_seconds / 3600.0
        return 0.0

    @staticmethod
    def risk_assessment(params: SpringParams, curve: List[TorquePoint],
                         case_check: dict) -> List[str]:
        """满弦力矩风险评估"""
        warnings = []

        max_torque = curve[0].torque if curve else 0
        min_torque = curve[-1].torque if curve else 0
        torque_drop = (max_torque - min_torque) / max_torque * 100 if max_torque > 0 else 0

        if max_torque > 80:
            warnings.append(f"高风险：满弦力矩{max_torque:.1f}g·cm过大，可能冲击擒纵机构")
        elif max_torque > 60:
            warnings.append(f"注意：满弦力矩{max_torque:.1f}g·cm偏高，建议检查擒纵强度")

        if torque_drop > 60:
            warnings.append(f"力矩衰减{torque_drop:.1f}%过大，后段摆幅可能明显下跌")
        elif torque_drop > 40:
            warnings.append(f"力矩衰减{torque_drop:.1f}%，建议考虑均力装置")

        if not case_check.get("safe", True):
            warnings.extend(case_check.get("warnings", []))

        mat_info = MaterialLibrary.get_material(params.material)
        if mat_info:
            max_torque_Nmm = max_torque * 0.0980665
            stress = TorqueCalculator.calc_bending_stress(
                max_torque_Nmm, params.width, params.thickness
            )
            yield_strength = mat_info.get("yield_strength", 1600.0)
            safety_factor = yield_strength / stress if stress > 0 else 999

            if safety_factor < 1.5:
                warnings.append(f"安全系数{safety_factor:.2f}过低，发条可能发生塑性变形")
            elif safety_factor < 2.0:
                warnings.append(f"安全系数{safety_factor:.2f}偏低，疲劳寿命可能受影响")

        return warnings


class CompensationCalculator:
    """均力补偿计算器"""

    @staticmethod
    def calc_fusee_compensation(curve: List[TorquePoint],
                                 fusee_stages: int = 5) -> CompensationResult:
        """计算宝塔轮（Fusee）补偿效果"""
        if len(curve) < 2:
            return CompensationResult(
                name="宝塔轮补偿",
                original_curve=[],
                compensated_curve=[],
                torque_std_before=0,
                torque_std_after=0,
                improvement_pct=0
            )

        original_torques = [p.torque for p in curve]
        max_torque = max(original_torques)

        compensated = []
        stage_turns = len(curve) // fusee_stages

        for i, point in enumerate(curve):
            stage = min(i // stage_turns, fusee_stages - 1)
            stage_ratio = (stage + 1) / fusee_stages

            target_ratio = 0.8 + 0.2 * stage_ratio
            compensation_factor = max_torque * target_ratio / point.torque if point.torque > 0 else 1

            compensation_factor = max(0.5, min(compensation_factor, 2.0))

            new_torque = point.torque * (1 + (compensation_factor - 1) * 0.7)

            new_point = TorquePoint(
                turn=point.turn,
                angle=point.angle,
                torque=new_torque,
                radius_outer=point.radius_outer,
                radius_inner=point.radius_inner,
                turns_remaining=point.turns_remaining
            )
            compensated.append(new_point)

        compensated_torques = [p.torque for p in compensated]

        std_before = _std_dev(original_torques)
        std_after = _std_dev(compensated_torques)
        improvement = (std_before - std_after) / std_before * 100 if std_before > 0 else 0

        return CompensationResult(
            name=f"宝塔轮补偿({fusee_stages}级)",
            original_curve=curve,
            compensated_curve=compensated,
            torque_std_before=std_before,
            torque_std_after=std_after,
            improvement_pct=improvement,
            params={"stages": fusee_stages}
        )

    @staticmethod
    def calc_constant_force_compensation(curve: List[TorquePoint]) -> CompensationResult:
        """计算恒力装置补偿效果（理想情况）"""
        if len(curve) < 2:
            return CompensationResult(
                name="恒力装置",
                original_curve=[],
                compensated_curve=[],
                torque_std_before=0,
                torque_std_after=0,
                improvement_pct=0
            )

        original_torques = [p.torque for p in curve]
        avg_torque = sum(original_torques) / len(original_torques)

        compensated = []
        efficiency = 0.92
        target_torque = avg_torque * efficiency

        for i, point in enumerate(curve):
            release_ratio = 0.9 + 0.1 * (i / max(1, len(curve) - 1))
            actual_torque = target_torque * release_ratio

            new_point = TorquePoint(
                turn=point.turn,
                angle=point.angle,
                torque=actual_torque,
                radius_outer=point.radius_outer,
                radius_inner=point.radius_inner,
                turns_remaining=point.turns_remaining
            )
            compensated.append(new_point)

        compensated_torques = [p.torque for p in compensated]

        std_before = _std_dev(original_torques)
        std_after = _std_dev(compensated_torques)
        improvement = (std_before - std_after) / std_before * 100 if std_before > 0 else 0

        return CompensationResult(
            name="恒力装置(理想)",
            original_curve=curve,
            compensated_curve=compensated,
            torque_std_before=std_before,
            torque_std_after=std_after,
            improvement_pct=improvement,
            params={"efficiency": efficiency}
        )

    @staticmethod
    def calc_stackfreed_compensation(curve: List[TorquePoint]) -> CompensationResult:
        """计算Stackfreed补偿效果"""
        if len(curve) < 2:
            return CompensationResult(
                name="Stackfreed",
                original_curve=[],
                compensated_curve=[],
                torque_std_before=0,
                torque_std_after=0,
                improvement_pct=0
            )

        original_torques = [p.torque for p in curve]
        max_torque = max(original_torques)

        compensated = []
        for i, point in enumerate(curve):
            ratio = i / max(1, len(curve) - 1)

            friction_torque = max_torque * 0.3 * (1 - ratio)
            new_torque = point.torque - friction_torque
            new_torque = max(new_torque, 0)

            new_point = TorquePoint(
                turn=point.turn,
                angle=point.angle,
                torque=new_torque,
                radius_outer=point.radius_outer,
                radius_inner=point.radius_inner,
                turns_remaining=point.turns_remaining
            )
            compensated.append(new_point)

        compensated_torques = [p.torque for p in compensated]

        std_before = _std_dev(original_torques)
        std_after = _std_dev(compensated_torques)
        improvement = (std_before - std_after) / std_before * 100 if std_before > 0 else 0

        return CompensationResult(
            name="Stackfreed补偿",
            original_curve=curve,
            compensated_curve=compensated,
            torque_std_before=std_before,
            torque_std_after=std_after,
            improvement_pct=improvement,
            params={}
        )


class DesignOptimizer:
    """设计优化器 - 反推发条参数"""

    @staticmethod
    def reverse_design(target_reserve_hours: float,
                       case_inner_dia: float,
                       arbor_dia: float,
                       material: str = "镍铬钢",
                       target_torque: float = 30.0,
                       power_consumption: float = 1.5e-6,
                       temp: float = 20.0) -> List[dict]:
        """
        根据目标动力储备反推发条料厚与长度组合
        返回多个可行方案
        """
        mat_info = MaterialLibrary.get_material(material) or MaterialLibrary.MATERIALS["镍铬钢"]

        case_r = case_inner_dia / 2.0
        arbor_r = arbor_dia / 2.0
        gap = case_r - arbor_r

        target_energy_J = target_reserve_hours * 3600 * power_consumption

        solutions = []

        thickness_options = [0.08, 0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.18, 0.20]
        width_options = [0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6]

        for thickness in thickness_options:
            for width in width_options:
                if thickness * width < 0.05:
                    continue

                params_tmp = SpringParams(
                    thickness=thickness,
                    width=width,
                    length=100.0,
                    case_inner_dia=case_inner_dia,
                    arbor_dia=arbor_dia,
                    material=material
                )

                max_torque = TorqueCalculator.calc_max_torque(params_tmp, temp)

                if max_torque < target_torque * 0.6:
                    continue
                if max_torque > target_torque * 2.0:
                    continue

                max_turns_safe = gap / thickness * 0.80

                avg_torque_ratio = 0.65
                avg_torque = max_torque * avg_torque_ratio

                if avg_torque > 0:
                    avg_torque_Nm = avg_torque * 9.80665e-5
                    total_angle_rad = target_energy_J / avg_torque_Nm if avg_torque_Nm > 0 else 0
                    required_turns = total_angle_rad / (2 * math.pi)
                else:
                    required_turns = 0

                if required_turns < 3:
                    continue
                if required_turns > max_turns_safe:
                    continue

                required_turns = max(required_turns, 4)

                est_length = SpringGeometry.calc_spring_length_from_turns(
                    required_turns * 1.1, case_inner_dia, arbor_dia, thickness
                )

                if est_length < 50:
                    continue

                params = SpringParams(
                    thickness=thickness,
                    width=width,
                    length=round(est_length, 1),
                    case_inner_dia=case_inner_dia,
                    arbor_dia=arbor_dia,
                    material=material,
                    E_ref=mat_info["E_ref"],
                    E_temp_coeff=mat_info["E_temp_coeff"],
                    density=mat_info["density"]
                )

                curve = TorqueCalculator.generate_torque_curve(params, temp)
                reserve = TorqueCalculator.estimate_power_reserve(
                    curve, min_torque=max_torque * 0.35,
                    power_consumption=power_consumption
                )

                case_check = SpringGeometry.check_case_volume(params)

                if not case_check["safe"]:
                    continue

                solution = {
                    "thickness": thickness,
                    "width": width,
                    "length": round(est_length, 1),
                    "estimated_reserve_hours": round(reserve, 1),
                    "max_torque": round(curve[0].torque, 1) if curve else 0,
                    "min_torque": round(curve[-1].torque, 1) if curve else 0,
                    "total_turns": round(curve[-1].turn, 1) if curve else 0,
                    "fill_ratio": round(case_check["fill_ratio"] * 100, 1),
                    "case_safe": case_check["safe"],
                    "params": params
                }
                solutions.append(solution)

        solutions.sort(key=lambda x: abs(x["estimated_reserve_hours"] - target_reserve_hours))

        return solutions[:10]


class TempEffectAnalyzer:
    """温度影响分析器"""

    @staticmethod
    def analyze_temp_effects(params: SpringParams,
                              temps: List[float] = None) -> Dict[float, dict]:
        """分析不同温度下的发条性能"""
        if temps is None:
            temps = [-10, 0, 10, 20, 30, 40, 50]

        results = {}

        for temp in temps:
            curve = TorqueCalculator.generate_torque_curve(params, temp)
            max_t = curve[0].torque if curve else 0
            min_t = curve[-1].torque if curve else 0
            avg_t = sum(p.torque for p in curve) / len(curve) if curve else 0
            reserve = TorqueCalculator.estimate_power_reserve(
                curve, min_torque=max_t * 0.3
            )

            results[temp] = {
                "temperature": temp,
                "elastic_modulus": TorqueCalculator.calc_elastic_modulus(
                    params.E_ref, params.E_temp_coeff, temp, params.temp_ref
                ),
                "max_torque": max_t,
                "min_torque": min_t,
                "avg_torque": avg_t,
                "power_reserve_hours": reserve,
                "curve": curve
            }

        return results


def _std_dev(values: List[float]) -> float:
    """计算标准差"""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def perform_full_analysis(params: SpringParams,
                           temp: float = 20.0) -> AnalysisResult:
    """执行完整分析"""
    curve = TorqueCalculator.generate_torque_curve(params, temp)

    max_t = curve[0].torque if curve else 0
    min_t = curve[-1].torque if curve else 0
    avg_t = sum(p.torque for p in curve) / len(curve) if curve else 0

    total_turns = curve[-1].turn if curve else 0
    total_energy = TorqueCalculator.calc_total_energy(curve)

    decay_segments = TorqueCalculator.analyze_decay_segments(curve)

    case_check = SpringGeometry.check_case_volume(params)

    risks = TorqueCalculator.risk_assessment(params, curve, case_check)

    temp_effects = TempEffectAnalyzer.analyze_temp_effects(
        params, [-10, 0, 10, 20, 30, 40]
    )

    return AnalysisResult(
        params=params,
        torque_curve=curve,
        max_torque=max_t,
        min_torque=min_t,
        avg_torque=avg_t,
        total_turns=total_turns,
        total_energy=total_energy,
        decay_segments=decay_segments,
        risk_warnings=risks,
        case_check=case_check,
        temp_effects=temp_effects
    )

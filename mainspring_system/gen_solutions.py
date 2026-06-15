"""生成准确的方案库数据"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.mechanics import SpringParams, perform_full_analysis, TorqueCalculator


def calc_solution_performance(params: SpringParams):
    """计算方案性能"""
    result = perform_full_analysis(params)
    reserve = TorqueCalculator.estimate_power_reserve(
        result.torque_curve,
        min_torque=result.max_torque * 0.35
    )
    return {
        "max_torque": round(result.max_torque, 1),
        "min_torque": round(result.min_torque, 1),
        "reserve_hours": round(reserve, 1),
        "total_turns": round(result.total_turns, 1),
    }


solutions = [
    {
        "name": "标准42小时动储",
        "category": "标准配置",
        "reserve_grade": "标准",
        "description": "经典42小时动力储备配置，适用于大多数自动机械机芯",
        "params": {
            "thickness": 0.10,
            "width": 1.2,
            "length": 350.0,
            "case_inner_dia": 10.0,
            "arbor_dia": 1.5,
            "material": "镍铬钢"
        },
        "application_scenarios": ["大三针", "日期显示", "基础自动机芯"],
        "reference_movements": ["ETA2824", "SW200", "MIYOTA9015"],
    },
    {
        "name": "长动力72小时",
        "category": "长动力",
        "reserve_grade": "长动力",
        "description": "72小时长动力配置，三日链，适合周末不佩戴也能持续走时",
        "params": {
            "thickness": 0.11,
            "width": 1.4,
            "length": 520.0,
            "case_inner_dia": 12.0,
            "arbor_dia": 1.8,
            "material": "镍铬钢"
        },
        "application_scenarios": ["三日链", "大三针", "正装表"],
        "reference_movements": ["PT5000", "SW300"],
    },
    {
        "name": "超长动力120小时",
        "category": "长动力",
        "reserve_grade": "超长动力",
        "description": "120小时五日链超长动力，适合出差旅行使用",
        "params": {
            "thickness": 0.10,
            "width": 1.8,
            "length": 850.0,
            "case_inner_dia": 14.0,
            "arbor_dia": 2.0,
            "material": "钴基合金"
        },
        "application_scenarios": ["五日链", "年历表", "复杂功能"],
        "reference_movements": ["Cal.3120", "ML115"],
    },
    {
        "name": "紧凑36小时",
        "category": "紧凑型",
        "reserve_grade": "标准",
        "description": "小尺寸条盒配置，适合女表或超薄机芯",
        "params": {
            "thickness": 0.09,
            "width": 0.9,
            "length": 240.0,
            "case_inner_dia": 8.0,
            "arbor_dia": 1.2,
            "material": "镍铬钢"
        },
        "application_scenarios": ["女表", "超薄机芯", "两针表"],
        "reference_movements": ["ETA2671", "SW1000"],
    },
    {
        "name": "高力矩配置",
        "category": "特殊应用",
        "reserve_grade": "标准",
        "description": "高力矩输出配置，适合复杂功能或大摆轮机芯",
        "params": {
            "thickness": 0.14,
            "width": 1.5,
            "length": 320.0,
            "case_inner_dia": 11.0,
            "arbor_dia": 2.0,
            "material": "钴基合金"
        },
        "application_scenarios": ["计时码表", "大摆轮", "复杂功能"],
        "reference_movements": ["Valjoux7750", "SW500"],
    },
    {
        "name": "硅发条80小时",
        "category": "新材料",
        "reserve_grade": "长动力",
        "description": "采用硅材料发条，弹性优异，抗疲劳性能好",
        "params": {
            "thickness": 0.08,
            "width": 1.2,
            "length": 550.0,
            "case_inner_dia": 11.0,
            "arbor_dia": 1.5,
            "material": "硅硅"
        },
        "application_scenarios": ["高端腕表", "硅材质", "高振频"],
        "reference_movements": ["Nivarox硅游丝"],
    },
]

print("生成方案库性能数据...")
print()

for i, sol in enumerate(solutions):
    params = SpringParams.from_dict(sol["params"])
    perf = calc_solution_performance(params)
    sol["performance"] = perf
    print(f"  [{sol['reserve_grade']}] {sol['name']}")
    print(f"      力矩: {perf['max_torque']} - {perf['min_torque']} g·cm")
    print(f"      动储: {perf['reserve_hours']} 小时")
    print(f"      圈数: {perf['total_turns']} 圈")
    print()

print(f"共 {len(solutions)} 个方案")
print()

import json
from datetime import datetime

output = []
for sol in solutions:
    sol_data = {
        "id": f"sol_{sol['name'].replace(' ', '_')}",
        "name": sol["name"],
        "category": sol["category"],
        "reserve_grade": sol["reserve_grade"],
        "description": sol["description"],
        "params": sol["params"],
        "performance": sol["performance"],
        "application_scenarios": sol["application_scenarios"],
        "reference_movements": sol["reference_movements"],
        "created_at": datetime.now().isoformat()
    }
    output.append(sol_data)

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(data_dir, exist_ok=True)
filepath = os.path.join(data_dir, 'solutions.json')

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"方案库数据已保存到 {filepath}")

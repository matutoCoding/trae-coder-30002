"""测试脚本 - 验证核心算法"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.mechanics import (
    SpringParams,
    perform_full_analysis,
    DesignOptimizer,
    CompensationCalculator,
    TorqueCalculator
)

def test_basic():
    print("=" * 50)
    print("测试1: 基础力矩计算")
    print("=" * 50)

    p = SpringParams()
    r = perform_full_analysis(p)

    print(f"满弦力矩: {r.max_torque:.2f} g·cm")
    print(f"末端力矩: {r.min_torque:.2f} g·cm")
    print(f"平均力矩: {r.avg_torque:.2f} g·cm")
    print(f"总圈数: {r.total_turns:.2f} 圈")
    decay_rate = (r.max_torque - r.min_torque) / r.max_torque * 100
    print(f"力矩衰减率: {decay_rate:.1f}%")
    print(f"总储能: {r.total_energy:.2f} mJ")
    print()

    print("衰减区段:", len(r.decay_segments))
    for i, (s, e) in enumerate(r.decay_segments):
        print(f"  区段{i}: 索引{s}-{e}")
    print()

    print("风险预警:")
    if r.risk_warnings:
        for w in r.risk_warnings:
            print(f"  ⚠ {w}")
    else:
        print("  ✓ 无明显风险")
    print()

    print("条盒校验:")
    print(f"  装填系数: {r.case_check['fill_ratio']*100:.1f}%")
    print(f"  安全状态: {'安全' if r.case_check['safe'] else '危险'}")
    if r.case_check['warnings']:
        for w in r.case_check['warnings']:
            print(f"  提示: {w}")
    print()

    print("温度影响:")
    for t, info in sorted(r.temp_effects.items()):
        print(f"  {t:>3}°C: 最大力矩 {info['max_torque']:.1f} g·cm, "
              f"动储 {info['power_reserve_hours']:.1f} h")

def test_compensation():
    print()
    print("=" * 50)
    print("测试2: 均力补偿")
    print("=" * 50)

    p = SpringParams()
    r = perform_full_analysis(p)
    curve = r.torque_curve

    fusee = CompensationCalculator.calc_fusee_compensation(curve, 5)
    print(f"宝塔轮(5级) 改善率: {fusee.improvement_pct:.1f}%")
    print(f"  补偿前标准差: {fusee.torque_std_before:.2f}")
    print(f"  补偿后标准差: {fusee.torque_std_after:.2f}")

    cf = CompensationCalculator.calc_constant_force_compensation(curve)
    print(f"恒力装置 改善率: {cf.improvement_pct:.1f}%")
    print(f"  补偿前标准差: {cf.torque_std_before:.2f}")
    print(f"  补偿后标准差: {cf.torque_std_after:.2f}")

    sf = CompensationCalculator.calc_stackfreed_compensation(curve)
    print(f"Stackfreed 改善率: {sf.improvement_pct:.1f}%")

def test_optimizer():
    print()
    print("=" * 50)
    print("测试3: 反推设计")
    print("=" * 50)

    solutions = DesignOptimizer.reverse_design(
        target_reserve_hours=72,
        case_inner_dia=10.0,
        arbor_dia=1.5,
        material="镍铬钢",
        target_torque=30.0
    )

    print(f"找到 {len(solutions)} 个可行方案:")
    for i, sol in enumerate(solutions[:5]):
        print(f"  方案{i+1}: 料厚{sol['thickness']}mm × 宽度{sol['width']}mm × "
              f"长度{sol['length']}mm")
        print(f"         预计动储: {sol['estimated_reserve_hours']:.1f}h, "
              f"满弦力矩: {sol['max_torque']:.1f} g·cm, "
              f"装填率: {sol['fill_ratio']:.1f}%")

def test_storage():
    print()
    print("=" * 50)
    print("测试4: 数据存储")
    print("=" * 50)

    from core.storage import DataStorage

    storage = DataStorage()
    solutions = storage.list_solutions()
    print(f"方案库方案数: {len(solutions)}")
    for s in solutions:
        print(f"  - {s.name} ({s.reserve_grade})")

    archives = storage.list_archives()
    print(f"档案数: {len(archives)}")

if __name__ == "__main__":
    test_basic()
    test_compensation()
    test_optimizer()
    test_storage()
    print()
    print("✓ 所有测试完成")

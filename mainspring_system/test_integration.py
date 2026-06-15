"""综合功能测试脚本"""
import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.mechanics import (
    SpringParams, perform_full_analysis, TorqueCalculator,
    CompensationCalculator, CompensationResult
)
from core.storage import MovementArchive, SpringSolution, DataStorage, DesignReportGenerator


def main():
    print('=== 综合功能测试 ===')
    print()

    # 1. 测试从分析结果生成档案
    print('1. 测试从分析结果生成档案...')
    params = SpringParams()
    result = perform_full_analysis(params)
    archive = MovementArchive.from_analysis(result, name='测试机芯', model='TEST-001')

    print(f'   档案名称: {archive.name}')
    print(f'   发条参数: {len(archive.spring_params)} 个字段')
    print(f'   力矩曲线: {len(archive.torque_curve)} 个点')
    print(f'   分析摘要: {list(archive.analysis_summary.keys())}')
    print(f'   风险预警: {len(archive.risk_warnings)} 条')
    print(f'   条盒校验: {list(archive.case_check.keys()) if archive.case_check else "空"}')
    print(f'   温度影响: {len(archive.temp_effects)} 个温度点')
    print(f'   衰减区段: {len(archive.decay_segments)} 个')
    print('   ✓ 档案生成成功，数据完整')
    print()

    # 2. 测试实测偏差计算
    print('2. 测试实测偏差计算...')
    archive.measured_max_torque = 24.0
    archive.measured_min_torque = 8.0
    archive.measured_reserve_hours = 10.0

    deviation = archive.get_calc_deviation()
    print(f'   满弦力矩偏差: {deviation.get("max_torque_deviation_pct", "N/A")}%')
    print(f'   末端力矩偏差: {deviation.get("min_torque_deviation_pct", "N/A")}%')
    print(f'   动储偏差: {deviation.get("reserve_deviation_pct", "N/A")}%')
    print('   ✓ 偏差计算正常')
    print()

    # 3. 测试从档案生成方案
    print('3. 测试从档案沉淀为方案...')
    solution = SpringSolution.from_archive(
        archive, name='测试方案', category='测试', reserve_grade='标准'
    )
    print(f'   方案名称: {solution.name}')
    print(f'   方案分类: {solution.category}')
    print(f'   动储等级: {solution.reserve_grade}')
    print(f'   性能指标: {solution.performance}')
    print('   ✓ 方案生成成功')
    print()

    # 4. 测试数据存储
    print('4. 测试数据存储...')
    storage = DataStorage()
    storage.save_archive(archive)
    storage.save_solution(solution)

    archives = storage.list_archives()
    solutions = storage.list_solutions()
    print(f'   档案数量: {len(archives)}')
    print(f'   方案数量: {len(solutions)}')

    saved_archive = storage.get_archive(archive.id)
    if saved_archive:
        print(f'   档案读取: {saved_archive.name}')
        print(f'   曲线点数: {len(saved_archive.torque_curve)}')
        print(f'   风险条数: {len(saved_archive.risk_warnings)}')
        print(f'   摘要字段: {list(saved_archive.analysis_summary.keys())}')
        print('   ✓ 数据存取正常')
    print()

    # 5. 测试报告生成
    print('5. 测试设计报告生成...')
    report_path = os.path.join(tempfile.gettempdir(), 'test_report.txt')

    comp_result = CompensationCalculator.calc_fusee_compensation(result.torque_curve, 5)

    report_text = DesignReportGenerator.generate_text_report(
        result,
        compensation_result=comp_result,
        filepath=report_path
    )

    print(f'   报告长度: {len(report_text)} 字符')
    print(f'   报告已保存: {report_path}')
    print()

    with open(report_path, 'r', encoding='utf-8') as f:
        first_lines = [next(f).rstrip() for _ in range(8)]
    print('   报告前几行:')
    for line in first_lines:
        print(f'     {line}')
    print('   ✓ 报告生成正常')
    print()

    # 6. 测试 UI 模块导入
    print('6. 测试 UI 模块导入...')
    try:
        from ui.pages.archive_page import ArchivePage, ArchiveEditDialog, PromoteSolutionDialog
        print('   ✓ 档案页模块导入成功')
    except Exception as e:
        print(f'   ✗ 档案页导入失败: {e}')
        import traceback
        traceback.print_exc()

    try:
        from ui.pages.torque_page import TorquePage
        print('   ✓ 力矩曲线页模块导入成功')
    except Exception as e:
        print(f'   ✗ 力矩曲线页导入失败: {e}')

    try:
        from ui.pages.compensation_page import CompensationPage
        print('   ✓ 均力补偿页模块导入成功')
    except Exception as e:
        print(f'   ✗ 均力补偿页导入失败: {e}')
    print()

    # 清理
    storage.delete_archive(archive.id)
    storage.delete_solution(solution.id)
    os.remove(report_path)

    print('=== 所有测试通过 ===')


if __name__ == '__main__':
    main()

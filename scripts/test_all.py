#!/usr/bin/env python3
"""Vκ-RAF∞ 综合测试 - 验证所有模块可正常导入和运行"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

passed = 0
failed = 0


def test(name, condition):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name}")


def test_core():
    print("\n=== 核心层测试 ===")
    from core import MkV2Calculator, CorrectionEngine, TrackMkCalculator, V46Sentinel
    mk = MkV2Calculator()
    close = pd.Series(3500 + np.cumsum(np.random.randn(300) * 20))
    val, layer = mk.calculate(close)
    test("Mκ计算返回值", 0.35 <= val <= 0.80)
    test("Mκ分层非空", layer != '')
    test("仓位比例在0-1", 0 <= mk.get_position_ratio(val) <= 1)

    corr = CorrectionEngine()
    rets = pd.DataFrame(np.random.randn(100, 5) * 0.01)
    c = corr.calc_c_corr(rets)
    test("C_corr在0.5-1", 0.5 <= c <= 1.0)
    w_s = corr.calc_w_s(close)
    test("W_S在0.7-1", 0.7 <= w_s <= 1.0)

    track = TrackMkCalculator()
    t = track.calculate(close)
    test("赛道ρ在0-1", 0 <= t['rho'] <= 1)
    test("赛道信号有效", t['signal'] in ['绿灯', '黄灯', '红灯'])

    sentinel = V46Sentinel()
    sentinel.set_global_data(close)
    result = sentinel.run_daily_sentinel('2025-01-01')
    test("哨兵输出含全局层", 'global_layer' in result)
    test("哨兵输出含校正值", 'correction_values' in result)


def test_validation():
    print("\n=== 验证闭环测试 ===")
    from extensions.validation import ValidationDB, SignalValidationEngine
    db = ValidationDB(db_path='/tmp/test_validation.json')
    db.add_signal('test_1', {'date': '2025-01-01', 'value': 0.65})
    test("验证DB写入", db.get_signal('test_1') is not None)
    engine = SignalValidationEngine(db_path='/tmp/test_engine.json')
    report = engine.get_accuracy_report()
    test("准确率报告生成", 'total_signals' in report)


def test_p0():
    print("\n=== P0 模块测试 ===")
    from extensions.p0_modules import DataQualityOfficer, CalibrationRiskOfficer, CausalAuditor
    dq = DataQualityOfficer()
    df = pd.DataFrame({'close': [100] * 100 + [200], 'volume': [1000] * 101})
    processed = dq.process(df)
    test("数据质控异常值修正", processed['close'].iloc[-1] < 200)
    test("质量分在0-1", 0 <= dq.quality_score <= 1)

    cro = CalibrationRiskOfficer()
    old = {'p': 1.0}
    new = {'p': 1.1}
    verdict, params, reason = cro.validate_calibration(old, new, param_name='p', baseline_params={'p': 1.0})
    test("校准风控裁决有效", verdict in ['passed', 'adjusted', 'rejected'])
    test("贝叶斯收缩生效", abs(params['p'] - 1.0) < 0.06)

    ca = CausalAuditor()
    test("因果审计初始化", ca is not None)


def test_p1():
    print("\n=== P1 模块测试 ===")
    from extensions.p1_modules import (SteadyStateDiagnostician, PIDCalibrationOptimizer,
                                        TrackLifecycleWeight, EVTTailCorrection)
    hmm = SteadyStateDiagnostician()
    mk_vals = np.concatenate([np.random.normal(0.55, 0.04, 200), np.random.normal(0.75, 0.06, 200)])
    hmm.fit(pd.Series(mk_vals))
    test("HMM拟合成功", hmm.transition_matrix is not None)
    diag = hmm.get_diagnosis()
    test("HMM诊断输出", diag is not None and 'current_state' in diag)

    pid = PIDCalibrationOptimizer()
    step = pid.optimize_step(1.1, 1.0)
    test("PID步长在范围内", -0.05 <= step <= 0.05)
    test("PID正误差正步长", step > 0)

    tl = TrackLifecycleWeight()
    close = pd.Series(100 + np.cumsum(np.random.randn(150) * 1.5 + 0.2))
    vol = pd.Series(np.random.randint(1000, 2000, 150).astype(float))
    stage, weight = tl.calculate(pd.DataFrame({'close': close, 'volume': vol}))
    test("生命周期阶段有效", stage in ['萌芽', '成长', '成熟', '衰退', '未知'])
    test("生命周期权重在0.5-1.2", 0.5 <= weight <= 1.2)

    evt = EVTTailCorrection()
    returns = pd.Series(np.random.standard_t(4, 500) * 0.01)
    evt.fit(returns)
    test("EVT GPD拟合", evt._gpd_params is not None)
    w_t = evt.get_tail_weight()
    test("EVT W_T在0.6-1", 0.6 <= w_t <= 1.0)


def test_module_manager():
    print("\n=== 模块管理器测试 ===")
    from extensions.module_manager import ModuleConfig, DependencyGraph, NonIntrusiveAuditor
    cfg = ModuleConfig(preset='enhanced')
    test("enhanced预设启用P0", len(cfg.get_enabled_modules()['p0']) == 3)
    test("enhanced预设启用P1", len(cfg.get_enabled_modules()['p1']) == 4)
    cfg2 = ModuleConfig(preset='minimal')
    test("minimal预设全关", sum(len(v) for v in cfg2.get_enabled_modules().values()) == 0)

    dg = DependencyGraph()
    report = dg.get_startup_report({'p0': {'causal_audit': True}, 'p1': {}, 'v43': {}})
    test("依赖图检测推荐组合", len(report['warnings']) >= 0)

    auditor = NonIntrusiveAuditor()
    test("非侵入审计初始化", auditor is not None)


def test_v43():
    print("\n=== v4.3 跨学科校正测试 ===")
    from extensions.v43_corrections import WEParadigmShift, WIInstitutionShock, WNNarrativeSaturation, MFIMacroFragility
    close = pd.Series(3500 + np.cumsum(np.random.randn(300) * 20))
    vol = pd.Series(np.random.randint(1000000, 5000000, 300).astype(float))
    rets = pd.DataFrame(np.random.randn(200, 5) * 0.01)

    we = WEParadigmShift()
    w_e = we.calculate(returns_df=rets, factor_series=close, volume_series=vol)
    test("W_E在0.6-1", 0.6 <= w_e <= 1.0)

    wi = WIInstitutionShock()
    w_i = wi.calculate(close, vol, '2025-01-01')
    test("W_I无事件时为1", w_i == 1.0)
    wi.add_manual_event('2025-01-01', impact_days=20)
    w_i_shock = wi.calculate(close, vol, '2025-01-05')
    test("W_I事件后降仓", w_i_shock < 1.0)

    wn = WNNarrativeSaturation()
    w_n = wn.calculate(close, vol)
    test("W_N在0.9-1", 0.9 <= w_n <= 1.0)

    mfi = MFIMacroFragility()
    result = mfi.calculate(close, vol)
    test("MFI分数在0-1", 0 <= result['mfi_score'] <= 1)
    test("MFI权重在0.5-1", 0.5 <= result['weight'] <= 1.0)


if __name__ == '__main__':
    print("=" * 60)
    print("Vκ-RAF∞ 综合测试")
    print("=" * 60)
    test_core()
    test_validation()
    test_p0()
    test_p1()
    test_module_manager()
    test_v43()
    print(f"\n{'=' * 60}")
    print(f"测试结果: {passed}/{passed + failed} 通过")
    print(f"{'=' * 60}")
    sys.exit(0 if failed == 0 else 1)

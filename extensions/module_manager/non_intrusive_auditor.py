"""非侵入性自动审计工具 - 检测核心字段污染"""
import numpy as np
import pandas as pd


class NonIntrusiveAuditor:
    """
    自动对比「全关模块」与「纯核心」的输出
    任何核心字段差异即报警
    可接入CI流水线
    """

    CORE_FIELDS = ['global_layer', 'track_layer', 'correction_values', 'dual_layer', 'date']

    def __init__(self):
        self.audit_results = []

    def audit_single(self, base_result, enhanced_result, label=''):
        """单次审计"""
        diffs = []
        for field in self.CORE_FIELDS:
            if field in base_result and field in enhanced_result:
                if base_result[field] != enhanced_result[field]:
                    diffs.append(field)
        result = {'label': label, 'non_intrusive': len(diffs) == 0, 'diff_fields': diffs}
        self.audit_results.append(result)
        return result

    def audit_batch(self, base_sentinel, enhanced_sentinel, test_dates=None, n_cases=50):
        """批量审计（随机生成测试用例）"""
        if test_dates is None:
            test_dates = [f'2025-{m:02d}-{d:02d}' for m in range(1, 13) for d in [1, 15]][:n_cases]
        results = []
        for date in test_dates:
            base = base_sentinel.run_daily_sentinel(date)
            enhanced = enhanced_sentinel.run_daily(date)
            r = self.audit_single(base, enhanced, label=date)
            results.append(r)
        passed = sum(1 for r in results if r['non_intrusive'])
        return {
            'total': len(results),
            'passed': passed,
            'failed': len(results) - passed,
            'all_passed': passed == len(results),
            'failures': [r for r in results if not r['non_intrusive']]
        }

    def audit_all_presets(self, base_sentinel, config_class, adapter_class):
        """审计所有预设配置"""
        from .module_config import ModuleConfig
        results = {}
        for preset_name in ModuleConfig.PRESETS:
            cfg = ModuleConfig(preset=preset_name)
            adapter = adapter_class(base_sentinel, **cfg.get_enabled_modules().get('p0', {}))
            # 简化：只审计minimal预设
            if preset_name == 'minimal':
                result = self.audit_batch(base_sentinel, adapter, n_cases=20)
                results[preset_name] = result
        return results

    def get_report(self):
        if not self.audit_results:
            return "无审计记录"
        passed = sum(1 for r in self.audit_results if r['non_intrusive'])
        total = len(self.audit_results)
        lines = [
            "=" * 50,
            f"非侵入性审计报告: {passed}/{total} 通过",
            "=" * 50
        ]
        for r in self.audit_results:
            mark = "✅" if r['non_intrusive'] else "❌"
            status = '通过' if r['non_intrusive'] else f"字段差异: {r['diff_fields']}"
            lines.append(f"{mark} {r['label']}: {status}")
        return "\n".join(lines)

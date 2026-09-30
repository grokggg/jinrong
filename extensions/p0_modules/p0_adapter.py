"""P0 增强层适配器 - 非侵入式包装核心哨兵"""
import pandas as pd
from datetime import datetime
from .data_quality_officer import DataQualityOfficer
from .calibration_risk_officer import CalibrationRiskOfficer
from .causal_auditor import CausalAuditor


class P0EnhancedSentinel:
    """所有模块默认关闭，可单独开关，关闭即纯核心版"""

    def __init__(self, base_sentinel, enable_data_quality=False,
                 enable_calibration_risk=False, enable_causal_audit=False):
        self.base = base_sentinel
        self.enable_dq = enable_data_quality
        self.enable_cr = enable_calibration_risk
        self.enable_ca = enable_causal_audit
        if self.enable_dq:
            self.dq_officer = DataQualityOfficer()
        if self.enable_cr:
            self.cr_officer = CalibrationRiskOfficer()
        if self.enable_ca:
            self.ca_auditor = CausalAuditor()
        self._price_cache = None
        self._dq_info = {'quality_score': 1.0, 'warning': False}

    def set_price_data(self, price_df):
        if self.enable_dq:
            processed = self.dq_officer.process(price_df)
            self._price_cache = processed
            self._dq_info = self.dq_officer.get_quality_info()
        else:
            self._price_cache = price_df
            self._dq_info = {'quality_score': 1.0, 'warning': False}
        return self

    def run_daily(self, date_str=None):
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        base_result = self.base.run_daily_sentinel(date_str)
        p0_info = {'modules_enabled': {
            'data_quality': self.enable_dq,
            'calibration_risk': self.enable_cr,
            'causal_audit': self.enable_ca}}
        if self.enable_dq:
            p0_info['data_quality'] = self._dq_info
        if self.enable_cr:
            p0_info['calibration_risk'] = self.cr_officer.get_status()
        base_result['p0_layer'] = p0_info
        return base_result

    def run_daily_sentinel(self, date_str=None):
        """兼容核心哨兵接口，供上层适配器嵌套调用"""
        return self.run_daily(date_str)

    def validate_calibration(self, old_params, new_params, **kwargs):
        if not self.enable_cr:
            return 'passed', new_params, '未启用校准风控'
        return self.cr_officer.validate_calibration(old_params, new_params, **kwargs)

    def export_report(self, date_str=None):
        base_report = self.base.export_report(date_str)
        result = self.run_daily(date_str)
        lines = [base_report, "\n", "=" * 60, "【P0 增强层】", "=" * 60]
        p0 = result.get('p0_layer', {})
        if p0['modules_enabled']['data_quality']:
            dq = p0['data_quality']
            lines.append(f"  数据质量分: {dq['quality_score']}")
        if p0['modules_enabled']['calibration_risk']:
            cr = p0['calibration_risk']
            lines.append(f"  校准状态: {cr['status']}")
        lines.append("\n  P0模块均为审计增强层，不修改核心计算逻辑")
        return "\n".join(lines)

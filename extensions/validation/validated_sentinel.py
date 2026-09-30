"""带验证闭环的哨兵适配器 - 非侵入式包装v4.6核心"""
import os
import pandas as pd
from datetime import datetime
from .signal_engine import SignalValidationEngine


class ValidatedSentinel:
    """
    验证闭环增强版哨兵
    非侵入：包装原哨兵，核心逻辑一字不动
    """

    def __init__(self, base_sentinel, validation_db='data/validation/v46_signals.json',
                 auto_verify=True, auto_calibrate=False):
        self.sentinel = base_sentinel
        self.engine = SignalValidationEngine(validation_db)
        self.auto_verify = auto_verify
        self.auto_calibrate = auto_calibrate
        self._price_data = None

    def set_price_data(self, price_df):
        self._price_data = price_df
        return self

    def run_daily(self, date_str=None):
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        result = self.sentinel.run_daily_sentinel(date_str)
        self.engine.record_daily_signals(date_str, result)
        verified_count = 0
        if self.auto_verify and self._price_data is not None:
            verified_count = self.engine.verify_expired_signals(self._price_data)
        val_stats = self.engine.get_accuracy_report()
        result['validation'] = {
            'enabled': True,
            'verified_count_30d': val_stats['verified_30d'],
            'accuracy_30d': val_stats['accuracy_30d'],
            'verified_count_60d': val_stats['verified_60d'],
            'accuracy_60d': val_stats['accuracy_60d'],
            'total_signals': val_stats['total_signals'],
            'verified_today': verified_count
        }
        return result

    def export_report(self, date_str=None):
        base_report = self.sentinel.export_report(date_str)
        result = self.run_daily(date_str)
        val = result['validation']
        lines = [base_report, "\n", "=" * 60, "【验证闭环统计】", "=" * 60]
        lines.append(f"  累计信号数: {val['total_signals']}")
        lines.append(f"  已验证(30天): {val['verified_count_30d']} 个")
        if val['accuracy_30d']:
            lines.append(f"  30天准确率: {val['accuracy_30d']*100:.1f}%")
        lines.append(f"  已验证(60天): {val['verified_count_60d']} 个")
        if val['accuracy_60d']:
            lines.append(f"  60天准确率: {val['accuracy_60d']*100:.1f}%")
        lines.append("\n  系统处于持续验证进化中...")
        return "\n".join(lines)

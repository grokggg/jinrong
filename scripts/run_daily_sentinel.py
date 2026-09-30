#!/usr/bin/env python3
"""Vκ-RAF∞ 每日哨兵运行入口"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import numpy as np
import pandas as pd
from datetime import datetime
from core import V46Sentinel
from extensions.validation import ValidatedSentinel
from extensions.p0_modules import P0EnhancedSentinel
from extensions.p1_modules import P1EnhancedSentinel
from extensions.module_manager import ModuleConfig


def generate_mock_data(n=500):
    """生成模拟行情数据（演示用）"""
    np.random.seed(42)
    dates = pd.date_range('2024-01-01', periods=n, freq='B')
    close = 3500 + np.cumsum(np.random.randn(n) * 20)
    volume = np.random.randint(1000000, 5000000, n).astype(float)
    return pd.DataFrame({'close': close, 'volume': volume}, index=dates)


def main():
    parser = argparse.ArgumentParser(description='Vκ-RAF∞ 每日哨兵')
    parser.add_argument('--date', default=None, help='日期 YYYY-MM-DD')
    parser.add_argument('--p0', action='store_true', help='启用P0审计层')
    parser.add_argument('--p1', action='store_true', help='启用P1增强层')
    parser.add_argument('--validation', action='store_true', help='启用验证闭环')
    parser.add_argument('--preset', default='minimal',
                       choices=['minimal', 'audit', 'enhanced', 'tail_risk_only', 'causal_audit_only'],
                       help='预设配置方案')
    args = parser.parse_args()

    # 生成/加载数据
    df = generate_mock_data()
    print(f"数据区间: {df.index[0].date()} ~ {df.index[-1].date()}")

    # 初始化核心哨兵
    sentinel = V46Sentinel()
    sentinel.set_global_data(df['close'], df['volume'])

    # 添加模拟赛道
    for name in ['科技', '消费', '金融']:
        track_close = df['close'] * (1 + np.random.randn(len(df)) * 0.02)
        sentinel.set_track_data(name, track_close, df['volume'])

    # 按配置包装
    config = ModuleConfig(preset=args.preset)
    p0_mods = config.get_enabled_modules().get('p0', {})
    p1_mods = config.get_enabled_modules().get('p1', {})
    # 参数名映射
    p0_kwargs = {
        'enable_data_quality': p0_mods.get('data_quality', False),
        'enable_calibration_risk': p0_mods.get('calibration_risk', False),
        'enable_causal_audit': p0_mods.get('causal_audit', False),
    }
    p1_kwargs = {
        'enable_hmm': p1_mods.get('hmm', False),
        'enable_pid': p1_mods.get('pid', False),
        'enable_lifecycle': p1_mods.get('lifecycle', False),
        'enable_evt': p1_mods.get('evt', False),
    }
    if args.p0 or any(p0_kwargs.values()):
        sentinel = P0EnhancedSentinel(sentinel, **p0_kwargs)
    if args.p1 or any(p1_kwargs.values()):
        sentinel = P1EnhancedSentinel(sentinel, **p1_kwargs)
    if args.validation:
        sentinel = ValidatedSentinel(sentinel)
        sentinel.set_price_data(df)

    # 运行
    date = args.date or datetime.now().strftime('%Y-%m-%d')
    report = sentinel.export_report(date)
    print(report)


if __name__ == '__main__':
    main()

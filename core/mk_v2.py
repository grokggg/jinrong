"""Mκ V2 全局市场稳态指数 - 核心公式（永久冻结，非侵入原则）"""
import numpy as np
import pandas as pd


def gaussian(x, opt, width):
    """高斯隶属函数"""
    return np.exp(-((x - opt) ** 2) / (2 * width ** 2))


class MkV2Calculator:
    """
    Mκ V2 全局市场稳态指数计算器
    四因子加权：估值疏密度 + 波动率 + 趋势 + 量比
    输出范围 [0.35, 0.80]
    分层：崩溃(<0.45) / 高危(0.45-0.55) / 预警(0.55-0.58) / 黄金稳态(0.58-0.72) / 过热(>=0.72)
    """

    def __init__(self, overheat_threshold=0.72, golden_lower=0.58):
        self.overheat_threshold = overheat_threshold
        self.golden_lower = golden_lower

    def calculate(self, close_series, volume_series=None):
        """
        输入：收盘价序列、成交量序列
        输出：Mκ 值 + 分层标签
        """
        close = close_series.dropna()
        if len(close) < 120:
            return 0.65, '数据不足'

        # 因子1：估值疏密度（价格相对252日高点的位置）
        pe_pct = close.iloc[-1] / close.rolling(252).max().iloc[-1]
        pe_pct = np.clip(pe_pct, 0.2, 1.0)

        # 因子2：波动率（20日年化波动率）
        returns = close.pct_change().dropna()
        vol_20 = returns.tail(20).std() * np.sqrt(252)

        # 因子3：趋势（60日涨跌幅）
        trend_60 = close.iloc[-1] / close.iloc[-60] - 1 if len(close) >= 60 else 0

        # 因子4：量比（20日均量/60日均量）
        if volume_series is not None:
            vol = volume_series.reindex(close.index).ffill()
            vol_20_mean = vol.tail(20).mean()
            vol_60_mean = vol.tail(60).mean()
            vol_ratio = vol_20_mean / vol_60_mean if vol_60_mean > 0 else 1.0
        else:
            vol_ratio = 1.0

        # 高斯隶属度加权
        f_pe = gaussian(pe_pct, 0.30, 0.25)
        f_vol = gaussian(vol_20, 0.15, 0.10)
        f_trend = gaussian(trend_60, 0.05, 0.15)
        f_volratio = gaussian(vol_ratio, 1.1, 0.3)

        mk = 0.45 + 0.12 * f_pe + 0.10 * f_vol + 0.08 * f_trend + 0.05 * f_volratio
        mk = float(np.clip(mk, 0.35, 0.80))

        # 分层
        if mk < 0.45:
            layer = '崩溃区'
        elif mk < 0.55:
            layer = '高危区'
        elif mk < self.golden_lower:
            layer = '预警稳态'
        elif mk < self.overheat_threshold:
            layer = '黄金稳态'
        else:
            layer = '过热区'

        return mk, layer

    def get_position_ratio(self, mk_value):
        """根据 Mκ 输出基准仓位比例"""
        if mk_value < 0.45:
            return 0.0
        elif mk_value < 0.55:
            return 0.2
        elif mk_value < 0.58:
            return 0.5
        elif mk_value < 0.72:
            return 0.8
        else:
            return 0.3

"""赛道级 Mk 计算器 - ρ博弈曲率 + Ξ叙事分歧双序参量"""
import numpy as np
import pandas as pd


class TrackMkCalculator:
    """
    赛道级稳态识别
    ρ: 博弈曲率（成交额集中度 + 价格离散度）
    Ξ: 叙事分歧（波动率 + 涨跌幅分化）
    信号：绿灯(ρ<0.65 且 Ξ<0.5) / 黄灯 / 红灯(ρ>0.75 或 Ξ>0.65)
    """

    def __init__(self):
        self.track_params = {}

    def calc_rho(self, track_close, track_volume, benchmark_close=None):
        """ρ 博弈曲率"""
        if len(track_close) < 60:
            return 0.5
        returns = track_close.pct_change().dropna()
        # 成交额集中度
        if track_volume is not None:
            vol = track_volume.reindex(track_close.index).ffill()
            vol_hhi = (vol.tail(20) / vol.tail(20).sum()).pow(2).sum()
        else:
            vol_hhi = 0.1
        # 价格离散度（相对基准）
        if benchmark_close is not None:
            bench_ret = benchmark_close.pct_change().dropna()
            common_idx = returns.index.intersection(bench_ret.index)
            tracking_error = (returns.loc[common_idx] - bench_ret.loc[common_idx]).std()
        else:
            tracking_error = returns.std()
        rho = 0.4 * np.clip(vol_hhi * 5, 0, 1) + 0.6 * np.clip(tracking_error * 10, 0, 1)
        return float(np.clip(rho, 0, 1))

    def calc_xi(self, track_close):
        """Ξ 叙事分歧"""
        if len(track_close) < 60:
            return 0.4
        returns = track_close.pct_change().dropna()
        vol = returns.tail(20).std() * np.sqrt(252)
        # 涨跌幅分化（20日振幅）
        amplitude = (track_close.tail(20).max() - track_close.tail(20).min()) / track_close.tail(20).mean()
        xi = 0.5 * np.clip(vol / 0.4, 0, 1) + 0.5 * np.clip(amplitude / 0.15, 0, 1)
        return float(np.clip(xi, 0, 1))

    def get_signal(self, rho, xi):
        """赛道信号灯"""
        if rho > 0.75 or xi > 0.65:
            return '红灯', '强制减仓'
        elif rho > 0.65 or xi > 0.50:
            return '黄灯', '禁止新仓'
        else:
            return '绿灯', '可正常开仓'

    def calculate(self, track_close, track_volume=None, benchmark_close=None):
        """完整赛道评估"""
        rho = self.calc_rho(track_close, track_volume, benchmark_close)
        xi = self.calc_xi(track_close)
        signal, action = self.get_signal(rho, xi)
        return {
            'rho': round(rho, 4),
            'xi': round(xi, 4),
            'signal': signal,
            'action': action
        }

"""W_E 范式跃迁校正 - 因子分布偏移+相关性升高+集中度"""
import numpy as np
import pandas as pd


class WEParadigmShift:
    """
    范式跃迁校正：旧规则失效期降仓
    三因子代理：因子分布偏移 + 平均相关性升高 + 成交额集中度
    """

    def __init__(self, window=60, baseline_window=252):
        self.window = window
        self.baseline_window = baseline_window

    def calculate(self, returns_df=None, factor_series=None, volume_series=None):
        score = 0.0
        factors = 0
        # 因子1：因子分布偏移（KS统计量代理：近期均值与长期均值的标准化距离）
        if factor_series is not None and len(factor_series) >= self.baseline_window:
            recent = factor_series.tail(self.window)
            baseline = factor_series.tail(self.baseline_window)
            if baseline.std() > 0:
                ks_proxy = abs(recent.mean() - baseline.mean()) / baseline.std()
                score += np.clip(ks_proxy / 2.0, 0, 1)
                factors += 1
        # 因子2：平均相关性升高
        if returns_df is not None and returns_df.shape[1] >= 2:
            corr = returns_df.tail(self.window).corr()
            avg_corr = corr.values[np.triu_indices_from(corr, k=1)].mean()
            score += np.clip((avg_corr - 0.3) / 0.5, 0, 1)
            factors += 1
        # 因子3：成交额集中度（HHI）
        if volume_series is not None and len(volume_series) >= self.window:
            vol = volume_series.tail(self.window)
            if vol.sum() > 0:
                hhi = (vol / vol.sum()).pow(2).sum()
                score += np.clip((hhi - 0.05) / 0.15, 0, 1)
                factors += 1
        if factors == 0:
            return 1.0
        paradigm_score = score / factors
        # 映射：0→1.0, 0.5→0.85, 1.0→0.6
        w_e = np.clip(1.0 - paradigm_score * 0.4, 0.6, 1.0)
        return float(w_e)

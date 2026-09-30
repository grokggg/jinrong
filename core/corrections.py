"""三大标准校正因子 - C_corr 关联发散 / W_L 流动性 / W_S 多尺度结构"""
import numpy as np
import pandas as pd


class CorrectionEngine:
    """
    三大校正因子引擎（乘法叠加在基准仓位上）
    C_corr: 关联发散校正（市场相关性升高时降仓）
    W_L:   流动性校正（流动性收紧时降仓）
    W_S:   多尺度结构校正（WD-SSM小波分解结构风险）
    """

    def __init__(self):
        pass

    def calc_c_corr(self, returns_df, window=60):
        """
        C_corr 关联发散校正
        输入：多资产收益率DataFrame
        逻辑：平均相关性升高 → 分散化失效 → 降仓
        """
        if returns_df.shape[1] < 2:
            return 1.0
        corr_matrix = returns_df.tail(window).corr()
        avg_corr = corr_matrix.values[np.triu_indices_from(corr_matrix, k=1)].mean()
        # 相关性 0.3→1.0, 0.8→0.5
        c_corr = np.clip(1.0 - (avg_corr - 0.3) * 0.8, 0.5, 1.0)
        return float(c_corr)

    def calc_w_l(self, volume_series, close_series, window=20):
        """
        W_L 流动性校正
        逻辑：成交额萎缩 + 价差扩大 → 流动性收紧 → 降仓
        """
        if volume_series is None or len(volume_series) < window:
            return 1.0
        vol_recent = volume_series.tail(window).mean()
        vol_60 = volume_series.tail(60).mean() if len(volume_series) >= 60 else vol_recent
        ratio = vol_recent / vol_60 if vol_60 > 0 else 1.0
        # 流动性 ratio 0.5→0.7, 1.5→1.0
        w_l = np.clip(0.7 + (ratio - 0.5) * 0.3, 0.7, 1.0)
        return float(w_l)

    def calc_w_s(self, close_series, wavelet_level=3):
        """
        W_S 多尺度结构校正（WD-SSM 简化实现版）
        对话中定义为 WD-SSM 小波分解结构风险保护器；
        代码中用"短期波动率/长期波动率能量比"作为可计算代理，
        避免引入 pywt 额外依赖，保持核心层极简。
        逻辑：高频能量占比升高 → 结构风险 → 降仓
        """
        close = close_series.dropna()
        if len(close) < 60:
            return 1.0
        returns = close.pct_change().dropna()
        # 简化：用不同周期滚动标准差的比值代替小波分解
        vol_short = returns.tail(5).std()
        vol_long = returns.tail(60).std()
        if vol_long == 0:
            return 1.0
        energy_ratio = vol_short / vol_long
        # 高频能量比 1.0→1.0, 2.5→0.7
        w_s = np.clip(1.0 - (energy_ratio - 1.0) * 0.2, 0.7, 1.0)
        return float(w_s)

    def calculate_all(self, close_series, volume_series=None, returns_df=None):
        """计算全部三大校正因子"""
        c_corr = self.calc_c_corr(returns_df) if returns_df is not None else 1.0
        w_l = self.calc_w_l(volume_series, close_series)
        w_s = self.calc_w_s(close_series)
        combined = c_corr * w_l * w_s
        return {
            'c_corr': round(c_corr, 4),
            'w_l': round(w_l, 4),
            'w_s': round(w_s, 4),
            'combined': round(combined, 4)
        }

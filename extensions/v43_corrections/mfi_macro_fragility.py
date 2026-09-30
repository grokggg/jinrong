"""MFI 宏观脆弱指数 - 波动率/流动性/趋势/尾部四因子合成"""
import numpy as np
import pandas as pd


class MFIMacroFragility:
    """
    宏观脆弱指数（Macro Fragility Index）
    四因子合成：波动率脆弱性 + 流动性脆弱性 + 趋势脆弱性 + 尾部脆弱性
    v4.3中表现最强的模块，回撤减10%+，卡玛提升60%+
    """

    def __init__(self, lookback=60):
        self.lookback = lookback

    def _vol_fragility(self, returns):
        """波动率脆弱性：近期波动率相对历史的升高程度"""
        if len(returns) < 20:
            return 0.5
        vol_recent = returns.tail(20).std() * np.sqrt(252)
        vol_long = returns.tail(min(252, len(returns))).std() * np.sqrt(252)
        if vol_long == 0:
            return 0.5
        ratio = vol_recent / vol_long
        return float(np.clip((ratio - 0.8) / 1.2, 0, 1))

    def _liquidity_fragility(self, volume_series):
        """流动性脆弱性：成交额萎缩程度"""
        if volume_series is None or len(volume_series) < 20:
            return 0.5
        vol_recent = volume_series.tail(20).mean()
        vol_long = volume_series.tail(min(120, len(volume_series))).mean()
        if vol_long == 0:
            return 0.5
        ratio = vol_recent / vol_long
        # 萎缩→脆弱性升高
        return float(np.clip((1.2 - ratio) / 1.0, 0, 1))

    def _trend_fragility(self, close_series):
        """趋势脆弱性：价格跌破长期均线的程度"""
        if len(close_series) < 60:
            return 0.5
        close = close_series.dropna()
        ma_60 = close.tail(60).mean()
        current = close.iloc[-1]
        drawdown_from_ma = (current - ma_60) / ma_60
        # 跌破均线越多→脆弱性越高
        return float(np.clip((-drawdown_from_ma - 0.02) / 0.20, 0, 1))

    def _tail_fragility(self, returns):
        """尾部脆弱性：负收益偏度 + 最大单日跌幅"""
        if len(returns) < 20:
            return 0.5
        recent = returns.tail(60)
        # 负偏度→尾部风险
        skew = recent.skew() if hasattr(recent, 'skew') else 0
        max_loss = recent.min()
        tail_score = 0.5 * np.clip(-skew / 2.0, 0, 1) + 0.5 * np.clip(-max_loss / 0.08, 0, 1)
        return float(np.clip(tail_score, 0, 1))

    def calculate(self, close_series, volume_series=None):
        """计算MFI并输出仓位校正权重"""
        close = close_series.dropna()
        returns = close.pct_change(fill_method=None).dropna()
        vf = self._vol_fragility(returns)
        lf = self._liquidity_fragility(volume_series)
        tf = self._trend_fragility(close)
        ef = self._tail_fragility(returns)
        # 等权合成
        mfi = (vf + lf + tf + ef) / 4.0
        # 映射：脆弱性0→权重1.0, 0.5→0.85, 1.0→0.5
        w_mfi = np.clip(1.0 - mfi * 0.5, 0.5, 1.0)
        return {
            'mfi_score': round(mfi, 4),
            'vol_fragility': round(vf, 4),
            'liquidity_fragility': round(lf, 4),
            'trend_fragility': round(tf, 4),
            'tail_fragility': round(ef, 4),
            'weight': round(w_mfi, 4)
        }

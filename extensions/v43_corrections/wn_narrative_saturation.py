"""W_N 叙事动力学校正 - 极端保险模式（高阈值+小幅降仓）"""
import numpy as np
import pandas as pd


class WNNarrativeSaturation:
    """
    叙事饱和校正 - 定位为"极端保险"
    只在高饱和度（>0.6）且上涨趋势中触发，小幅降仓（floor=0.9）
    纯量价代理识别叙事泡沫效果有限，需舆情数据接入后重新验证
    """

    def __init__(self, saturation_threshold=0.6, floor=0.9, lookback=60):
        self.saturation_threshold = saturation_threshold
        self.floor = floor
        self.lookback = lookback

    def _calc_saturation(self, close_series, volume_series=None):
        """计算叙事饱和度（纯量价代理）"""
        if len(close_series) < self.lookback:
            return 0.0
        close = close_series.dropna()
        returns = close.pct_change(fill_method=None).dropna()
        # 只在上涨趋势中计算饱和度
        trend = close.iloc[-1] / close.iloc[-min(20, len(close))] - 1
        if trend < 0:
            return 0.0
        # 因子1：价格加速（短期涨幅/长期涨幅）
        if len(close) >= 60:
            short_ret = close.iloc[-1] / close.iloc[-20] - 1
            long_ret = close.iloc[-1] / close.iloc[-60] - 1
            if abs(long_ret) > 0.01:
                acceleration = short_ret / (3 * long_ret)
            else:
                acceleration = 0.5
        else:
            acceleration = 0.5
        # 因子2：放量（20日均量/60日均量）
        if volume_series is not None:
            vol = volume_series.reindex(close.index).ffill()
            vol_ratio = vol.tail(20).mean() / vol.tail(60).mean() if len(vol) >= 60 else 1.0
        else:
            vol_ratio = 1.0
        # 因子3：波动率压缩（20日波动率/60日波动率）
        vol_20 = returns.tail(20).std() if len(returns) >= 20 else 0.02
        vol_60 = returns.tail(60).std() if len(returns) >= 60 else 0.02
        vol_compression = vol_60 / vol_20 if vol_20 > 0 else 1.0
        # 合成饱和度
        saturation = (
            0.4 * np.clip(acceleration, 0, 1.5) / 1.5 +
            0.3 * np.clip((vol_ratio - 0.8) / 1.2, 0, 1) +
            0.3 * np.clip((vol_compression - 0.5) / 1.5, 0, 1)
        )
        return float(np.clip(saturation, 0, 1))

    def calculate(self, close_series, volume_series=None):
        saturation = self._calc_saturation(close_series, volume_series)
        if saturation < self.saturation_threshold:
            return 1.0
        # 超过阈值后非线性小幅降仓
        excess = (saturation - self.saturation_threshold) / (1.0 - self.saturation_threshold)
        w_n = 1.0 - (excess ** 1.5) * (1.0 - self.floor)
        return float(np.clip(w_n, self.floor, 1.0))

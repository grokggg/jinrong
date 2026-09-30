"""P1-3 赛道生命周期权重 - 萌芽/成长/成熟/衰退四阶段"""
import numpy as np
import pandas as pd


class TrackLifecycleWeight:
    """
    多指标评分判断赛道生命周期
    权重：萌芽0.8 / 成长1.2 / 成熟1.0 / 衰退0.5
    非侵入：乘法叠加在赛道配置权重上
    """

    def __init__(self, lookback=120):
        self.lookback = lookback

    def _calc_metrics(self, price_df):
        if len(price_df) < self.lookback:
            return None
        close = price_df['close']
        volume = price_df.get('volume', pd.Series(index=close.index, data=1.0))
        vol_recent = volume.tail(30).mean()
        vol_prev = volume.tail(60).head(30).mean()
        vol_growth = (vol_recent / vol_prev - 1) if vol_prev > 0 else 0
        price_trend = close.iloc[-1] / close.iloc[-60] - 1 if len(close) >= 60 else 0
        returns = close.pct_change(fill_method=None).dropna()
        volatility = returns.tail(60).std() * np.sqrt(252) if len(returns) >= 60 else 0.2
        vol_ma_20 = volume.tail(20).mean()
        vol_ma_60 = volume.tail(60).mean()
        vol_ratio = vol_ma_20 / vol_ma_60 if vol_ma_60 > 0 else 1.0
        return {'vol_growth': vol_growth, 'price_trend': price_trend,
                'volatility': volatility, 'vol_ratio': vol_ratio}

    def _classify_stage(self, metrics):
        scores = {'萌芽': 0, '成长': 0, '成熟': 0, '衰退': 0}
        vg, pt, vol, vr = metrics['vol_growth'], metrics['price_trend'], metrics['volatility'], metrics['vol_ratio']
        # 萌芽：高波动+横盘+成交刚放大
        if vol > 0.35 and abs(pt) < 0.08 and vg > 0.1:
            scores['萌芽'] += 3
        elif vol > 0.28 and abs(pt) < 0.12:
            scores['萌芽'] += 1
        # 成长：成交放大+价格上涨+波动适中
        if vg > 0.2 and pt > 0.10 and 0.2 < vol < 0.4:
            scores['成长'] += 3
        elif vg > 0.1 and pt > 0.05:
            scores['成长'] += 1
        if vr > 1.2:
            scores['成长'] += 1
        # 成熟：成交稳定+价格平缓+低波动
        if abs(vg) < 0.1 and abs(pt) < 0.05 and vol < 0.25:
            scores['成熟'] += 3
        elif abs(vg) < 0.15 and vol < 0.3:
            scores['成熟'] += 1
        # 衰退：成交萎缩+价格下跌
        if vg < -0.15 and pt < -0.05:
            scores['衰退'] += 3
        elif vg < -0.08 and pt < -0.03:
            scores['衰退'] += 1
        stage = max(scores, key=scores.get)
        weight_map = {'萌芽': 0.8, '成长': 1.2, '成熟': 1.0, '衰退': 0.5}
        return stage, weight_map[stage]

    def calculate(self, price_df):
        metrics = self._calc_metrics(price_df)
        if metrics is None:
            return '未知', 1.0
        stage, weight = self._classify_stage(metrics)
        return stage, round(weight, 3)

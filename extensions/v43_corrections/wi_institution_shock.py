"""W_I 制度扰动校正 - 手动事件驱动+极端自动检测兜底"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


class WIInstitutionShock:
    """
    制度扰动校正
    核心模式：手动标记重大政策事件（注册制、降息、监管突变等）
    自动模式：波动率+成交量突变极端检测（仅作兜底，阈值高）
    温和降仓（floor=0.7），快速恢复（recovery=10天）
    """

    def __init__(self, ki=0.3, recovery_days=10, floor=0.7,
                 auto_detect=True, vol_threshold=5.0):
        self.ki = ki
        self.recovery_days = recovery_days
        self.floor = floor
        self.auto_detect = auto_detect
        self.vol_threshold = vol_threshold
        self.manual_events = []  # 手动标记的事件日期列表
        self._shock_state = {}

    def add_manual_event(self, event_date, impact_days=20, description=''):
        """手动标记重大政策事件"""
        self.manual_events.append({
            'date': event_date, 'impact_days': impact_days,
            'description': description, 'active': True
        })

    def _detect_auto_shock(self, close_series, volume_series, date):
        """自动检测极端制度冲击（高阈值，仅兜底）"""
        if not self.auto_detect or close_series is None:
            return False
        if len(close_series) < 30:
            return False
        returns = close_series.pct_change().dropna()
        if len(returns) < 20:
            return False
        recent_vol = returns.tail(5).std() * np.sqrt(252)
        baseline_vol = returns.tail(60).std() * np.sqrt(252)
        if baseline_vol == 0:
            return False
        vol_spike = recent_vol / baseline_vol
        # 成交量突变
        vol_spike_v = 1.0
        if volume_series is not None:
            recent_v = volume_series.tail(5).mean()
            baseline_v = volume_series.tail(60).mean()
            if baseline_v > 0:
                vol_spike_v = recent_v / baseline_v
        # 极端条件：波动率突增5倍以上 且 成交量突增3倍以上
        return vol_spike > self.vol_threshold and vol_spike_v > 3.0

    def calculate(self, close_series=None, volume_series=None, date_str=None):
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        current_date = pd.to_datetime(date_str)
        # 检查手动事件
        active_shock = False
        for event in self.manual_events:
            event_date = pd.to_datetime(event['date'])
            days_since = (current_date - event_date).days
            if 0 <= days_since < event['impact_days']:
                active_shock = True
                # 线性恢复
                recovery_progress = days_since / event['impact_days']
                shock_intensity = 1.0 - recovery_progress * 0.5
                break
        # 自动检测兜底
        if not active_shock:
            active_shock = self._detect_auto_shock(close_series, volume_series, date_str)
            shock_intensity = 1.0 if active_shock else 0.0
        if not active_shock:
            return 1.0
        # 温和降仓
        w_i = 1.0 - shock_intensity * self.ki * (1.0 - self.floor)
        return float(np.clip(w_i, self.floor, 1.0))

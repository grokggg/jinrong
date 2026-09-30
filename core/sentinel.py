"""v4.6 标准版哨兵 - 全局+赛道双层稳态监控（核心层，永久冻结）"""
import numpy as np
import pandas as pd
from datetime import datetime
from .mk_v2 import MkV2Calculator
from .corrections import CorrectionEngine
from .track_mk import TrackMkCalculator


class V46Sentinel:
    """
    v4.6 标准版每日哨兵
    全局层：Mκ V2 + 三大校正 → 基准仓位
    赛道层：ρ/Ξ 双序参量 → 赛道信号灯
    输出：每日哨兵报告 + 仓位建议
    """

    def __init__(self, overheat_threshold=0.72):
        self.mk_calc = MkV2Calculator(overheat_threshold=overheat_threshold)
        self.correction = CorrectionEngine()
        self.track_calc = TrackMkCalculator()
        self._price_data = {}
        self._track_data = {}

    def set_global_data(self, close, volume=None):
        """设置全局指数数据"""
        self._global_close = close
        self._global_volume = volume

    def set_track_data(self, track_name, close, volume=None):
        """设置赛道数据"""
        self._track_data[track_name] = {'close': close, 'volume': volume}

    def run_daily_sentinel(self, date_str=None):
        """运行每日哨兵"""
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')

        result = {'date': date_str, 'global_layer': {}, 'track_layer': {}, 'correction_values': {}, 'dual_layer': {}}

        # 全局层
        if hasattr(self, '_global_close') and self._global_close is not None:
            mk_val, mk_layer = self.mk_calc.calculate(self._global_close, self._global_volume)
            base_pos = self.mk_calc.get_position_ratio(mk_val)
            result['global_layer'] = {
                'mk_value': round(mk_val, 4),
                'mk_layer': mk_layer,
                'base_position': base_pos
            }

            # 三大校正
            corrections = self.correction.calculate_all(
                self._global_close, self._global_volume
            )
            result['correction_values'] = corrections

            # 调整后仓位
            adj_pos = base_pos * corrections['combined']
            result['global_layer']['position_adj'] = round(adj_pos, 4)
        else:
            result['global_layer'] = {'mk_value': 0.65, 'mk_layer': '数据不足', 'base_position': 0.5, 'position_adj': 0.5}
            result['correction_values'] = {'c_corr': 1.0, 'w_l': 1.0, 'w_s': 1.0, 'combined': 1.0}

        # 赛道层
        for track_name, data in self._track_data.items():
            track_result = self.track_calc.calculate(
                data['close'], data['volume'],
                getattr(self, '_global_close', None)
            )
            result['track_layer'][track_name] = track_result

        # 双层合成
        global_pos = result['global_layer'].get('position_adj', 0.5)
        for track_name in result['track_layer']:
            sig = result['track_layer'][track_name]['signal']
            track_mult = 1.0 if sig == '绿灯' else 0.5 if sig == '黄灯' else 0.0
            result['dual_layer'][track_name] = {
                'global_position_adj': round(global_pos, 4),
                'track_multiplier': track_mult,
                'final_position': round(global_pos * track_mult, 4)
            }

        return result

    def export_report(self, date_str=None):
        """导出文本报告"""
        result = self.run_daily_sentinel(date_str)
        lines = []
        lines.append("=" * 60)
        lines.append(f"Vκ-RAF∞ v4.6 每日哨兵报告  {result['date']}")
        lines.append("=" * 60)
        g = result['global_layer']
        lines.append(f"\n【全局层】Mκ = {g['mk_value']}  状态: {g['mk_layer']}")
        lines.append(f"  基准仓位: {g['base_position']*100:.0f}%  校正后: {g.get('position_adj', g['base_position'])*100:.0f}%")
        c = result['correction_values']
        lines.append(f"  校正因子: C_corr={c['c_corr']} W_L={c['w_l']} W_S={c['w_s']} 合成={c['combined']}")
        lines.append(f"\n【赛道层】")
        for name, info in result['track_layer'].items():
            mark = '🟢' if info['signal'] == '绿灯' else '🟡' if info['signal'] == '黄灯' else '🔴'
            lines.append(f"  {mark} {name}: ρ={info['rho']} Ξ={info['xi']} {info['signal']} - {info['action']}")
        lines.append("\n" + "=" * 60)
        return "\n".join(lines)

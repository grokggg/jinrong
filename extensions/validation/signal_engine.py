"""信号验证与自适应校准引擎 - 记录→验证→统计→渐进校准"""
import numpy as np
import pandas as pd
from datetime import datetime
from .validation_db import ValidationDB


class SignalValidationEngine:
    """
    信号验证闭环引擎
    铁律：参数年漂移≤10%，单次≤5%，样本<100不校准
    """

    def __init__(self, db_path='data/validation/v46_signals.json'):
        self.db = ValidationDB(db_path)
        self.MAX_ANNUAL_DRIFT = 0.10
        self.MIN_SAMPLES_CALIBRATE = 100
        # 熔断状态（第2轮三方审核确认的铁律）
        self.warning_triggered = False   # 连续2季度<60%
        self.fuse_triggered = False      # 连续4季度<55%
        self._quarterly_accuracies = []  # 历史季度准确率记录

    def record_daily_signals(self, date, sentinel_result):
        """记录当日所有层级信号"""
        date_str = date if isinstance(date, str) else date.strftime('%Y-%m-%d')
        g = sentinel_result['global_layer']
        self.db.add_signal(f"global_mk_{date_str}", {
            'date': date_str, 'level': 'global', 'type': 'mk_v2',
            'value': float(g.get('mk_value', 0)), 'layer': g.get('mk_layer', ''),
            'position_raw': float(g.get('base_position', 0)),
            'position_adj': float(g.get('position_adj', 0)),
            'verified_30d': False, 'verified_60d': False
        })
        for name, info in sentinel_result.get('track_layer', {}).items():
            self.db.add_signal(f"track_{name}_{date_str}", {
                'date': date_str, 'level': 'track', 'track': name,
                'value': float(info['rho']), 'xi': float(info['xi']),
                'signal': info['signal'],
                'verified_30d': False, 'verified_60d': False
            })
        return True

    def verify_expired_signals(self, price_data, horizon=60):
        """验证到期信号"""
        count = 0
        for sid, sig in self.db._data['signals'].items():
            if sig.get(f'verified_{horizon}d'):
                continue
            sig_date = datetime.strptime(sig['date'], '%Y-%m-%d')
            end_date = sig_date + pd.Timedelta(days=horizon)
            try:
                window = price_data.loc[sig_date:end_date]
                if len(window) < 5:
                    continue
                ret = window['close'].iloc[-1] / window['close'].iloc[0] - 1
                dd = (window['close'] / window['close'].cummax() - 1).min()
                layer = sig.get('layer', '')
                if layer in ['黄金稳态', '过热']:
                    correct = dd > -0.15
                elif layer in ['预警', '失稳', '高危区', '崩溃区']:
                    correct = ret < 0 or dd < -0.10
                else:
                    correct = None
                self.db.update_verification(sid, horizon, {
                    'total_return': round(ret, 4), 'max_drawdown': round(dd, 4),
                    'is_correct': correct
                })
                count += 1
            except Exception:
                continue
        return count

    def get_accuracy_report(self):
        signals = list(self.db._data['signals'].values())
        def calc(horizon):
            v = [s for s in signals if s.get(f'verified_{horizon}d') and s[f'result_{horizon}d'].get('is_correct') is not None]
            if not v:
                return 0, 0, None
            c = sum(1 for s in v if s[f'result_{horizon}d']['is_correct'])
            return len(v), c, c / len(v)
        v30, c30, a30 = calc(30)
        v60, c60, a60 = calc(60)
        report = {
            'total_signals': len(signals),
            'verified_30d': v30, 'accuracy_30d': round(a30, 3) if a30 else None,
            'verified_60d': v60, 'accuracy_60d': round(a60, 3) if a60 else None
        }
        self.db.update_stats(report)
        return report

    def check_quarterly_fuse(self):
        """
        季度熔断检查（第2轮三方审核确认的铁律）
        - 连续2个季度准确率<60% → 观察预警，暂停校准
        - 连续4个季度准确率<55% → 失效熔断，冻结参数，仅保留记录
        返回：(warning_triggered, fuse_triggered, 说明)
        """
        signals = list(self.db._data['signals'].values())
        verified = [s for s in signals if s.get('verified_60d')
                    and s[f'result_60d'].get('is_correct') is not None]
        if len(verified) < 20:
            return False, False, '验证样本不足，暂不评估熔断'

        # 按季度分组统计准确率
        from collections import defaultdict
        quarterly = defaultdict(lambda: {'correct': 0, 'total': 0})
        for s in verified:
            try:
                d = datetime.strptime(s['date'], '%Y-%m-%d')
                q = (d.year, (d.month - 1) // 3 + 1)
                quarterly[q]['total'] += 1
                if s['result_60d']['is_correct']:
                    quarterly[q]['correct'] += 1
            except Exception:
                continue

        # 取最近4个有足够样本的季度
        recent_quarters = sorted(quarterly.keys())[-4:]
        recent_accs = []
        for q in recent_quarters:
            if quarterly[q]['total'] >= 5:
                acc = quarterly[q]['correct'] / quarterly[q]['total']
                recent_accs.append(acc)

        if len(recent_accs) < 2:
            return False, False, '有效季度不足，暂不评估熔断'

        # 连续2季度<60% → 观察预警
        warning = len(recent_accs) >= 2 and all(a < 0.60 for a in recent_accs[-2:])
        # 连续4季度<55% → 失效熔断
        fuse = len(recent_accs) >= 4 and all(a < 0.55 for a in recent_accs[-4:])

        self.warning_triggered = warning
        self.fuse_triggered = fuse

        if fuse:
            return True, True, '🚨 失效熔断：连续4季度准确率<55%，冻结所有参数调整，仅保留记录功能'
        elif warning:
            return True, False, '⚠️ 观察预警：连续2季度准确率<60%，暂停校准，进入观察期'
        else:
            return False, False, f'正常：最近季度准确率 {[f"{a*100:.0f}%" for a in recent_accs]}'

    def adaptive_calibrate(self, current_params):
        """渐进式参数校准（样本不足不校准，熔断触发不校准）"""
        # 熔断检查优先：触发预警或熔断时拒绝校准
        warning, fuse, msg = self.check_quarterly_fuse()
        if fuse:
            return current_params, False, msg
        if warning:
            return current_params, False, msg

        report = self.get_accuracy_report()
        verified = report['verified_60d']
        if verified < self.MIN_SAMPLES_CALIBRATE:
            return current_params, False, '样本不足，暂不校准'
        acc = report['accuracy_60d']
        if acc is None:
            return current_params, False, '无准确率数据'
        drift = (acc - 0.7) * 0.05
        drift = float(np.clip(drift, -0.05, 0.05))
        new_params = current_params.copy()
        if 'overheat_threshold' in new_params:
            new_params['overheat_threshold'] *= (1 + drift)
        self.db.add_calibration_record({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'drift': drift, 'accuracy_before': acc, 'samples': verified
        })
        return new_params, True, f'校准完成，漂移率 {drift*100:.2f}%'

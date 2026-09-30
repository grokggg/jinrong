"""P0-2 校准风控官 - 漂移审计 + 贝叶斯收缩 + 过拟合预警"""
import numpy as np
from datetime import datetime


class CalibrationRiskOfficer:
    """
    非侵入式：只审计校准动作，三种裁决：通过/修正步长/驳回
    含 James-Stein 贝叶斯收缩因子，降低噪声环境下的MSE
    """

    def __init__(self, max_single_drift=0.05, max_annual_drift=0.10,
                 min_calibration_interval=90, shrinkage_factor=0.5):
        self.max_single_drift = max_single_drift
        self.max_annual_drift = max_annual_drift
        self.min_interval = min_calibration_interval
        self.shrinkage_factor = shrinkage_factor
        self.calibration_history = []
        self.overfit_warning = False
        self.fuse_triggered = False

    def _calc_cumulative_drift(self, current_params, baseline_params):
        if baseline_params is None:
            return 0.0
        drifts = []
        for key in current_params:
            if key in baseline_params and baseline_params[key] != 0:
                drift = abs(current_params[key] - baseline_params[key]) / abs(baseline_params[key])
                drifts.append(drift)
        return float(np.mean(drifts)) if drifts else 0.0

    def validate_calibration(self, old_params, new_params, param_name='overheat_threshold',
                            baseline_params=None, accuracy_before=None):
        old_val = old_params.get(param_name, 0)
        new_val = new_params.get(param_name, old_val)

        # 校准间隔检查
        if self.calibration_history:
            last_date = self.calibration_history[-1]['date']
            if (datetime.now() - last_date).days < self.min_interval:
                return 'rejected', old_params, f'校准间隔不足{self.min_interval}天'

        # 单次漂移计算
        raw_drift = (new_val - old_val) / old_val if old_val != 0 else 0

        # 第一步：大步长截断
        if abs(raw_drift) > self.max_single_drift:
            direction = 1 if raw_drift > 0 else -1
            adjusted_val = old_val * (1 + direction * self.max_single_drift)
            verdict = 'adjusted'
            reason = f'单次漂移{raw_drift*100:.1f}%超限，截断为{self.max_single_drift*100:.1f}%'
        else:
            adjusted_val = new_val
            verdict = 'passed'
            reason = '合规通过'

        # 第二步：贝叶斯收缩（James-Stein估计量）
        if abs(raw_drift) > 0.001:
            direction = 1 if adjusted_val > old_val else -1
            actual_drift = abs(adjusted_val - old_val) / old_val
            shrunk_drift = actual_drift * self.shrinkage_factor
            adjusted_val = old_val * (1 + direction * shrunk_drift)
            verdict = 'adjusted'
            reason += f'；贝叶斯收缩至{shrunk_drift*100:.1f}%'

        new_params[param_name] = adjusted_val

        # 第三步：累计漂移校验
        cum_drift = self._calc_cumulative_drift(new_params, baseline_params)
        if cum_drift > self.max_annual_drift:
            verdict = 'rejected'
            reason = f'累计漂移{cum_drift*100:.1f}%超年化上限'
            new_params = old_params

        # 过拟合征兆识别
        if accuracy_before is not None and len(self.calibration_history) >= 3:
            accs = [h['accuracy'] for h in self.calibration_history[-3:]]
            if accuracy_before < np.mean(accs) and abs(raw_drift) > 0.02:
                self.overfit_warning = True
                reason += '；⚠️ 过拟合征兆'

        self.calibration_history.append({
            'date': datetime.now(), 'param': param_name,
            'old_value': old_val, 'new_value': new_params.get(param_name, old_val),
            'verdict': verdict, 'accuracy': accuracy_before
        })
        return verdict, new_params, reason

    def get_status(self):
        return {
            'total_calibrations': len(self.calibration_history),
            'overfit_warning': self.overfit_warning,
            'fuse_triggered': self.fuse_triggered,
            'status': '正常' if not self.overfit_warning else '过拟合预警'
        }

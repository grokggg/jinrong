"""P1 增强层适配器 - 非侵入式包装核心哨兵"""
import pandas as pd
from datetime import datetime
from .steady_state_diagnostician import SteadyStateDiagnostician
from .pid_calibration_optimizer import PIDCalibrationOptimizer
from .track_lifecycle_weight import TrackLifecycleWeight
from .evt_tail_correction import EVTTailCorrection


class P1EnhancedSentinel:
    """所有模块默认关闭，可单独开关"""

    def __init__(self, base_sentinel, enable_hmm=False, enable_pid=False,
                 enable_lifecycle=False, enable_evt=False):
        self.base = base_sentinel
        self.enable_hmm = enable_hmm
        self.enable_pid = enable_pid
        self.enable_lifecycle = enable_lifecycle
        self.enable_evt = enable_evt
        if self.enable_hmm:
            self.hmm = SteadyStateDiagnostician()
        if self.enable_pid:
            self.pid = PIDCalibrationOptimizer()
        if self.enable_lifecycle:
            self.lifecycle = TrackLifecycleWeight()
        if self.enable_evt:
            self.evt = EVTTailCorrection()
        self._sector_data = {}

    def set_data(self, mk_series=None, sector_data=None):
        if mk_series is not None and self.enable_hmm:
            self.hmm.fit(mk_series)
        if sector_data is not None:
            self._sector_data = sector_data
        return self

    def run_daily(self, date_str=None):
        if date_str is None:
            date_str = datetime.now().strftime('%Y-%m-%d')
        base_result = self.base.run_daily_sentinel(date_str)
        p1_info = {'modules_enabled': {
            'hmm_diagnosis': self.enable_hmm, 'pid_calibration': self.enable_pid,
            'track_lifecycle': self.enable_lifecycle, 'evt_tail_correction': self.enable_evt}}
        if self.enable_hmm and self.hmm.transition_matrix is not None:
            p1_info['hmm_diagnosis'] = self.hmm.get_diagnosis()
        if self.enable_evt:
            p1_info['evt_tail_correction'] = {'w_t': round(self.evt.get_tail_weight(), 4)}
        if self.enable_lifecycle and self._sector_data:
            lc = {}
            for name, sdf in self._sector_data.items():
                stage, weight = self.lifecycle.calculate(sdf)
                lc[name] = {'stage': stage, 'weight': weight}
            p1_info['track_lifecycle'] = lc
        base_result['p1_layer'] = p1_info
        return base_result

    def run_daily_sentinel(self, date_str=None):
        """兼容核心哨兵接口，供上层适配器嵌套调用"""
        return self.run_daily(date_str)

    def optimize_calibration_step(self, target, current):
        if not self.enable_pid:
            return (target - current) / current if current != 0 else 0
        return self.pid.optimize_step(target, current)

    def export_report(self, date_str=None):
        base_report = self.base.export_report(date_str)
        result = self.run_daily(date_str)
        lines = [base_report, "\n", "=" * 60, "【P1 增强层】", "=" * 60]
        p1 = result.get('p1_layer', {})
        if p1['modules_enabled']['hmm_diagnosis'] and 'hmm_diagnosis' in p1:
            d = p1['hmm_diagnosis']
            lines.append(f"  HMM状态: {d['current_state']} (置信度{d['current_confidence']*100:.0f}%)")
            lines.append(f"  预期持续: {d['expected_duration_days']}天  20日切换概率: {d['switch_prob_20d']*100:.1f}%")
        if p1['modules_enabled']['evt_tail_correction'] and 'evt_tail_correction' in p1:
            lines.append(f"  EVT尾部校正 W_T: {p1['evt_tail_correction']['w_t']}")
        lines.append("\n  P1模块均为扩展增强层，默认关闭")
        return "\n".join(lines)

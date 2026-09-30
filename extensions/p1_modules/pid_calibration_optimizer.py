"""P1-2 PID校准优化器 - 比例-积分-微分闭环控制"""
import numpy as np


class PIDCalibrationOptimizer:
    """
    PID控制优化校准步长
    P: 按误差比例调整
    I: 累积历史偏差，消除稳态误差
    D: 预测趋势变化，防止超调
    """

    def __init__(self, Kp=0.45, Ki=0.18, Kd=0.20, max_step=0.05,
                 min_step=0.001, integral_window=5):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.max_step = max_step
        self.min_step = min_step
        self.integral_window = integral_window
        self.error_history = []
        self.last_error = 0.0

    def reset(self):
        self.error_history = []
        self.last_error = 0.0

    def optimize_step(self, target_value, current_value):
        if current_value == 0:
            return 0.0
        error = (target_value - current_value) / current_value
        # P项
        p_term = self.Kp * error
        # I项（含抗积分饱和限幅）
        self.error_history.append(error)
        if len(self.error_history) > self.integral_window:
            self.error_history.pop(0)
        integral_limit = self.max_step / self.Ki if self.Ki > 0 else float('inf')
        i_val = np.clip(np.mean(self.error_history), -integral_limit, integral_limit)
        i_term = self.Ki * i_val
        # D项
        d_term = self.Kd * (error - self.last_error)
        self.last_error = error
        # 总输出限幅
        step = p_term + i_term + d_term
        if abs(step) < self.min_step:
            step = 0
        return float(np.clip(step, -self.max_step, self.max_step))

    def auto_tune(self, historical_errors):
        """基于历史误差的Ziegler-Nichols简化整定"""
        if len(historical_errors) < 10:
            return self.Kp, self.Ki, self.Kd
        errors = np.array(historical_errors)
        # 临界增益法简化
        ku = 1.0 / (np.mean(np.abs(errors)) + 1e-6)
        ku = np.clip(ku, 0.1, 2.0)
        self.Kp = 0.6 * ku * 0.5  # 保守系数
        self.Ki = 0.4 * ku * 0.3
        self.Kd = 0.2 * ku * 0.4
        return self.Kp, self.Ki, self.Kd

    def get_diagnostics(self):
        return {
            'error_history': self.error_history.copy(),
            'last_error': self.last_error,
            'params': {'Kp': self.Kp, 'Ki': self.Ki, 'Kd': self.Kd}
        }

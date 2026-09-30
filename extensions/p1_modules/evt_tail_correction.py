"""P1-4 EVT极值理论尾部校正 W_T - POT/GPD尾部风险"""
import numpy as np
import pandas as pd
from scipy.stats import genpareto


class EVTTailCorrection:
    """
    第四大标准校正因子 W_T
    POT方法拟合GPD分布，估计99% VaR/ES
    尾部风险超过正态假设时非线性降仓，最低0.6
    """

    def __init__(self, threshold_quantile=0.85, lookback_window=1000):
        self.threshold_quantile = threshold_quantile
        self.lookback_window = lookback_window
        self._gpd_params = None
        self._threshold = None
        self._exceedances = None
        self._n_losses = 0

    def _select_optimal_threshold(self, losses):
        """Mean Excess Function法自适应选择阈值"""
        sorted_losses = np.sort(losses)
        n = len(sorted_losses)
        best_u = np.percentile(losses, self.threshold_quantile * 100)
        best_linearity = float('inf')
        for q in np.arange(0.70, 0.96, 0.05):
            u = np.percentile(losses, q * 100)
            exceed = sorted_losses[sorted_losses > u] - u
            if len(exceed) < 20:
                continue
            # MEF线性度检验
            if len(exceed) > 1:
                x = np.arange(len(exceed))
                mef = np.cumsum(exceed) / (np.arange(len(exceed)) + 1)
                if len(mef) > 2:
                    corr = np.corrcoef(x[:len(mef)], mef)[0, 1]
                    linearity = abs(1 - abs(corr))
                    if linearity < best_linearity:
                        best_linearity = linearity
                        best_u = u
        return best_u

    def fit(self, returns_series):
        returns = returns_series.dropna().values
        if len(returns) < 200:
            return False
        losses = -returns
        self._n_losses = len(losses)
        u = self._select_optimal_threshold(losses)
        self._threshold = u
        exceedances = losses[losses > u] - u
        self._exceedances = exceedances
        if len(exceedances) < 20:
            return False
        try:
            shape, loc, scale = genpareto.fit(exceedances, floc=0)
            self._gpd_params = {'shape': shape, 'scale': scale, 'loc': loc}
            return True
        except Exception:
            return False

    def calculate_var(self, quantile=0.99):
        if self._gpd_params is None:
            return None
        xi = self._gpd_params['shape']
        beta = self._gpd_params['scale']
        u = self._threshold
        exceed_prob = len(self._exceedances) / self._n_losses
        tail_prob = 1 - quantile
        if abs(xi) < 0.001:
            var = u + beta * np.log(exceed_prob / tail_prob)
        else:
            var = u + (beta / xi) * ((exceed_prob / tail_prob) ** xi - 1)
        return float(var)

    def calculate_es(self, quantile=0.99):
        var = self.calculate_var(quantile)
        if var is None or self._gpd_params is None:
            return None
        xi = self._gpd_params['shape']
        beta = self._gpd_params['scale']
        u = self._threshold
        if abs(xi - 1) < 0.001:
            return var
        return float(var / (1 - xi) + (beta - xi * u) / (1 - xi))

    def get_tail_weight(self):
        if self._gpd_params is None:
            return 1.0
        gpd_var = self.calculate_var(0.99)
        if gpd_var is None:
            return 1.0
        # 正态分布99% VaR
        all_losses = np.concatenate([self._exceedances + self._threshold,
                                      np.zeros(max(0, self._n_losses - len(self._exceedances)))])
        std = np.std(all_losses) if len(all_losses) > 0 else 0.01
        normal_var = std * 2.326
        if normal_var == 0:
            return 1.0
        var_ratio = gpd_var / normal_var
        # 非线性映射：1.3倍开始降仓，2.0倍到0.6
        if var_ratio <= 1.3:
            w_t = 1.0
        elif var_ratio >= 2.0:
            w_t = 0.6
        else:
            progress = (var_ratio - 1.3) / 0.7
            w_t = 1.0 - (progress ** 1.3) * 0.4
        return float(np.clip(w_t, 0.6, 1.0))

    def get_diagnostics(self):
        return {
            'threshold': self._threshold,
            'gpd_shape': self._gpd_params['shape'] if self._gpd_params else None,
            'var_99': self.calculate_var(0.99),
            'es_99': self.calculate_es(0.99),
            'w_t': self.get_tail_weight()
        }

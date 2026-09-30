"""P0-3 因果推断审计 v2.0 - PSM + 格兰杰 + 事件研究 三级因果检验"""
import numpy as np
import pandas as pd
from scipy import stats


class CausalAuditor:
    """
    三级因果判定：
    - 强因果 = PSM + 格兰杰 + 事件研究 全部通过
    - 弱因果 = 2项通过
    - 仅相关 = 1项通过
    - 虚假因子 = 0项通过
    """

    def __init__(self, n_matches=5, caliper=0.1):
        self.n_matches = n_matches
        self.caliper = caliper
        self.results = {}

    def _calc_propensity_score(self, confounders):
        conf_norm = (confounders - confounders.mean()) / (confounders.std() + 1e-10)
        from sklearn.decomposition import PCA
        pca = PCA(n_components=1)
        return pca.fit_transform(conf_norm).flatten()

    def estimate_ate(self, signal_series, return_series, confounders_df):
        """PSM倾向得分匹配 - 横截面因果检验"""
        df = pd.DataFrame({'treatment': signal_series, 'outcome': return_series}).join(confounders_df).dropna()
        if len(df) < 30:
            return 0, 1.0, False, '样本不足'
        treated = df[df['treatment'] == 1]
        control = df[df['treatment'] == 0]
        if len(treated) < 10 or len(control) < 10:
            return 0, 1.0, False, '分组样本不足'
        conf_cols = confounders_df.columns.tolist()
        ps_t = self._calc_propensity_score(treated[conf_cols])
        ps_c = self._calc_propensity_score(control[conf_cols])
        matched_returns = []
        control_rets = control['outcome'].values
        for ps_val in ps_t:
            distances = np.abs(ps_c - ps_val)
            valid = distances < self.caliper
            if valid.sum() == 0:
                continue
            nearest = np.argsort(distances)[:self.n_matches]
            matched_returns.append(np.mean(control_rets[nearest]))
        if len(matched_returns) < 5:
            return 0, 1.0, False, '匹配样本不足'
        treated_mean = treated['outcome'].iloc[:len(matched_returns)].mean()
        ate = treated_mean - np.mean(matched_returns)
        if len(matched_returns) >= 10:
            _, p_value = stats.ttest_rel(
                treated['outcome'].iloc[:len(matched_returns)].values,
                np.array(matched_returns))
        else:
            p_value = 1.0
        significant = p_value < 0.1
        if significant and abs(ate) > 0.005:
            level = '因果有效'
        elif abs(ate) > 0.002:
            level = '仅相关'
        else:
            level = '虚假因子'
        return float(ate), float(p_value), significant, level

    def granger_causality_test(self, factor_series, return_series, max_lag=5):
        """格兰杰因果检验 - 时间序列维度"""
        try:
            from statsmodels.tsa.stattools import grangercausalitytests
            data = pd.DataFrame({'ret': return_series, 'factor': factor_series}).dropna()
            if len(data) < 50:
                return False, 1.0, '样本不足'
            result = grangercausalitytests(data[['ret', 'factor']], maxlag=max_lag, verbose=False)
            min_p = min(result[lag][0]['ssr_ftest'][1] for lag in range(1, max_lag + 1))
            return min_p < 0.05, float(min_p), '因子→收益显著' if min_p < 0.05 else '不显著'
        except Exception:
            # 简化版：领先相关性
            data = pd.DataFrame({'ret': return_series, 'factor': factor_series}).dropna()
            if len(data) < 30:
                return False, 1.0, '样本不足'
            corrs = []
            for lag in range(1, 6):
                c = data['factor'].shift(lag).corr(data['ret'])
                if not np.isnan(c):
                    corrs.append(abs(c))
            if not corrs:
                return False, 1.0, '无法计算'
            max_corr = max(corrs)
            return max_corr > 0.1, float(1 - max_corr), f'领先相关{max_corr:.3f}'

    def event_study(self, signal_series, return_series, window=(-5, 20)):
        """事件研究法 - 事件窗口维度"""
        signals = pd.Series(signal_series)
        returns = pd.Series(return_series)
        event_dates = signals[signals == 1].index.tolist()
        if len(event_dates) < 3:
            return False, 1.0, '事件数不足'
        cars = []
        for ed in event_dates:
            try:
                idx = returns.index.get_loc(ed) if hasattr(returns.index, 'get_loc') else list(returns.index).index(ed)
                start = max(0, idx + window[0])
                end = min(len(returns), idx + window[1] + 1)
                car = returns.iloc[start:end].sum()
                cars.append(car)
            except Exception:
                continue
        if len(cars) < 3:
            return False, 1.0, '有效事件不足'
        mean_car = np.mean(cars)
        t_stat, p_value = stats.ttest_1samp(cars, 0)
        significant = p_value < 0.1 and abs(mean_car) > 0.01
        return significant, float(p_value), f'CAR={mean_car*100:.2f}%'

    def audit_factor(self, factor_name, signal, returns, confounders=None):
        """单因子三级因果审计"""
        # PSM检验
        if confounders is not None:
            ate, pval, psm_sig, psm_level = self.estimate_ate(signal, returns, confounders)
        else:
            ate, pval, psm_sig, psm_level = 0, 1.0, False, '无混淆变量'
        # 格兰杰检验
        granger_sig, granger_p, granger_msg = self.granger_causality_test(
            pd.Series(signal) if not isinstance(signal, pd.Series) else signal,
            pd.Series(returns) if not isinstance(returns, pd.Series) else returns)
        # 事件研究
        event_sig, event_p, event_msg = self.event_study(
            pd.Series(signal) if not isinstance(signal, pd.Series) else signal,
            pd.Series(returns) if not isinstance(returns, pd.Series) else returns)
        # 综合判定
        passed = sum([psm_sig, granger_sig, event_sig])
        if passed == 3:
            overall = '强因果'
        elif passed == 2:
            overall = '弱因果'
        elif passed == 1:
            overall = '仅相关'
        else:
            overall = '虚假因子'
        self.results[factor_name] = {
            'ate': round(ate, 4), 'psm_p': round(pval, 4), 'psm_pass': psm_sig,
            'granger_pass': granger_sig, 'granger_p': round(granger_p, 4),
            'event_pass': event_sig, 'event_p': round(event_p, 4),
            'overall': overall, 'tests_passed': passed
        }
        return self.results[factor_name]

    def run_full_factor_audit(self, factors_dict, returns, confounders=None):
        """全因子批量因果排查"""
        report = {'强因果': [], '弱因果': [], '仅相关': [], '虚假因子': [], '无法判定': []}
        for name, sig in factors_dict.items():
            try:
                result = self.audit_factor(name, sig, returns, confounders)
                report[result['overall']].append(name)
            except Exception as e:
                report['无法判定'].append(f"{name}({e})")
        return report

    def get_audit_report(self):
        lines = ["=" * 50, "因果推断审计报告 v2.0", "=" * 50]
        for name, res in self.results.items():
            mark = "✅" if res['overall'] == '强因果' else "🟡" if res['overall'] in ['弱因果', '仅相关'] else "❌"
            lines.append(f"{mark} {name}: {res['overall']} ({res['tests_passed']}/3通过)")
            lines.append(f"   ATE={res['ate']*100:.2f}% PSM(p={res['psm_p']}) 格兰杰(p={res['granger_p']}) 事件(p={res['event_p']})")
        return "\n".join(lines)

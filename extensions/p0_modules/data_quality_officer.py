"""P0-1 数据质控官 - 异常值鲁棒化 + 缺失值插补 + 质量评分"""
import numpy as np
import pandas as pd


class DataQualityOfficer:
    """非侵入式：只处理输入数据，不改变后续计算逻辑"""

    def __init__(self, enable_outlier_robust=True, enable_missing_impute=True):
        self.enable_outlier = enable_outlier_robust
        self.enable_impute = enable_missing_impute
        self.quality_score = 1.0

    def _detect_outliers(self, series, n_sigma=3):
        mean = series.mean()
        std = series.std()
        if std == 0:
            return pd.Series(False, index=series.index)
        return (series < mean - n_sigma * std) | (series > mean + n_sigma * std)

    def _robust_impute(self, series):
        outliers = self._detect_outliers(series)
        result = series.copy()
        if outliers.sum() > 0:
            rolling_median = series.rolling(20, center=True, min_periods=1).median()
            # 边界NaN回退到全局中位数
            rolling_median = rolling_median.fillna(series.median())
            result[outliers] = rolling_median[outliers]
        return result

    def _fill_missing(self, df):
        df = df.copy()
        for col in ['open', 'close', 'high', 'low']:
            if col in df.columns:
                df[col] = df[col].interpolate(method='linear', limit=5).ffill()
        if 'volume' in df.columns:
            df['volume'] = df['volume'].ffill()
            vol_median = df['volume'].rolling(60).median()
            df['volume'] = np.where(df['volume'].isna(), vol_median, df['volume'])
        return df

    def _calc_quality_score(self, df):
        score = 1.0
        if 'close' in df.columns:
            missing_ratio = df['close'].isna().sum() / len(df)
            score -= missing_ratio * 2
            rets = df['close'].pct_change(fill_method=None).dropna()
            if len(rets) > 0:
                outliers = self._detect_outliers(rets)
                outlier_ratio = outliers.sum() / len(outliers)
                if outlier_ratio > 0.02:
                    score -= (outlier_ratio - 0.02) * 5
        return float(np.clip(score, 0, 1))

    def process(self, df):
        result = df.copy()
        if self.enable_impute:
            result = self._fill_missing(result)
        if self.enable_outlier:
            if 'close' in result.columns:
                result['close'] = self._robust_impute(result['close'])
            if 'volume' in result.columns:
                result['volume'] = self._robust_impute(result['volume'])
        self.quality_score = self._calc_quality_score(result)
        return result

    def get_quality_info(self):
        return {
            'quality_score': round(self.quality_score, 3),
            'warning': self.quality_score < 0.7,
            'suggested_confidence_discount': max(0, 1 - self.quality_score) * 0.3
        }

"""独立验证数据库 - 单文件JSON，无共享，无锁"""
import os
import json
import numpy as np
from datetime import datetime


class ValidationDB:
    """信号验证独立存储（严格隔离核心系统）"""

    def __init__(self, db_path='data/validation/v46_signals.json'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._data = self._load()

    def _load(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {'signals': {}, 'stats': {}, 'calibration_history': []}

    def _save(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2, default=str)

    def add_signal(self, signal_id, signal_data):
        self._data['signals'][signal_id] = signal_data
        self._save()

    def get_signal(self, signal_id):
        return self._data['signals'].get(signal_id)

    def get_all_unverified(self, horizon_days):
        today = datetime.now()
        unverified = []
        for sid, sig in self._data['signals'].items():
            sig_date = datetime.strptime(sig['date'], '%Y-%m-%d')
            days_passed = (today - sig_date).days
            if days_passed >= horizon_days and not sig.get(f'verified_{horizon_days}d'):
                unverified.append(sid)
        return unverified

    def update_verification(self, signal_id, horizon_days, result):
        if signal_id in self._data['signals']:
            self._data['signals'][signal_id][f'verified_{horizon_days}d'] = True
            self._data['signals'][signal_id][f'result_{horizon_days}d'] = result
            self._save()

    def update_stats(self, stats):
        self._data['stats'] = stats
        self._save()

    def add_calibration_record(self, record):
        self._data['calibration_history'].append(record)
        self._save()

    def get_calibration_count(self):
        return len(self._data['calibration_history'])

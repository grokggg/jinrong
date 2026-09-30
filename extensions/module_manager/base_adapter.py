"""统一适配器接口规范 - 所有增强适配器必须继承此基类"""
from abc import ABC, abstractmethod


class BaseEnhancedAdapter(ABC):
    """
    所有增强适配器统一接口
    内置非侵入校验：关闭所有模块时输出必须与纯核心一致
    """

    def __init__(self, base_sentinel):
        self.base = base_sentinel

    @abstractmethod
    def run_daily(self, date_str=None) -> dict:
        pass

    @abstractmethod
    def export_report(self, date_str=None) -> str:
        pass

    @abstractmethod
    def get_module_status(self) -> dict:
        pass

    def verify_non_intrusive(self, date_str=None):
        """非侵入性自检：对比纯核心输出"""
        base_result = self.base.run_daily_sentinel(date_str)
        enhanced_result = self.run_daily(date_str)
        # 核心字段必须一致
        core_keys = ['global_layer', 'track_layer', 'correction_values', 'dual_layer']
        diffs = []
        for key in core_keys:
            if key in base_result and key in enhanced_result:
                if base_result[key] != enhanced_result[key]:
                    diffs.append(key)
        return {'non_intrusive': len(diffs) == 0, 'diff_fields': diffs}

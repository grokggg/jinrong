"""模块配置中心 - 统一管理所有扩展模块的开关与预设方案"""


class ModuleConfig:
    """
    预设方案：
    - minimal: 全关（纯核心版）
    - audit: 只开P0审计层
    - enhanced: 开P0+P1全部
    - tail_risk_only: 只开EVT尾部校正
    - causal_audit_only: 只开因果审计
    """

    PRESETS = {
        'minimal': {'p0': {}, 'p1': {}, 'v43': {}},
        'audit': {
            'p0': {'data_quality': True, 'calibration_risk': True, 'causal_audit': True},
            'p1': {}, 'v43': {}
        },
        'enhanced': {
            'p0': {'data_quality': True, 'calibration_risk': True, 'causal_audit': True},
            'p1': {'hmm': True, 'pid': True, 'lifecycle': True, 'evt': True},
            'v43': {'mfi': True, 'we': True}
        },
        'tail_risk_only': {
            'p0': {}, 'p1': {'evt': True}, 'v43': {'mfi': True}
        },
        'causal_audit_only': {
            'p0': {'causal_audit': True}, 'p1': {}, 'v43': {}
        }
    }

    def __init__(self, preset='minimal', p0=None, p1=None, v43=None):
        if preset in self.PRESETS:
            cfg = self.PRESETS[preset]
            self.p0 = cfg['p0'].copy()
            self.p1 = cfg['p1'].copy()
            self.v43 = cfg['v43'].copy()
        else:
            self.p0 = {}
            self.p1 = {}
            self.v43 = {}
        if p0:
            self.p0.update(p0)
        if p1:
            self.p1.update(p1)
        if v43:
            self.v43.update(v43)

    def is_enabled(self, layer, module_name):
        return getattr(self, layer, {}).get(module_name, False)

    def enable(self, layer, module_name):
        getattr(self, layer)[module_name] = True

    def disable(self, layer, module_name):
        getattr(self, layer)[module_name] = False

    def get_enabled_modules(self):
        return {'p0': {k: v for k, v in self.p0.items() if v},
                'p1': {k: v for k, v in self.p1.items() if v},
                'v43': {k: v for k, v in self.v43.items() if v}}

    def summary(self):
        enabled = self.get_enabled_modules()
        total = sum(len(v) for v in enabled.values())
        return f"已启用 {total} 个模块: P0={list(enabled['p0'].keys())} P1={list(enabled['p1'].keys())} v43={list(enabled['v43'].keys())}"

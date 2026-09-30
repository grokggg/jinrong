"""模块依赖图 - 推荐组合关系检测与拓扑排序"""


class DependencyGraph:
    """
    模块间推荐组合关系（非硬依赖，缺失只警告不阻断）
    P0→P1 拓扑排序启动
    """

    # 推荐组合：被依赖模块 -> 推荐同时开启的模块
    RECOMMENDED_COMBOS = {
        'pid_calibration': ['calibration_risk'],
        'causal_audit': ['data_quality'],
        'evt': ['mfi'],
        'hmm': ['data_quality'],
    }

    def __init__(self):
        pass

    def check_dependencies(self, enabled_modules):
        """检查推荐组合，返回警告列表"""
        warnings = []
        enabled_flat = set()
        for layer_mods in enabled_modules.values():
            enabled_flat.update(layer_mods.keys())
        for module, deps in self.RECOMMENDED_COMBOS.items():
            if module in enabled_flat:
                for dep in deps:
                    if dep not in enabled_flat:
                        warnings.append(f"模块 '{module}' 推荐与 '{dep}' 同时启用（当前未开启）")
        return warnings

    def topological_sort(self, enabled_modules):
        """P0→P1→v43 拓扑排序启动顺序"""
        order = []
        layers = ['p0', 'p1', 'v43']
        for layer in layers:
            for mod_name in enabled_modules.get(layer, {}):
                order.append((layer, mod_name))
        return order

    def get_startup_report(self, enabled_modules):
        warnings = self.check_dependencies(enabled_modules)
        order = self.topological_sort(enabled_modules)
        return {
            'startup_order': order,
            'warnings': warnings,
            'has_warnings': len(warnings) > 0
        }

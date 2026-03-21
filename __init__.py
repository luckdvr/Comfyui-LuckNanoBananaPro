from importlib import import_module


def _load_node_module(module_name):
    try:
        module = import_module(f".{module_name}", __name__)
    except Exception as exc:
        print(f"[LuckNanoBananaPro] 跳过加载 {module_name}: {exc}")
        return {}, {}

    return (
        getattr(module, "NODE_CLASS_MAPPINGS", {}),
        getattr(module, "NODE_DISPLAY_NAME_MAPPINGS", {}),
    )


GEMINI_MAPPINGS, GEMINI_DISPLAY_MAPPINGS = _load_node_module("gemini_editor")
APIYI_MAPPINGS, APIYI_DISPLAY_MAPPINGS = _load_node_module("apiyi_node")

# 前端扩展目录（用于节点实时状态栏）
WEB_DIRECTORY = "./web"

# 合并所有节点
NODE_CLASS_MAPPINGS = {**GEMINI_MAPPINGS, **APIYI_MAPPINGS}
NODE_DISPLAY_NAME_MAPPINGS = {**GEMINI_DISPLAY_MAPPINGS, **APIYI_DISPLAY_MAPPINGS}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

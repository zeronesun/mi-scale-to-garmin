"""
PyInstaller Runtime Hook
修复打包后 inspect.getsource() 失败的问题

关键：必须在任何 patch 之前捕获 inspect 的真实函数，
再安装包装器。若先 patch 再捕获，捕获到的就是包装器自身，
调用时会无限递归（RecursionError）。
"""
import os

# 禁用 logfire 的 pydantic 集成（会导致 inspect.getsource 错误）
os.environ['LOGFIRE_SKIP_PYDANTIC_PLUGIN'] = '1'
os.environ['PYDANTIC_DISABLE_PYDANTIC_V2_PLUGINS'] = '1'

import inspect

# 立即捕获真实实现（此时尚未 patch）
_true_getsource = inspect.getsource
_true_getsourcelines = inspect.getsourcelines
_true_getsourcefile = inspect.getsourcefile

_PLACEHOLDER = "# Source code not available in frozen application"


def _patched_getsource(object):
    try:
        return _true_getsource(object)
    except (OSError, TypeError):
        return _PLACEHOLDER


def _patched_getsourcelines(object):
    try:
        return _true_getsourcelines(object)
    except (OSError, TypeError):
        return [_PLACEHOLDER], 1


def _patched_getsourcefile(object):
    try:
        return _true_getsourcefile(object)
    except (OSError, TypeError):
        return None


inspect.getsource = _patched_getsource
inspect.getsourcelines = _patched_getsourcelines
inspect.getsourcefile = _patched_getsourcefile

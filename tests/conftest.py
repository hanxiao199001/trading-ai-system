"""pytest 公共配置

- 确保项目根目录在 sys.path 中(无论从哪里启动 pytest)
- 默认跳过需要访问外部交易所的网络测试, 设置 RUN_NETWORK_TESTS=1 可启用
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 需要真实网络连接(外部交易所公开API)的测试
NETWORK_TESTS = {"test_okx_connection"}


def pytest_collection_modifyitems(config, items):
    if os.environ.get("RUN_NETWORK_TESTS") == "1":
        return
    skip_net = pytest.mark.skip(reason="需要外部交易所网络连接, 设置 RUN_NETWORK_TESTS=1 启用")
    for item in items:
        if item.name in NETWORK_TESTS:
            item.add_marker(skip_net)

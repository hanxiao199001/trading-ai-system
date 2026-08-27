"""
Trading AI System - Backtest Module
回测模块,支持历史数据回放和策略验证
"""

from .engine import BacktestEngine
from .metrics import PerformanceMetrics
from .types import BacktestConfig, BacktestResult, BacktestMode
from .data_loader import DataLoader, KlineData

# matplotlib 为可选依赖, 缺失时可视化功能不可用但不影响回测
try:
    from .visualizer import BacktestVisualizer
except ImportError:  # pragma: no cover
    BacktestVisualizer = None

__all__ = [
    'BacktestEngine',
    'PerformanceMetrics',
    'BacktestConfig',
    'BacktestResult',
    'BacktestMode',
    'DataLoader',
    'KlineData',
    'BacktestVisualizer',
]

__version__ = '1.0.0'

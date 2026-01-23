"""
Trading AI System - Backtest Module
回测模块,支持历史数据回放和策略验证
"""

from .engine import BacktestEngine
from .metrics import PerformanceMetrics
from .types import BacktestConfig, BacktestResult

__all__ = [
    'BacktestEngine',
    'PerformanceMetrics', 
    'BacktestConfig',
    'BacktestResult',
]

__version__ = '1.0.0'

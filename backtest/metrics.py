"""
回测性能指标计算
"""
import numpy as np
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Tuple
from .types import Trade, EquityPoint


class PerformanceMetrics:
    """性能指标计算器"""
    
    @staticmethod
    def calculate_returns(equity_curve: List[EquityPoint]) -> np.ndarray:
        """计算收益率序列"""
        if len(equity_curve) < 2:
            return np.array([])
        
        equities = [float(point.equity) for point in equity_curve]
        returns = np.diff(equities) / equities[:-1]
        return returns
    
    @staticmethod
    def sharpe_ratio(equity_curve: List[EquityPoint], risk_free_rate: float = 0.02) -> float:
        """
        计算夏普比率
        
        Args:
            equity_curve: 权益曲线
            risk_free_rate: 无风险利率(年化)
        
        Returns:
            夏普比率
        """
        returns = PerformanceMetrics.calculate_returns(equity_curve)
        
        if len(returns) == 0:
            return 0.0
        
        # 计算年化收益率和波动率
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0.0
        
        # 假设每日数据,年化因子为sqrt(365)
        daily_rf = risk_free_rate / 365
        sharpe = (mean_return - daily_rf) / std_return * np.sqrt(365)
        
        return float(sharpe)
    
    @staticmethod
    def sortino_ratio(equity_curve: List[EquityPoint], risk_free_rate: float = 0.02) -> float:
        """
        计算索提诺比率(只考虑下行波动)
        
        Args:
            equity_curve: 权益曲线
            risk_free_rate: 无风险利率(年化)
        
        Returns:
            索提诺比率
        """
        returns = PerformanceMetrics.calculate_returns(equity_curve)
        
        if len(returns) == 0:
            return 0.0
        
        mean_return = np.mean(returns)
        
        # 只考虑负收益的标准差
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return float('inf') if mean_return > 0 else 0.0
        
        downside_std = np.std(downside_returns)
        if downside_std == 0:
            return 0.0
        
        daily_rf = risk_free_rate / 365
        sortino = (mean_return - daily_rf) / downside_std * np.sqrt(365)
        
        return float(sortino)
    
    @staticmethod
    def max_drawdown(equity_curve: List[EquityPoint]) -> Tuple[Decimal, int]:
        """
        计算最大回撤和持续时间
        
        Returns:
            (最大回撤百分比, 持续天数)
        """
        if len(equity_curve) < 2:
            return Decimal("0"), 0
        
        equities = [float(point.equity) for point in equity_curve]
        timestamps = [point.timestamp for point in equity_curve]
        
        max_dd = 0.0
        max_dd_duration = 0
        peak = equities[0]
        peak_time = timestamps[0]
        trough_time = timestamps[0]
        
        for i, equity in enumerate(equities):
            if equity > peak:
                # 新高点
                peak = equity
                peak_time = timestamps[i]
            else:
                # 计算回撤
                dd = (peak - equity) / peak
                if dd > max_dd:
                    max_dd = dd
                    trough_time = timestamps[i]
                    max_dd_duration = (trough_time - peak_time).days
        
        return Decimal(str(max_dd)), max_dd_duration
    
    @staticmethod
    def win_rate(trades: List[Trade]) -> float:
        """计算胜率"""
        if not trades:
            return 0.0
        
        profitable_trades = [t for t in trades if t.pnl and t.pnl > 0]
        return len(profitable_trades) / len(trades)
    
    @staticmethod
    def profit_factor(trades: List[Trade]) -> float:
        """
        计算盈亏比 (总盈利/总亏损)
        """
        if not trades:
            return 0.0
        
        total_profit = sum(float(t.pnl) for t in trades if t.pnl and t.pnl > 0)
        total_loss = abs(sum(float(t.pnl) for t in trades if t.pnl and t.pnl < 0))
        
        if total_loss == 0:
            return float('inf') if total_profit > 0 else 0.0
        
        return total_profit / total_loss
    
    @staticmethod
    def average_trade_pnl(trades: List[Trade], winning: bool = True) -> Decimal:
        """
        计算平均盈利/亏损
        
        Args:
            trades: 交易列表
            winning: True=计算盈利, False=计算亏损
        """
        if not trades:
            return Decimal("0")
        
        if winning:
            filtered = [t for t in trades if t.pnl and t.pnl > 0]
        else:
            filtered = [t for t in trades if t.pnl and t.pnl < 0]
        
        if not filtered:
            return Decimal("0")
        
        total = sum(t.pnl for t in filtered if t.pnl)
        return total / len(filtered)
    
    @staticmethod
    def largest_trade(trades: List[Trade], winning: bool = True) -> Decimal:
        """最大单笔盈利/亏损"""
        if not trades:
            return Decimal("0")
        
        if winning:
            filtered = [t.pnl for t in trades if t.pnl and t.pnl > 0]
            return max(filtered) if filtered else Decimal("0")
        else:
            filtered = [t.pnl for t in trades if t.pnl and t.pnl < 0]
            return min(filtered) if filtered else Decimal("0")
    
    @staticmethod
    def average_holding_period(trades: List[Trade], positions_history: List) -> float:
        """
        计算平均持仓时间(小时)
        
        注: 这里简化处理,实际需要跟踪开仓平仓配对
        """
        if len(trades) < 2:
            return 0.0
        
        # 简化计算: 假设相邻交易为开仓-平仓配对
        holding_periods = []
        for i in range(0, len(trades) - 1, 2):
            if i + 1 < len(trades):
                duration = (trades[i + 1].timestamp - trades[i].timestamp).total_seconds() / 3600
                holding_periods.append(duration)
        
        return np.mean(holding_periods) if holding_periods else 0.0
    
    @staticmethod
    def calculate_drawdown_curve(equity_curve: List[EquityPoint]) -> List[Decimal]:
        """计算回撤曲线"""
        if len(equity_curve) < 2:
            return [Decimal("0")] * len(equity_curve)
        
        equities = [float(point.equity) for point in equity_curve]
        drawdowns = []
        peak = equities[0]
        
        for equity in equities:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            drawdowns.append(Decimal(str(dd)))
        
        return drawdowns

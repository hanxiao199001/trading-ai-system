"""
改进的回测引擎 - 添加止盈止损功能
基于原 backtest/engine.py,增加风控机制
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Any
from collections import defaultdict

from core.types import Signal, SignalData, OrderSide, PositionSide
from strategies.base import StrategyBase
from risk.manager import RiskManager, RiskConfig
from backtest.types import (
    BacktestConfig, BacktestResult, Trade, Position, 
    EquityPoint, BacktestMode
)
from backtest.data_loader import DataLoader, KlineData
from backtest.metrics import PerformanceMetrics

logger = logging.getLogger(__name__)


class BacktestEngineWithStops:
    """带止盈止损的回测引擎"""
    
    def __init__(self, config: BacktestConfig, stop_loss: float = 0.02, take_profit: float = 0.03):
        """
        初始化回测引擎
        
        Args:
            config: 回测配置
            stop_loss: 止损百分比 (例如 0.02 = 2%)
            take_profit: 止盈百分比 (例如 0.03 = 3%)
        """
        self.config = config
        self.stop_loss = Decimal(str(stop_loss))
        self.take_profit = Decimal(str(take_profit))
        
        # 账户状态
        self.cash = config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.equity_curve: List[EquityPoint] = []
        self.trades: List[Trade] = []
        
        # 风控管理器
        risk_config = RiskConfig(
            max_position_size=config.max_position_size,
            max_positions=3,
            max_daily_loss=Decimal("0.05")
        )
        self.risk_manager = RiskManager(risk_config)
        
        # 数据
        self.klines: Dict[str, List[KlineData]] = {}
        
        logger.info(f"回测引擎初始化: 止损={stop_loss:.1%}, 止盈={take_profit:.1%}")
    
    def load_data(self, symbol: str, klines: List[KlineData]):
        """加载历史数据"""
        self.klines[symbol] = sorted(klines, key=lambda x: x.timestamp)
        logger.info(f"加载 {symbol} 数据: {len(klines)} 条K线")
    
    def run(self, strategy: StrategyBase) -> BacktestResult:
        """运行回测"""
        logger.info("开始回测...")
        start_time = datetime.now()
        
        # 初始化策略
        strategy.initialize(self.config.strategy_params)
        
        # 获取所有时间点
        all_timestamps = set()
        for klines in self.klines.values():
            all_timestamps.update(k.timestamp for k in klines)
        timestamps = sorted(all_timestamps)
        
        # 过滤时间范围
        timestamps = [
            t for t in timestamps 
            if self.config.start_time <= t <= self.config.end_time
        ]
        
        logger.info(f"回测时间点数: {len(timestamps)}")
        
        # 逐时间点回放
        for i, timestamp in enumerate(timestamps):
            if i % 100 == 0:
                progress = i / len(timestamps) * 100
                logger.debug(f"回测进度: {progress:.1f}%")
            
            # 获取当前市场数据
            current_data = self._get_market_data_at(timestamp)
            
            # 【关键改进】先检查止盈止损
            self._check_stop_loss_take_profit(current_data, timestamp)
            
            # 更新持仓盈亏
            self._update_positions(current_data)
            
            # 策略生成信号
            signals = strategy.generate_signals(current_data)
            
            # 处理信号
            for signal in signals:
                self._process_signal(signal, current_data[signal.symbol])
            
            # 记录权益曲线
            self._record_equity(timestamp)
        
        # 平掉所有持仓
        self._close_all_positions(timestamps[-1])
        
        # 生成回测结果
        result = self._generate_result()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"回测完成,耗时 {elapsed:.2f}秒")
        
        return result
    
    def _check_stop_loss_take_profit(self, current_data: Dict[str, KlineData], timestamp: datetime):
        """
        【核心改进】检查止盈止损
        """
        symbols_to_close = []
        
        for symbol, position in self.positions.items():
            if symbol not in current_data:
                continue
            
            current_price = current_data[symbol].close
            
            # 计算盈亏百分比
            if position.side == 'long':
                pnl_pct = (current_price - position.entry_price) / position.entry_price
            else:
                pnl_pct = (position.entry_price - current_price) / position.entry_price
            
            # 检查止损
            if pnl_pct <= -self.stop_loss:
                logger.debug(f"触发止损: {symbol} {position.side} 亏损 {pnl_pct:.2%}")
                symbols_to_close.append((symbol, current_price, timestamp, 'stop_loss'))
                continue
            
            # 检查止盈
            if pnl_pct >= self.take_profit:
                logger.debug(f"触发止盈: {symbol} {position.side} 盈利 {pnl_pct:.2%}")
                symbols_to_close.append((symbol, current_price, timestamp, 'take_profit'))
                continue
        
        # 执行平仓
        for symbol, price, ts, reason in symbols_to_close:
            self._close_position(symbol, price, ts, reason)
    
    def _get_market_data_at(self, timestamp: datetime) -> Dict[str, KlineData]:
        """获取指定时刻的市场数据"""
        data = {}
        for symbol, klines in self.klines.items():
            for kline in reversed(klines):
                if kline.timestamp <= timestamp:
                    data[symbol] = kline
                    break
        return data
    
    def _update_positions(self, current_data: Dict[str, KlineData]):
        """更新持仓未实现盈亏"""
        for symbol, position in self.positions.items():
            if symbol in current_data:
                current_price = current_data[symbol].close
                position.update_pnl(current_price)
    
    def _process_signal(self, signal: Signal, kline: KlineData):
        """处理交易信号"""
        symbol = signal.symbol
        
        # 风控检查
        check_result = self.risk_manager.check_signal(signal, self.cash + self._get_total_position_value())
        if not check_result.approved:
            logger.debug(f"信号被风控拒绝: {check_result.reason}")
            return
        
        # 计算交易价格(考虑滑点)
        if signal.side == OrderSide.BUY:
            price = kline.close * (1 + self.config.slippage)
        else:
            price = kline.close * (1 - self.config.slippage)
        
        # 检查是否有持仓
        if symbol in self.positions:
            # 平仓(反向信号)
            self._close_position(symbol, price, signal.timestamp, 'signal')
        else:
            # 开仓
            self._open_position(signal, price, kline)
    
    def _open_position(self, signal: Signal, price: Decimal, kline: KlineData):
        """开仓"""
        symbol = signal.symbol
        
        # 计算仓位大小
        position_value = self.cash * self.config.max_position_size
        quantity = position_value / price
        
        # 计算手续费
        fee = position_value * self.config.taker_fee
        
        # 检查资金
        total_cost = position_value + fee
        if total_cost > self.cash:
            logger.warning(f"资金不足: 需要 ${total_cost}, 可用 ${self.cash}")
            return
        
        # 扣除资金
        self.cash -= total_cost
        
        # 创建持仓
        side = 'long' if signal.side == OrderSide.BUY else 'short'
        position = Position(
            symbol=symbol,
            side=side,
            entry_price=price,
            quantity=quantity,
            entry_time=signal.timestamp
        )
        self.positions[symbol] = position
        
        # 记录交易
        trade = Trade(
            timestamp=signal.timestamp,
            symbol=symbol,
            side='buy' if signal.side == OrderSide.BUY else 'sell',
            price=price,
            quantity=quantity,
            fee=fee
        )
        self.trades.append(trade)
        
        logger.debug(f"开仓: {symbol} {side} @ ${price}, 数量: {quantity:.4f}")
    
    def _close_position(self, symbol: str, price: Decimal, timestamp: datetime, reason: str = 'signal'):
        """
        平仓
        
        Args:
            reason: 平仓原因 ('signal', 'stop_loss', 'take_profit')
        """
        if symbol not in self.positions:
            return
        
        position = self.positions[symbol]
        
        # 计算盈亏
        if position.side == 'long':
            pnl = (price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - price) * position.quantity
        
        # 计算手续费
        position_value = price * position.quantity
        fee = position_value * self.config.taker_fee
        
        # 更新资金
        self.cash += position_value - fee
        
        # 记录交易
        trade = Trade(
            timestamp=timestamp,
            symbol=symbol,
            side='sell' if position.side == 'long' else 'buy',
            price=price,
            quantity=position.quantity,
            fee=fee,
            pnl=pnl - fee  # 净盈亏
        )
        self.trades.append(trade)
        
        # 删除持仓
        del self.positions[symbol]
        
        logger.debug(f"平仓({reason}): {symbol} @ ${price}, 盈亏: ${pnl:.2f}")
    
    def _close_all_positions(self, timestamp: datetime):
        """平掉所有持仓"""
        symbols = list(self.positions.keys())
        for symbol in symbols:
            if symbol in self.klines:
                last_kline = self.klines[symbol][-1]
                self._close_position(symbol, last_kline.close, timestamp, 'end')
    
    def _get_total_position_value(self) -> Decimal:
        """获取持仓总价值"""
        total = Decimal("0")
        for symbol, position in self.positions.items():
            if symbol in self.klines:
                last_kline = self.klines[symbol][-1]
                value = position.quantity * last_kline.close
                total += value
        return total
    
    def _record_equity(self, timestamp: datetime):
        """记录权益曲线点"""
        position_value = self._get_total_position_value()
        equity = self.cash + position_value
        
        point = EquityPoint(
            timestamp=timestamp,
            equity=equity,
            cash=self.cash,
            position_value=position_value
        )
        self.equity_curve.append(point)
    
    def _generate_result(self) -> BacktestResult:
        """生成回测结果"""
        # 基本统计
        final_capital = self.cash
        total_pnl = final_capital - self.config.initial_capital
        total_return = total_pnl / self.config.initial_capital
        
        # 交易统计
        closed_trades = [t for t in self.trades if t.pnl is not None]
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl < 0]
        
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0.0
        
        # 盈亏统计
        avg_win = PerformanceMetrics.average_trade_pnl(closed_trades, winning=True)
        avg_loss = PerformanceMetrics.average_trade_pnl(closed_trades, winning=False)
        largest_win = PerformanceMetrics.largest_trade(closed_trades, winning=True)
        largest_loss = PerformanceMetrics.largest_trade(closed_trades, winning=False)
        profit_factor = PerformanceMetrics.profit_factor(closed_trades)
        
        # 风险指标
        sharpe = PerformanceMetrics.sharpe_ratio(self.equity_curve)
        sortino = PerformanceMetrics.sortino_ratio(self.equity_curve)
        max_dd, max_dd_duration = PerformanceMetrics.max_drawdown(self.equity_curve)
        
        # 费用统计
        total_fees = sum(t.fee for t in self.trades)
        avg_holding = PerformanceMetrics.average_holding_period(self.trades, [])
        
        # 时间统计
        duration_days = (self.config.end_time - self.config.start_time).days
        
        result = BacktestResult(
            config=self.config,
            start_time=self.config.start_time,
            end_time=self.config.end_time,
            duration_days=duration_days,
            initial_capital=self.config.initial_capital,
            final_capital=final_capital,
            total_pnl=total_pnl,
            total_return=total_return,
            total_trades=len(closed_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            max_drawdown=max_dd,
            max_drawdown_duration_days=max_dd_duration,
            trades=self.trades,
            equity_curve=self.equity_curve,
            total_fees=total_fees,
            avg_holding_period_hours=avg_holding
        )
        
        return result

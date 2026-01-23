"""
回测数据类型定义
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Optional, Any
from enum import Enum


class BacktestMode(Enum):
    """回测模式"""
    FULL = "full"  # 完整回测
    FAST = "fast"  # 快速回测(跳过部分计算)
    DEBUG = "debug"  # 调试模式(详细日志)


@dataclass
class BacktestConfig:
    """回测配置"""
    # 时间范围
    start_time: datetime
    end_time: datetime
    
    # 初始资金
    initial_capital: Decimal = Decimal("100000")
    
    # 交易设置
    maker_fee: Decimal = Decimal("0.0002")  # 0.02%
    taker_fee: Decimal = Decimal("0.0005")  # 0.05%
    slippage: Decimal = Decimal("0.0001")   # 0.01% 滑点
    
    # 回测模式
    mode: BacktestMode = BacktestMode.FULL
    
    # 数据源
    data_source: str = "binance"  # binance, okx, csv
    symbols: List[str] = field(default_factory=lambda: ["BTC-USDT-SWAP"])
    
    # 策略参数
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    
    # 风控参数
    max_position_size: Decimal = Decimal("0.3")  # 最大30%仓位
    stop_loss_pct: Optional[Decimal] = None
    take_profit_pct: Optional[Decimal] = None


@dataclass
class Trade:
    """交易记录"""
    timestamp: datetime
    symbol: str
    side: str  # 'buy' or 'sell'
    price: Decimal
    quantity: Decimal
    fee: Decimal
    pnl: Optional[Decimal] = None  # 平仓时的盈亏
    
    @property
    def value(self) -> Decimal:
        """交易金额"""
        return self.price * self.quantity


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    side: str  # 'long' or 'short'
    entry_price: Decimal
    quantity: Decimal
    entry_time: datetime
    unrealized_pnl: Decimal = Decimal("0")
    
    def update_pnl(self, current_price: Decimal):
        """更新未实现盈亏"""
        if self.side == 'long':
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity


@dataclass
class EquityPoint:
    """权益曲线点"""
    timestamp: datetime
    equity: Decimal
    cash: Decimal
    position_value: Decimal
    drawdown: Decimal = Decimal("0")


@dataclass
class BacktestResult:
    """回测结果"""
    # 基本信息
    config: BacktestConfig
    start_time: datetime
    end_time: datetime
    duration_days: int
    
    # 资金情况
    initial_capital: Decimal
    final_capital: Decimal
    total_pnl: Decimal
    total_return: Decimal  # 总收益率
    
    # 交易统计
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    
    # 盈亏统计
    avg_win: Decimal
    avg_loss: Decimal
    largest_win: Decimal
    largest_loss: Decimal
    profit_factor: float  # 盈亏比
    
    # 风险指标
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: Decimal
    max_drawdown_duration_days: int
    
    # 详细数据
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[EquityPoint] = field(default_factory=list)
    
    # 其他指标
    total_fees: Decimal = Decimal("0")
    avg_holding_period_hours: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'summary': {
                'initial_capital': float(self.initial_capital),
                'final_capital': float(self.final_capital),
                'total_pnl': float(self.total_pnl),
                'total_return': float(self.total_return),
                'sharpe_ratio': self.sharpe_ratio,
                'max_drawdown': float(self.max_drawdown),
            },
            'trades': {
                'total': self.total_trades,
                'winning': self.winning_trades,
                'losing': self.losing_trades,
                'win_rate': self.win_rate,
            },
            'risk': {
                'sharpe_ratio': self.sharpe_ratio,
                'sortino_ratio': self.sortino_ratio,
                'max_drawdown': float(self.max_drawdown),
                'profit_factor': self.profit_factor,
            }
        }
    
    def __str__(self) -> str:
        """格式化输出"""
        return f"""
回测结果摘要
{'='*50}
时间范围: {self.start_time.date()} 至 {self.end_time.date()} ({self.duration_days}天)
初始资金: ${self.initial_capital:,.2f}
最终资金: ${self.final_capital:,.2f}
总收益: ${self.total_pnl:,.2f} ({self.total_return:.2%})

交易统计:
  总交易次数: {self.total_trades}
  胜率: {self.win_rate:.2%} ({self.winning_trades}胜 / {self.losing_trades}败)
  平均盈利: ${self.avg_win:,.2f}
  平均亏损: ${self.avg_loss:,.2f}
  盈亏比: {self.profit_factor:.2f}

风险指标:
  夏普比率: {self.sharpe_ratio:.2f}
  索提诺比率: {self.sortino_ratio:.2f}
  最大回撤: {self.max_drawdown:.2%}
  最大回撤持续: {self.max_drawdown_duration_days}天

费用统计:
  总手续费: ${self.total_fees:,.2f}
  平均持仓时间: {self.avg_holding_period_hours:.1f}小时
{'='*50}
"""

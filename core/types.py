"""
统一数据类型定义
所有模块使用统一的数据结构，确保跨交易所兼容性
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any


class Signal(Enum):
    """交易信号"""
    LONG = "long"           # 做多
    SHORT = "short"         # 做空
    CLOSE_LONG = "close_long"   # 平多
    CLOSE_SHORT = "close_short" # 平空
    HOLD = "hold"           # 持仓观望
    NONE = "none"           # 无信号


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"       # 市价单
    LIMIT = "limit"         # 限价单
    STOP_LOSS = "stop_loss" # 止损单
    TAKE_PROFIT = "take_profit"  # 止盈单


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"
    NONE = "none"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class MarketData:
    """市场数据"""
    symbol: str
    exchange: str
    timestamp: datetime
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: Optional[float] = None
    funding_rate: Optional[float] = None
    next_funding_time: Optional[datetime] = None
    open_interest: Optional[float] = None
    index_price: Optional[float] = None
    mark_price: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.timestamp, str):
            self.timestamp = datetime.fromisoformat(self.timestamp)


@dataclass
class Order:
    """订单"""
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None      # 限价单价格
    stop_price: Optional[float] = None # 止损/止盈触发价
    leverage: int = 1
    reduce_only: bool = False
    client_order_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResult:
    """订单执行结果"""
    success: bool
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: float = 0.0
    avg_price: float = 0.0
    fee: float = 0.0
    fee_currency: str = "USDT"
    timestamp: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    exchange: str
    side: PositionSide
    quantity: float
    entry_price: float
    mark_price: float = 0.0
    liquidation_price: Optional[float] = None
    leverage: int = 1
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    margin: float = 0.0
    timestamp: Optional[datetime] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.quantity > 0 and self.side != PositionSide.NONE


@dataclass
class Fill:
    """成交记录"""
    order_id: str
    symbol: str
    side: OrderSide
    price: float
    quantity: float
    fee: float
    fee_currency: str
    timestamp: datetime
    trade_id: Optional[str] = None
    is_maker: bool = False


@dataclass
class Trade:
    """完整交易记录（开仓到平仓）"""
    trade_id: str
    symbol: str
    exchange: str
    side: PositionSide          # 交易方向
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: datetime
    exit_time: datetime
    pnl: float                  # 盈亏金额
    pnl_pct: float             # 盈亏百分比
    fee_total: float           # 总手续费
    strategy: str              # 策略名称
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """持仓时长（秒）"""
        return (self.exit_time - self.timestamp).total_seconds()

    @property
    def net_pnl(self) -> float:
        """扣除手续费后的净盈亏"""
        return self.pnl - self.fee_total

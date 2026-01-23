"""
统一数据类型定义
所有模块使用统一的数据结构，确保跨交易所兼容性
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from decimal import Decimal


class Signal(Enum):
    """交易信号"""
    LONG = "long"
    SHORT = "short"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"
    HOLD = "hold"
    NONE = "none"


@dataclass
class SignalData:
    """交易信号数据对象"""
    strategy_name: str
    symbol: str
    side: 'OrderSide'
    timestamp: datetime
    confidence: float = 1.0
    suggested_size: Optional[Decimal] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"
    SHORT = "short"
    NONE = "none"

@dataclass
class MarketData:
    """市场数据"""
    symbol: str
    timestamp: datetime
    last_price: Decimal
    volume: Decimal
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    high_24h: Optional[Decimal] = None
    low_24h: Optional[Decimal] = None
    funding_rate: Optional[Decimal] = None
    open_interest: Optional[Decimal] = None


@dataclass
class Order:
    """订单"""
    order_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: Decimal
    price: Optional[Decimal]
    status: OrderStatus
    timestamp: datetime
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    fee: Decimal = Decimal("0")
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Position:
    """持仓"""
    symbol: str
    side: PositionSide
    quantity: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal = Decimal("0")
    leverage: Decimal = Decimal("1")
    margin: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Account:
    """账户信息"""
    total_balance: Decimal
    available_balance: Decimal
    margin_balance: Decimal
    unrealized_pnl: Decimal
    timestamp: datetime
    positions: Dict[str, Position] = field(default_factory=dict)


@dataclass
class Fill:
    """成交回报"""
    order_id: str
    symbol: str
    side: OrderSide
    price: Decimal
    quantity: Decimal
    timestamp: datetime
    fee: Decimal = Decimal("0")
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResult:
    """订单结果"""
    success: bool
    order_id: str = ""
    message: str = ""
    filled_price: Optional[Decimal] = None
    filled_quantity: Optional[Decimal] = None
    fee: Decimal = Decimal("0")
    timestamp: datetime = field(default_factory=datetime.now)

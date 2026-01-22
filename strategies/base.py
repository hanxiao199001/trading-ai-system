"""
策略抽象基类
所有交易策略必须继承此类并实现核心方法
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging

from core.types import Signal, MarketData, Position, Fill, PositionSide

if TYPE_CHECKING:
    from risk.manager import RiskManager

logger = logging.getLogger(__name__)


@dataclass
class StrategyState:
    """策略状态"""
    position: PositionSide = PositionSide.NONE
    entry_price: float = 0.0
    entry_time: Optional[datetime] = None
    quantity: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    trade_count: int = 0
    win_count: int = 0
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def win_rate(self) -> float:
        """胜率"""
        if self.trade_count == 0:
            return 0.0
        return self.win_count / self.trade_count

    @property
    def has_position(self) -> bool:
        """是否持仓"""
        return self.position != PositionSide.NONE and self.quantity > 0


class StrategyBase(ABC):
    """
    策略抽象基类

    子类需实现:
    - name: 策略名称
    - generate_signal: 生成交易信号
    - on_fill: 成交回调（可选）
    """

    def __init__(
        self,
        config: Dict[str, Any],
        risk_manager: Optional["RiskManager"] = None,
    ):
        self.config = config
        self.risk_manager = risk_manager
        self.state = StrategyState()
        self._enabled = True
        self._last_signal: Optional[Signal] = None
        self._last_signal_time: Optional[datetime] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称"""
        pass

    @property
    def enabled(self) -> bool:
        """策略是否启用"""
        return self._enabled

    def enable(self) -> None:
        """启用策略"""
        self._enabled = True
        logger.info(f"Strategy {self.name} enabled")

    def disable(self) -> None:
        """禁用策略"""
        self._enabled = False
        logger.info(f"Strategy {self.name} disabled")

    # ============ 核心方法 ============

    @abstractmethod
    def generate_signal(self, market_data: MarketData) -> Signal:
        """
        生成交易信号

        Args:
            market_data: 市场数据

        Returns:
            Signal: 交易信号
        """
        pass

    def on_fill(self, fill: Fill) -> None:
        """
        成交回调（可选覆盖）

        Args:
            fill: 成交记录
        """
        pass

    def on_position_opened(self, position: Position) -> None:
        """
        开仓回调（可选覆盖）

        Args:
            position: 持仓信息
        """
        self.state.position = position.side
        self.state.entry_price = position.entry_price
        self.state.entry_time = datetime.now()
        self.state.quantity = position.quantity
        logger.info(f"[{self.name}] Position opened: {position.side.value} @ {position.entry_price}")

    def on_position_closed(self, pnl: float, pnl_pct: float) -> None:
        """
        平仓回调（可选覆盖）

        Args:
            pnl: 盈亏金额
            pnl_pct: 盈亏百分比
        """
        self.state.realized_pnl += pnl
        self.state.trade_count += 1
        if pnl > 0:
            self.state.win_count += 1

        logger.info(f"[{self.name}] Position closed: PnL={pnl:.2f} ({pnl_pct:.2%})")

        # 重置持仓状态
        self.state.position = PositionSide.NONE
        self.state.entry_price = 0.0
        self.state.entry_time = None
        self.state.quantity = 0.0
        self.state.unrealized_pnl = 0.0

    # ============ 辅助方法 ============

    def update_unrealized_pnl(self, current_price: float) -> float:
        """
        更新未实现盈亏

        Args:
            current_price: 当前价格

        Returns:
            float: 未实现盈亏百分比
        """
        if not self.state.has_position or self.state.entry_price == 0:
            self.state.unrealized_pnl = 0.0
            return 0.0

        if self.state.position == PositionSide.LONG:
            pnl_pct = (current_price - self.state.entry_price) / self.state.entry_price
        else:  # SHORT
            pnl_pct = (self.state.entry_price - current_price) / self.state.entry_price

        self.state.unrealized_pnl = pnl_pct
        return pnl_pct

    def should_stop_loss(self, current_price: float) -> bool:
        """检查是否触发止损"""
        if self.risk_manager is None:
            return False
        pnl_pct = self.update_unrealized_pnl(current_price)
        return pnl_pct <= -self.risk_manager.stop_loss_pct

    def should_take_profit(self, current_price: float) -> bool:
        """检查是否触发止盈"""
        if self.risk_manager is None:
            return False
        pnl_pct = self.update_unrealized_pnl(current_price)
        return pnl_pct >= self.risk_manager.take_profit_pct

    def get_position_size(self, balance: float, price: float) -> float:
        """
        计算建仓数量

        Args:
            balance: 可用余额
            price: 当前价格

        Returns:
            float: 建议持仓数量
        """
        if self.risk_manager is None:
            return 0.0
        return self.risk_manager.calculate_position_size(balance, price)

    # ============ 状态管理 ============

    def reset(self) -> None:
        """重置策略状态"""
        self.state = StrategyState()
        self._last_signal = None
        self._last_signal_time = None
        logger.info(f"Strategy {self.name} reset")

    def get_state(self) -> Dict[str, Any]:
        """获取策略状态（用于持久化）"""
        return {
            "name": self.name,
            "enabled": self._enabled,
            "position": self.state.position.value,
            "entry_price": self.state.entry_price,
            "entry_time": self.state.entry_time.isoformat() if self.state.entry_time else None,
            "quantity": self.state.quantity,
            "realized_pnl": self.state.realized_pnl,
            "trade_count": self.state.trade_count,
            "win_count": self.state.win_count,
            "config": self.config,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """加载策略状态"""
        self._enabled = state.get("enabled", True)
        self.state.position = PositionSide(state.get("position", "none"))
        self.state.entry_price = state.get("entry_price", 0.0)
        entry_time = state.get("entry_time")
        self.state.entry_time = datetime.fromisoformat(entry_time) if entry_time else None
        self.state.quantity = state.get("quantity", 0.0)
        self.state.realized_pnl = state.get("realized_pnl", 0.0)
        self.state.trade_count = state.get("trade_count", 0)
        self.state.win_count = state.get("win_count", 0)
        logger.info(f"Strategy {self.name} state loaded")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name}, enabled={self._enabled})"

"""
风险管理器
基于原okx-funding-bot的风控逻辑，增强为通用风控模块
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

from core.types import Position, Signal, PositionSide
from core.event_bus import EventBus, EventType, get_event_bus
from decimal import Decimal


@dataclass
class RiskConfig:
    """风控配置"""
    max_position_size: Decimal = Decimal("0.3")
    max_positions: int = 3
    max_daily_loss: Decimal = Decimal("0.05")
    max_leverage: Decimal = Decimal("3")


@dataclass
class RiskCheckResult:
    """风控检查结果"""
    approved: bool
    reason: str = ""


logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskAlert:
    """风险告警"""
    level: RiskLevel
    message: str
    timestamp: datetime
    data: Dict[str, Any]


class RiskManager:
    """
    风险管理器

    核心功能:
    1. 仓位计算 - 基于资金比例计算开仓数量
    2. 止盈止损 - 监控持仓盈亏，触发平仓信号
    3. 杠杆控制 - 限制最大杠杆倍数
    4. 每日亏损限制 - 当日亏损达到阈值时停止交易
    5. 最大持仓限制 - 限制同时持有的仓位数量

    默认参数来自原项目:
    - 止损: -2.0%
    - 止盈: +1.5%
    - 单笔仓位: 30%
    - 杠杆: 1x
    """

    def __init__(
        self,
        stop_loss_pct: float = 0.02,       # 止损百分比 (2%)
        take_profit_pct: float = 0.015,    # 止盈百分比 (1.5%)
        position_size_pct: float = 0.30,   # 单笔仓位占比 (30%)
        max_leverage: int = 1,             # 最大杠杆
        max_positions: int = 3,            # 最大同时持仓数
        daily_loss_limit_pct: float = 0.05,  # 每日最大亏损 (5%)
        min_order_value: float = 10.0,     # 最小订单价值 (USDT)
        event_bus: Optional[EventBus] = None,
    ):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.position_size_pct = position_size_pct
        self.max_leverage = max_leverage
        self.max_positions = max_positions
        self.daily_loss_limit_pct = daily_loss_limit_pct
        self.min_order_value = min_order_value

        self._event_bus = event_bus or get_event_bus()
        self._daily_pnl: float = 0.0
        self._daily_reset_time: datetime = datetime.now().replace(hour=0, minute=0, second=0)
        self._alerts: List[RiskAlert] = []
        self._trading_enabled = True
        self._positions: Dict[str, Position] = {}

    # ============ 仓位计算 ============

    def calculate_position_size(
        self,
        available_balance: float,
        price: float,
        leverage: int = 1,
        custom_size_pct: Optional[float] = None,
    ) -> float:
        """
        计算建仓数量

        公式: (余额 × 仓位比例 × 杠杆) / 价格

        Args:
            available_balance: 可用余额
            price: 当前价格
            leverage: 杠杆倍数
            custom_size_pct: 自定义仓位比例（覆盖默认值）

        Returns:
            float: 建议开仓数量
        """
        size_pct = custom_size_pct or self.position_size_pct
        leverage = min(leverage, self.max_leverage)  # 限制杠杆

        position_value = available_balance * size_pct * leverage
        quantity = position_value / price

        # 检查最小订单价值
        if position_value < self.min_order_value:
            logger.warning(f"Position value {position_value:.2f} below minimum {self.min_order_value}")
            return 0.0

        return quantity

    def calculate_position_value(
        self,
        quantity: float,
        price: float,
    ) -> float:
        """计算仓位价值"""
        return quantity * price

    # ============ 止盈止损检查 ============

    def check_stop_loss(self, position: Position) -> bool:
        """
        检查是否触发止损

        Args:
            position: 持仓信息

        Returns:
            bool: 是否需要止损平仓
        """
        if not position.is_open:
            return False

        pnl_pct = self._calculate_pnl_pct(position)

        if pnl_pct <= -self.stop_loss_pct:
            self._emit_alert(
                RiskLevel.HIGH,
                f"Stop loss triggered for {position.symbol}: {pnl_pct:.2%}",
                {"position": position, "pnl_pct": pnl_pct}
            )
            self._event_bus.emit(
                EventType.STOP_LOSS_TRIGGERED,
                {"position": position, "pnl_pct": pnl_pct},
                source="risk_manager"
            )
            return True

        return False

    def check_take_profit(self, position: Position) -> bool:
        """
        检查是否触发止盈

        Args:
            position: 持仓信息

        Returns:
            bool: 是否需要止盈平仓
        """
        if not position.is_open:
            return False

        pnl_pct = self._calculate_pnl_pct(position)

        if pnl_pct >= self.take_profit_pct:
            self._emit_alert(
                RiskLevel.LOW,
                f"Take profit triggered for {position.symbol}: {pnl_pct:.2%}",
                {"position": position, "pnl_pct": pnl_pct}
            )
            self._event_bus.emit(
                EventType.TAKE_PROFIT_TRIGGERED,
                {"position": position, "pnl_pct": pnl_pct},
                source="risk_manager"
            )
            return True

        return False

    def check_position(self, position: Position) -> Optional[Signal]:
        """
        综合检查持仓风险

        Args:
            position: 持仓信息

        Returns:
            Signal: 如需平仓返回对应信号，否则返回None
        """
        if self.check_stop_loss(position):
            if position.side == PositionSide.LONG:
                return Signal.CLOSE_LONG
            else:
                return Signal.CLOSE_SHORT

        if self.check_take_profit(position):
            if position.side == PositionSide.LONG:
                return Signal.CLOSE_LONG
            else:
                return Signal.CLOSE_SHORT

        return None

    # ============ 每日亏损控制 ============

    def update_daily_pnl(self, pnl: float) -> None:
        """更新每日盈亏"""
        self._check_daily_reset()
        self._daily_pnl += pnl

        if self._daily_pnl < 0:
            loss_pct = abs(self._daily_pnl)  # 需要除以初始资金，这里简化处理
            if loss_pct >= self.daily_loss_limit_pct:
                self._trading_enabled = False
                self._emit_alert(
                    RiskLevel.CRITICAL,
                    f"Daily loss limit reached: {loss_pct:.2%}",
                    {"daily_pnl": self._daily_pnl}
                )

    def _check_daily_reset(self) -> None:
        """检查是否需要重置每日统计"""
        now = datetime.now()
        if now.date() > self._daily_reset_time.date():
            self._daily_pnl = 0.0
            self._daily_reset_time = now.replace(hour=0, minute=0, second=0)
            self._trading_enabled = True  # 新的一天重新启用交易
            logger.info("Daily risk stats reset")

    # ============ 持仓限制 ============

    def can_open_position(self) -> bool:
        """检查是否可以开新仓位"""
        if not self._trading_enabled:
            logger.warning("Trading disabled due to risk limits")
            return False

        if len(self._positions) >= self.max_positions:
            logger.warning(f"Max positions ({self.max_positions}) reached")
            return False

        return True

    def register_position(self, position: Position) -> None:
        """注册新持仓"""
        self._positions[position.symbol] = position

    def unregister_position(self, symbol: str) -> None:
        """注销持仓"""
        if symbol in self._positions:
            del self._positions[symbol]

    # ============ 信号验证 ============

    def check_signal(self, signal, total_value: float):
        """
        检查信号是否通过风控
        
        Args:
            signal: 交易信号
            total_value: 账户总价值
        
        Returns:
            RiskCheckResult: 检查结果
        """
        # 检查交易是否启用
        if not self._trading_enabled:
            return RiskCheckResult(approved=False, reason="Trading disabled")
        
        # 检查是否可以开仓
        if not self.can_open_position():
            return RiskCheckResult(approved=False, reason="Max positions reached")
        
        # 检查每日亏损
        if self._daily_pnl >= self.daily_loss_limit_pct * float(total_value):
            return RiskCheckResult(approved=False, reason="Daily loss limit reached")
        
        return RiskCheckResult(approved=True, reason="OK")


    def validate_signal(
        self,
        signal: Signal,
        symbol: str,
        balance: float,
        price: float,
    ) -> bool:
        """
        验证交易信号是否符合风控要求

        Args:
            signal: 交易信号
            symbol: 交易对
            balance: 可用余额
            price: 当前价格

        Returns:
            bool: 信号是否有效
        """
        # 检查交易是否启用
        if not self._trading_enabled:
            logger.warning("Trading disabled, signal rejected")
            return False

        # 开仓信号检查
        if signal in (Signal.LONG, Signal.SHORT):
            if not self.can_open_position():
                return False

            # 检查是否有足够资金
            position_size = self.calculate_position_size(balance, price)
            if position_size <= 0:
                logger.warning("Insufficient balance for position")
                return False

        return True

    # ============ 工具方法 ============

    def _calculate_pnl_pct(self, position: Position) -> float:
        """计算持仓盈亏百分比"""
        if position.entry_price == 0:
            return 0.0

        if position.side == PositionSide.LONG:
            return (position.mark_price - position.entry_price) / position.entry_price
        else:  # SHORT
            return (position.entry_price - position.mark_price) / position.entry_price

    def _emit_alert(self, level: RiskLevel, message: str, data: Dict[str, Any]) -> None:
        """发送风险告警"""
        alert = RiskAlert(
            level=level,
            message=message,
            timestamp=datetime.now(),
            data=data
        )
        self._alerts.append(alert)

        self._event_bus.emit(
            EventType.RISK_ALERT,
            alert,
            source="risk_manager"
        )
        logger.warning(f"[RISK ALERT - {level.value.upper()}] {message}")

    def get_alerts(self, level: Optional[RiskLevel] = None, limit: int = 50) -> List[RiskAlert]:
        """获取风险告警"""
        alerts = self._alerts
        if level:
            alerts = [a for a in alerts if a.level == level]
        return alerts[-limit:]

    def get_status(self) -> Dict[str, Any]:
        """获取风控状态"""
        return {
            "trading_enabled": self._trading_enabled,
            "daily_pnl": self._daily_pnl,
            "position_count": len(self._positions),
            "max_positions": self.max_positions,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "position_size_pct": self.position_size_pct,
            "max_leverage": self.max_leverage,
        }

    def __repr__(self) -> str:
        return (
            f"RiskManager(stop_loss={self.stop_loss_pct:.1%}, "
            f"take_profit={self.take_profit_pct:.1%}, "
            f"position_size={self.position_size_pct:.0%})"
        )

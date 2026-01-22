"""
资金费率套利策略
迁移自okx-funding-bot/funding_strategy.py

策略逻辑:
- 当资金费率极高时做空（收取多头支付的费用）
- 当资金费率极低时做多（收取空头支付的费用）
- 费率回归中性时平仓获利

原项目参数:
- 做空阈值: 0.5% (费率 > 0.5% 时做空)
- 做多阈值: -0.3% (费率 < -0.3% 时做多)
- 平仓阈值: ±0.1% (费率回归中性时平仓)
"""
from datetime import datetime
from typing import Any, Dict, Optional
import logging

from strategies.base import StrategyBase
from core.types import Signal, MarketData, Position, PositionSide
from risk.manager import RiskManager

logger = logging.getLogger(__name__)


class FundingRateStrategy(StrategyBase):
    """
    资金费率套利策略

    参数:
        short_threshold: 做空阈值 (默认0.5%)
        long_threshold: 做多阈值 (默认-0.3%)
        exit_threshold: 平仓阈值 (默认0.1%)
        price_profit_exit: 价格盈利平仓阈值 (默认1%)
    """

    DEFAULT_CONFIG = {
        "short_threshold": 0.005,    # 0.5% - 做空阈值
        "long_threshold": -0.003,    # -0.3% - 做多阈值
        "exit_threshold": 0.001,     # 0.1% - 费率回归平仓阈值
        "price_profit_exit": 0.01,   # 1% - 价格盈利平仓
    }

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        risk_manager: Optional[RiskManager] = None,
    ):
        # 合并默认配置和用户配置
        merged_config = {**self.DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config, risk_manager)

        # 策略参数
        self.short_threshold = self.config["short_threshold"]
        self.long_threshold = self.config["long_threshold"]
        self.exit_threshold = self.config["exit_threshold"]
        self.price_profit_exit = self.config["price_profit_exit"]

        # 记录上次信号
        self._last_funding_rate: Optional[float] = None

    @property
    def name(self) -> str:
        return "FundingRateArbitrage"

    def generate_signal(self, market_data: MarketData) -> Signal:
        """
        生成交易信号

        逻辑:
        1. 无仓位时:
           - 费率 > short_threshold → 做空
           - 费率 < long_threshold → 做多

        2. 持多仓时:
           - 费率回归中性 (> -exit_threshold) → 平仓
           - 费率反向突破 (> short_threshold) → 平仓（止损）
           - 触发风控止盈止损 → 平仓

        3. 持空仓时:
           - 费率回归中性 (< exit_threshold) → 平仓
           - 费率反向突破 (< long_threshold) → 平仓（止损）
           - 价格盈利超过阈值 → 平仓（止盈）
           - 触发风控止盈止损 → 平仓
        """
        if not self.enabled:
            return Signal.NONE

        funding_rate = market_data.funding_rate
        if funding_rate is None:
            logger.warning("No funding rate data available")
            return Signal.NONE

        current_price = market_data.price
        self._last_funding_rate = funding_rate

        # 更新未实现盈亏
        self.update_unrealized_pnl(current_price)

        # ========== 无持仓：寻找入场机会 ==========
        if not self.state.has_position:
            if funding_rate > self.short_threshold:
                logger.info(
                    f"[{self.name}] SHORT signal: funding_rate={funding_rate:.4%} > {self.short_threshold:.4%}"
                )
                return Signal.SHORT

            elif funding_rate < self.long_threshold:
                logger.info(
                    f"[{self.name}] LONG signal: funding_rate={funding_rate:.4%} < {self.long_threshold:.4%}"
                )
                return Signal.LONG

            return Signal.NONE

        # ========== 持多仓：寻找平仓机会 ==========
        if self.state.position == PositionSide.LONG:
            # 风控检查
            if self.should_stop_loss(current_price):
                logger.info(f"[{self.name}] CLOSE_LONG: stop loss triggered")
                return Signal.CLOSE_LONG

            if self.should_take_profit(current_price):
                logger.info(f"[{self.name}] CLOSE_LONG: take profit triggered")
                return Signal.CLOSE_LONG

            # 费率回归中性
            if funding_rate > -self.exit_threshold:
                logger.info(
                    f"[{self.name}] CLOSE_LONG: funding rate normalized ({funding_rate:.4%})"
                )
                return Signal.CLOSE_LONG

            # 费率反向突破（止损）
            if funding_rate > self.short_threshold:
                logger.info(
                    f"[{self.name}] CLOSE_LONG: funding rate reversed ({funding_rate:.4%})"
                )
                return Signal.CLOSE_LONG

            return Signal.HOLD

        # ========== 持空仓：寻找平仓机会 ==========
        if self.state.position == PositionSide.SHORT:
            # 风控检查
            if self.should_stop_loss(current_price):
                logger.info(f"[{self.name}] CLOSE_SHORT: stop loss triggered")
                return Signal.CLOSE_SHORT

            if self.should_take_profit(current_price):
                logger.info(f"[{self.name}] CLOSE_SHORT: take profit triggered")
                return Signal.CLOSE_SHORT

            # 价格盈利超过阈值
            pnl_pct = self.state.unrealized_pnl
            if pnl_pct >= self.price_profit_exit:
                logger.info(
                    f"[{self.name}] CLOSE_SHORT: price profit ({pnl_pct:.2%}) >= {self.price_profit_exit:.2%}"
                )
                return Signal.CLOSE_SHORT

            # 费率回归中性
            if funding_rate < self.exit_threshold:
                logger.info(
                    f"[{self.name}] CLOSE_SHORT: funding rate normalized ({funding_rate:.4%})"
                )
                return Signal.CLOSE_SHORT

            # 费率反向突破（止损）
            if funding_rate < self.long_threshold:
                logger.info(
                    f"[{self.name}] CLOSE_SHORT: funding rate reversed ({funding_rate:.4%})"
                )
                return Signal.CLOSE_SHORT

            return Signal.HOLD

        return Signal.NONE

    def get_state(self) -> Dict[str, Any]:
        """获取策略状态"""
        state = super().get_state()
        state.update({
            "last_funding_rate": self._last_funding_rate,
            "thresholds": {
                "short": self.short_threshold,
                "long": self.long_threshold,
                "exit": self.exit_threshold,
                "price_profit": self.price_profit_exit,
            }
        })
        return state

    def __repr__(self) -> str:
        return (
            f"FundingRateStrategy("
            f"short={self.short_threshold:.2%}, "
            f"long={self.long_threshold:.2%}, "
            f"exit={self.exit_threshold:.2%})"
        )

"""
交易引擎
负责协调数据、策略、风控和交易所之间的交互
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
import logging

from core.types import Signal, MarketData, OrderSide, PositionSide
from core.event_bus import EventBus, EventType, get_event_bus
from exchanges.base import ExchangeBase
from strategies.base import StrategyBase
from risk.manager import RiskManager

logger = logging.getLogger(__name__)


class TradingEngine:
    """
    交易引擎

    职责:
    1. 管理多个交易所连接
    2. 运行多个策略
    3. 协调风控检查
    4. 执行交易指令
    """

    def __init__(
        self,
        risk_manager: Optional[RiskManager] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.risk_manager = risk_manager or RiskManager()
        self.event_bus = event_bus or get_event_bus()

        self._exchanges: Dict[str, ExchangeBase] = {}
        self._strategies: Dict[str, StrategyBase] = {}
        self._running = False
        self._tasks: List[asyncio.Task] = []

    def register_exchange(self, exchange: ExchangeBase) -> None:
        """注册交易所"""
        self._exchanges[exchange.name.lower()] = exchange
        logger.info(f"Exchange registered: {exchange.name}")

    def register_strategy(
        self,
        strategy: StrategyBase,
        exchange: str,
        symbols: List[str],
    ) -> None:
        """
        注册策略

        Args:
            strategy: 策略实例
            exchange: 使用的交易所名称
            symbols: 交易的标的列表
        """
        key = f"{strategy.name}:{exchange}"
        self._strategies[key] = {
            "strategy": strategy,
            "exchange": exchange.lower(),
            "symbols": symbols,
        }
        logger.info(f"Strategy registered: {strategy.name} on {exchange} for {symbols}")

    async def start(self, interval: int = 300) -> None:
        """
        启动交易引擎

        Args:
            interval: 策略执行间隔（秒）
        """
        logger.info("Starting trading engine...")
        self._running = True

        # 连接所有交易所
        for name, exchange in self._exchanges.items():
            await exchange.connect()

        # 发布启动事件
        self.event_bus.emit(
            EventType.SYSTEM_START,
            {"timestamp": datetime.now()},
            source="engine"
        )

        # 启动主循环
        try:
            while self._running:
                await self._run_cycle()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Engine stopped by cancellation")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """停止交易引擎"""
        logger.info("Stopping trading engine...")
        self._running = False

        # 取消所有任务
        for task in self._tasks:
            task.cancel()

        # 断开所有交易所连接
        for exchange in self._exchanges.values():
            await exchange.disconnect()

        # 发布停止事件
        self.event_bus.emit(
            EventType.SYSTEM_STOP,
            {"timestamp": datetime.now()},
            source="engine"
        )

    async def _run_cycle(self) -> None:
        """执行一个交易周期"""
        for key, config in self._strategies.items():
            strategy: StrategyBase = config["strategy"]
            exchange_name: str = config["exchange"]
            symbols: List[str] = config["symbols"]

            if not strategy.enabled:
                continue

            exchange = self._exchanges.get(exchange_name)
            if not exchange:
                logger.error(f"Exchange not found: {exchange_name}")
                continue

            for symbol in symbols:
                try:
                    await self._process_symbol(strategy, exchange, symbol)
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    self.event_bus.emit(
                        EventType.ERROR,
                        {"symbol": symbol, "error": str(e)},
                        source="engine"
                    )

    async def _process_symbol(
        self,
        strategy: StrategyBase,
        exchange: ExchangeBase,
        symbol: str,
    ) -> None:
        """处理单个交易对"""
        # 获取市场数据
        market_data = await exchange.get_market_data(symbol)

        # 发布市场数据事件
        self.event_bus.emit(
            EventType.MARKET_DATA,
            market_data,
            source=exchange.name
        )

        # 检查现有持仓的风控
        position = await exchange.get_position(symbol)
        if position and position.is_open:
            # 更新策略状态
            strategy.state.position = position.side
            strategy.state.entry_price = position.entry_price
            strategy.state.quantity = position.quantity

            # 风控检查
            risk_signal = self.risk_manager.check_position(position)
            if risk_signal:
                await self._execute_signal(risk_signal, strategy, exchange, symbol, market_data)
                return

        # 生成策略信号
        signal = strategy.generate_signal(market_data)

        if signal not in (Signal.NONE, Signal.HOLD):
            # 发布信号事件
            self.event_bus.emit(
                EventType.SIGNAL,
                {"signal": signal, "symbol": symbol, "strategy": strategy.name},
                source="engine"
            )

            # 执行信号
            await self._execute_signal(signal, strategy, exchange, symbol, market_data)

    async def _execute_signal(
        self,
        signal: Signal,
        strategy: StrategyBase,
        exchange: ExchangeBase,
        symbol: str,
        market_data: MarketData,
    ) -> None:
        """执行交易信号"""
        logger.info(f"Executing signal: {signal.value} for {symbol}")

        # 获取余额
        balance = await exchange.get_balance()
        available = balance.get("available", 0)

        # 验证信号
        if not self.risk_manager.validate_signal(
            signal, symbol, available, market_data.price
        ):
            logger.warning(f"Signal {signal.value} rejected by risk manager")
            return

        # 开仓信号
        if signal == Signal.LONG:
            quantity = self.risk_manager.calculate_position_size(
                available, market_data.price
            )
            if quantity > 0:
                result = await exchange.place_market_order(
                    symbol=symbol,
                    side=OrderSide.BUY,
                    quantity=quantity,
                )
                if result.success:
                    # 更新策略状态
                    strategy.on_position_opened(
                        await exchange.get_position(symbol)
                    )
                    self.risk_manager.register_position(
                        await exchange.get_position(symbol)
                    )

        elif signal == Signal.SHORT:
            quantity = self.risk_manager.calculate_position_size(
                available, market_data.price
            )
            if quantity > 0:
                result = await exchange.place_market_order(
                    symbol=symbol,
                    side=OrderSide.SELL,
                    quantity=quantity,
                )
                if result.success:
                    strategy.on_position_opened(
                        await exchange.get_position(symbol)
                    )
                    self.risk_manager.register_position(
                        await exchange.get_position(symbol)
                    )

        # 平仓信号
        elif signal in (Signal.CLOSE_LONG, Signal.CLOSE_SHORT):
            position_side = "long" if signal == Signal.CLOSE_LONG else "short"
            result = await exchange.close_position(symbol, position_side)
            if result.success:
                # 计算盈亏
                pnl_pct = strategy.state.unrealized_pnl
                pnl = pnl_pct * strategy.state.entry_price * strategy.state.quantity
                strategy.on_position_closed(pnl, pnl_pct)
                self.risk_manager.unregister_position(symbol)
                self.risk_manager.update_daily_pnl(pnl)

    async def run_once(self, symbol: str, exchange_name: str = "okx") -> Dict[str, Any]:
        """
        执行一次分析（用于调试）

        Returns:
            分析结果
        """
        exchange = self._exchanges.get(exchange_name.lower())
        if not exchange:
            return {"error": f"Exchange {exchange_name} not found"}

        market_data = await exchange.get_market_data(symbol)

        result = {
            "symbol": symbol,
            "exchange": exchange_name,
            "timestamp": datetime.now().isoformat(),
            "price": market_data.price,
            "funding_rate": market_data.funding_rate,
            "signals": {},
        }

        for key, config in self._strategies.items():
            strategy: StrategyBase = config["strategy"]
            if symbol in config["symbols"] and config["exchange"] == exchange_name.lower():
                signal = strategy.generate_signal(market_data)
                result["signals"][strategy.name] = signal.value

        return result

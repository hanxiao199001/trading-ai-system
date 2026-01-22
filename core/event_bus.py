"""
事件总线 - 模块间解耦通信
支持同步和异步事件处理
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class EventType(Enum):
    """事件类型"""
    # 市场数据事件
    MARKET_DATA = "market_data"
    FUNDING_RATE = "funding_rate"
    ORDERBOOK = "orderbook"
    TRADE_TICK = "trade_tick"

    # 交易事件
    SIGNAL = "signal"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_REJECTED = "order_rejected"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"
    POSITION_UPDATED = "position_updated"

    # 风控事件
    RISK_ALERT = "risk_alert"
    STOP_LOSS_TRIGGERED = "stop_loss_triggered"
    TAKE_PROFIT_TRIGGERED = "take_profit_triggered"
    MARGIN_CALL = "margin_call"

    # 系统事件
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    ERROR = "error"
    WARNING = "warning"

    # 分析事件
    SENTIMENT_UPDATE = "sentiment_update"
    INDICATOR_UPDATE = "indicator_update"


@dataclass
class Event:
    """事件对象"""
    event_type: EventType
    data: Any
    source: str = ""                    # 事件来源模块
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0                   # 优先级，数字越大优先级越高
    correlation_id: Optional[str] = None  # 关联ID，用于追踪相关事件

    def __lt__(self, other):
        """优先级比较，用于优先队列"""
        return self.priority > other.priority


# 事件处理器类型
EventHandler = Callable[[Event], None]
AsyncEventHandler = Callable[[Event], asyncio.Future]


class EventBus:
    """
    事件总线
    支持同步和异步事件处理，支持优先级队列
    """

    def __init__(self):
        self._handlers: Dict[EventType, List[Union[EventHandler, AsyncEventHandler]]] = defaultdict(list)
        self._async_queue: Optional[asyncio.Queue] = None
        self._running = False
        self._event_history: List[Event] = []
        self._max_history = 1000

    def subscribe(self, event_type: EventType, handler: Union[EventHandler, AsyncEventHandler]) -> None:
        """订阅事件"""
        if handler not in self._handlers[event_type]:
            self._handlers[event_type].append(handler)
            logger.debug(f"Handler subscribed to {event_type.value}")

    def unsubscribe(self, event_type: EventType, handler: Union[EventHandler, AsyncEventHandler]) -> None:
        """取消订阅"""
        if handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Handler unsubscribed from {event_type.value}")

    def publish(self, event: Event) -> None:
        """
        同步发布事件
        立即调用所有订阅者
        """
        self._record_event(event)
        handlers = self._handlers.get(event.event_type, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    # 如果是异步处理器，创建任务
                    asyncio.create_task(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event.event_type.value}: {e}")
                self._publish_error(e, event)

    async def publish_async(self, event: Event) -> None:
        """
        异步发布事件
        等待所有异步处理器完成
        """
        self._record_event(event)
        handlers = self._handlers.get(event.event_type, [])

        tasks = []
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(event))
                else:
                    handler(event)
            except Exception as e:
                logger.error(f"Error in event handler for {event.event_type.value}: {e}")
                self._publish_error(e, event)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def emit(self, event_type: EventType, data: Any, source: str = "", **kwargs) -> None:
        """便捷方法：创建并发布事件"""
        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            **kwargs
        )
        self.publish(event)

    async def emit_async(self, event_type: EventType, data: Any, source: str = "", **kwargs) -> None:
        """便捷方法：创建并异步发布事件"""
        event = Event(
            event_type=event_type,
            data=data,
            source=source,
            **kwargs
        )
        await self.publish_async(event)

    def _record_event(self, event: Event) -> None:
        """记录事件历史"""
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

    def _publish_error(self, error: Exception, original_event: Event) -> None:
        """发布错误事件"""
        error_event = Event(
            event_type=EventType.ERROR,
            data={
                "error": str(error),
                "error_type": type(error).__name__,
                "original_event": original_event.event_type.value,
            },
            source="event_bus",
            correlation_id=original_event.correlation_id,
        )
        # 避免递归错误
        for handler in self._handlers.get(EventType.ERROR, []):
            try:
                if not asyncio.iscoroutinefunction(handler):
                    handler(error_event)
            except Exception:
                logger.exception("Error in error handler")

    def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """获取事件历史"""
        events = self._event_history
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def clear_history(self) -> None:
        """清空事件历史"""
        self._event_history.clear()

    @property
    def handler_count(self) -> Dict[str, int]:
        """获取各事件类型的处理器数量"""
        return {et.value: len(handlers) for et, handlers in self._handlers.items() if handlers}


# 全局事件总线实例
_global_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """获取全局事件总线实例"""
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = EventBus()
    return _global_event_bus

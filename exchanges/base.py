"""
交易所抽象基类
所有交易所适配器必须继承此类并实现抽象方法
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from decimal import Decimal
import logging

from core.types import (
    MarketData,
    Order,
    OrderResult,
    Position,
    Fill,
    OrderSide,
    OrderType,
)

logger = logging.getLogger(__name__)


class ExchangeBase(ABC):
    """
    交易所抽象基类

    子类需实现:
    - 认证相关: _sign_request
    - 市场数据: get_price, get_funding_rate, get_orderbook
    - 交易操作: place_order, cancel_order, close_position
    - 账户信息: get_balance, get_position, get_positions
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        testnet: bool = False,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.testnet = testnet
        self._session = None

    @property
    @abstractmethod
    def name(self) -> str:
        """交易所名称"""
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """API基础URL"""
        pass

    # ============ 认证相关 ============

    @abstractmethod
    def _sign_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
    ) -> Dict[str, str]:
        """
        生成请求签名
        返回包含签名的headers
        """
        pass

    # ============ 市场数据 ============

    @abstractmethod
    async def get_price(self, symbol: str) -> float:
        """获取最新价格"""
        pass

    @abstractmethod
    async def get_funding_rate(self, symbol: str) -> float:
        """获取当前资金费率"""
        pass

    @abstractmethod
    async def get_market_data(self, symbol: str) -> MarketData:
        """获取完整市场数据"""
        pass

    async def get_funding_rate_history(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取历史资金费率（可选实现）"""
        raise NotImplementedError(f"{self.name} does not support funding rate history")

    async def get_orderbook(
        self,
        symbol: str,
        depth: int = 20
    ) -> Dict[str, List]:
        """获取订单簿（可选实现）"""
        raise NotImplementedError(f"{self.name} does not support orderbook")

    # ============ 交易操作 ============

    @abstractmethod
    async def place_order(self, order: Order) -> OrderResult:
        """下单"""
        pass

    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """取消订单"""
        pass

    @abstractmethod
    async def close_position(
        self,
        symbol: str,
        position_side: Optional[str] = None
    ) -> OrderResult:
        """平仓"""
        pass

    async def place_market_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        leverage: int = 1,
        reduce_only: bool = False,
    ) -> OrderResult:
        """便捷方法：下市价单"""
        order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            leverage=leverage,
            reduce_only=reduce_only,
        )
        return await self.place_order(order)

    async def place_limit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        price: float,
        leverage: int = 1,
        reduce_only: bool = False,
    ) -> OrderResult:
        """便捷方法：下限价单"""
        order = Order(
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            price=price,
            leverage=leverage,
            reduce_only=reduce_only,
        )
        return await self.place_order(order)

    # ============ 账户信息 ============

    @abstractmethod
    async def get_balance(self, currency: str = "USDT") -> Dict[str, float]:
        """
        获取账户余额
        返回: {"total": x, "available": y, "frozen": z}
        """
        pass

    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定交易对的持仓"""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """获取所有持仓"""
        pass

    async def get_order(self, symbol: str, order_id: str) -> Optional[OrderResult]:
        """获取订单详情（可选实现）"""
        raise NotImplementedError(f"{self.name} does not support get_order")

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[OrderResult]:
        """获取未完成订单（可选实现）"""
        raise NotImplementedError(f"{self.name} does not support get_open_orders")

    async def get_fills(
        self,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Fill]:
        """获取成交记录（可选实现）"""
        raise NotImplementedError(f"{self.name} does not support get_fills")

    # ============ 杠杆设置 ============

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆倍数（可选实现）"""
        raise NotImplementedError(f"{self.name} does not support set_leverage")

    # ============ 工具方法 ============

    def normalize_symbol(self, symbol: str) -> str:
        """
        标准化交易对符号
        子类可覆盖以处理不同交易所的符号格式
        统一格式: BTC-USDT-SWAP
        """
        return symbol.upper()

    def denormalize_symbol(self, symbol: str) -> str:
        """
        将标准符号转换为交易所特定格式
        子类必须覆盖
        """
        return symbol

    @staticmethod
    def round_price(price: float, tick_size: float) -> float:
        """价格精度处理"""
        return float(Decimal(str(price)).quantize(Decimal(str(tick_size))))

    @staticmethod
    def round_quantity(quantity: float, step_size: float) -> float:
        """数量精度处理"""
        return float(Decimal(str(quantity)).quantize(Decimal(str(step_size))))

    # ============ 生命周期 ============

    async def connect(self) -> None:
        """建立连接（可选）"""
        pass

    async def disconnect(self) -> None:
        """断开连接（可选）"""
        if self._session:
            await self._session.close()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(testnet={self.testnet})"

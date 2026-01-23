"""
OKX交易所适配器
基于原okx-funding-bot的OKXTrader重构
支持永续合约交易
"""
import hmac
import base64
import hashlib
import json
import aiohttp
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

from exchanges.base import ExchangeBase
from core.types import (
    MarketData,
    Order,
    OrderResult,
    Position,
    Fill,
    OrderSide,
    OrderType,
    OrderStatus,
    PositionSide,
)

logger = logging.getLogger(__name__)


class OKXExchange(ExchangeBase):
    """
    OKX交易所适配器

    实现功能:
    - 市场数据: 价格、资金费率、订单簿
    - 交易操作: 下单、撤单、平仓
    - 账户信息: 余额、持仓
    """

    MAINNET_URL = "https://www.okx.com"
    TESTNET_URL = "https://www.okx.com"  # OKX模拟盘使用同一域名，通过header区分

    # 交易对映射
    SYMBOL_MAP = {
        "BTC-USDT-SWAP": "BTC-USDT-SWAP",
        "ETH-USDT-SWAP": "ETH-USDT-SWAP",
        "BTCUSDT": "BTC-USDT-SWAP",
        "ETHUSDT": "ETH-USDT-SWAP",
    }

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        testnet: bool = False,
    ):
        super().__init__(api_key, api_secret, passphrase, testnet)
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def name(self) -> str:
        return "OKX"

    @property
    def base_url(self) -> str:
        return self.TESTNET_URL if self.testnet else self.MAINNET_URL

    # ============ 认证相关 ============

    def _sign_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
    ) -> Dict[str, str]:
        """
        生成OKX API签名
        签名算法: HMAC-SHA256(timestamp + method + requestPath + body)
        """
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        # 构建签名消息
        if body:
            body_str = json.dumps(body)
        else:
            body_str = ""

        if params:
            query_string = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
            request_path = f"{endpoint}?{query_string}"
        else:
            request_path = endpoint

        message = timestamp + method.upper() + request_path + body_str

        # HMAC-SHA256签名
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                message.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')

        headers = {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json',
        }

        # 模拟盘标识
        if self.testnet:
            headers['x-simulated-trading'] = '1'

        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        body: Optional[Dict] = None,
        signed: bool = False,
    ) -> Dict[str, Any]:
        """发送HTTP请求"""
        if self._session is None:
            self._session = aiohttp.ClientSession()

        url = f"{self.base_url}{endpoint}"

        headers = {'Content-Type': 'application/json'}
        if signed:
            headers = self._sign_request(method, endpoint, params, body)

        try:
            async with self._session.request(
                method,
                url,
                params=params,
                json=body,
                headers=headers,
            ) as response:
                data = await response.json()

                if data.get('code') != '0':
                    logger.error(f"OKX API error: {data}")

                return data

        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {"code": "-1", "msg": str(e), "data": []}

    # ============ 市场数据 ============

    async def get_price(self, symbol: str) -> float:
        """获取最新价格"""
        inst_id = self.denormalize_symbol(symbol)
        data = await self._request(
            "GET",
            "/api/v5/market/ticker",
            params={"instId": inst_id}
        )

        if data.get('code') == '0' and data.get('data'):
            return float(data['data'][0]['last'])

        return 0.0

    async def get_funding_rate(self, symbol: str) -> float:
        """获取当前资金费率"""
        inst_id = self.denormalize_symbol(symbol)
        data = await self._request(
            "GET",
            "/api/v5/public/funding-rate",
            params={"instId": inst_id}
        )

        if data.get('code') == '0' and data.get('data'):
            return float(data['data'][0]['fundingRate'])

        return 0.0

    async def get_market_data(self, symbol: str) -> MarketData:
        """获取完整市场数据"""
        inst_id = self.denormalize_symbol(symbol)

        # 并行获取多个数据
        ticker_data = await self._request(
            "GET",
            "/api/v5/market/ticker",
            params={"instId": inst_id}
        )
        funding_data = await self._request(
            "GET",
            "/api/v5/public/funding-rate",
            params={"instId": inst_id}
        )

        ticker = ticker_data.get('data', [{}])[0] if ticker_data.get('code') == '0' else {}
        funding = funding_data.get('data', [{}])[0] if funding_data.get('code') == '0' else {}

        return MarketData(
            symbol=symbol,
            exchange=self.name,
            timestamp=datetime.now(),
            price=float(ticker.get('last', 0)),
            bid=float(ticker.get('bidPx', 0)) if ticker.get('bidPx') else None,
            ask=float(ticker.get('askPx', 0)) if ticker.get('askPx') else None,
            volume_24h=float(ticker.get('vol24h', 0)) if ticker.get('vol24h') else None,
            funding_rate=float(funding.get('fundingRate', 0)) if funding.get('fundingRate') else None,
            next_funding_time=datetime.fromtimestamp(
                int(funding.get('nextFundingTime', 0)) / 1000
            ) if funding.get('nextFundingTime') else None,
            open_interest=float(ticker.get('oi', 0)) if ticker.get('oi') else None,
        )

    async def get_funding_rate_history(
        self,
        symbol: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取历史资金费率"""
        inst_id = self.denormalize_symbol(symbol)
        data = await self._request(
            "GET",
            "/api/v5/public/funding-rate-history",
            params={"instId": inst_id, "limit": str(limit)}
        )

        if data.get('code') == '0':
            return [
                {
                    "funding_rate": float(item['fundingRate']),
                    "timestamp": datetime.fromtimestamp(int(item['fundingTime']) / 1000),
                }
                for item in data.get('data', [])
            ]

        return []


    async def get_klines(
        self,
        symbol: str,
        interval: str = "1H",
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        获取历史K线数据
        
        Args:
            symbol: 交易对 (如 BTC-USDT-SWAP)
            interval: K线周期 (1m/5m/15m/1H/4H/1D等)
            limit: 数量限制 (最大100)
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            K线数据列表
        """
        inst_id = self.denormalize_symbol(symbol)
        params = {
            "instId": inst_id,
            "bar": interval,
            "limit": str(min(limit, 100))
        }
        
        if end_time:
            params["after"] = str(int(end_time.timestamp() * 1000))
        if start_time:
            params["before"] = str(int(start_time.timestamp() * 1000))
        
        data = await self._request(
            "GET",
            "/api/v5/market/candles",
            params=params
        )
        
        if data.get("code") == "0":
            klines = []
            for item in data.get("data", []):
                klines.append({
                    "timestamp": datetime.fromtimestamp(int(item[0]) / 1000),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                })
            return sorted(klines, key=lambda x: x["timestamp"])
        
        logger.error(f"获取K线失败: {data}")
        return []

    async def get_history_klines(
        self,
        symbol: str,
        interval: str = "1H",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_candles: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        获取大量历史K线 (自动分页)
        
        Args:
            symbol: 交易对
            interval: K线周期
            start_time: 开始时间
            end_time: 结束时间
            max_candles: 最大K线数量
        
        Returns:
            K线数据列表
        """
        all_klines = []
        current_end = end_time or datetime.now()
        
        while len(all_klines) < max_candles:
            batch = await self.get_klines(
                symbol=symbol,
                interval=interval,
                limit=100,
                end_time=current_end
            )
            
            if not batch:
                break
            
            all_klines = batch + all_klines
            
            if start_time and batch[0]["timestamp"] <= start_time:
                all_klines = [k for k in all_klines if k["timestamp"] >= start_time]
                break
            
            current_end = batch[0]["timestamp"]
            
            import asyncio
            await asyncio.sleep(0.1)
        
        logger.info(f"获取了 {len(all_klines)} 条K线数据")
        return all_klines[:max_candles]

    # ============ 交易操作 ============

    async def place_order(self, order: Order) -> OrderResult:
        """下单"""
        inst_id = self.denormalize_symbol(order.symbol)

        # OKX订单参数映射
        side = "buy" if order.side == OrderSide.BUY else "sell"
        ord_type = "market" if order.order_type == OrderType.MARKET else "limit"

        # 永续合约使用张数，需要根据合约面值转换
        # BTC永续: 1张 = 0.01 BTC (100美元面值)
        # 这里简化处理，假设quantity已经是张数
        sz = str(int(order.quantity))

        body = {
            "instId": inst_id,
            "tdMode": "cross",  # 全仓模式
            "side": side,
            "ordType": ord_type,
            "sz": sz,
        }

        # 持仓方向
        if order.side == OrderSide.BUY:
            body["posSide"] = "long"
        else:
            body["posSide"] = "short"

        # 限价单需要价格
        if order.order_type == OrderType.LIMIT and order.price:
            body["px"] = str(order.price)

        # reduce_only模式
        if order.reduce_only:
            body["reduceOnly"] = True

        data = await self._request(
            "POST",
            "/api/v5/trade/order",
            body=body,
            signed=True
        )

        if data.get('code') == '0' and data.get('data'):
            order_data = data['data'][0]
            return OrderResult(
                success=True,
                order_id=order_data.get('ordId'),
                client_order_id=order_data.get('clOrdId'),
                status=OrderStatus.OPEN,
                raw_response=data
            )
        else:
            return OrderResult(
                success=False,
                error_code=data.get('code'),
                error_message=data.get('msg') or data.get('data', [{}])[0].get('sMsg'),
                raw_response=data
            )

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        """取消订单"""
        inst_id = self.denormalize_symbol(symbol)

        data = await self._request(
            "POST",
            "/api/v5/trade/cancel-order",
            body={
                "instId": inst_id,
                "ordId": order_id,
            },
            signed=True
        )

        return data.get('code') == '0'

    async def close_position(
        self,
        symbol: str,
        position_side: Optional[str] = None
    ) -> OrderResult:
        """平仓"""
        inst_id = self.denormalize_symbol(symbol)

        body = {
            "instId": inst_id,
            "mgnMode": "cross",
        }

        if position_side:
            body["posSide"] = position_side

        data = await self._request(
            "POST",
            "/api/v5/trade/close-position",
            body=body,
            signed=True
        )

        if data.get('code') == '0':
            return OrderResult(
                success=True,
                status=OrderStatus.FILLED,
                raw_response=data
            )
        else:
            return OrderResult(
                success=False,
                error_code=data.get('code'),
                error_message=data.get('msg'),
                raw_response=data
            )

    # ============ 账户信息 ============

    async def get_balance(self, currency: str = "USDT") -> Dict[str, float]:
        """获取账户余额"""
        data = await self._request(
            "GET",
            "/api/v5/account/balance",
            params={"ccy": currency},
            signed=True
        )

        if data.get('code') == '0' and data.get('data'):
            details = data['data'][0].get('details', [])
            for detail in details:
                if detail.get('ccy') == currency:
                    return {
                        "total": float(detail.get('eq', 0)),
                        "available": float(detail.get('availBal', 0)),
                        "frozen": float(detail.get('frozenBal', 0)),
                    }

        return {"total": 0.0, "available": 0.0, "frozen": 0.0}

    async def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定交易对的持仓"""
        inst_id = self.denormalize_symbol(symbol)

        data = await self._request(
            "GET",
            "/api/v5/account/positions",
            params={"instId": inst_id},
            signed=True
        )

        if data.get('code') == '0' and data.get('data'):
            for pos_data in data['data']:
                pos = float(pos_data.get('pos', 0))
                if pos != 0:
                    return self._parse_position(pos_data)

        return None

    async def get_positions(self) -> List[Position]:
        """获取所有持仓"""
        data = await self._request(
            "GET",
            "/api/v5/account/positions",
            params={"instType": "SWAP"},
            signed=True
        )

        positions = []
        if data.get('code') == '0' and data.get('data'):
            for pos_data in data['data']:
                pos = float(pos_data.get('pos', 0))
                if pos != 0:
                    positions.append(self._parse_position(pos_data))

        return positions

    def _parse_position(self, data: Dict) -> Position:
        """解析持仓数据"""
        pos = float(data.get('pos', 0))
        side = PositionSide.LONG if data.get('posSide') == 'long' else PositionSide.SHORT

        avg_px = float(data.get('avgPx', 0))
        mark_px = float(data.get('markPx', 0))
        upl = float(data.get('upl', 0))

        # 计算盈亏百分比
        if avg_px > 0:
            if side == PositionSide.LONG:
                upl_pct = (mark_px - avg_px) / avg_px
            else:
                upl_pct = (avg_px - mark_px) / avg_px
        else:
            upl_pct = 0.0

        return Position(
            symbol=self.normalize_symbol(data.get('instId', '')),
            exchange=self.name,
            side=side,
            quantity=abs(pos),
            entry_price=avg_px,
            mark_price=mark_px,
            liquidation_price=float(data.get('liqPx', 0)) if data.get('liqPx') else None,
            leverage=int(data.get('lever', 1)),
            unrealized_pnl=upl,
            unrealized_pnl_pct=upl_pct,
            margin=float(data.get('margin', 0)),
            timestamp=datetime.now(),
        )

    # ============ 杠杆设置 ============

    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """设置杠杆倍数"""
        inst_id = self.denormalize_symbol(symbol)

        data = await self._request(
            "POST",
            "/api/v5/account/set-leverage",
            body={
                "instId": inst_id,
                "lever": str(leverage),
                "mgnMode": "cross",
            },
            signed=True
        )

        return data.get('code') == '0'

    # ============ 符号转换 ============

    def normalize_symbol(self, symbol: str) -> str:
        """标准化交易对符号"""
        return symbol.upper()

    def denormalize_symbol(self, symbol: str) -> str:
        """转换为OKX格式"""
        symbol = symbol.upper()
        return self.SYMBOL_MAP.get(symbol, symbol)

    # ============ 生命周期 ============

    async def connect(self) -> None:
        """建立连接"""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        logger.info(f"Connected to {self.name} {'(testnet)' if self.testnet else ''}")

    async def disconnect(self) -> None:
        """断开连接"""
        if self._session:
            await self._session.close()
            self._session = None
        logger.info(f"Disconnected from {self.name}")

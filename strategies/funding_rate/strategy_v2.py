"""
资金费率策略 V2 - 加入趋势过滤
优化点:
1. 价格趋势确认 - 只在趋势方向交易
2. 动量过滤 - 避免震荡市场
3. 资金费率极值 - 只在费率极端时交易
4. 冷却期 - 避免频繁交易
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import logging

from strategies.base import StrategyBase
from core.types import SignalData, OrderSide

logger = logging.getLogger(__name__)


class FundingRateStrategyV2(StrategyBase):
    """资金费率套利策略 V2"""
    
    DEFAULT_CONFIG = {
        # 资金费率阈值
        'high_funding_threshold': 0.0001,   # 0.01% 做空阈值
        'low_funding_threshold': -0.0001,   # -0.01% 做多阈值
        
        # 趋势过滤
        'trend_ma_period': 20,              # 趋势MA周期
        'trend_strength_threshold': 0.005,  # 0.5% 趋势强度要求
        
        # 动量过滤
        'momentum_period': 5,               # 动量计算周期
        'momentum_threshold': 0.002,        # 0.2% 动量阈值
        
        # 交易控制
        'position_size': 0.20,              # 20% 仓位
        'min_holding_hours': 8,             # 最少持仓8小时
        'cooldown_hours': 4,                # 交易冷却期
        
        # 趋势跟随模式
        'trend_follow_mode': True,          # True=顺势, False=逆势
    }
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._name = "FundingRateV2"
        self._price_history: Dict[str, List[float]] = {}
        self._last_signal_time: Dict[str, datetime] = {}
        
    @property
    def name(self) -> str:
        return self._name
    
    def initialize(self, params: Optional[Dict] = None) -> None:
        if params:
            self.config.update(params)
        self._price_history = {}
        self._last_signal_time = {}
        logger.info(f"策略初始化: {self.name}")
    

    def generate_signal(self, market_data) -> "Signal":
        """实现抽象方法"""
        from core.types import Signal
        result = self.on_market_data(market_data)
        if result and result.side == OrderSide.BUY:
            return Signal.LONG
        elif result and result.side == OrderSide.SELL:
            return Signal.SHORT
        return Signal.NONE

    def on_market_data(self, market_data) -> Optional[SignalData]:
        signals = self.generate_signals({market_data.symbol: market_data})
        return signals[0] if signals else None
    
    def _update_price_history(self, symbol: str, price: float, max_len: int = 50):
        """更新价格历史"""
        if symbol not in self._price_history:
            self._price_history[symbol] = []
        self._price_history[symbol].append(price)
        if len(self._price_history[symbol]) > max_len:
            self._price_history[symbol] = self._price_history[symbol][-max_len:]
    
    def _calculate_ma(self, symbol: str, period: int) -> Optional[float]:
        """计算移动平均"""
        prices = self._price_history.get(symbol, [])
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def _calculate_momentum(self, symbol: str, period: int) -> Optional[float]:
        """计算动量 (价格变化率)"""
        prices = self._price_history.get(symbol, [])
        if len(prices) < period + 1:
            return None
        return (prices[-1] - prices[-period-1]) / prices[-period-1]
    
    def _get_trend_direction(self, symbol: str, current_price: float) -> Optional[str]:
        """获取趋势方向"""
        ma = self._calculate_ma(symbol, self.config['trend_ma_period'])
        if ma is None:
            return None
        
        diff_pct = (current_price - ma) / ma
        threshold = self.config['trend_strength_threshold']
        
        if diff_pct > threshold:
            return "up"
        elif diff_pct < -threshold:
            return "down"
        return "sideways"
    
    def _check_cooldown(self, symbol: str, current_time: datetime) -> bool:
        """检查是否在冷却期"""
        last_time = self._last_signal_time.get(symbol)
        if last_time is None:
            return False
        
        cooldown = timedelta(hours=self.config['cooldown_hours'])
        return (current_time - last_time) < cooldown
    
    def generate_signals(self, market_data: Dict[str, Any]) -> List[SignalData]:
        """生成交易信号"""
        signals = []
        
        for symbol, kline in market_data.items():
            current_price = float(kline.close)
            current_time = kline.timestamp
            
            # 更新价格历史
            self._update_price_history(symbol, current_price)
            
            # 检查冷却期
            if self._check_cooldown(symbol, current_time):
                continue
            
            # 检查资金费率
            if not hasattr(kline, 'funding_rate') or kline.funding_rate is None:
                continue
            
            funding_rate = float(kline.funding_rate)
            
            # 获取趋势方向
            trend = self._get_trend_direction(symbol, current_price)
            if trend is None or trend == "sideways":
                continue  # 震荡市不交易
            
            # 计算动量
            momentum = self._calculate_momentum(symbol, self.config['momentum_period'])
            if momentum is None:
                continue
            
            # 动量过滤
            if abs(momentum) < self.config['momentum_threshold']:
                continue  # 动量不足不交易
            
            signal = None
            
            # 策略逻辑
            if self.config['trend_follow_mode']:
                # 顺势模式: 趋势向上 + 负费率 = 做多
                if trend == "up" and funding_rate < self.config['low_funding_threshold'] and momentum > 0:
                    signal = self._create_signal(symbol, OrderSide.BUY, kline, funding_rate, trend, momentum)
                # 趋势向下 + 正费率 = 做空
                elif trend == "down" and funding_rate > self.config['high_funding_threshold'] and momentum < 0:
                    signal = self._create_signal(symbol, OrderSide.SELL, kline, funding_rate, trend, momentum)
            else:
                # 逆势模式 (原始逻辑)
                if funding_rate > self.config['high_funding_threshold'] and trend != "up":
                    signal = self._create_signal(symbol, OrderSide.SELL, kline, funding_rate, trend, momentum)
                elif funding_rate < self.config['low_funding_threshold'] and trend != "down":
                    signal = self._create_signal(symbol, OrderSide.BUY, kline, funding_rate, trend, momentum)
            
            if signal:
                signals.append(signal)
                self._last_signal_time[symbol] = current_time
                logger.debug(f"V2信号: {symbol} {signal.side.value} 费率={funding_rate:.4%} 趋势={trend} 动量={momentum:.3%}")
        
        return signals
    
    def _create_signal(self, symbol: str, side: OrderSide, kline, funding_rate: float, trend: str, momentum: float) -> SignalData:
        """创建交易信号"""
        # 根据费率极端程度调整置信度
        confidence = min(abs(funding_rate) * 500 + abs(momentum) * 50, 1.0)
        
        return SignalData(
            strategy_name=self.name,
            symbol=symbol,
            side=side,
            timestamp=kline.timestamp,
            confidence=confidence,
            suggested_size=Decimal(str(self.config["position_size"])),
            metadata={
                "funding_rate": funding_rate,
                "trend": trend,
                "momentum": momentum,
                "price": float(kline.close),
                "version": "v2"
            }
        )

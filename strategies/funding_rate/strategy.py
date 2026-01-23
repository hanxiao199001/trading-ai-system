"""
资金费率套利策略
"""
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime
import logging

from core.types import SignalData, OrderSide
from strategies.base import StrategyBase
from risk.manager import RiskManager

logger = logging.getLogger(__name__)


class FundingRateStrategy(StrategyBase):
    """资金费率套利策略"""
    
    DEFAULT_CONFIG = {
        "high_funding_threshold": 0.0005,
        "low_funding_threshold": -0.0005,
        "min_holding_hours": 8,
        "position_size": 0.3,
    }
    
    def __init__(
        self, 
        config: Optional[Dict[str, Any]] = None,
        risk_manager: Optional[RiskManager] = None,
    ):
        merged_config = {**self.DEFAULT_CONFIG, **(config or {})}
        super().__init__(merged_config, risk_manager)
        self._name = "FundingRateStrategy"
    
    @property
    def name(self) -> str:
        """策略名称"""
        return self._name
    
    def initialize(self, params: Dict[str, Any] = None):
        """初始化策略参数"""
        if params:
            self.config.update(params)
        logger.info(f"策略初始化: {self.name}, 参数: {self.config}")
    
    def generate_signal(self, market_data: Any) -> Optional[SignalData]:
        """生成单个信号"""
        if hasattr(market_data, 'symbol'):
            signals = self.generate_signals({market_data.symbol: market_data})
            return signals[0] if signals else None
        return None
    
    def generate_signals(self, market_data: Dict[str, Any]) -> List[SignalData]:
        """生成交易信号"""
        signals = []
        
        for symbol, kline in market_data.items():
            if not hasattr(kline, 'funding_rate') or kline.funding_rate is None:
                continue
            
            funding_rate = float(kline.funding_rate)
            
            # 高费率 -> 做空信号
            if funding_rate > self.config["high_funding_threshold"]:
                signal = SignalData(
                    strategy_name=self.name,
                    symbol=symbol,
                    side=OrderSide.SELL,
                    timestamp=kline.timestamp,
                    confidence=min(abs(funding_rate) * 100, 1.0),
                    suggested_size=Decimal(str(self.config["position_size"])),
                    metadata={
                        "funding_rate": funding_rate,
                        "reason": "high_funding_rate",
                        "price": float(kline.close)
                    }
                )
                signals.append(signal)
                logger.debug(f"生成做空信号: {symbol} 费率={funding_rate:.4%}")
            
            # 低费率 -> 做多信号
            elif funding_rate < self.config["low_funding_threshold"]:
                signal = SignalData(
                    strategy_name=self.name,
                    symbol=symbol,
                    side=OrderSide.BUY,
                    timestamp=kline.timestamp,
                    confidence=min(abs(funding_rate) * 100, 1.0),
                    suggested_size=Decimal(str(self.config["position_size"])),
                    metadata={
                        "funding_rate": funding_rate,
                        "reason": "low_funding_rate",
                        "price": float(kline.close)
                    }
                )
                signals.append(signal)
                logger.debug(f"生成做多信号: {symbol} 费率={funding_rate:.4%}")
        
        return signals
    
    def on_trade_executed(self, trade: Any):
        """交易执行回调"""
        logger.info(f"交易执行: {trade.symbol} {trade.side} @ ${trade.price}")
    
    def on_position_closed(self, position: Any, pnl: Decimal):
        """持仓关闭回调"""
        logger.info(f"平仓: {position.symbol} 盈亏: ${pnl:.2f}")

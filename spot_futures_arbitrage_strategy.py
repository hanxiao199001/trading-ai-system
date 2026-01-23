"""
现货期货套利策略 (Spot-Futures Arbitrage)
基于价差的市场中性策略

策略逻辑:
1. 监控现货和永续合约的价差
2. 当价差超过阈值时开仓对冲
3. 当价差回归时平仓获利

优势:
- 市场中性,不受涨跌影响
- 低风险,双边对冲
- 高胜率,价差必然收敛
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
import logging

from strategies.base import StrategyBase
from core.types import SignalData, OrderSide

logger = logging.getLogger(__name__)


class SpotFuturesArbitrageStrategy(StrategyBase):
    """现货期货套利策略"""
    
    DEFAULT_CONFIG = {
        # 价差阈值
        'entry_spread_pct': 0.005,      # 0.5% 开仓价差
        'exit_spread_pct': 0.001,       # 0.1% 平仓价差
        
        # 风控参数
        'max_holding_hours': 72,        # 最长持仓72小时
        'stop_loss_pct': 0.02,          # 2% 止损(防止极端行情)
        'position_size': 0.30,          # 30% 仓位(因为是对冲)
        
        # 价差计算
        'spread_ma_period': 20,         # 价差均值周期
        'spread_std_multiplier': 2.0,   # 标准差倍数
        
        # 交易控制
        'min_volume_ratio': 0.8,        # 最小成交量比率(避免流动性问题)
        'cooldown_hours': 1,            # 冷却期
    }
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self._name = "SpotFuturesArbitrage"
        
        # 价差历史
        self._spread_history: Dict[str, List[float]] = {}
        self._position_info: Dict[str, Dict] = {}  # 记录持仓信息
        self._last_trade_time: Dict[str, datetime] = {}
        
    @property
    def name(self) -> str:
        return self._name
    
    def initialize(self, params: Optional[Dict] = None) -> None:
        if params:
            self.config.update(params)
        self._spread_history = {}
        self._position_info = {}
        self._last_trade_time = {}
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
    
    def _update_spread_history(self, symbol: str, spread: float, max_len: int = 100):
        """更新价差历史"""
        if symbol not in self._spread_history:
            self._spread_history[symbol] = []
        self._spread_history[symbol].append(spread)
        if len(self._spread_history[symbol]) > max_len:
            self._spread_history[symbol] = self._spread_history[symbol][-max_len:]
    
    def _calculate_spread_stats(self, symbol: str) -> Optional[Dict]:
        """计算价差统计数据"""
        spreads = self._spread_history.get(symbol, [])
        period = self.config['spread_ma_period']
        
        if len(spreads) < period:
            return None
        
        recent_spreads = spreads[-period:]
        mean = sum(recent_spreads) / len(recent_spreads)
        variance = sum((x - mean) ** 2 for x in recent_spreads) / len(recent_spreads)
        std = variance ** 0.5
        
        return {
            'mean': mean,
            'std': std,
            'upper_band': mean + std * self.config['spread_std_multiplier'],
            'lower_band': mean - std * self.config['spread_std_multiplier']
        }
    
    def _check_cooldown(self, symbol: str, current_time: datetime) -> bool:
        """检查冷却期"""
        last_time = self._last_trade_time.get(symbol)
        if last_time is None:
            return False
        
        cooldown = timedelta(hours=self.config['cooldown_hours'])
        return (current_time - last_time) < cooldown
    
    def _check_holding_time(self, symbol: str, current_time: datetime) -> bool:
        """检查是否超过最大持仓时间"""
        if symbol not in self._position_info:
            return False
        
        entry_time = self._position_info[symbol].get('entry_time')
        if entry_time is None:
            return False
        
        max_holding = timedelta(hours=self.config['max_holding_hours'])
        return (current_time - entry_time) >= max_holding
    
    def generate_signals(self, market_data: Dict[str, Any]) -> List[SignalData]:
        """
        生成交易信号
        
        注意: 这里简化处理,实际需要同时获取现货和期货数据
        在真实环境中,market_data应该包含spot_price和futures_price
        """
        signals = []
        
        for symbol, kline in market_data.items():
            current_time = kline.timestamp
            
            # 检查冷却期
            if self._check_cooldown(symbol, current_time):
                continue
            
            # 这里假设kline包含现货和期货价格
            # 实际使用时需要调整数据获取方式
            if not hasattr(kline, 'spot_price') or not hasattr(kline, 'futures_price'):
                # 如果没有双边数据,跳过
                continue
            
            spot_price = float(kline.spot_price)
            futures_price = float(kline.futures_price)
            
            # 计算价差百分比
            spread_pct = (futures_price - spot_price) / spot_price
            
            # 更新价差历史
            self._update_spread_history(symbol, spread_pct)
            
            # 计算价差统计
            spread_stats = self._calculate_spread_stats(symbol)
            if spread_stats is None:
                continue
            
            # 检查是否有持仓
            has_position = symbol in self._position_info
            
            if has_position:
                # 已有持仓,检查平仓条件
                position = self._position_info[symbol]
                entry_spread = position['entry_spread']
                position_type = position['type']  # 'positive' or 'negative'
                
                # 平仓条件1: 价差回归
                should_close = False
                if position_type == 'positive' and spread_pct <= self.config['exit_spread_pct']:
                    should_close = True
                elif position_type == 'negative' and spread_pct >= -self.config['exit_spread_pct']:
                    should_close = True
                
                # 平仓条件2: 超过最大持仓时间
                if self._check_holding_time(symbol, current_time):
                    should_close = True
                    logger.info(f"持仓超时,强制平仓: {symbol}")
                
                # 平仓条件3: 止损(价差继续扩大)
                if position_type == 'positive':
                    if spread_pct > entry_spread * (1 + self.config['stop_loss_pct']):
                        should_close = True
                        logger.warning(f"触发止损: {symbol}")
                else:
                    if spread_pct < entry_spread * (1 - self.config['stop_loss_pct']):
                        should_close = True
                        logger.warning(f"触发止损: {symbol}")
                
                if should_close:
                    # 生成平仓信号(反向操作)
                    side = OrderSide.SELL if position_type == 'positive' else OrderSide.BUY
                    signal = self._create_signal(
                        symbol, side, kline, spread_pct, spread_stats,
                        action='close'
                    )
                    signals.append(signal)
                    del self._position_info[symbol]
                    self._last_trade_time[symbol] = current_time
                    
            else:
                # 无持仓,检查开仓条件
                
                # 开仓条件: 价差超过阈值
                if spread_pct > self.config['entry_spread_pct']:
                    # 正溢价: 做空期货 + 做多现货
                    signal = self._create_signal(
                        symbol, OrderSide.SELL, kline, spread_pct, spread_stats,
                        action='open'
                    )
                    signals.append(signal)
                    
                    # 记录持仓信息
                    self._position_info[symbol] = {
                        'type': 'positive',
                        'entry_spread': spread_pct,
                        'entry_time': current_time,
                        'spot_price': spot_price,
                        'futures_price': futures_price
                    }
                    self._last_trade_time[symbol] = current_time
                    
                elif spread_pct < -self.config['entry_spread_pct']:
                    # 负溢价: 做多期货 + 做空现货
                    signal = self._create_signal(
                        symbol, OrderSide.BUY, kline, spread_pct, spread_stats,
                        action='open'
                    )
                    signals.append(signal)
                    
                    # 记录持仓信息
                    self._position_info[symbol] = {
                        'type': 'negative',
                        'entry_spread': spread_pct,
                        'entry_time': current_time,
                        'spot_price': spot_price,
                        'futures_price': futures_price
                    }
                    self._last_trade_time[symbol] = current_time
        
        return signals
    
    def _create_signal(self, symbol: str, side: OrderSide, kline, spread_pct: float, 
                       spread_stats: Dict, action: str) -> SignalData:
        """创建交易信号"""
        
        # 计算置信度(基于价差偏离程度)
        mean = spread_stats['mean']
        std = spread_stats['std']
        
        if std > 0:
            z_score = abs(spread_pct - mean) / std
            confidence = min(z_score / 3.0, 1.0)  # 3倍标准差 = 100%置信度
        else:
            confidence = 0.5
        
        return SignalData(
            strategy_name=self.name,
            symbol=symbol,
            side=side,
            timestamp=kline.timestamp,
            confidence=confidence,
            suggested_size=Decimal(str(self.config["position_size"])),
            metadata={
                "spread_pct": spread_pct,
                "spread_mean": mean,
                "spread_std": std,
                "action": action,  # 'open' or 'close'
                "spot_price": float(kline.spot_price) if hasattr(kline, 'spot_price') else None,
                "futures_price": float(kline.futures_price) if hasattr(kline, 'futures_price') else None,
                "version": "v1"
            }
        )


# ========== 使用示例 ==========

if __name__ == "__main__":
    """
    使用示例
    
    注意: 实际使用时需要:
    1. 同时获取现货和期货的价格数据
    2. 在回测引擎中实现双边开仓逻辑
    3. 考虑双边手续费
    4. 考虑资金费率(如果用永续合约)
    """
    
    print("="*80)
    print("现货期货套利策略示例")
    print("="*80)
    
    # 创建策略实例
    strategy = SpotFuturesArbitrageStrategy({
        'entry_spread_pct': 0.005,  # 0.5% 价差开仓
        'exit_spread_pct': 0.001,   # 0.1% 价差平仓
        'position_size': 0.30,      # 30% 仓位
    })
    
    print("\n策略配置:")
    print(f"  开仓价差: {strategy.config['entry_spread_pct']:.1%}")
    print(f"  平仓价差: {strategy.config['exit_spread_pct']:.1%}")
    print(f"  仓位大小: {strategy.config['position_size']:.0%}")
    print(f"  最大持仓: {strategy.config['max_holding_hours']}小时")
    print(f"  止损: {strategy.config['stop_loss_pct']:.0%}")
    
    print("\n" + "="*80)
    print("策略特点:")
    print("="*80)
    print("✅ 市场中性 - 不受涨跌影响")
    print("✅ 低风险 - 双边对冲")
    print("✅ 高胜率 - 价差必然收敛")
    print("✅ 稳定收益 - 赚取价差")
    
    print("\n" + "="*80)
    print("实施要点:")
    print("="*80)
    print("1. 需要同时获取现货和期货价格")
    print("2. 双边开仓需要2倍资金")
    print("3. 手续费会侵蚀收益,要选低费率交易所")
    print("4. 价差过小(<0.3%)不建议开仓")
    print("5. 交割日前价差会快速收敛")
    
    print("\n" + "="*80)
    print("风险提示:")
    print("="*80)
    print("⚠️  极端行情下价差可能继续扩大")
    print("⚠️  需要足够的保证金防止爆仓")
    print("⚠️  流动性不足可能导致滑点")
    print("⚠️  永续合约有资金费率成本")
    
    print("\n" + "="*80)
    print("下一步:")
    print("="*80)
    print("1. 获取OKX的现货和期货历史数据")
    print("2. 改造回测引擎支持双边开仓")
    print("3. 回测验证策略效果")
    print("4. 如果效果好,部署到模拟盘")
    print("="*80)

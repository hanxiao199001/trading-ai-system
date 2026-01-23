"""
微调顺势-宽松参数
"""
from decimal import Decimal
from backtest.engine import BacktestEngine
from backtest.types import BacktestConfig
from backtest.data_loader import DataLoader
from strategies.funding_rate.strategy_v2 import FundingRateStrategyV2


def run_tune():
    klines = DataLoader.load_from_csv("data/btc_usdt_swap_30d.csv", "BTC-USDT-SWAP")
    
    # 在顺势-宽松基础上微调
    test_cases = [
        ('基准', 0.00005, -0.00005, 12, 0.003, 0.001, 0.25, 2),
        ('更低阈值', 0.00003, -0.00003, 12, 0.003, 0.001, 0.25, 2),
        ('更短MA', 0.00005, -0.00005, 8, 0.002, 0.001, 0.25, 2),
        ('更高仓位', 0.00005, -0.00005, 12, 0.003, 0.001, 0.35, 2),
        ('无冷却', 0.00005, -0.00005, 12, 0.003, 0.001, 0.25, 0),
        ('低动量', 0.00005, -0.00005, 12, 0.003, 0.0005, 0.25, 2),
        ('组合A', 0.00003, -0.00003, 8, 0.002, 0.0005, 0.30, 1),
        ('组合B', 0.00004, -0.00004, 10, 0.0025, 0.0008, 0.28, 2),
    ]
    
    print(f"{'名称':<12} {'收益':>8} {'交易':>6} {'胜率':>7} {'盈亏比':>7} {'回撤':>7}")
    print("-" * 55)
    
    for name, hi, lo, ma, trend, mom, pos, cool in test_cases:
        config = BacktestConfig(
            start_time=klines[0].timestamp,
            end_time=klines[-1].timestamp,
            initial_capital=Decimal("100000"),
            taker_fee=Decimal("0.0005"),
            slippage=Decimal("0.0002"),
        )
        
        engine = BacktestEngine(config)
        engine.load_data("BTC-USDT-SWAP", klines)
        
        strategy = FundingRateStrategyV2({
            'high_funding_threshold': hi,
            'low_funding_threshold': lo,
            'trend_ma_period': ma,
            'trend_strength_threshold': trend,
            'momentum_threshold': mom,
            'position_size': pos,
            'cooldown_hours': cool,
            'trend_follow_mode': True,
        })
        
        result = engine.run(strategy)
        ret = float(result.total_return) * 100
        print(f"{name:<12} {ret:>7.2f}% {result.total_trades:>6} {result.win_rate*100:>6.1f}% {result.profit_factor:>7.2f} {float(result.max_drawdown)*100:>6.2f}%")


if __name__ == "__main__":
    run_tune()

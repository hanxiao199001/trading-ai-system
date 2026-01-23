"""
90天数据回测
"""
from decimal import Decimal
from backtest.engine import BacktestEngine
from backtest.types import BacktestConfig
from backtest.data_loader import DataLoader
from strategies.funding_rate.strategy_v2 import FundingRateStrategyV2


def run_90d():
    # 加载90天数据
    klines = DataLoader.load_from_csv("data/btc_usdt_swap_90d.csv", "BTC-USDT-SWAP")
    
    print("=" * 60)
    print("90天真实数据回测")
    print("=" * 60)
    print(f"数据: {len(klines)} 条K线")
    print(f"时间: {klines[0].timestamp.date()} 至 {klines[-1].timestamp.date()}")
    print(f"价格: ${float(min(k.close for k in klines)):,.0f} - ${float(max(k.close for k in klines)):,.0f}")
    
    test_cases = [
        ('顺势-宽松', 0.00005, -0.00005, 12, 0.003, 0.001, 0.25, 2, True),
        ('顺势-标准', 0.0001, -0.0001, 20, 0.005, 0.002, 0.20, 4, True),
        ('顺势-激进', 0.00003, -0.00003, 8, 0.002, 0.0008, 0.30, 1, True),
        ('逆势-宽松', 0.00005, -0.00005, 12, 0.003, 0.001, 0.25, 2, False),
    ]
    
    print(f"\n{'策略':<12} {'收益':>10} {'交易':>7} {'胜率':>8} {'盈亏比':>8} {'回撤':>8} {'夏普':>8}")
    print("-" * 65)
    
    best_ret = -999
    best_name = ""
    best_result = None
    
    for name, hi, lo, ma, trend, mom, pos, cool, follow in test_cases:
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
            'trend_follow_mode': follow,
        })
        
        result = engine.run(strategy)
        ret = float(result.total_return) * 100
        
        print(f"{name:<12} {ret:>9.2f}% {result.total_trades:>7} {result.win_rate*100:>7.1f}% {result.profit_factor:>8.2f} {float(result.max_drawdown)*100:>7.2f}% {result.sharpe_ratio:>8.2f}")
        
        if ret > best_ret:
            best_ret = ret
            best_name = name
            best_result = result
    
    print("-" * 65)
    print(f"\n最佳: {best_name} ({best_ret:.2f}%)")
    
    if best_result and best_result.total_trades > 0:
        days = best_result.duration_days
        annual = best_ret * (365 / days) if days > 0 else 0
        print(f"\n详细:")
        print(f"  周期: {days} 天")
        print(f"  年化收益: {annual:.1f}%")
        print(f"  最终资金: ${float(best_result.final_capital):,.2f}")
        print(f"  总交易: {best_result.total_trades} 笔")
        print(f"  盈/亏: {best_result.winning_trades}/{best_result.losing_trades}")


if __name__ == "__main__":
    run_90d()

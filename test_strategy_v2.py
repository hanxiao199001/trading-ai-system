"""
测试优化后的资金费率策略V2
"""
from decimal import Decimal
from backtest.engine import BacktestEngine
from backtest.types import BacktestConfig
from backtest.data_loader import DataLoader
from strategies.funding_rate.strategy_v2 import FundingRateStrategyV2


def run_v2_backtest():
    print("=" * 70)
    print("Trading AI System - 资金费率策略V2测试")
    print("=" * 70)
    
    # 加载数据
    klines = DataLoader.load_from_csv("data/btc_usdt_swap_30d.csv", "BTC-USDT-SWAP")
    print(f"数据: {len(klines)} 条K线")
    print(f"价格范围: ${float(min(k.close for k in klines)):,.0f} - ${float(max(k.close for k in klines)):,.0f}")
    
    # 测试参数组合
    test_cases = [
        {
            'name': '顺势-宽松',
            'params': {
                'high_funding_threshold': 0.00005,
                'low_funding_threshold': -0.00005,
                'trend_ma_period': 12,
                'trend_strength_threshold': 0.003,
                'momentum_threshold': 0.001,
                'position_size': 0.25,
                'cooldown_hours': 2,
                'trend_follow_mode': True,
            }
        },
        {
            'name': '顺势-标准',
            'params': {
                'high_funding_threshold': 0.0001,
                'low_funding_threshold': -0.0001,
                'trend_ma_period': 20,
                'trend_strength_threshold': 0.005,
                'momentum_threshold': 0.002,
                'position_size': 0.20,
                'cooldown_hours': 4,
                'trend_follow_mode': True,
            }
        },
        {
            'name': '顺势-严格',
            'params': {
                'high_funding_threshold': 0.0002,
                'low_funding_threshold': -0.0002,
                'trend_ma_period': 24,
                'trend_strength_threshold': 0.008,
                'momentum_threshold': 0.003,
                'position_size': 0.15,
                'cooldown_hours': 6,
                'trend_follow_mode': True,
            }
        },
        {
            'name': '逆势-宽松',
            'params': {
                'high_funding_threshold': 0.00005,
                'low_funding_threshold': -0.00005,
                'trend_ma_period': 12,
                'trend_strength_threshold': 0.003,
                'momentum_threshold': 0.001,
                'position_size': 0.25,
                'cooldown_hours': 2,
                'trend_follow_mode': False,
            }
        },
    ]
    
    print(f"\n{'策略':<15} {'收益率':>10} {'交易':>8} {'胜率':>8} {'盈亏比':>8} {'回撤':>8} {'夏普':>8}")
    print("-" * 70)
    
    best_result = None
    best_return = -999
    best_name = ""
    
    for case in test_cases:
        config = BacktestConfig(
            start_time=klines[0].timestamp,
            end_time=klines[-1].timestamp,
            initial_capital=Decimal("100000"),
            taker_fee=Decimal("0.0005"),
            slippage=Decimal("0.0002"),
        )
        
        engine = BacktestEngine(config)
        engine.load_data("BTC-USDT-SWAP", klines)
        
        strategy = FundingRateStrategyV2(case['params'])
        result = engine.run(strategy)
        
        ret = float(result.total_return) * 100
        trades = result.total_trades
        win_rate = result.win_rate * 100
        pf = result.profit_factor
        mdd = float(result.max_drawdown) * 100
        sharpe = result.sharpe_ratio
        
        print(f"{case['name']:<15} {ret:>9.2f}% {trades:>8} {win_rate:>7.1f}% {pf:>8.2f} {mdd:>7.2f}% {sharpe:>8.2f}")
        
        if ret > best_return:
            best_return = ret
            best_result = result
            best_name = case['name']
    
    print("-" * 70)
    print(f"\n最佳: {best_name} ({best_return:.2f}%)")
    
    if best_result and best_result.total_trades > 0:
        print(f"\n详细:")
        print(f"  最终资金: ${float(best_result.final_capital):,.2f}")
        print(f"  平均盈利: ${float(best_result.avg_win):,.2f}")
        print(f"  平均亏损: ${float(best_result.avg_loss):,.2f}")


if __name__ == "__main__":
    run_v2_backtest()

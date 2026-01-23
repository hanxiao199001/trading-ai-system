"""
使用真实OKX数据进行回测 - 参数优化版
"""
from datetime import datetime
from decimal import Decimal

from backtest.engine import BacktestEngine
from backtest.types import BacktestConfig
from backtest.data_loader import DataLoader
from strategies.funding_rate.strategy import FundingRateStrategy


def run_backtest_with_params(high_threshold, low_threshold, position_size, min_holding):
    """用指定参数运行回测"""
    klines = DataLoader.load_from_csv("data/btc_usdt_swap_30d.csv", "BTC-USDT-SWAP")
    
    config = BacktestConfig(
        start_time=klines[0].timestamp,
        end_time=klines[-1].timestamp,
        initial_capital=Decimal("100000"),
        taker_fee=Decimal("0.0005"),
        slippage=Decimal("0.0002"),
    )
    
    engine = BacktestEngine(config)
    engine.load_data("BTC-USDT-SWAP", klines)
    
    strategy = FundingRateStrategy({
        'high_funding_threshold': high_threshold,
        'low_funding_threshold': low_threshold,
        'min_holding_hours': min_holding,
        'position_size': position_size,
    })
    
    return engine.run(strategy)


def main():
    print("=" * 70)
    print("Trading AI System - 参数优化测试")
    print("=" * 70)
    
    # 测试不同参数组合
    test_cases = [
        # (high_threshold, low_threshold, position_size, min_holding, 描述)
        (0.00001, -0.00003, 0.25, 4, "原始参数"),
        (0.00005, -0.00005, 0.20, 8, "提高阈值+延长持仓"),
        (0.0001, -0.0001, 0.15, 12, "高阈值+长持仓"),
        (0.00003, -0.00004, 0.30, 6, "中等阈值"),
        (0.00002, -0.00002, 0.10, 16, "保守策略"),
    ]
    
    print(f"\n{'参数描述':<20} {'收益率':>10} {'交易次数':>10} {'胜率':>10} {'盈亏比':>10} {'最大回撤':>10}")
    print("-" * 70)
    
    best_result = None
    best_return = -999
    best_desc = ""
    
    for high_th, low_th, pos_size, min_hold, desc in test_cases:
        result = run_backtest_with_params(high_th, low_th, pos_size, min_hold)
        
        ret = float(result.total_return) * 100
        trades = result.total_trades
        win_rate = result.win_rate * 100
        pf = result.profit_factor
        mdd = float(result.max_drawdown) * 100
        
        print(f"{desc:<20} {ret:>9.2f}% {trades:>10} {win_rate:>9.1f}% {pf:>10.2f} {mdd:>9.2f}%")
        
        if ret > best_return:
            best_return = ret
            best_result = result
            best_desc = desc
    
    print("-" * 70)
    print(f"\n最佳参数: {best_desc}")
    print(f"最佳收益: {best_return:.2f}%")
    
    if best_result:
        print(f"\n详细结果:")
        print(f"  最终资金: ${float(best_result.final_capital):,.2f}")
        print(f"  总交易: {best_result.total_trades}")
        print(f"  夏普比率: {best_result.sharpe_ratio:.2f}")


if __name__ == "__main__":
    main()

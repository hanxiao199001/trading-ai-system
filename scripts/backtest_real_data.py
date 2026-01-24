#!/usr/bin/env python3
"""
使用真实OKX数据进行回测
"""
import sys
from pathlib import Path
import pandas as pd
from datetime import datetime
from decimal import Decimal
import logging

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.engine import BacktestEngine
from backtest.types import BacktestConfig, BacktestMode
from backtest.data_loader import DataLoader, KlineData
from backtest.visualizer import BacktestVisualizer
from strategies.funding_rate.strategy import FundingRateStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_csv_to_klines(csv_path: str) -> list:
    """加载CSV数据转换为KlineData列表"""
    df = pd.read_csv(csv_path)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    klines = []
    for _, row in df.iterrows():
        kline = KlineData(
            timestamp=row['timestamp'].to_pydatetime(),
            open=Decimal(str(row['open'])),
            high=Decimal(str(row['high'])),
            low=Decimal(str(row['low'])),
            close=Decimal(str(row['close'])),
            volume=Decimal(str(row['volume'])),
            funding_rate=Decimal(str(row['funding_rate'])) if pd.notna(row.get('funding_rate')) else None
        )
        klines.append(kline)

    return klines


def run_single_backtest(klines, params, initial_capital=10000):
    """运行单次回测"""
    if not klines:
        return None

    config = BacktestConfig(
        start_time=klines[0].timestamp,
        end_time=klines[-1].timestamp,
        initial_capital=Decimal(str(initial_capital)),
        maker_fee=Decimal("0.0002"),
        taker_fee=Decimal("0.0005"),
        slippage=Decimal("0.0001"),
        mode=BacktestMode.FULL,
        symbols=["BTC-USDT-SWAP"],
        max_position_size=Decimal("0.3"),
        strategy_params=params
    )

    engine = BacktestEngine(config)
    engine.load_data("BTC-USDT-SWAP", klines)

    strategy = FundingRateStrategy(config=params)
    result = engine.run(strategy)

    return result


def parameter_grid_search(klines):
    """参数网格搜索"""
    logger.info("=" * 60)
    logger.info("  参数优化 - 网格搜索")
    logger.info("=" * 60)

    # 参数网格 (调整为匹配真实费率范围: -0.006% ~ 0.01%)
    # 费率值是小数形式: 0.00005 = 0.005%
    high_thresholds = [0.00004, 0.00005, 0.00006, 0.00007, 0.00008]  # 0.004% ~ 0.008%
    low_thresholds = [-0.00002, -0.00003, -0.00004, -0.00005]  # -0.002% ~ -0.005%

    results = []
    total = len(high_thresholds) * len(low_thresholds)
    count = 0

    for high_t in high_thresholds:
        for low_t in low_thresholds:
            count += 1
            params = {
                "high_funding_threshold": high_t,
                "low_funding_threshold": low_t,
                "min_holding_hours": 8,
                "position_size": 0.3,
            }

            result = run_single_backtest(klines, params)
            if result:
                results.append({
                    "high_threshold": high_t,
                    "low_threshold": low_t,
                    "total_return": float(result.total_return),
                    "sharpe_ratio": result.sharpe_ratio,
                    "max_drawdown": float(result.max_drawdown),
                    "total_trades": result.total_trades,
                    "win_rate": result.win_rate,
                    "profit_factor": result.profit_factor,
                })

                logger.info(f"[{count}/{total}] 阈值[{high_t:.4f}, {low_t:.4f}] "
                           f"收益:{float(result.total_return):.2%} "
                           f"夏普:{result.sharpe_ratio:.2f} "
                           f"交易:{result.total_trades}笔")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="真实数据回测")
    parser.add_argument("--data", default="data/btc_funding_90d.csv", help="数据文件")
    parser.add_argument("--mode", choices=["single", "optimize"], default="single")
    parser.add_argument("--capital", type=float, default=10000, help="初始资金")

    args = parser.parse_args()

    # 加载数据
    logger.info(f"加载数据: {args.data}")
    klines = load_csv_to_klines(args.data)
    logger.info(f"加载完成: {len(klines)}条K线")

    if args.mode == "single":
        # 单次回测（使用默认参数）
        params = {
            "high_funding_threshold": 0.0005,  # 0.05%
            "low_funding_threshold": -0.0005,  # -0.05%
            "min_holding_hours": 8,
            "position_size": 0.3,
        }

        result = run_single_backtest(klines, params, args.capital)

        if result:
            print(result)

            # 生成报告
            visualizer = BacktestVisualizer(result)
            visualizer.generate_report(save_path="backtest_real_data.png", show=False)
            visualizer.save_html_report("backtest_real_data.html")

            logger.info("报告已生成: backtest_real_data.png, backtest_real_data.html")

    elif args.mode == "optimize":
        # 参数优化
        results = parameter_grid_search(klines)

        if results:
            # 按夏普比率排序
            results.sort(key=lambda x: x["sharpe_ratio"], reverse=True)

            print("\n" + "=" * 80)
            print("  参数优化结果 (按夏普比率排序)")
            print("=" * 80)
            print(f"{'做空阈值':>10} {'做多阈值':>10} {'收益率':>10} {'夏普':>8} {'回撤':>8} {'交易':>6} {'胜率':>8}")
            print("-" * 80)

            for r in results[:10]:  # 显示前10名
                print(f"{r['high_threshold']:>10.4%} {r['low_threshold']:>10.4%} "
                      f"{r['total_return']:>10.2%} {r['sharpe_ratio']:>8.2f} "
                      f"{r['max_drawdown']:>8.2%} {r['total_trades']:>6} {r['win_rate']:>8.2%}")

            print("=" * 80)

            # 使用最优参数重新回测并生成报告
            best = results[0]
            logger.info(f"\n使用最优参数生成详细报告...")

            best_params = {
                "high_funding_threshold": best["high_threshold"],
                "low_funding_threshold": best["low_threshold"],
                "min_holding_hours": 8,
                "position_size": 0.3,
            }

            best_result = run_single_backtest(klines, best_params, args.capital)
            if best_result:
                print(best_result)

                visualizer = BacktestVisualizer(best_result)
                visualizer.generate_report(save_path="backtest_optimized.png", show=False)
                visualizer.save_html_report("backtest_optimized.html")

                logger.info("最优参数报告: backtest_optimized.png, backtest_optimized.html")

            # 保存所有结果到CSV
            pd.DataFrame(results).to_csv("optimization_results.csv", index=False)
            logger.info("优化结果已保存: optimization_results.csv")


if __name__ == "__main__":
    main()

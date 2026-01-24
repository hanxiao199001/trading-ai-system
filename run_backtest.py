#!/usr/bin/env python3
"""
回测示例脚本
用于测试资金费率策略在历史数据上的表现
"""
import sys
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from backtest.engine import BacktestEngine
from backtest.types import BacktestConfig, BacktestMode
from backtest.data_loader import DataLoader
from backtest.visualizer import BacktestVisualizer
from strategies.funding_rate.strategy import FundingRateStrategy

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def run_backtest_with_sample_data():
    """使用示例数据运行回测"""
    logger.info("=" * 60)
    logger.info("  资金费率策略回测")
    logger.info("=" * 60)

    # 1. 配置回测参数
    start_time = datetime(2024, 1, 1)
    end_time = datetime(2024, 3, 1)

    config = BacktestConfig(
        start_time=start_time,
        end_time=end_time,
        initial_capital=Decimal("10000"),  # 10000 USDT
        maker_fee=Decimal("0.0002"),       # 0.02%
        taker_fee=Decimal("0.0005"),       # 0.05%
        slippage=Decimal("0.0001"),        # 0.01%
        mode=BacktestMode.FULL,
        symbols=["BTC-USDT-SWAP"],
        max_position_size=Decimal("0.3"),  # 30%仓位
        strategy_params={
            "high_funding_threshold": 0.0003,  # 0.03% 做空阈值
            "low_funding_threshold": -0.0003,  # -0.03% 做多阈值
            "min_holding_hours": 8,
            "position_size": 0.3,
        }
    )

    logger.info(f"回测周期: {start_time.date()} - {end_time.date()}")
    logger.info(f"初始资金: ${config.initial_capital}")
    logger.info(f"交易费率: maker={config.maker_fee:.4%}, taker={config.taker_fee:.4%}")

    # 2. 创建回测引擎
    engine = BacktestEngine(config)

    # 3. 加载数据（使用生成的示例数据）
    logger.info("生成示例K线数据...")
    sample_klines = DataLoader.generate_sample_data(
        symbol="BTC-USDT-SWAP",
        start_time=start_time,
        end_time=end_time,
        interval_hours=8  # 8小时K线（与资金费率结算周期匹配）
    )
    engine.load_data("BTC-USDT-SWAP", sample_klines)

    # 4. 创建策略
    strategy = FundingRateStrategy(config=config.strategy_params)

    # 5. 运行回测
    logger.info("开始回测...")
    result = engine.run(strategy)

    # 6. 输出结果
    print(result)

    # 7. 生成可视化报告
    logger.info("生成可视化报告...")
    visualizer = BacktestVisualizer(result)

    # 保存图表
    chart_path = "backtest_report.png"
    visualizer.generate_report(save_path=chart_path, show=False)

    # 保存HTML报告
    html_path = "backtest_report.html"
    visualizer.save_html_report(html_path)

    logger.info("=" * 60)
    logger.info("  回测完成")
    logger.info("=" * 60)
    logger.info(f"图表报告: {chart_path}")
    logger.info(f"HTML报告: {html_path}")

    return result


def run_backtest_with_csv(csv_path: str):
    """使用CSV数据运行回测"""
    logger.info(f"从CSV加载数据: {csv_path}")

    # 加载数据
    klines = DataLoader.load_from_csv(
        filepath=csv_path,
        symbol="BTC-USDT-SWAP"
    )

    if not klines:
        logger.error("无法加载数据")
        return None

    # 配置
    config = BacktestConfig(
        start_time=klines[0].timestamp,
        end_time=klines[-1].timestamp,
        initial_capital=Decimal("10000"),
        symbols=["BTC-USDT-SWAP"],
        strategy_params={
            "high_funding_threshold": 0.0005,
            "low_funding_threshold": -0.0005,
        }
    )

    # 运行回测
    engine = BacktestEngine(config)
    engine.load_data("BTC-USDT-SWAP", klines)

    strategy = FundingRateStrategy(config=config.strategy_params)
    result = engine.run(strategy)

    print(result)
    return result


def parameter_optimization():
    """参数优化示例"""
    logger.info("=" * 60)
    logger.info("  参数优化")
    logger.info("=" * 60)

    start_time = datetime(2024, 1, 1)
    end_time = datetime(2024, 3, 1)

    # 生成数据
    sample_klines = DataLoader.generate_sample_data(
        symbol="BTC-USDT-SWAP",
        start_time=start_time,
        end_time=end_time,
        interval_hours=8
    )

    # 参数网格
    thresholds = [0.0002, 0.0003, 0.0005, 0.0008]
    results = []

    for high_threshold in thresholds:
        for low_threshold in [-t for t in thresholds]:
            config = BacktestConfig(
                start_time=start_time,
                end_time=end_time,
                initial_capital=Decimal("10000"),
                symbols=["BTC-USDT-SWAP"],
                strategy_params={
                    "high_funding_threshold": high_threshold,
                    "low_funding_threshold": low_threshold,
                }
            )

            engine = BacktestEngine(config)
            engine.load_data("BTC-USDT-SWAP", sample_klines)

            strategy = FundingRateStrategy(config=config.strategy_params)
            result = engine.run(strategy)

            results.append({
                "high_threshold": high_threshold,
                "low_threshold": low_threshold,
                "total_return": float(result.total_return),
                "sharpe_ratio": result.sharpe_ratio,
                "max_drawdown": float(result.max_drawdown),
                "total_trades": result.total_trades,
                "win_rate": result.win_rate,
            })

            logger.info(f"阈值 [{high_threshold:.4f}, {low_threshold:.4f}] -> "
                       f"收益: {float(result.total_return):.2%}, "
                       f"夏普: {result.sharpe_ratio:.2f}")

    # 找到最优参数
    best = max(results, key=lambda x: x["sharpe_ratio"])

    logger.info("\n" + "=" * 60)
    logger.info("  最优参数")
    logger.info("=" * 60)
    logger.info(f"做空阈值: {best['high_threshold']:.4%}")
    logger.info(f"做多阈值: {best['low_threshold']:.4%}")
    logger.info(f"总收益率: {best['total_return']:.2%}")
    logger.info(f"夏普比率: {best['sharpe_ratio']:.2f}")
    logger.info(f"最大回撤: {best['max_drawdown']:.2%}")
    logger.info(f"交易次数: {best['total_trades']}")
    logger.info(f"胜率: {best['win_rate']:.2%}")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="资金费率策略回测")
    parser.add_argument(
        "--mode",
        choices=["sample", "csv", "optimize"],
        default="sample",
        help="回测模式: sample(示例数据), csv(CSV文件), optimize(参数优化)"
    )
    parser.add_argument(
        "--csv",
        type=str,
        help="CSV数据文件路径"
    )

    args = parser.parse_args()

    if args.mode == "sample":
        run_backtest_with_sample_data()
    elif args.mode == "csv":
        if not args.csv:
            print("请指定CSV文件路径: --csv path/to/data.csv")
            sys.exit(1)
        run_backtest_with_csv(args.csv)
    elif args.mode == "optimize":
        parameter_optimization()


if __name__ == "__main__":
    main()

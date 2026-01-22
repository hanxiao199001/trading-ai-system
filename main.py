#!/usr/bin/env python3
"""
Trading AI System - 入口文件

使用方法:
    # 运行交易系统
    python main.py run

    # 单次分析（调试）
    python main.py analyze --symbol BTC-USDT-SWAP

    # 查看系统状态
    python main.py status
"""
import asyncio
import argparse
import logging
import os
import sys
from pathlib import Path

import yaml

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent))

from core.engine import TradingEngine
from core.event_bus import get_event_bus
from exchanges.okx import OKXExchange
from strategies.funding_rate import FundingRateStrategy
from risk.manager import RiskManager


def setup_logging(level: str = "INFO") -> None:
    """配置日志"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_config(config_path: str = "config/settings.yaml") -> dict:
    """加载配置文件"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_engine(config: dict) -> TradingEngine:
    """根据配置创建交易引擎"""
    # 创建风控管理器
    risk_config = config.get("risk", {})
    risk_manager = RiskManager(
        stop_loss_pct=risk_config.get("stop_loss_pct", 0.02),
        take_profit_pct=risk_config.get("take_profit_pct", 0.015),
        position_size_pct=risk_config.get("position_size_pct", 0.30),
        max_leverage=risk_config.get("max_leverage", 1),
        max_positions=risk_config.get("max_positions", 3),
        daily_loss_limit_pct=risk_config.get("daily_loss_limit_pct", 0.05),
        min_order_value=risk_config.get("min_order_value", 10.0),
    )

    # 创建引擎
    engine = TradingEngine(risk_manager=risk_manager)

    # 注册交易所
    exchanges_config = config.get("exchanges", {})

    if exchanges_config.get("okx", {}).get("enabled", False):
        okx = OKXExchange(
            api_key=os.environ.get("OKX_API_KEY", ""),
            api_secret=os.environ.get("OKX_API_SECRET", ""),
            passphrase=os.environ.get("OKX_PASSPHRASE", ""),
            testnet=exchanges_config["okx"].get("testnet", True),
        )
        engine.register_exchange(okx)

    # 注册策略
    strategies_config = config.get("strategies", {})

    if strategies_config.get("funding_rate", {}).get("enabled", False):
        fr_config = strategies_config["funding_rate"]
        strategy = FundingRateStrategy(
            config=fr_config.get("params", {}),
            risk_manager=risk_manager,
        )
        engine.register_strategy(
            strategy,
            exchange="okx",
            symbols=fr_config.get("symbols", ["BTC-USDT-SWAP"]),
        )

    return engine


async def cmd_run(args, config: dict) -> None:
    """运行交易系统"""
    engine = create_engine(config)
    interval = config.get("data", {}).get("fetch_interval", 300)

    print(f"Starting trading system with {interval}s interval...")
    print("Press Ctrl+C to stop")

    try:
        await engine.start(interval=interval)
    except KeyboardInterrupt:
        print("\nShutting down...")
        await engine.stop()


async def cmd_analyze(args, config: dict) -> None:
    """单次分析"""
    engine = create_engine(config)

    # 连接交易所
    for exchange in engine._exchanges.values():
        await exchange.connect()

    try:
        result = await engine.run_once(args.symbol, args.exchange)

        print("\n" + "=" * 50)
        print(f"Analysis Result for {result['symbol']}")
        print("=" * 50)
        print(f"Exchange:     {result['exchange']}")
        print(f"Timestamp:    {result['timestamp']}")
        print(f"Price:        ${result['price']:,.2f}")
        print(f"Funding Rate: {result['funding_rate']:.4%}" if result['funding_rate'] else "Funding Rate: N/A")
        print("\nSignals:")
        for strategy, signal in result.get("signals", {}).items():
            print(f"  {strategy}: {signal}")
        print("=" * 50 + "\n")

    finally:
        for exchange in engine._exchanges.values():
            await exchange.disconnect()


async def cmd_status(args, config: dict) -> None:
    """显示系统状态"""
    engine = create_engine(config)

    print("\n" + "=" * 50)
    print("Trading AI System Status")
    print("=" * 50)

    print("\nExchanges:")
    for name in engine._exchanges:
        print(f"  - {name}")

    print("\nStrategies:")
    for key, cfg in engine._strategies.items():
        strategy = cfg["strategy"]
        print(f"  - {strategy.name}")
        print(f"      Exchange: {cfg['exchange']}")
        print(f"      Symbols:  {cfg['symbols']}")
        print(f"      Enabled:  {strategy.enabled}")

    print("\nRisk Manager:")
    status = engine.risk_manager.get_status()
    for key, value in status.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.2%}")
        else:
            print(f"  {key}: {value}")

    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Trading AI System")
    parser.add_argument(
        "--config",
        default="config/settings.yaml",
        help="Path to config file"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run命令
    run_parser = subparsers.add_parser("run", help="Run trading system")

    # analyze命令
    analyze_parser = subparsers.add_parser("analyze", help="Single analysis")
    analyze_parser.add_argument(
        "--symbol",
        default="BTC-USDT-SWAP",
        help="Trading symbol"
    )
    analyze_parser.add_argument(
        "--exchange",
        default="okx",
        help="Exchange name"
    )

    # status命令
    status_parser = subparsers.add_parser("status", help="Show system status")

    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)
    setup_logging(config.get("system", {}).get("log_level", "INFO"))

    # 执行命令
    if args.command == "run":
        asyncio.run(cmd_run(args, config))
    elif args.command == "analyze":
        asyncio.run(cmd_analyze(args, config))
    elif args.command == "status":
        asyncio.run(cmd_status(args, config))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

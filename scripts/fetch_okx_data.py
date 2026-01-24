#!/usr/bin/env python3
"""
OKX历史数据爬取脚本
获取K线和资金费率数据用于回测
"""
import asyncio
import aiohttp
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import logging
import sys
import time

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class OKXDataFetcher:
    """OKX历史数据获取器"""

    BASE_URL = "https://www.okx.com"

    # 时间间隔映射
    INTERVALS = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1H",
        "4h": "4H",
        "1d": "1D",
    }

    def __init__(self):
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    async def _request(self, endpoint: str, params: dict = None) -> dict:
        """发送请求"""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            async with self.session.get(url, params=params, timeout=30) as resp:
                data = await resp.json()
                if data.get("code") != "0":
                    logger.warning(f"API错误: {data.get('msg')}")
                return data
        except Exception as e:
            logger.error(f"请求失败: {e}")
            return {"code": "-1", "data": []}

    async def fetch_klines(
        self,
        symbol: str,
        interval: str = "1h",
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        获取K线数据

        Args:
            symbol: 交易对 (如 BTC-USDT-SWAP)
            interval: K线周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 每次请求数量

        Returns:
            DataFrame: K线数据
        """
        bar = self.INTERVALS.get(interval, "1H")
        all_klines = []

        # 计算时间范围
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(days=30)

        current_end = end_time

        while current_end > start_time:
            params = {
                "instId": symbol,
                "bar": bar,
                "limit": str(limit),
                "after": str(int(current_end.timestamp() * 1000)),
            }

            data = await self._request("/api/v5/market/candles", params)

            if data.get("code") != "0" or not data.get("data"):
                break

            klines = data["data"]
            if not klines:
                break

            all_klines.extend(klines)

            # 更新时间游标
            oldest_ts = int(klines[-1][0])
            current_end = datetime.fromtimestamp(oldest_ts / 1000)

            logger.info(f"获取K线: {len(klines)}条, 最早: {current_end}")

            # 避免请求过快
            await asyncio.sleep(0.2)

            if current_end <= start_time:
                break

        if not all_klines:
            return pd.DataFrame()

        # 转换为DataFrame
        df = pd.DataFrame(all_klines, columns=[
            "timestamp", "open", "high", "low", "close",
            "volume", "volume_ccy", "volume_ccy_quote", "confirm"
        ])

        df["timestamp"] = pd.to_datetime(df["timestamp"].astype(int), unit="ms")
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        df = df.sort_values("timestamp").reset_index(drop=True)

        # 过滤时间范围
        df = df[(df["timestamp"] >= start_time) & (df["timestamp"] <= end_time)]

        logger.info(f"K线数据获取完成: {len(df)}条")
        return df

    async def fetch_funding_rate_history(
        self,
        symbol: str,
        start_time: datetime = None,
        end_time: datetime = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        获取历史资金费率

        Args:
            symbol: 交易对
            start_time: 开始时间
            end_time: 结束时间

        Returns:
            DataFrame: 资金费率数据
        """
        all_rates = []

        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(days=30)

        current_end = end_time

        while current_end > start_time:
            params = {
                "instId": symbol,
                "limit": str(limit),
                "after": str(int(current_end.timestamp() * 1000)),
            }

            data = await self._request("/api/v5/public/funding-rate-history", params)

            if data.get("code") != "0" or not data.get("data"):
                break

            rates = data["data"]
            if not rates:
                break

            all_rates.extend(rates)

            # 更新时间游标
            oldest_ts = int(rates[-1]["fundingTime"])
            current_end = datetime.fromtimestamp(oldest_ts / 1000)

            logger.info(f"获取资金费率: {len(rates)}条, 最早: {current_end}")

            await asyncio.sleep(0.2)

            if current_end <= start_time:
                break

        if not all_rates:
            return pd.DataFrame()

        # 转换为DataFrame
        df = pd.DataFrame(all_rates)
        df["timestamp"] = pd.to_datetime(df["fundingTime"].astype(int), unit="ms")
        df["funding_rate"] = df["fundingRate"].astype(float)
        df["realized_rate"] = df["realizedRate"].astype(float) if "realizedRate" in df.columns else None

        df = df[["timestamp", "funding_rate", "realized_rate"]]
        df = df.sort_values("timestamp").reset_index(drop=True)

        # 过滤时间范围
        df = df[(df["timestamp"] >= start_time) & (df["timestamp"] <= end_time)]

        logger.info(f"资金费率数据获取完成: {len(df)}条")
        return df

    async def fetch_combined_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        kline_interval: str = "1h",
    ) -> pd.DataFrame:
        """
        获取合并的K线和资金费率数据

        Args:
            symbol: 交易对
            start_time: 开始时间
            end_time: 结束时间
            kline_interval: K线周期

        Returns:
            DataFrame: 合并数据
        """
        logger.info(f"获取 {symbol} 数据: {start_time.date()} - {end_time.date()}")

        # 并行获取K线和资金费率
        klines_task = self.fetch_klines(symbol, kline_interval, start_time, end_time)
        funding_task = self.fetch_funding_rate_history(symbol, start_time, end_time)

        klines_df, funding_df = await asyncio.gather(klines_task, funding_task)

        if klines_df.empty:
            logger.warning("无K线数据")
            return pd.DataFrame()

        # 合并数据
        if not funding_df.empty:
            # 将资金费率按时间对齐到K线
            klines_df = klines_df.set_index("timestamp")
            funding_df = funding_df.set_index("timestamp")

            # 前向填充资金费率
            combined = klines_df.join(funding_df, how="left")
            combined["funding_rate"] = combined["funding_rate"].ffill()
            combined = combined.reset_index()
        else:
            combined = klines_df
            combined["funding_rate"] = None

        logger.info(f"合并数据完成: {len(combined)}条")
        return combined


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="OKX历史数据获取")
    parser.add_argument("--symbol", default="BTC-USDT-SWAP", help="交易对")
    parser.add_argument("--days", type=int, default=90, help="获取天数")
    parser.add_argument("--interval", default="8h", help="K线周期")
    parser.add_argument("--output", default="data/okx_history.csv", help="输出文件")

    args = parser.parse_args()

    end_time = datetime.now()
    start_time = end_time - timedelta(days=args.days)

    # 创建数据目录
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with OKXDataFetcher() as fetcher:
        df = await fetcher.fetch_combined_data(
            symbol=args.symbol,
            start_time=start_time,
            end_time=end_time,
            kline_interval=args.interval,
        )

        if not df.empty:
            df.to_csv(output_path, index=False)
            logger.info(f"数据已保存: {output_path}")

            # 显示统计信息
            print("\n" + "=" * 50)
            print(f"  数据统计 - {args.symbol}")
            print("=" * 50)
            print(f"  时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
            print(f"  数据条数: {len(df)}")
            print(f"  价格范围: ${df['close'].min():,.2f} ~ ${df['close'].max():,.2f}")

            if "funding_rate" in df.columns and df["funding_rate"].notna().any():
                fr = df["funding_rate"].dropna()
                print(f"  资金费率: {fr.min():.4%} ~ {fr.max():.4%}")
                print(f"  平均费率: {fr.mean():.4%}")
            print("=" * 50)
        else:
            logger.error("未获取到数据")


if __name__ == "__main__":
    asyncio.run(main())

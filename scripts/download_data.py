"""
下载OKX历史K线数据（支持代理）
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest.data_loader import DataLoader, KlineData

# 代理配置
PROXY = "http://127.0.0.1:7890"
BASE_URL = "https://www.okx.com"


async def fetch_klines(session, symbol: str, interval: str = "1H", limit: int = 100, after: int = None):
    """获取K线数据"""
    url = f"{BASE_URL}/api/v5/market/candles"
    params = {
        "instId": symbol,
        "bar": interval,
        "limit": str(limit)
    }
    if after:
        params["after"] = str(after)
    
    try:
        async with session.get(url, params=params, proxy=PROXY) as resp:
            data = await resp.json()
            if data.get("code") == "0":
                return data.get("data", [])
            print(f"API错误: {data}")
            return []
    except Exception as e:
        print(f"请求失败: {e}")
        return []


async def fetch_funding_rates(session, symbol: str, limit: int = 100):
    """获取资金费率历史"""
    url = f"{BASE_URL}/api/v5/public/funding-rate-history"
    params = {"instId": symbol, "limit": str(limit)}
    
    try:
        async with session.get(url, params=params, proxy=PROXY) as resp:
            data = await resp.json()
            if data.get("code") == "0":
                return data.get("data", [])
            return []
    except Exception as e:
        print(f"获取资金费率失败: {e}")
        return []


async def download_btc_klines(days: int = 30):
    """下载BTC历史K线"""
    print(f"开始下载最近 {days} 天的BTC K线数据...")
    print(f"使用代理: {PROXY}")
    
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    print(f"时间范围: {start_time.strftime('%Y-%m-%d')} 至 {end_time.strftime('%Y-%m-%d')}")
    
    symbol = "BTC-USDT-SWAP"
    all_klines = []
    after = None
    
    async with aiohttp.ClientSession() as session:
        # 分页获取K线
        target_count = days * 24
        print(f"目标获取: {target_count} 条K线")
        
        while len(all_klines) < target_count:
            batch = await fetch_klines(session, symbol, "1H", 100, after)
            
            if not batch:
                break
            
            all_klines.extend(batch)
            after = batch[-1][0]  # 最后一条的时间戳
            
            print(f"  已获取: {len(all_klines)} 条")
            await asyncio.sleep(0.2)  # 避免频率限制
        
        if not all_klines:
            print("获取K线数据失败!")
            return
        
        # 获取资金费率
        print("获取资金费率历史...")
        fr_data = await fetch_funding_rates(session, symbol, 100)
    
    # 处理资金费率映射
    fr_map = {}
    for item in fr_data:
        ts = datetime.fromtimestamp(int(item['fundingTime']) / 1000)
        aligned = ts.replace(hour=(ts.hour // 8) * 8, minute=0, second=0, microsecond=0)
        fr_map[aligned] = float(item['fundingRate'])
    
    # 转换为KlineData对象
    klines = []
    for item in all_klines:
        ts = datetime.fromtimestamp(int(item[0]) / 1000)
        aligned = ts.replace(hour=(ts.hour // 8) * 8, minute=0, second=0, microsecond=0)
        funding_rate = fr_map.get(aligned)
        
        kline = KlineData(
            timestamp=ts,
            open=Decimal(item[1]),
            high=Decimal(item[2]),
            low=Decimal(item[3]),
            close=Decimal(item[4]),
            volume=Decimal(item[5]),
            funding_rate=Decimal(str(funding_rate)) if funding_rate else None
        )
        klines.append(kline)
    
    # 按时间排序
    klines.sort(key=lambda x: x.timestamp)
    
    # 过滤时间范围
    klines = [k for k in klines if k.timestamp >= start_time]
    
    # 保存到CSV
    os.makedirs('data', exist_ok=True)
    filepath = f'data/btc_usdt_swap_{days}d.csv'
    DataLoader.save_to_csv(klines, filepath)
    
    print(f"\n✓ 数据已保存到: {filepath}")
    print(f"  K线数量: {len(klines)}")
    print(f"  价格范围: ${float(min(k.close for k in klines)):,.2f} - ${float(max(k.close for k in klines)):,.2f}")
    print(f"  时间范围: {klines[0].timestamp} 至 {klines[-1].timestamp}")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    asyncio.run(download_btc_klines(days))

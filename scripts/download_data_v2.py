"""
下载OKX历史数据（K线+资金费率）- 修复版
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest.data_loader import DataLoader, KlineData

PROXY = "http://127.0.0.1:7890"
BASE_URL = "https://www.okx.com"


async def fetch_json(session, url, params):
    try:
        async with session.get(url, params=params, proxy=PROXY) as resp:
            return await resp.json()
    except Exception as e:
        print(f"请求失败: {e}")
        return {"code": "-1", "data": []}


async def download_with_funding(days: int = 90):
    print(f"下载 {days} 天数据（含资金费率）...")
    
    symbol = "BTC-USDT-SWAP"
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days)
    
    async with aiohttp.ClientSession() as session:
        # 1. 获取K线
        print("获取K线...")
        all_klines = []
        after = None
        
        while len(all_klines) < days * 24:
            params = {"instId": symbol, "bar": "1H", "limit": "100"}
            if after:
                params["after"] = str(after)
            
            data = await fetch_json(session, f"{BASE_URL}/api/v5/market/candles", params)
            
            if data.get("code") != "0" or not data.get("data"):
                break
            
            all_klines.extend(data["data"])
            after = data["data"][-1][0]
            print(f"  K线: {len(all_klines)}")
            await asyncio.sleep(0.2)
        
        # 2. 获取资金费率历史（分页获取更多）
        print("获取资金费率...")
        all_funding = []
        after_fr = None
        
        for _ in range(20):  # 最多获取2000条
            params = {"instId": symbol, "limit": "100"}
            if after_fr:
                params["after"] = str(after_fr)
            
            data = await fetch_json(session, f"{BASE_URL}/api/v5/public/funding-rate-history", params)
            
            if data.get("code") != "0" or not data.get("data"):
                break
            
            all_funding.extend(data["data"])
            after_fr = data["data"][-1]["fundingTime"]
            print(f"  资金费率: {len(all_funding)}")
            await asyncio.sleep(0.2)
            
            # 检查是否已经超过开始时间
            oldest = datetime.fromtimestamp(int(data["data"][-1]["fundingTime"]) / 1000)
            if oldest < start_time:
                break
    
    print(f"\n获取完成: {len(all_klines)} K线, {len(all_funding)} 资金费率")
    
    # 3. 创建资金费率映射
    fr_map = {}
    for item in all_funding:
        ts = datetime.fromtimestamp(int(item['fundingTime']) / 1000)
        fr_map[ts] = float(item['fundingRate'])
    
    # 4. 合并数据
    klines = []
    for item in all_klines:
        ts = datetime.fromtimestamp(int(item[0]) / 1000)
        if ts < start_time:
            continue
        
        # 找最近的资金费率（每8小时一次）
        aligned = ts.replace(hour=(ts.hour // 8) * 8, minute=0, second=0, microsecond=0)
        funding_rate = fr_map.get(aligned)
        
        # 如果精确匹配不到，找最近的
        if funding_rate is None:
            for offset in [0, 8, -8, 16, -16]:
                check_time = aligned + timedelta(hours=offset)
                if check_time in fr_map:
                    funding_rate = fr_map[check_time]
                    break
        
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
    
    klines.sort(key=lambda x: x.timestamp)
    
    # 统计有资金费率的K线数量
    with_fr = sum(1 for k in klines if k.funding_rate is not None)
    
    # 保存
    os.makedirs('data', exist_ok=True)
    filepath = f'data/btc_usdt_swap_{days}d.csv'
    DataLoader.save_to_csv(klines, filepath)
    
    print(f"\n✓ 保存: {filepath}")
    print(f"  K线: {len(klines)}")
    print(f"  有资金费率: {with_fr} ({with_fr*100/len(klines):.1f}%)")
    print(f"  时间: {klines[0].timestamp} 至 {klines[-1].timestamp}")


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 90
    asyncio.run(download_with_funding(days))

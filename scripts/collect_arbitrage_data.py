#!/usr/bin/env python3
"""
现货-期货套利数据采集脚本
每5分钟采集一次现货价格、期货价格和资金费率
"""
import asyncio
import aiohttp
import sqlite3
from datetime import datetime
from pathlib import Path
import logging
import sys

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class ArbitrageDataCollector:
    """现货-期货套利数据采集器"""
    
    BASE_URL = "https://www.okx.com"
    
    # 要监控的币种
    SYMBOLS = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / 'database' / 'trading.db'
        self.db_path = str(db_path)
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def _request(self, endpoint: str, params: dict = None) -> dict:
        """发送HTTP请求"""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            async with self.session.get(url, params=params, timeout=10) as resp:
                data = await resp.json()
                if data.get("code") != "0":
                    logger.warning(f"API错误: {data.get('msg')}")
                return data
        except Exception as e:
            logger.error(f"请求失败 {endpoint}: {e}")
            return {"code": "-1", "data": []}
    
    async def fetch_spot_price(self, symbol: str) -> dict:
        """获取现货价格"""
        params = {"instId": symbol}
        data = await self._request("/api/v5/market/ticker", params)
        
        if data.get("code") == "0" and data.get("data"):
            ticker = data["data"][0]
            return {
                "symbol": symbol,
                "price": float(ticker["last"]),
                "volume_24h": float(ticker["vol24h"]) if ticker.get("vol24h") else None,
                "bid": float(ticker["bidPx"]) if ticker.get("bidPx") else None,
                "ask": float(ticker["askPx"]) if ticker.get("askPx") else None,
            }
        return None
    
    async def fetch_futures_price(self, symbol: str) -> dict:
        """获取期货价格"""
        futures_symbol = symbol.replace('-USDT', '-USDT-SWAP')
        params = {"instId": futures_symbol}
        data = await self._request("/api/v5/market/ticker", params)
        
        if data.get("code") == "0" and data.get("data"):
            ticker = data["data"][0]
            return {
                "symbol": futures_symbol,
                "price": float(ticker["last"]),
                "mark_price": float(ticker.get("markPx", ticker["last"])),
                "index_price": float(ticker.get("idxPx", ticker["last"])),
                "open_interest": float(ticker.get("openInterest", 0)),
                "volume_24h": float(ticker["vol24h"]) if ticker.get("vol24h") else None,
            }
        return None
    
    async def fetch_funding_rate(self, symbol: str) -> dict:
        """获取资金费率"""
        futures_symbol = symbol.replace('-USDT', '-USDT-SWAP')
        params = {"instId": futures_symbol}
        data = await self._request("/api/v5/public/funding-rate", params)
        
        if data.get("code") == "0" and data.get("data"):
            fr = data["data"][0]
            return {
                "symbol": futures_symbol,
                "funding_rate": float(fr["fundingRate"]),
                "next_funding_time": fr.get("nextFundingTime"),
            }
        return None
    
    def save_to_database(self, spot_data: dict, futures_data: dict, 
                        funding_data: dict, arb_opportunity: dict = None):
        """保存数据到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 1. 保存现货价格
            if spot_data:
                cursor.execute('''
                    INSERT INTO spot_prices 
                    (timestamp, symbol, price, volume_24h, bid, ask)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    spot_data['symbol'],
                    spot_data['price'],
                    spot_data.get('volume_24h'),
                    spot_data.get('bid'),
                    spot_data.get('ask')
                ))
            
            # 2. 保存期货价格
            if futures_data:
                cursor.execute('''
                    INSERT INTO futures_prices 
                    (timestamp, symbol, price, mark_price, index_price, open_interest, volume_24h)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    futures_data['symbol'],
                    futures_data['price'],
                    futures_data.get('mark_price'),
                    futures_data.get('index_price'),
                    futures_data.get('open_interest'),
                    futures_data.get('volume_24h')
                ))
            
            # 3. 保存套利机会
            if arb_opportunity:
                cursor.execute('''
                    INSERT INTO arbitrage_opportunities
                    (timestamp, symbol, spot_price, futures_price, basis, basis_rate,
                     annualized_basis, funding_rate, funding_cost_7d, total_cost, 
                     net_return, is_profitable, arbitrage_type)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    timestamp,
                    arb_opportunity['symbol'],
                    arb_opportunity['spot_price'],
                    arb_opportunity['futures_price'],
                    arb_opportunity['basis'],
                    arb_opportunity['basis_rate'],
                    arb_opportunity['annualized_basis'],
                    arb_opportunity['funding_rate'],
                    arb_opportunity['funding_cost_7d'],
                    arb_opportunity['total_cost'],
                    arb_opportunity['net_return'],
                    arb_opportunity['is_profitable'],
                    arb_opportunity['arbitrage_type']
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"数据库保存失败: {e}")
    
    def calculate_arbitrage_opportunity(self, symbol: str, spot_data: dict, 
                                       futures_data: dict, funding_data: dict) -> dict:
        """计算套利机会"""
        if not all([spot_data, futures_data, funding_data]):
            return None
        
        spot_price = spot_data['price']
        futures_price = futures_data['price']
        funding_rate = funding_data['funding_rate']
        
        # 计算基差
        basis = futures_price - spot_price
        basis_rate = basis / spot_price
        
        # 年化基差 (假设7天持仓)
        annualized_basis = basis_rate * 365 / 7
        
        # 资金费率成本 (7天,每8小时一次)
        funding_cost_7d = funding_rate * 3 * 7
        
        # 手续费成本 (开仓+平仓,现货+期货,按0.05%计算)
        fee_cost = 0.0005 * 4
        
        # 总成本
        total_cost = funding_cost_7d + fee_cost
        
        # 净收益
        net_return = annualized_basis - total_cost
        
        # 判断套利类型
        if basis > 0:
            arbitrage_type = "contango"  # 正向市场
        else:
            arbitrage_type = "backwardation"  # 反向市场
        
        # 是否有利可图 (年化收益 > 5%)
        is_profitable = net_return > 0.05
        
        return {
            "symbol": symbol,
            "spot_price": spot_price,
            "futures_price": futures_price,
            "basis": basis,
            "basis_rate": basis_rate,
            "annualized_basis": annualized_basis,
            "funding_rate": funding_rate,
            "funding_cost_7d": funding_cost_7d,
            "total_cost": total_cost,
            "net_return": net_return,
            "is_profitable": is_profitable,
            "arbitrage_type": arbitrage_type
        }
    
    async def collect_once(self):
        """采集一次数据"""
        logger.info("=" * 60)
        logger.info("开始采集数据...")
        
        for symbol in self.SYMBOLS:
            try:
                # 并行获取3个数据源
                spot_task = self.fetch_spot_price(symbol)
                futures_task = self.fetch_futures_price(symbol)
                funding_task = self.fetch_funding_rate(symbol)
                
                spot_data, futures_data, funding_data = await asyncio.gather(
                    spot_task, futures_task, funding_task
                )
                
                # 计算套利机会
                arb_opportunity = self.calculate_arbitrage_opportunity(
                    symbol, spot_data, futures_data, funding_data
                )
                
                # 保存到数据库
                self.save_to_database(spot_data, futures_data, funding_data, arb_opportunity)
                
                # 显示结果
                if arb_opportunity:
                    logger.info(f"{symbol}:")
                    logger.info(f"  现货: ${spot_data['price']:,.2f}")
                    logger.info(f"  期货: ${futures_data['price']:,.2f}")
                    logger.info(f"  基差: ${arb_opportunity['basis']:+,.2f} ({arb_opportunity['basis_rate']:+.4%})")
                    logger.info(f"  资金费率: {funding_data['funding_rate']:.4%}")
                    logger.info(f"  年化收益: {arb_opportunity['annualized_basis']:.2%}")
                    logger.info(f"  净收益: {arb_opportunity['net_return']:+.2%} {'✅' if arb_opportunity['is_profitable'] else '❌'}")
                
                # 避免请求过快
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"{symbol} 采集失败: {e}")
        
        logger.info("数据采集完成")
        logger.info("=" * 60)
    
    async def run_continuously(self, interval_minutes: int = 5):
        """持续运行采集"""
        logger.info(f"启动数据采集服务 (间隔: {interval_minutes}分钟)")
        logger.info(f"监控币种: {', '.join(self.SYMBOLS)}")
        logger.info(f"数据库: {self.db_path}")
        
        while True:
            try:
                await self.collect_once()
                
                # 等待下一次采集
                await asyncio.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("收到停止信号,退出...")
                break
            except Exception as e:
                logger.error(f"运行错误: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再重试


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="现货-期货套利数据采集")
    parser.add_argument("--once", action="store_true", help="只采集一次")
    parser.add_argument("--interval", type=int, default=5, help="采集间隔(分钟)")
    
    args = parser.parse_args()
    
    async with ArbitrageDataCollector() as collector:
        if args.once:
            await collector.collect_once()
        else:
            await collector.run_continuously(args.interval)


if __name__ == "__main__":
    asyncio.run(main())

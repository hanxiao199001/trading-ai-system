# fetch_basis_data.py
"""
采集BTC现货和永续合约的历史数据,用于价差分析
"""

import ccxt
import pandas as pd
import time
from datetime import datetime, timedelta
import json

def fetch_historical_data(exchange, symbol, timeframe='5m', days=30):
    """
    获取历史K线数据
    
    Args:
        exchange: ccxt交易所对象
        symbol: 交易对符号
        timeframe: K线周期
        days: 获取多少天的数据
    """
    since = exchange.parse8601((datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ'))
    all_candles = []
    
    print(f"开始获取 {symbol} 的历史数据...")
    
    while since < exchange.milliseconds():
        try:
            candles = exchange.fetch_ohlcv(symbol, timeframe, since, limit=300)
            if not candles:
                break
            
            all_candles.extend(candles)
            since = candles[-1][0] + 1
            print(f"已获取 {len(all_candles)} 条数据, 最新时间: {datetime.fromtimestamp(candles[-1][0]/1000)}")
            time.sleep(0.5)  # 避免触发限流
            
        except Exception as e:
            print(f"获取数据出错: {e}")
            time.sleep(2)
            continue
    
    # 转换为DataFrame
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    return df

def calculate_basis(spot_df, future_df):
    """
    计算现货-期货价差
    
    Args:
        spot_df: 现货数据
        future_df: 期货数据
    
    Returns:
        合并后的DataFrame,包含价差信息
    """
    # 按时间戳合并
    merged = pd.merge(
        spot_df[['timestamp', 'datetime', 'close']],
        future_df[['timestamp', 'close']],
        on='timestamp',
        suffixes=('_spot', '_future')
    )
    
    # 计算价差和价差率
    merged['basis'] = merged['close_future'] - merged['close_spot']
    merged['basis_rate'] = (merged['basis'] / merged['close_spot']) * 100  # 百分比
    
    return merged

def main():
    # 配置
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # 初始化交易所
    exchange = ccxt.okx({
        'apiKey': config['api_key'],
        'secret': config['secret_key'],
        'password': config['passphrase'],
        'enableRateLimit': True,
    })
    
    # 设置为模拟盘(可选)
    # exchange.set_sandbox_mode(True)
    
    print("="*80)
    print("BTC 现货-永续合约价差数据采集")
    print("="*80)
    
    # 获取现货数据
    print("\n[1/3] 获取现货数据 (BTC-USDT)")
    spot_symbol = 'BTC/USDT'
    spot_df = fetch_historical_data(exchange, spot_symbol, timeframe='5m', days=30)
    print(f"✓ 现货数据获取完成: {len(spot_df)} 条")
    
    # 获取永续合约数据
    print("\n[2/3] 获取永续合约数据 (BTC-USDT-SWAP)")
    future_symbol = 'BTC/USDT:USDT'  # OKX的永续合约格式
    future_df = fetch_historical_data(exchange, future_symbol, timeframe='5m', days=30)
    print(f"✓ 永续合约数据获取完成: {len(future_df)} 条")
    
    # 计算价差
    print("\n[3/3] 计算价差...")
    basis_df = calculate_basis(spot_df, future_df)
    
    # 保存数据
    filename = f'basis_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    basis_df.to_csv(filename, index=False)
    print(f"✓ 数据已保存到: {filename}")
    
    # 基础统计
    print("\n" + "="*80)
    print("数据概览")
    print("="*80)
    print(f"数据时间范围: {basis_df['datetime'].min()} 到 {basis_df['datetime'].max()}")
    print(f"总数据量: {len(basis_df)} 条")
    print(f"\n价差统计:")
    print(f"  平均价差率: {basis_df['basis_rate'].mean():.4f}%")
    print(f"  价差率标准差: {basis_df['basis_rate'].std():.4f}%")
    print(f"  最大价差率: {basis_df['basis_rate'].max():.4f}%")
    print(f"  最小价差率: {basis_df['basis_rate'].min():.4f}%")
    print(f"  中位数价差率: {basis_df['basis_rate'].median():.4f}%")
    
    print("\n价差率分布:")
    print(basis_df['basis_rate'].describe())
    
    return basis_df

if __name__ == '__main__':
    df = main()

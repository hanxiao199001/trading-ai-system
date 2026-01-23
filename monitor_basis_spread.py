# monitor_basis_spread.py
"""
持续监控现货-期货价差
"""

import ccxt
import pandas as pd
import json
import time
from datetime import datetime
import os

def get_current_basis(exchange):
    """获取当前价差"""
    try:
        spot_ticker = exchange.fetch_ticker('BTC/USDT')
        spot_price = spot_ticker['last']
        
        future_ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        future_price = future_ticker['last']
        
        basis = future_price - spot_price
        basis_rate = (basis / spot_price) * 100
        
        return {
            'timestamp': datetime.now(),
            'spot_price': spot_price,
            'future_price': future_price,
            'basis': basis,
            'basis_rate': basis_rate
        }
    except Exception as e:
        print(f"获取价差失败: {e}")
        return None

def load_history():
    """加载历史数据"""
    filename = 'basis_monitor_history.csv'
    if os.path.exists(filename):
        df = pd.read_csv(filename)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    else:
        return pd.DataFrame(columns=['timestamp', 'spot_price', 'future_price', 
                                     'basis', 'basis_rate'])

def save_data(df):
    """保存数据"""
    filename = 'basis_monitor_history.csv'
    df.to_csv(filename, index=False)

def analyze_market_structure(df):
    """分析市场结构"""
    if len(df) < 10:
        return "数据不足,继续收集中..."
    
    recent_data = df.tail(100)
    positive_count = (recent_data['basis_rate'] > 0).sum()
    negative_count = (recent_data['basis_rate'] < 0).sum()
    
    current_rate = df.iloc[-1]['basis_rate']
    mean_rate = recent_data['basis_rate'].mean()
    
    if positive_count > negative_count * 2:
        market_state = "正价差 Contango - 经典套利机会!"
    elif negative_count > positive_count * 2:
        market_state = "贴水 Backwardation - 反向套利"
    else:
        market_state = "混合状态 - 观察中"
    
    signal = ""
    if current_rate > 0.05:
        signal = "套利信号: 做多现货 + 做空期货"
    elif current_rate < -0.08:
        signal = "反向套利信号: 做空现货 + 做多期货"
    
    return f"""
市场结构: {market_state}
当前价差率: {current_rate:.4f}%
近期均值: {mean_rate:.4f}%
正价差次数: {positive_count}/{len(recent_data)} ({positive_count/len(recent_data)*100:.1f}%)
{signal}
"""

def main():
    print("="*80)
    print("BTC 现货-期货价差持续监控")
    print("="*80)
    print("监控频率: 每小时一次")
    print("按 Ctrl+C 停止监控")
    print("="*80 + "\n")
    
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    exchange = ccxt.okx({
        'apiKey': config['api_key'],
        'secret': config['secret_key'],
        'password': config['passphrase'],
        'enableRateLimit': True,
    })
    
    df = load_history()
    print(f"已加载历史数据: {len(df)} 条记录\n")
    
    try:
        while True:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
            
            data = get_current_basis(exchange)
            if data:
                df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
                save_data(df)
                
                print(f"现货价格: ${data['spot_price']:,.2f}")
                print(f"期货价格: ${data['future_price']:,.2f}")
                print(f"价差率: {data['basis_rate']:.4f}%")
                
                analysis = analyze_market_structure(df)
                print(analysis)
                
                # 检查首次正价差
                if data['basis_rate'] > 0:
                    prev_positive = (df.iloc[:-1]['basis_rate'] > 0).any()
                    if not prev_positive:
                        print("\n首次出现正价差(Contango)!")
                
                print(f"\n总数据点: {len(df)} | 下次更新: 1小时后")
            
            time.sleep(3600)  # 1小时
            
    except KeyboardInterrupt:
        print("\n\n监控已停止")
        print(f"共收集 {len(df)} 条数据")
        save_data(df)

if __name__ == '__main__':
    main()

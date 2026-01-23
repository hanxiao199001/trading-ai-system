# check_basis_now.py
"""
快速查询当前价差 - 无需等待
"""

import ccxt
import json
from datetime import datetime

def main():
    # 加载配置
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    # 初始化交易所
    exchange = ccxt.okx({
        'apiKey': config['api_key'],
        'secret': config['secret_key'],
        'password': config['passphrase'],
        'enableRateLimit': True,
    })
    
    print("="*60)
    print("BTC 现货-期货价差实时查询")
    print("="*60)
    
    try:
        # 获取现货价格
        spot_ticker = exchange.fetch_ticker('BTC/USDT')
        spot_price = spot_ticker['last']
        
        # 获取永续合约价格
        future_ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        future_price = future_ticker['last']
        
        # 计算价差
        basis = future_price - spot_price
        basis_rate = (basis / spot_price) * 100
        
        print(f"\n查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n现货价格 (BTC/USDT):      ${spot_price:,.2f}")
        print(f"期货价格 (BTC-USDT-SWAP): ${future_price:,.2f}")
        print(f"价差:                      ${basis:,.2f}")
        print(f"价差率:                    {basis_rate:.4f}%")
        
        # 判断市场状态
        if basis_rate > 0:
            print(f"\n市场状态: 正价差 Contango")
            print(f"策略建议: 做多现货 + 做空期货")
            if basis_rate > 0.05:
                print(f"套利信号: 价差率 > 0.05%")
        else:
            print(f"\n市场状态: 贴水 Backwardation")
            print(f"策略建议: 继续关注资金费率套利")
            if basis_rate < -0.08:
                print(f"反向套利信号: 价差率 < -0.08%")
        
        print("\n" + "="*60)
        
    except Exception as e:
        print(f"查询失败: {e}")

if __name__ == '__main__':
    main()

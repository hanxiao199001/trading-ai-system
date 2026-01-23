# live_funding_bot_fixed.py
"""
OKX 资金费率套利 - 实盘交易系统 (修复版)
"""

import ccxt
import json
import time
from datetime import datetime
import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('live_trading.log'),
        logging.StreamHandler()
    ]
)

class FundingRateBot:
    def __init__(self, config_file='config.json'):
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        self.exchange = ccxt.okx({
            'apiKey': config['api_key'],
            'secret': config['secret_key'],
            'password': config['passphrase'],
            'enableRateLimit': True,
        })
        
        self.symbol = 'BTC/USDT:USDT'
        self.funding_threshold = 0.003
        self.take_profit = 0.015
        self.stop_loss = 0.02
        self.position_size = 0.001
        
        self.position = None
        self.entry_price = 0
        self.entry_time = None
        
        logging.info("=" * 80)
        logging.info("资金费率套利机器人启动")
        logging.info("=" * 80)
        logging.info(f"交易对: {self.symbol}")
        logging.info(f"开仓阈值: {self.funding_threshold * 100}%")
        logging.info(f"止盈: {self.take_profit * 100}%")
        logging.info(f"止损: {self.stop_loss * 100}%")
        logging.info(f"仓位大小: {self.position_size} BTC")
        logging.info("=" * 80)
    
    def get_funding_rate(self):
        """获取当前资金费率"""
        try:
            funding_info = self.exchange.fetch_funding_rate(self.symbol)
            return float(funding_info['fundingRate'])
        except Exception as e:
            logging.error(f"获取资金费率失败: {e}")
            return None
    
    def get_current_price(self):
        """获取当前价格"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return float(ticker['last'])
        except Exception as e:
            logging.error(f"获取价格失败: {e}")
            return None
    
    def get_balance(self):
        """获取账户余额"""
        try:
            balance = self.exchange.fetch_balance()
            usdt_balance = balance['USDT']['free']
            return float(usdt_balance)
        except Exception as e:
            logging.error(f"获取余额失败: {e}")
            return None
    
    def check_position(self):
        """检查当前持仓"""
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                if float(pos['contracts']) != 0:
                    return {
                        'side': pos['side'],
                        'size': float(pos['contracts']),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unrealizedPnl']),
                        'percentage': float(pos['percentage'])
                    }
            return None
        except Exception as e:
            logging.error(f"检查持仓失败: {e}")
            return None
    
    def open_short(self, price):
        """开空仓"""
        try:
            logging.info(f"准备开空仓: 价格 ${price:.2f}, 数量 {self.position_size} BTC")
            
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='market',
                side='sell',
                amount=self.position_size,
                params={'tdMode': 'cross'}
            )
            
            self.position = 'short'
            self.entry_price = price
            self.entry_time = datetime.now()
            
            logging.info(f"✅ 开空成功!")
            logging.info(f"订单ID: {order['id']}")
            logging.info(f"入场价格: ${self.entry_price:.2f}")
            
            return True
            
        except Exception as e:
            logging.error(f"❌ 开仓失败: {e}")
            return False
    
    def close_position(self, reason="手动平仓"):
        """平仓"""
        try:
            current_price = self.get_current_price()
            if not current_price:
                return False
            
            logging.info(f"准备平仓: {reason}")
            
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='market',
                side='buy',
                amount=self.position_size,
                params={'tdMode': 'cross'}
            )
            
            pnl = (self.entry_price - current_price) / self.entry_price
            holding_time = (datetime.now() - self.entry_time).total_seconds() / 3600
            
            logging.info(f"✅ 平仓成功!")
            logging.info(f"入场价格: ${self.entry_price:.2f}")
            logging.info(f"出场价格: ${current_price:.2f}")
            logging.info(f"收益率: {pnl * 100:.2f}%")
            logging.info(f"持仓时间: {holding_time:.2f} 小时")
            
            self.position = None
            self.entry_price = 0
            self.entry_time = None
            
            return True
            
        except Exception as e:
            logging.error(f"❌ 平仓失败: {e}")
            return False
    
    def check_stop_conditions(self, current_price):
        """检查止盈止损"""
        if not self.position:
            return False
        
        pnl = (self.entry_price - current_price) / self.entry_price
        
        if pnl >= self.take_profit:
            logging.info(f"触发止盈! 当前收益: {pnl * 100:.2f}%")
            return self.close_position("止盈")
        
        if pnl <= -self.stop_loss:
            logging.warning(f"触发止损! 当前亏损: {pnl * 100:.2f}%")
            return self.close_position("止损")
        
        return False
    
    def run(self):
        """主循环"""
        logging.info("机器人开始运行...")
        
        while True:
            try:
                funding_rate = self.get_funding_rate()
                current_price = self.get_current_price()
                balance = self.get_balance()
                
                if not all([funding_rate is not None, current_price, balance]):
                    logging.warning("数据获取失败,等待下次检查...")
                    time.sleep(60)
                    continue
                
                logging.info("-" * 80)
                logging.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                logging.info(f"价格: ${current_price:,.2f}")
                logging.info(f"资金费率: {funding_rate * 100:.4f}%")
                logging.info(f"余额: ${balance:.2f} USDT")
                
                pos = self.check_position()
                if pos:
                    logging.info(f"当前持仓: {pos['side']} {pos['size']} BTC")
                    logging.info(f"未实现盈亏: ${pos['unrealized_pnl']:.2f} ({pos['percentage']:.2f}%)")
                    self.check_stop_conditions(current_price)
                else:
                    logging.info("当前无持仓")
                    
                    if funding_rate > self.funding_threshold:
                        logging.info(f"⚡ 发现开仓机会! 资金费率 {funding_rate * 100:.4f}%")
                        self.open_short(current_price)
                
                logging.info("-" * 80)
                time.sleep(300)
                
            except KeyboardInterrupt:
                logging.info("\n收到停止信号...")
                if self.position:
                    response = input("是否平仓后退出? (y/n): ")
                    if response.lower() == 'y':
                        self.close_position("手动退出")
                logging.info("机器人已停止")
                break
                
            except Exception as e:
                logging.error(f"运行错误: {e}")
                time.sleep(60)

def main():
    if not os.path.exists('config.json'):
        logging.error("错误: 找不到 config.json 文件")
        return
    
    bot = FundingRateBot()
    
    balance = bot.get_balance()
    if balance:
        logging.info(f"账户余额: ${balance:.2f} USDT")
    
    pos = bot.check_position()
    if pos:
        logging.info(f"当前持仓: {pos}")
    else:
        logging.info("当前无持仓")
    
    print("\n" + "=" * 80)
    print("准备启动实盘交易!")
    print("=" * 80)
    response = input("确认启动? (yes/no): ")
    
    if response.lower() != 'yes':
        logging.info("用户取消启动")
        return
    
    bot.run()

if __name__ == '__main__':
    main()

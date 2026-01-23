"""
独立参数优化脚本 - 适配你的项目
基于你现有的回测结果 (年化7.1%, 回撤2.03%, 胜率55.9%)
"""

import pandas as pd
import numpy as np
from itertools import product
from datetime import datetime
import json


class SimpleBacktester:
    """简化回测引擎 - 用于快速参数测试"""
    
    def __init__(self, df: pd.DataFrame, initial_capital: float = 10000):
        """
        Args:
            df: 包含 OHLCV 数据的 DataFrame
            initial_capital: 初始资金
        """
        self.df = df.copy()
        self.initial_capital = initial_capital
        
    def run_backtest(self, params: dict) -> dict:
        """
        运行回测
        
        Args:
            params: 策略参数字典
                - trend_threshold: 趋势阈值
                - stop_loss: 止损百分比
                - take_profit: 止盈百分比
                - volume_confirm: 成交量确认倍数
                - volatility_threshold: 波动率阈值
        """
        df = self.df.copy()
        
        # 计算技术指标
        df['returns'] = df['close'].pct_change()
        df['sma_20'] = df['close'].rolling(20).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        df['volatility'] = df['returns'].rolling(20).std()
        df['volume_ma'] = df['volume'].rolling(20).mean()
        
        # 趋势信号
        df['trend'] = (df['sma_20'] - df['sma_50']) / df['sma_50']
        
        # 成交量确认
        df['volume_signal'] = df['volume'] > (df['volume_ma'] * params['volume_confirm'])
        
        # 波动率过滤
        df['vol_filter'] = df['volatility'] < params['volatility_threshold']
        
        # 生成交易信号
        df['signal'] = 0
        df.loc[
            (df['trend'] > params['trend_threshold']) & 
            df['volume_signal'] & 
            df['vol_filter'], 
            'signal'
        ] = 1  # 做多
        
        df.loc[
            (df['trend'] < -params['trend_threshold']) & 
            df['volume_signal'] & 
            df['vol_filter'], 
            'signal'
        ] = -1  # 做空
        
        # 模拟交易
        trades = []
        position = 0
        entry_price = 0
        capital = self.initial_capital
        
        for i in range(len(df)):
            if pd.isna(df.iloc[i]['signal']):
                continue
            
            current_price = df.iloc[i]['close']
            signal = df.iloc[i]['signal']
            
            # 开仓
            if position == 0 and signal != 0:
                position = signal
                entry_price = current_price
                
            # 平仓检查
            elif position != 0:
                pnl_pct = (current_price - entry_price) / entry_price * position
                
                # 止损
                if pnl_pct <= -params['stop_loss']:
                    capital *= (1 + pnl_pct)
                    trades.append({
                        'entry': entry_price,
                        'exit': current_price,
                        'pnl_pct': pnl_pct,
                        'result': 'loss'
                    })
                    position = 0
                    
                # 止盈
                elif pnl_pct >= params['take_profit']:
                    capital *= (1 + pnl_pct)
                    trades.append({
                        'entry': entry_price,
                        'exit': current_price,
                        'pnl_pct': pnl_pct,
                        'result': 'win'
                    })
                    position = 0
                    
                # 反向信号平仓
                elif signal != 0 and signal != position:
                    capital *= (1 + pnl_pct)
                    trades.append({
                        'entry': entry_price,
                        'exit': current_price,
                        'pnl_pct': pnl_pct,
                        'result': 'win' if pnl_pct > 0 else 'loss'
                    })
                    position = signal
                    entry_price = current_price
        
        # 计算指标
        if len(trades) == 0:
            return {
                'total_return': 0,
                'annual_return': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'win_rate': 0,
                'total_trades': 0,
                'profit_factor': 0
            }
        
        total_return = (capital - self.initial_capital) / self.initial_capital
        days = (df.iloc[-1]['timestamp'] - df.iloc[0]['timestamp']).days
        annual_return = total_return * (365 / max(days, 1))
        
        wins = [t for t in trades if t['result'] == 'win']
        losses = [t for t in trades if t['result'] == 'loss']
        win_rate = len(wins) / len(trades) if trades else 0
        
        total_profit = sum([t['pnl_pct'] for t in wins])
        total_loss = abs(sum([t['pnl_pct'] for t in losses])) if losses else 0.01
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        # 计算最大回撤
        equity_curve = [self.initial_capital]
        for trade in trades:
            equity_curve.append(equity_curve[-1] * (1 + trade['pnl_pct']))
        
        peak = equity_curve[0]
        max_dd = 0
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (equity - peak) / peak
            if dd < max_dd:
                max_dd = dd
        
        # 夏普比率 (简化计算)
        returns_list = [t['pnl_pct'] for t in trades]
        sharpe = np.mean(returns_list) / np.std(returns_list) * np.sqrt(252) if len(returns_list) > 1 else 0
        
        return {
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'total_trades': len(trades),
            'profit_factor': profit_factor
        }


class ParameterOptimizer:
    """参数优化器"""
    
    def __init__(self, data_file: str):
        """
        Args:
            data_file: CSV数据文件路径
                需要包含列: timestamp, open, high, low, close, volume
        """
        self.df = pd.read_csv(data_file)
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        self.results = []
        
    def create_param_grid(self):
        """创建参数网格 - 稳健优化"""
        return {
            'trend_threshold': [0.25, 0.30, 0.35, 0.40],
            'stop_loss': [0.015, 0.020, 0.025],
            'take_profit': [0.020, 0.025, 0.030],
            'volume_confirm': [1.0, 1.2, 1.5],
            'volatility_threshold': [0.02, 0.03, 0.04],
        }
    
    def calculate_stability_score(self, result: dict) -> float:
        """
        稳健性评分 (0-100)
        权重: 回撤50% + 胜率30% + 收益20%
        """
        # 回撤得分 (50分)
        max_dd = abs(result['max_drawdown'])
        if max_dd <= 0.015:
            dd_score = 50
        elif max_dd <= 0.020:
            dd_score = 40
        elif max_dd <= 0.030:
            dd_score = 30
        else:
            dd_score = max(0, 30 - (max_dd - 0.03) * 500)
        
        # 胜率得分 (30分)
        wr_score = min(30, result['win_rate'] * 50)
        
        # 收益得分 (20分)
        annual_ret = result['annual_return']
        if annual_ret >= 0.10:
            ret_score = 20
        elif annual_ret >= 0.05:
            ret_score = 10 + (annual_ret - 0.05) * 200
        else:
            ret_score = max(0, annual_ret * 200)
        
        return dd_score + wr_score + ret_score
    
    def optimize(self):
        """执行网格搜索"""
        param_grid = self.create_param_grid()
        
        # 生成所有组合
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(product(*values))
        
        total = len(combinations)
        print(f"\n{'='*80}")
        print(f"开始参数优化 - 共 {total} 组组合")
        print(f"{'='*80}\n")
        
        # 创建回测引擎
        backtester = SimpleBacktester(self.df)
        
        # 遍历所有参数组合
        for idx, combo in enumerate(combinations, 1):
            params = dict(zip(keys, combo))
            
            # 运行回测
            result = backtester.run_backtest(params)
            
            # 计算稳健性得分
            stability_score = self.calculate_stability_score(result)
            
            # 保存结果
            self.results.append({
                'params': params,
                'metrics': result,
                'stability_score': stability_score
            })
            
            # 打印进度
            if idx % 10 == 0 or idx == 1:
                print(f"[{idx}/{total}] "
                      f"年化:{result['annual_return']:>6.1%} | "
                      f"回撤:{result['max_drawdown']:>6.2%} | "
                      f"胜率:{result['win_rate']:>6.1%} | "
                      f"交易:{result['total_trades']:>3}次 | "
                      f"稳健:{stability_score:>5.1f}分")
        
        print(f"\n{'='*80}")
        print("优化完成!")
        print(f"{'='*80}\n")
    
    def show_top_results(self, top_n: int = 5):
        """展示最佳结果"""
        if not self.results:
            print("没有结果")
            return
        
        # 按稳健性得分排序
        sorted_results = sorted(
            self.results,
            key=lambda x: x['stability_score'],
            reverse=True
        )
        
        print(f"\n{'='*80}")
        print(f"TOP {top_n} 最稳健参数组合")
        print(f"{'='*80}\n")
        
        for idx, item in enumerate(sorted_results[:top_n], 1):
            params = item['params']
            metrics = item['metrics']
            score = item['stability_score']
            
            print(f"【第 {idx} 名】稳健得分: {score:.1f}/100")
            print("\n参数设置:")
            print(f"  趋势阈值: {params['trend_threshold']:.2f}")
            print(f"  止损: {params['stop_loss']:.1%}")
            print(f"  止盈: {params['take_profit']:.1%}")
            print(f"  成交量确认: {params['volume_confirm']:.1f}x")
            print(f"  波动率阈值: {params['volatility_threshold']:.1%}")
            
            print("\n回测指标:")
            print(f"  总收益: {metrics['total_return']:>8.2%}")
            print(f"  年化收益: {metrics['annual_return']:>8.2%}")
            print(f"  最大回撤: {metrics['max_drawdown']:>8.2%}")
            print(f"  夏普比率: {metrics['sharpe_ratio']:>8.2f}")
            print(f"  胜率: {metrics['win_rate']:>8.1%}")
            print(f"  交易次数: {metrics['total_trades']:>8}笔")
            print(f"  盈亏比: {metrics['profit_factor']:>8.2f}")
            print(f"\n{'-'*80}\n")
    
    def export_results(self):
        """导出结果到文件"""
        # 保存完整结果
        with open('optimization_results.json', 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        # 导出对比表格
        rows = []
        for item in self.results:
            row = {**item['params'], **item['metrics']}
            row['stability_score'] = item['stability_score']
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df = df.sort_values('stability_score', ascending=False)
        df.to_csv('param_comparison.csv', index=False, encoding='utf-8-sig')
        
        print("\n结果已保存:")
        print("  - optimization_results.json")
        print("  - param_comparison.csv")


def main():
    """主函数"""
    # ===== 配置区域 =====
    DATA_FILE = 'data/btc_usdt_swap_90d.csv'  # 修改为你的数据文件路径
    TOP_N = 5  # 显示前N个最佳结果
    
    print("\n" + "="*80)
    print("资金费率策略参数优化")
    print("目标: 降低回撤 + 提升稳定性")
    print("="*80)
    print(f"数据文件: {DATA_FILE}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建优化器
    optimizer = ParameterOptimizer(DATA_FILE)
    
    # 执行优化
    optimizer.optimize()
    
    # 展示结果
    optimizer.show_top_results(TOP_N)
    
    # 导出结果
    optimizer.export_results()
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()

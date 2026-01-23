"""
参数优化脚本 - 网格搜索 + 稳健优化
目标: 降低回撤,提升稳定性
"""

import sys
import pandas as pd
import numpy as np
from itertools import product
from datetime import datetime
import json

# 添加项目路径(你需要根据实际情况调整)
sys.path.append('/path/to/trading-ai-system')

from backtest.engine import BacktestEngine
from strategies.funding_rate.base import FundingRateStrategy
from exchanges.okx_client import OKXClient


class ParameterOptimizer:
    """参数优化器"""
    
    def __init__(self, data_file: str):
        """
        Args:
            data_file: 历史数据文件路径
        """
        self.data = pd.read_csv(data_file, parse_dates=['timestamp'])
        self.results = []
        
    def create_param_grid(self):
        """创建参数网格 - 稳健优化方向"""
        param_grid = {
            # 趋势阈值 - 适当提高以减少假突破
            'trend_threshold': [0.25, 0.30, 0.35, 0.40],
            
            # 止损 - 收紧以降低回撤
            'stop_loss_pct': [0.015, 0.020, 0.025],  # 1.5%, 2%, 2.5%
            
            # 止盈 - 保守设置
            'take_profit_pct': [0.020, 0.025, 0.030],  # 2%, 2.5%, 3%
            
            # 成交量确认倍数 - 新增过滤条件
            'volume_confirm': [1.0, 1.2, 1.5],  # 1.0=不过滤, >1.0=要求成交量放大
            
            # 波动率过滤 - 高波动时降低仓位或不交易
            'volatility_threshold': [0.02, 0.03, 0.04],  # 2%, 3%, 4%
        }
        
        return param_grid
    
    def run_single_backtest(self, params: dict):
        """运行单次回测"""
        try:
            # 创建策略实例
            strategy = FundingRateStrategy(
                trend_threshold=params['trend_threshold'],
                stop_loss_pct=params['stop_loss_pct'],
                take_profit_pct=params['take_profit_pct'],
                volume_confirm=params['volume_confirm'],
                volatility_threshold=params['volatility_threshold']
            )
            
            # 创建回测引擎
            engine = BacktestEngine(
                strategy=strategy,
                initial_capital=10000,
                commission=0.0005  # 0.05% 手续费
            )
            
            # 运行回测
            result = engine.run(self.data)
            
            # 提取关键指标
            metrics = {
                'params': params,
                'total_return': result['total_return'],
                'annual_return': result['annual_return'],
                'max_drawdown': result['max_drawdown'],
                'sharpe_ratio': result['sharpe_ratio'],
                'win_rate': result['win_rate'],
                'total_trades': result['total_trades'],
                'profit_factor': result['profit_factor'],
                
                # 稳健性评分 (自定义指标)
                'stability_score': self._calculate_stability_score(result)
            }
            
            return metrics
            
        except Exception as e:
            print(f"回测失败: {params}, 错误: {str(e)}")
            return None
    
    def _calculate_stability_score(self, result: dict) -> float:
        """
        计算稳健性评分 (0-100分)
        优先考虑: 低回撤 > 高胜率 > 高收益
        """
        # 回撤得分 (50分权重) - 越低越好
        max_dd = abs(result['max_drawdown'])
        if max_dd <= 0.015:  # 1.5%以内
            dd_score = 50
        elif max_dd <= 0.020:  # 2%以内
            dd_score = 40
        elif max_dd <= 0.030:  # 3%以内
            dd_score = 30
        else:
            dd_score = max(0, 30 - (max_dd - 0.03) * 500)
        
        # 胜率得分 (30分权重)
        win_rate = result['win_rate']
        wr_score = min(30, win_rate * 50)  # 60%胜率 = 30分
        
        # 年化收益得分 (20分权重)
        annual_ret = result['annual_return']
        if annual_ret >= 0.10:  # 10%以上
            ret_score = 20
        elif annual_ret >= 0.05:  # 5-10%
            ret_score = 10 + (annual_ret - 0.05) * 200
        else:
            ret_score = max(0, annual_ret * 200)
        
        return dd_score + wr_score + ret_score
    
    def optimize(self):
        """执行网格搜索优化"""
        param_grid = self.create_param_grid()
        
        # 生成所有参数组合
        keys = param_grid.keys()
        values = param_grid.values()
        combinations = list(product(*values))
        
        total = len(combinations)
        print(f"开始网格搜索: 共 {total} 组参数组合")
        print("=" * 80)
        
        # 遍历所有组合
        for idx, combo in enumerate(combinations, 1):
            params = dict(zip(keys, combo))
            
            print(f"\n[{idx}/{total}] 测试参数:")
            for k, v in params.items():
                print(f"  {k}: {v}")
            
            # 运行回测
            result = self.run_single_backtest(params)
            
            if result:
                self.results.append(result)
                print(f"  → 年化: {result['annual_return']:.2%}, "
                      f"回撤: {result['max_drawdown']:.2%}, "
                      f"胜率: {result['win_rate']:.1%}, "
                      f"稳健得分: {result['stability_score']:.1f}")
        
        print("\n" + "=" * 80)
        print("优化完成!")
        
    def get_best_params(self, top_n: int = 5):
        """获取最佳参数组合"""
        if not self.results:
            print("没有可用结果")
            return None
        
        # 按稳健性得分排序
        sorted_results = sorted(
            self.results, 
            key=lambda x: x['stability_score'], 
            reverse=True
        )
        
        print(f"\n{'='*80}")
        print(f"TOP {top_n} 最稳健参数组合:")
        print(f"{'='*80}\n")
        
        for idx, result in enumerate(sorted_results[:top_n], 1):
            print(f"【第 {idx} 名】稳健得分: {result['stability_score']:.1f}")
            print("参数:")
            for k, v in result['params'].items():
                print(f"  {k}: {v}")
            print("\n回测指标:")
            print(f"  年化收益: {result['annual_return']:.2%}")
            print(f"  最大回撤: {result['max_drawdown']:.2%}")
            print(f"  夏普比率: {result['sharpe_ratio']:.2f}")
            print(f"  胜率: {result['win_rate']:.1%}")
            print(f"  交易次数: {result['total_trades']}")
            print(f"  盈亏比: {result['profit_factor']:.2f}")
            print("-" * 80)
        
        return sorted_results[:top_n]
    
    def save_results(self, filename: str = 'optimization_results.json'):
        """保存优化结果"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {filename}")
        
    def export_comparison(self, filename: str = 'param_comparison.csv'):
        """导出对比表格"""
        df = pd.DataFrame(self.results)
        
        # 展开 params 字典为独立列
        params_df = pd.json_normalize(df['params'])
        df = pd.concat([params_df, df.drop('params', axis=1)], axis=1)
        
        # 按稳健得分排序
        df = df.sort_values('stability_score', ascending=False)
        
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"对比表格已导出: {filename}")


def main():
    """主函数"""
    # 配置
    DATA_FILE = 'data/btc_usdt_1h_90d.csv'  # 你的数据文件路径
    
    print("="*80)
    print("资金费率策略 - 参数优化 (稳健优化 + 网格搜索)")
    print("="*80)
    print(f"数据文件: {DATA_FILE}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # 创建优化器
    optimizer = ParameterOptimizer(DATA_FILE)
    
    # 执行优化
    optimizer.optimize()
    
    # 获取最佳参数
    best_params = optimizer.get_best_params(top_n=5)
    
    # 保存结果
    optimizer.save_results('optimization_results.json')
    optimizer.export_comparison('param_comparison.csv')
    
    print(f"\n完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)


if __name__ == '__main__':
    main()

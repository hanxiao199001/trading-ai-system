"""
参数优化脚本 - 适配 FundingRateStrategyV2
目标: 稳健优化 (降低回撤 + 提升稳定性)
"""
from decimal import Decimal
from itertools import product
import pandas as pd
from datetime import datetime

from backtest.engine import BacktestEngine
from backtest.types import BacktestConfig
from backtest.data_loader import DataLoader
from strategies.funding_rate.strategy_v2 import FundingRateStrategyV2


class ParameterOptimizer:
    """参数优化器"""
    
    def __init__(self, data_file: str, symbol: str = "BTC-USDT-SWAP"):
        """
        Args:
            data_file: CSV数据文件路径
            symbol: 交易对符号
        """
        self.data_file = data_file
        self.symbol = symbol
        self.klines = DataLoader.load_from_csv(data_file, symbol)
        self.results = []
        
        # 基础配置
        self.base_config = BacktestConfig(
            start_time=self.klines[0].timestamp,
            end_time=self.klines[-1].timestamp,
            initial_capital=Decimal("100000"),
            taker_fee=Decimal("0.0005"),
            slippage=Decimal("0.0002"),
        )
    
    def create_param_grid(self):
        """创建参数网格 - 激进优化方向"""
        return {
            # 资金费率阈值 (提高阈值,减少交易频率,提高胜率)
            'high_funding_threshold': [0.00005, 0.00006, 0.00007],
            'low_funding_threshold': [-0.00005, -0.00006, -0.00007],
            
            # 趋势MA周期 (缩短周期,提高灵敏度)
            'trend_ma_period': [6, 8, 10],
            
            # 趋势强度阈值 (降低阈值,更容易触发交易)
            'trend_strength_threshold': [0.0015, 0.0020, 0.0025],
            
            # 动量阈值 (降低门槛)
            'momentum_threshold': [0.0003, 0.0005, 0.0008],
            
            # 仓位大小 (提高仓位,增加收益)
            'position_size': [0.30, 0.35, 0.40],
            
            # 冷却时间 (减少冷却,增加交易机会)
            'cooldown_hours': [0, 1],
        }
    
    def run_single_backtest(self, params: dict):
        """运行单次回测"""
        try:
            # 创建引擎
            engine = BacktestEngine(self.base_config)
            engine.load_data(self.symbol, self.klines)
            
            # 创建策略
            strategy_params = {
                **params,
                'trend_follow_mode': True,  # 固定使用顺势模式
            }
            strategy = FundingRateStrategyV2(strategy_params)
            
            # 运行回测
            result = engine.run(strategy)
            
            # 提取指标
            return {
                'params': params,
                'total_return': float(result.total_return),
                'annual_return': float(result.annual_return) if hasattr(result, 'annual_return') else 0,
                'max_drawdown': float(result.max_drawdown),
                'sharpe_ratio': float(result.sharpe_ratio) if hasattr(result, 'sharpe_ratio') else 0,
                'win_rate': float(result.win_rate),
                'total_trades': result.total_trades,
                'profit_factor': float(result.profit_factor),
            }
        except Exception as e:
            print(f"❌ 回测失败: {e}")
            return None
    
    def calculate_stability_score(self, metrics: dict) -> float:
        """
        综合评分 (0-100)
        激进优化权重: 收益40% > 盈亏比30% > 回撤20% > 胜率10%
        """
        # 收益得分 (40分) - 提高权重
        total_ret = metrics['total_return']
        if total_ret >= 0.08:  # 8%以上
            ret_score = 40
        elif total_ret >= 0.05:  # 5-8%
            ret_score = 30 + (total_ret - 0.05) * 333
        elif total_ret >= 0.02:  # 2-5%
            ret_score = 15 + (total_ret - 0.02) * 500
        else:
            ret_score = max(0, total_ret * 750)
        
        # 盈亏比得分 (30分) - 新增指标
        profit_factor = metrics['profit_factor']
        if profit_factor >= 2.0:
            pf_score = 30
        elif profit_factor >= 1.5:
            pf_score = 20 + (profit_factor - 1.5) * 20
        elif profit_factor >= 1.0:
            pf_score = 10 + (profit_factor - 1.0) * 20
        else:
            pf_score = max(0, profit_factor * 10)
        
        # 回撤得分 (20分) - 降低权重
        max_dd = abs(metrics['max_drawdown'])
        if max_dd <= 0.02:
            dd_score = 20
        elif max_dd <= 0.03:
            dd_score = 15
        elif max_dd <= 0.05:
            dd_score = 10
        else:
            dd_score = max(0, 10 - (max_dd - 0.05) * 200)
        
        # 胜率得分 (10分) - 降低权重
        wr_score = min(10, metrics['win_rate'] * 20)
        
        return ret_score + pf_score + dd_score + wr_score
    
    def optimize(self):
        """执行网格搜索优化"""
        param_grid = self.create_param_grid()
        
        # 生成所有参数组合
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(product(*values))
        
        total = len(combinations)
        print(f"\n{'='*80}")
        print(f"开始参数优化")
        print(f"{'='*80}")
        print(f"数据文件: {self.data_file}")
        print(f"总组合数: {total}")
        print(f"优化方向: 激进优化 (提高收益 + 提升盈亏比)")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        # 遍历所有组合
        for idx, combo in enumerate(combinations, 1):
            params = dict(zip(keys, combo))
            
            # 运行回测
            metrics = self.run_single_backtest(params)
            
            if metrics:
                # 计算稳健性得分
                stability_score = self.calculate_stability_score(metrics)
                
                self.results.append({
                    **metrics,
                    'stability_score': stability_score
                })
                
                # 打印进度
                if idx % 20 == 0 or idx == 1:
                    print(f"[{idx:>3}/{total}] "
                          f"收益:{metrics['total_return']*100:>6.2f}% | "
                          f"回撤:{metrics['max_drawdown']*100:>6.2f}% | "
                          f"胜率:{metrics['win_rate']*100:>5.1f}% | "
                          f"盈亏比:{metrics['profit_factor']:>5.2f} | "
                          f"交易:{metrics['total_trades']:>3}笔 | "
                          f"得分:{stability_score:>5.1f}")
        
        print(f"\n{'='*80}")
        print(f"优化完成! 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
    
    def show_top_results(self, top_n: int = 5):
        """展示最佳结果"""
        if not self.results:
            print("❌ 没有可用结果")
            return
        
        # 按稳健性得分排序
        sorted_results = sorted(
            self.results,
            key=lambda x: x['stability_score'],
            reverse=True
        )
        
        print(f"\n{'='*80}")
        print(f"TOP {top_n} 最佳参数组合 (激进优化)")
        print(f"{'='*80}\n")
        
        for idx, result in enumerate(sorted_results[:top_n], 1):
            params = result['params']
            
            print(f"【第 {idx} 名】综合得分: {result['stability_score']:.1f}/100")
            print("\n参数设置:")
            print(f"  高费率阈值: {params['high_funding_threshold']:.6f}")
            print(f"  低费率阈值: {params['low_funding_threshold']:.6f}")
            print(f"  趋势MA周期: {params['trend_ma_period']}小时")
            print(f"  趋势强度阈值: {params['trend_strength_threshold']:.4f}")
            print(f"  动量阈值: {params['momentum_threshold']:.4f}")
            print(f"  仓位大小: {params['position_size']:.0%}")
            print(f"  冷却时间: {params['cooldown_hours']}小时")
            
            print("\n回测指标:")
            print(f"  总收益率: {result['total_return']*100:>8.2f}%")
            print(f"  年化收益: {result['annual_return']*100:>8.2f}%")
            print(f"  最大回撤: {result['max_drawdown']*100:>8.2f}%")
            print(f"  夏普比率: {result['sharpe_ratio']:>8.2f}")
            print(f"  胜率: {result['win_rate']*100:>8.1f}%")
            print(f"  交易次数: {result['total_trades']:>8}笔")
            print(f"  盈亏比: {result['profit_factor']:>8.2f}")
            print(f"\n{'-'*80}\n")
        
        return sorted_results[:top_n]
    
    def export_results(self):
        """导出结果"""
        # 导出CSV
        rows = []
        for result in self.results:
            row = {**result['params'], **{k: v for k, v in result.items() if k != 'params'}}
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df = df.sort_values('stability_score', ascending=False)
        df.to_csv('optimization_results.csv', index=False, encoding='utf-8-sig')
        
        print("\n✅ 结果已导出: optimization_results.csv")


def main():
    """主函数"""
    # ===== 配置 =====
    DATA_FILE = 'data/btc_usdt_swap_30d.csv'  # 改用30天数据
    SYMBOL = 'BTC-USDT-SWAP'
    TOP_N = 5
    
    # 创建优化器
    optimizer = ParameterOptimizer(DATA_FILE, SYMBOL)
    
    # 执行优化
    optimizer.optimize()
    
    # 展示结果
    best_params = optimizer.show_top_results(TOP_N)
    
    # 导出结果
    optimizer.export_results()
    
    # 输出最佳参数配置代码
    if best_params:
        print("\n" + "="*80)
        print("📋 最佳参数代码 (可直接复制到策略中):")
        print("="*80)
        params = best_params[0]['params']
        print(f"""
strategy = FundingRateStrategyV2({{
    'high_funding_threshold': {params['high_funding_threshold']},
    'low_funding_threshold': {params['low_funding_threshold']},
    'trend_ma_period': {params['trend_ma_period']},
    'trend_strength_threshold': {params['trend_strength_threshold']},
    'momentum_threshold': {params['momentum_threshold']},
    'position_size': {params['position_size']},
    'cooldown_hours': {params['cooldown_hours']},
    'trend_follow_mode': True,
}})
""")
        print("="*80)


if __name__ == '__main__':
    main()

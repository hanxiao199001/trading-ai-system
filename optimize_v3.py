"""
参数优化脚本 V3 - 带止盈止损
使用改进的回测引擎,测试不同止盈止损参数组合
"""
from decimal import Decimal
from itertools import product
import pandas as pd
from datetime import datetime
import sys

# 添加项目路径
sys.path.insert(0, '/Users/a01/trading-ai-system')

from backtest.types import BacktestConfig
from backtest.data_loader import DataLoader
from strategies.funding_rate.strategy_v2 import FundingRateStrategyV2

# 导入改进的回测引擎
from backtest_engine_with_stops import BacktestEngineWithStops


class ParameterOptimizerV3:
    """参数优化器 V3 - 包含止盈止损优化"""
    
    def __init__(self, data_file: str, symbol: str = "BTC-USDT-SWAP"):
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
        """创建参数网格 - 包含止盈止损"""
        return {
            # 策略参数
            'high_funding_threshold': [0.00005, 0.00006],
            'low_funding_threshold': [-0.00005, -0.00006],
            'trend_ma_period': [6, 8],
            'trend_strength_threshold': [0.0015, 0.0020],
            'momentum_threshold': [0.0005, 0.0008],
            'position_size': [0.25, 0.30],
            'cooldown_hours': [0, 1],
            
            # 止盈止损参数 (新增)
            'stop_loss': [0.015, 0.020, 0.025],     # 1.5%, 2%, 2.5%
            'take_profit': [0.025, 0.030, 0.035],   # 2.5%, 3%, 3.5%
        }
    
    def run_single_backtest(self, params: dict):
        """运行单次回测"""
        try:
            # 分离策略参数和止盈止损参数
            strategy_params = {k: v for k, v in params.items() if k not in ['stop_loss', 'take_profit']}
            strategy_params['trend_follow_mode'] = True
            
            stop_loss = params['stop_loss']
            take_profit = params['take_profit']
            
            # 创建引擎(带止盈止损)
            engine = BacktestEngineWithStops(
                self.base_config,
                stop_loss=stop_loss,
                take_profit=take_profit
            )
            engine.load_data(self.symbol, self.klines)
            
            # 创建策略
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
            import traceback
            traceback.print_exc()
            return None
    
    def calculate_score(self, metrics: dict) -> float:
        """
        综合评分 (0-100)
        权重: 盈亏比35% > 收益30% > 回撤20% > 胜率15%
        """
        # 盈亏比得分 (35分)
        profit_factor = metrics['profit_factor']
        if profit_factor >= 2.0:
            pf_score = 35
        elif profit_factor >= 1.5:
            pf_score = 25 + (profit_factor - 1.5) * 20
        elif profit_factor >= 1.0:
            pf_score = 15 + (profit_factor - 1.0) * 20
        else:
            pf_score = max(0, profit_factor * 15)
        
        # 收益得分 (30分)
        total_ret = metrics['total_return']
        if total_ret >= 0.05:
            ret_score = 30
        elif total_ret >= 0.02:
            ret_score = 15 + (total_ret - 0.02) * 500
        elif total_ret >= 0:
            ret_score = total_ret * 300
        else:
            ret_score = 0
        
        # 回撤得分 (20分)
        max_dd = abs(metrics['max_drawdown'])
        if max_dd <= 0.02:
            dd_score = 20
        elif max_dd <= 0.03:
            dd_score = 15
        elif max_dd <= 0.05:
            dd_score = 10
        else:
            dd_score = max(0, 10 - (max_dd - 0.05) * 200)
        
        # 胜率得分 (15分)
        wr_score = min(15, metrics['win_rate'] * 30)
        
        return pf_score + ret_score + dd_score + wr_score
    
    def optimize(self):
        """执行网格搜索"""
        param_grid = self.create_param_grid()
        
        # 生成所有参数组合
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combinations = list(product(*values))
        
        total = len(combinations)
        print(f"\n{'='*80}")
        print(f"开始参数优化 V3 (带止盈止损)")
        print(f"{'='*80}")
        print(f"数据文件: {self.data_file}")
        print(f"总组合数: {total}")
        print(f"优化方向: 提高盈亏比 + 增加收益")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        # 遍历所有组合
        for idx, combo in enumerate(combinations, 1):
            params = dict(zip(keys, combo))
            
            # 运行回测
            metrics = self.run_single_backtest(params)
            
            if metrics:
                # 计算综合得分
                score = self.calculate_score(metrics)
                
                self.results.append({
                    **metrics,
                    'score': score
                })
                
                # 打印进度
                if idx % 10 == 0 or idx == 1:
                    print(f"[{idx:>3}/{total}] "
                          f"收益:{metrics['total_return']*100:>6.2f}% | "
                          f"盈亏比:{metrics['profit_factor']:>5.2f} | "
                          f"回撤:{metrics['max_drawdown']*100:>6.2f}% | "
                          f"胜率:{metrics['win_rate']*100:>5.1f}% | "
                          f"止损:{params['stop_loss']:.1%} | "
                          f"止盈:{params['take_profit']:.1%} | "
                          f"得分:{score:>5.1f}")
        
        print(f"\n{'='*80}")
        print(f"优化完成! 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
    
    def show_top_results(self, top_n: int = 5):
        """展示最佳结果"""
        if not self.results:
            print("❌ 没有可用结果")
            return
        
        # 按得分排序
        sorted_results = sorted(
            self.results,
            key=lambda x: x['score'],
            reverse=True
        )
        
        print(f"\n{'='*80}")
        print(f"TOP {top_n} 最佳参数组合")
        print(f"{'='*80}\n")
        
        for idx, result in enumerate(sorted_results[:top_n], 1):
            params = result['params']
            
            print(f"【第 {idx} 名】综合得分: {result['score']:.1f}/100")
            print("\n策略参数:")
            print(f"  高费率阈值: {params['high_funding_threshold']:.6f}")
            print(f"  低费率阈值: {params['low_funding_threshold']:.6f}")
            print(f"  趋势MA周期: {params['trend_ma_period']}小时")
            print(f"  趋势强度: {params['trend_strength_threshold']:.4f}")
            print(f"  动量阈值: {params['momentum_threshold']:.4f}")
            print(f"  仓位大小: {params['position_size']:.0%}")
            print(f"  冷却时间: {params['cooldown_hours']}小时")
            
            print("\n风控参数:")
            print(f"  止损: {params['stop_loss']:.1%}")
            print(f"  止盈: {params['take_profit']:.1%}")
            
            print("\n回测指标:")
            print(f"  总收益率: {result['total_return']*100:>8.2f}%")
            print(f"  最大回撤: {result['max_drawdown']*100:>8.2f}%")
            print(f"  盈亏比: {result['profit_factor']:>8.2f} ⭐")
            print(f"  胜率: {result['win_rate']*100:>8.1f}%")
            print(f"  交易次数: {result['total_trades']:>8}笔")
            print(f"\n{'-'*80}\n")
        
        return sorted_results[:top_n]
    
    def export_results(self):
        """导出结果"""
        rows = []
        for result in self.results:
            row = {**result['params'], **{k: v for k, v in result.items() if k != 'params'}}
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df = df.sort_values('score', ascending=False)
        df.to_csv('optimization_results_v3.csv', index=False, encoding='utf-8-sig')
        
        print("\n✅ 结果已导出: optimization_results_v3.csv")


def main():
    """主函数"""
    # ===== 配置 =====
    DATA_FILE = 'data/btc_usdt_swap_90d.csv'
    SYMBOL = 'BTC-USDT-SWAP'
    TOP_N = 5
    
    # 创建优化器
    optimizer = ParameterOptimizerV3(DATA_FILE, SYMBOL)
    
    # 执行优化
    optimizer.optimize()
    
    # 展示结果
    best_params = optimizer.show_top_results(TOP_N)
    
    # 导出结果
    optimizer.export_results()
    
    # 输出最佳配置
    if best_params:
        print("\n" + "="*80)
        print("📋 最佳参数配置:")
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

# 回测引擎配置
engine = BacktestEngineWithStops(
    config=backtest_config,
    stop_loss={params['stop_loss']},     # {params['stop_loss']:.1%} 止损
    take_profit={params['take_profit']},  # {params['take_profit']:.1%} 止盈
)
""")
        print("="*80)


if __name__ == '__main__':
    main()

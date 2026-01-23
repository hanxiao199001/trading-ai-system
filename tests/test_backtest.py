"""
回测引擎测试脚本
"""
import sys
from datetime import datetime, timedelta
from decimal import Decimal
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from backtest.engine import BacktestEngine
from backtest.types import BacktestConfig
from backtest.data_loader import DataLoader
from strategies.funding_rate.strategy import FundingRateStrategy

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_section(title):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{title}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")

def test_backtest_engine():
    """测试回测引擎"""
    
    print_section("回测引擎测试")
    
    # 1. 配置回测参数
    print(f"\n{Colors.YELLOW}[1] 配置回测参数{Colors.END}")
    
    start_time = datetime.now() - timedelta(days=30)
    end_time = datetime.now()
    
    config = BacktestConfig(
        start_time=start_time,
        end_time=end_time,
        initial_capital=Decimal("100000"),
        maker_fee=Decimal("0.0002"),
        taker_fee=Decimal("0.0005"),
        slippage=Decimal("0.0001"),
        symbols=["BTC-USDT-SWAP"],
        strategy_params={
            'high_funding_threshold': 0.0005,  # 0.05%
            'low_funding_threshold': -0.0005,
            'min_holding_hours': 8
        }
    )
    
    print(f"{Colors.GREEN}✓{Colors.END} 回测配置完成")
    print(f"  时间范围: {start_time.date()} 至 {end_time.date()}")
    print(f"  初始资金: ${config.initial_capital:,.2f}")
    
    # 2. 加载测试数据
    print(f"\n{Colors.YELLOW}[2] 加载历史数据{Colors.END}")
    
    # 生成模拟数据(实际使用时应从CSV或API加载)
    klines = DataLoader.generate_sample_data(
        symbol="BTC-USDT-SWAP",
        start_time=start_time,
        end_time=end_time,
        interval_hours=1
    )
    
    print(f"{Colors.GREEN}✓{Colors.END} 数据加载完成: {len(klines)} 条K线")
    print(f"  价格范围: ${float(min(k.close for k in klines)):,.2f} - ${float(max(k.close for k in klines)):,.2f}")
    
    # 3. 初始化回测引擎
    print(f"\n{Colors.YELLOW}[3] 初始化回测引擎{Colors.END}")
    
    engine = BacktestEngine(config)
    engine.load_data("BTC-USDT-SWAP", klines)
    
    print(f"{Colors.GREEN}✓{Colors.END} 引擎初始化完成")
    
    # 4. 初始化策略
    print(f"\n{Colors.YELLOW}[4] 初始化交易策略{Colors.END}")
    
    strategy = FundingRateStrategy({
    'high_funding_threshold': 0.0005,
    'low_funding_threshold': -0.0005,
})
    
    print(f"{Colors.GREEN}✓{Colors.END} 资金费率策略已加载")
    
    # 5. 运行回测
    print(f"\n{Colors.YELLOW}[5] 运行回测{Colors.END}")
    print("(这可能需要几秒钟...)")
    
    try:
        result = engine.run(strategy)
        
        print(f"\n{Colors.GREEN}✓{Colors.END} 回测完成!")
        
        # 6. 显示结果
        print_section("回测结果")
        
        print(result)
        
        # 详细统计
        print(f"\n{Colors.BLUE}详细分析:{Colors.END}")
        
        # 收益分析
        if result.total_return > 0:
            color = Colors.GREEN
            symbol = "📈"
        else:
            color = Colors.RED
            symbol = "📉"
        
        print(f"\n{color}收益表现 {symbol}{Colors.END}")
        print(f"  总收益率: {result.total_return:.2%}")
        print(f"  年化收益率: {(result.total_return * 365 / result.duration_days):.2%}")
        print(f"  总盈亏: ${result.total_pnl:,.2f}")
        
        # 风险分析
        if result.sharpe_ratio > 1.5:
            risk_color = Colors.GREEN
            risk_label = "优秀"
        elif result.sharpe_ratio > 1.0:
            risk_color = Colors.YELLOW
            risk_label = "良好"
        else:
            risk_color = Colors.RED
            risk_label = "需改进"
        
        print(f"\n{risk_color}风险指标 [{risk_label}]{Colors.END}")
        print(f"  夏普比率: {result.sharpe_ratio:.2f}")
        print(f"  最大回撤: {result.max_drawdown:.2%}")
        print(f"  回撤持续: {result.max_drawdown_duration_days}天")
        
        # 交易分析
        print(f"\n{Colors.BLUE}交易统计{Colors.END}")
        print(f"  总交易次数: {result.total_trades}")
        print(f"  胜率: {result.win_rate:.2%}")
        print(f"  盈亏比: {result.profit_factor:.2f}")
        print(f"  平均持仓时间: {result.avg_holding_period_hours:.1f}小时")
        
        # 成本分析
        print(f"\n{Colors.BLUE}成本分析{Colors.END}")
        print(f"  总手续费: ${result.total_fees:,.2f}")
        print(f"  费用占比: {(result.total_fees / config.initial_capital):.2%}")
        
        # 7. 总结
        print_section("测试总结")
        
        tests_passed = 0
        tests_total = 5
        
        checks = [
            ("回测成功完成", True),
            ("有交易记录", result.total_trades > 0),
            ("权益曲线生成", len(result.equity_curve) > 0),
            ("风险指标计算", result.sharpe_ratio != 0),
            ("费用统计正常", result.total_fees > 0)
        ]
        
        for check_name, passed in checks:
            if passed:
                print(f"{Colors.GREEN}✓{Colors.END} {check_name}")
                tests_passed += 1
            else:
                print(f"{Colors.RED}✗{Colors.END} {check_name}")
        
        print(f"\n通过率: {tests_passed}/{tests_total} ({tests_passed/tests_total*100:.0f}%)")
        
        if tests_passed == tests_total:
            print(f"\n{Colors.GREEN}🎉 回测引擎测试全部通过!{Colors.END}")
            print(f"\n{Colors.YELLOW}下一步:{Colors.END}")
            print("1. 用真实历史数据替换模拟数据")
            print("2. 调整策略参数优化收益")
            print("3. 添加更多交易策略")
            print("4. 实现可视化报告")
        else:
            print(f"\n{Colors.YELLOW}⚠️ 部分测试失败,请检查{Colors.END}")
        
        return result
        
    except Exception as e:
        print(f"\n{Colors.RED}✗ 回测失败: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print(f"\n{Colors.BLUE}Trading AI System - 回测引擎测试{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")
    
    result = test_backtest_engine()
    
    if result:
        print(f"\n{Colors.GREEN}测试完成!{Colors.END}\n")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}测试失败!{Colors.END}\n")
        sys.exit(1)

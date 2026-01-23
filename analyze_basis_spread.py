# analyze_basis_spread.py
"""
分析现货-期货价差分布,寻找套利机会
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# 设置中文显示
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # MacOS
plt.rcParams['axes.unicode_minus'] = False

def load_latest_data():
    """加载最新的价差数据"""
    import glob
    files = glob.glob('basis_data_*.csv')
    if not files:
        raise FileNotFoundError("找不到价差数据文件")
    
    latest_file = sorted(files)[-1]
    print(f"加载数据文件: {latest_file}")
    df = pd.read_csv(latest_file)
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df, latest_file

def analyze_spread_distribution(df):
    """分析价差分布"""
    print("\n" + "="*80)
    print("价差分布分析")
    print("="*80)
    
    # 基础统计
    print(f"\n数据时间范围: {df['datetime'].min()} 到 {df['datetime'].max()}")
    print(f"总样本数: {len(df)}")
    
    # 价差率统计
    print(f"\n价差率统计 (%):")
    print(f"  均值: {df['basis_rate'].mean():.4f}%")
    print(f"  中位数: {df['basis_rate'].median():.4f}%")
    print(f"  标准差: {df['basis_rate'].std():.4f}%")
    print(f"  最小值: {df['basis_rate'].min():.4f}%")
    print(f"  最大值: {df['basis_rate'].max():.4f}%")
    
    # 分位数
    print(f"\n分位数:")
    for q in [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99]:
        val = df['basis_rate'].quantile(q)
        print(f"  {q*100:5.1f}%: {val:8.4f}%")
    
    # 正负价差统计
    positive = (df['basis_rate'] > 0).sum()
    negative = (df['basis_rate'] < 0).sum()
    zero = (df['basis_rate'] == 0).sum()
    
    print(f"\n价差方向分布:")
    print(f"  正价差(期货>现货): {positive:5d} ({positive/len(df)*100:.2f}%)")
    print(f"  负价差(期货<现货): {negative:5d} ({negative/len(df)*100:.2f}%)")
    print(f"  零价差:             {zero:5d} ({zero/len(df)*100:.2f}%)")

def plot_analysis(df):
    """绘制分析图表"""
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # 1. 价差率时间序列
    ax1 = axes[0, 0]
    ax1.plot(df['datetime'], df['basis_rate'], linewidth=0.5, alpha=0.7)
    ax1.axhline(y=0, color='r', linestyle='--', label='零价差线')
    ax1.axhline(y=df['basis_rate'].mean(), color='g', linestyle='--', 
                label=f'均值: {df["basis_rate"].mean():.4f}%')
    ax1.set_xlabel('时间')
    ax1.set_ylabel('价差率 (%)')
    ax1.set_title('价差率时间序列')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. 价差率分布直方图
    ax2 = axes[0, 1]
    ax2.hist(df['basis_rate'], bins=50, edgecolor='black', alpha=0.7)
    ax2.axvline(x=0, color='r', linestyle='--', label='零价差')
    ax2.axvline(x=df['basis_rate'].mean(), color='g', linestyle='--', 
                label=f'均值: {df["basis_rate"].mean():.4f}%')
    ax2.set_xlabel('价差率 (%)')
    ax2.set_ylabel('频数')
    ax2.set_title('价差率分布')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # 3. 现货vs期货价格对比
    ax3 = axes[1, 0]
    ax3.plot(df['datetime'], df['close_spot'], label='现货', linewidth=0.8)
    ax3.plot(df['datetime'], df['close_future'], label='期货', linewidth=0.8, alpha=0.8)
    ax3.set_xlabel('时间')
    ax3.set_ylabel('价格 (USDT)')
    ax3.set_title('现货 vs 期货价格')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # 4. 价差率箱线图 (按小时分组)
    ax4 = axes[1, 1]
    df['hour'] = df['datetime'].dt.hour
    hourly_data = [df[df['hour']==h]['basis_rate'].values for h in range(24)]
    ax4.boxplot(hourly_data, labels=range(24))
    ax4.axhline(y=0, color='r', linestyle='--', alpha=0.5)
    ax4.set_xlabel('小时')
    ax4.set_ylabel('价差率 (%)')
    ax4.set_title('价差率按小时分布')
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    # 保存图表
    filename = f'basis_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    print(f"\n图表已保存: {filename}")
    plt.show()

def find_arbitrage_opportunities(df):
    """寻找套利机会"""
    print("\n" + "="*80)
    print("套利机会分析")
    print("="*80)
    
    # 由于价差始终为负,传统套利不可行
    # 分析反向套利机会: 做空现货 + 做多期货
    
    print("\n⚠️  重要发现:")
    print("价差率始终为负值,期货价格持续低于现货价格!")
    print("这是 **贴水(Backwardation)** 市场结构")
    
    print("\n传统套利策略 (做多现货+做空期货):")
    print("  ❌ 不适用 - 会产生持续亏损")
    
    print("\n可能的替代策略:")
    print("  1️⃣  反向套利: 做空现货 + 做多期货")
    print("      - 利润来源: 期货价格向现货价格收敛")
    print("      - 风险: 需要支付现货借贷成本")
    
    print("  2️⃣  等待价差扩大:")
    # 找出价差率最极端的时刻
    threshold_low = df['basis_rate'].quantile(0.05)  # 5%分位数
    extreme_spreads = df[df['basis_rate'] < threshold_low]
    
    print(f"      - 当价差率 < {threshold_low:.4f}% 时入场")
    print(f"      - 历史上有 {len(extreme_spreads)} 次 ({len(extreme_spreads)/len(df)*100:.2f}%)")
    print(f"      - 平均价差率: {extreme_spreads['basis_rate'].mean():.4f}%")
    
    print("\n  3️⃣  资金费率套利 (你当前策略):")
    print("      - 继续专注于资金费率套利")
    print("      - 现货-期货套利在当前市场不适用")

def calculate_strategy_returns(df):
    """计算假设策略收益"""
    print("\n" + "="*80)
    print("假设策略回测 (反向套利)")
    print("="*80)
    
    # 模拟策略: 价差率低于-0.06%时入场,回归到-0.04%时出场
    entry_threshold = -0.06
    exit_threshold = -0.04
    
    position = 0  # 0=无仓位, 1=持仓
    trades = []
    entry_price_spot = 0
    entry_price_future = 0
    
    for idx, row in df.iterrows():
        if position == 0 and row['basis_rate'] < entry_threshold:
            # 开仓: 做空现货, 做多期货
            position = 1
            entry_price_spot = row['close_spot']
            entry_price_future = row['close_future']
            entry_time = row['datetime']
            
        elif position == 1 and row['basis_rate'] > exit_threshold:
            # 平仓
            position = 0
            exit_price_spot = row['close_spot']
            exit_price_future = row['close_future']
            exit_time = row['datetime']
            
            # 计算收益
            # 做空现货: 卖出价格 - 买入价格
            spot_pnl = (entry_price_spot - exit_price_spot) / entry_price_spot
            # 做多期货: 买入价格 - 卖出价格
            future_pnl = (exit_price_future - entry_price_future) / entry_price_future
            
            total_pnl = (spot_pnl + future_pnl) * 100  # 转为百分比
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': exit_time,
                'duration_hours': (exit_time - entry_time).total_seconds() / 3600,
                'entry_spread': (entry_price_future - entry_price_spot) / entry_price_spot * 100,
                'exit_spread': (exit_price_future - exit_price_spot) / exit_price_spot * 100,
                'pnl_pct': total_pnl
            })
    
    if trades:
        trades_df = pd.DataFrame(trades)
        print(f"\n总交易次数: {len(trades_df)}")
        print(f"胜率: {(trades_df['pnl_pct'] > 0).sum() / len(trades_df) * 100:.2f}%")
        print(f"平均收益率: {trades_df['pnl_pct'].mean():.4f}%")
        print(f"总收益率: {trades_df['pnl_pct'].sum():.4f}%")
        print(f"最大单次收益: {trades_df['pnl_pct'].max():.4f}%")
        print(f"最大单次亏损: {trades_df['pnl_pct'].min():.4f}%")
        print(f"平均持仓时间: {trades_df['duration_hours'].mean():.2f} 小时")
        
        print("\n交易详情:")
        print(trades_df.to_string(index=False))
    else:
        print("\n⚠️  在当前参数下没有触发任何交易")
        print(f"   入场阈值: {entry_threshold}%")
        print(f"   出场阈值: {exit_threshold}%")
        print(f"   价差率范围: {df['basis_rate'].min():.4f}% 到 {df['basis_rate'].max():.4f}%")

def main():
    print("="*80)
    print("BTC 现货-期货价差深度分析")
    print("="*80)
    
    # 加载数据
    df, filename = load_latest_data()
    
    # 分析价差分布
    analyze_spread_distribution(df)
    
    # 寻找套利机会
    find_arbitrage_opportunities(df)
    
    # 计算策略收益
    calculate_strategy_returns(df)
    
    # 绘制图表
    plot_analysis(df)
    
    print("\n" + "="*80)
    print("分析完成!")
    print("="*80)

if __name__ == '__main__':
    main()

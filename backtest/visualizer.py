"""
回测结果可视化
生成权益曲线、回撤曲线、交易分布等图表
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from typing import List, Optional
from pathlib import Path
import numpy as np

from .types import BacktestResult, EquityPoint, Trade
from .metrics import PerformanceMetrics


class BacktestVisualizer:
    """回测可视化器"""

    def __init__(self, result: BacktestResult):
        self.result = result
        self.fig = None
        self.axes = None

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

    def generate_report(self, save_path: Optional[str] = None, show: bool = True):
        """
        生成完整的可视化报告

        Args:
            save_path: 保存路径（如果提供）
            show: 是否显示图表
        """
        # 创建 2x3 子图布局
        self.fig, self.axes = plt.subplots(2, 3, figsize=(16, 10))
        self.fig.suptitle(
            f'回测报告 | {self.result.start_time.strftime("%Y-%m-%d")} - {self.result.end_time.strftime("%Y-%m-%d")}',
            fontsize=14, fontweight='bold'
        )

        # 1. 权益曲线
        self._plot_equity_curve(self.axes[0, 0])

        # 2. 回撤曲线
        self._plot_drawdown_curve(self.axes[0, 1])

        # 3. 收益分布
        self._plot_return_distribution(self.axes[0, 2])

        # 4. 月度收益热力图
        self._plot_monthly_returns(self.axes[1, 0])

        # 5. 交易盈亏分布
        self._plot_trade_pnl(self.axes[1, 1])

        # 6. 关键指标摘要
        self._plot_metrics_summary(self.axes[1, 2])

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"报告已保存: {save_path}")

        if show:
            plt.show()

        return self.fig

    def _plot_equity_curve(self, ax):
        """绘制权益曲线"""
        if not self.result.equity_curve:
            ax.text(0.5, 0.5, '无数据', ha='center', va='center')
            ax.set_title('权益曲线')
            return

        timestamps = [p.timestamp for p in self.result.equity_curve]
        equities = [float(p.equity) for p in self.result.equity_curve]

        ax.plot(timestamps, equities, 'b-', linewidth=1.5, label='权益')
        ax.fill_between(timestamps, equities, alpha=0.3)

        # 标记最高点和最低点
        max_idx = np.argmax(equities)
        min_idx = np.argmin(equities)
        ax.scatter([timestamps[max_idx]], [equities[max_idx]], c='green', s=50, zorder=5)
        ax.scatter([timestamps[min_idx]], [equities[min_idx]], c='red', s=50, zorder=5)

        ax.axhline(y=float(self.result.initial_capital), color='gray', linestyle='--', alpha=0.5)

        ax.set_title('权益曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('权益 (USDT)')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.grid(True, alpha=0.3)
        ax.legend()

    def _plot_drawdown_curve(self, ax):
        """绘制回撤曲线"""
        if not self.result.equity_curve:
            ax.text(0.5, 0.5, '无数据', ha='center', va='center')
            ax.set_title('回撤曲线')
            return

        timestamps = [p.timestamp for p in self.result.equity_curve]
        drawdowns = PerformanceMetrics.calculate_drawdown_curve(self.result.equity_curve)
        dd_values = [float(d) * 100 for d in drawdowns]  # 转为百分比

        ax.fill_between(timestamps, dd_values, color='red', alpha=0.5)
        ax.plot(timestamps, dd_values, 'r-', linewidth=1)

        # 标记最大回撤
        max_dd_idx = np.argmax(dd_values)
        ax.scatter([timestamps[max_dd_idx]], [dd_values[max_dd_idx]], c='darkred', s=80, zorder=5)
        ax.annotate(f'{dd_values[max_dd_idx]:.1f}%',
                   (timestamps[max_dd_idx], dd_values[max_dd_idx]),
                   textcoords="offset points", xytext=(0,10), ha='center')

        ax.set_title('回撤曲线')
        ax.set_xlabel('日期')
        ax.set_ylabel('回撤 (%)')
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
        ax.grid(True, alpha=0.3)
        ax.invert_yaxis()

    def _plot_return_distribution(self, ax):
        """绘制收益分布"""
        returns = PerformanceMetrics.calculate_returns(self.result.equity_curve)

        if len(returns) == 0:
            ax.text(0.5, 0.5, '无数据', ha='center', va='center')
            ax.set_title('日收益分布')
            return

        returns_pct = returns * 100

        # 直方图
        n, bins, patches = ax.hist(returns_pct, bins=30, edgecolor='white', alpha=0.7)

        # 着色：正收益绿色，负收益红色
        for i, patch in enumerate(patches):
            if bins[i] < 0:
                patch.set_facecolor('red')
            else:
                patch.set_facecolor('green')

        # 标记均值
        mean_return = np.mean(returns_pct)
        ax.axvline(mean_return, color='blue', linestyle='--', linewidth=2, label=f'均值: {mean_return:.2f}%')

        ax.set_title('日收益分布')
        ax.set_xlabel('日收益率 (%)')
        ax.set_ylabel('频数')
        ax.legend()
        ax.grid(True, alpha=0.3)

    def _plot_monthly_returns(self, ax):
        """绘制月度收益"""
        if not self.result.equity_curve:
            ax.text(0.5, 0.5, '无数据', ha='center', va='center')
            ax.set_title('月度收益')
            return

        # 计算月度收益
        monthly_returns = {}
        prev_equity = float(self.result.initial_capital)

        for point in self.result.equity_curve:
            month_key = point.timestamp.strftime('%Y-%m')
            current_equity = float(point.equity)

            if month_key not in monthly_returns:
                monthly_returns[month_key] = {
                    'start': prev_equity,
                    'end': current_equity
                }
            else:
                monthly_returns[month_key]['end'] = current_equity

            prev_equity = current_equity

        # 计算收益率
        months = list(monthly_returns.keys())
        returns = []
        for month in months:
            data = monthly_returns[month]
            ret = (data['end'] - data['start']) / data['start'] * 100
            returns.append(ret)

        # 绘制柱状图
        colors = ['green' if r >= 0 else 'red' for r in returns]
        ax.bar(range(len(months)), returns, color=colors, alpha=0.7)

        ax.set_xticks(range(len(months)))
        ax.set_xticklabels([m[-2:] + '月' for m in months], rotation=45)
        ax.axhline(0, color='black', linewidth=0.5)

        ax.set_title('月度收益')
        ax.set_ylabel('收益率 (%)')
        ax.grid(True, alpha=0.3, axis='y')

    def _plot_trade_pnl(self, ax):
        """绘制交易盈亏分布"""
        closed_trades = [t for t in self.result.trades if t.pnl is not None]

        if not closed_trades:
            ax.text(0.5, 0.5, '无交易数据', ha='center', va='center')
            ax.set_title('交易盈亏')
            return

        pnls = [float(t.pnl) for t in closed_trades]
        colors = ['green' if p >= 0 else 'red' for p in pnls]

        ax.bar(range(len(pnls)), pnls, color=colors, alpha=0.7, width=0.8)
        ax.axhline(0, color='black', linewidth=0.5)

        ax.set_title(f'交易盈亏 (共{len(pnls)}笔)')
        ax.set_xlabel('交易序号')
        ax.set_ylabel('盈亏 (USDT)')
        ax.grid(True, alpha=0.3, axis='y')

    def _plot_metrics_summary(self, ax):
        """绘制关键指标摘要"""
        ax.axis('off')

        metrics = [
            ('总收益率', f'{float(self.result.total_return):.2%}'),
            ('年化收益', f'{float(self.result.total_return) * 365 / max(self.result.duration_days, 1):.2%}'),
            ('夏普比率', f'{self.result.sharpe_ratio:.2f}'),
            ('索提诺比率', f'{self.result.sortino_ratio:.2f}'),
            ('最大回撤', f'{float(self.result.max_drawdown):.2%}'),
            ('胜率', f'{self.result.win_rate:.2%}'),
            ('盈亏比', f'{self.result.profit_factor:.2f}'),
            ('总交易次数', f'{self.result.total_trades}'),
            ('平均盈利', f'${float(self.result.avg_win):.2f}'),
            ('平均亏损', f'${float(self.result.avg_loss):.2f}'),
            ('总手续费', f'${float(self.result.total_fees):.2f}'),
        ]

        # 绘制表格
        y_start = 0.95
        y_step = 0.08

        for i, (label, value) in enumerate(metrics):
            y = y_start - i * y_step

            # 根据数值着色
            if '收益' in label or '盈' in label:
                try:
                    val = float(value.replace('%', '').replace('$', ''))
                    color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                except:
                    color = 'black'
            else:
                color = 'black'

            ax.text(0.05, y, f'{label}:', fontsize=11, fontweight='bold', transform=ax.transAxes)
            ax.text(0.55, y, value, fontsize=11, color=color, transform=ax.transAxes)

        ax.set_title('关键指标', fontsize=12, fontweight='bold', pad=20)

    def save_html_report(self, filepath: str):
        """
        生成HTML报告

        Args:
            filepath: HTML文件路径
        """
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>回测报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
        .metric-card {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; }}
        .metric-label {{ color: #666; margin-top: 5px; }}
        .positive {{ color: #28a745; }}
        .negative {{ color: #dc3545; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #007bff; color: white; }}
        tr:hover {{ background: #f5f5f5; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 回测报告</h1>
        <p>回测周期: {self.result.start_time.strftime('%Y-%m-%d')} 至 {self.result.end_time.strftime('%Y-%m-%d')} ({self.result.duration_days} 天)</p>

        <div class="summary">
            <div class="metric-card">
                <div class="metric-value {'positive' if float(self.result.total_return) > 0 else 'negative'}">{float(self.result.total_return):.2%}</div>
                <div class="metric-label">总收益率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{self.result.sharpe_ratio:.2f}</div>
                <div class="metric-label">夏普比率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value negative">{float(self.result.max_drawdown):.2%}</div>
                <div class="metric-label">最大回撤</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{self.result.win_rate:.2%}</div>
                <div class="metric-label">胜率</div>
            </div>
        </div>

        <h2>💰 资金概况</h2>
        <table>
            <tr><th>指标</th><th>数值</th></tr>
            <tr><td>初始资金</td><td>${float(self.result.initial_capital):,.2f}</td></tr>
            <tr><td>最终资金</td><td>${float(self.result.final_capital):,.2f}</td></tr>
            <tr><td>总盈亏</td><td class="{'positive' if float(self.result.total_pnl) > 0 else 'negative'}">${float(self.result.total_pnl):,.2f}</td></tr>
            <tr><td>总手续费</td><td>${float(self.result.total_fees):,.2f}</td></tr>
        </table>

        <h2>📈 交易统计</h2>
        <table>
            <tr><th>指标</th><th>数值</th></tr>
            <tr><td>总交易次数</td><td>{self.result.total_trades}</td></tr>
            <tr><td>盈利次数</td><td class="positive">{self.result.winning_trades}</td></tr>
            <tr><td>亏损次数</td><td class="negative">{self.result.losing_trades}</td></tr>
            <tr><td>平均盈利</td><td class="positive">${float(self.result.avg_win):,.2f}</td></tr>
            <tr><td>平均亏损</td><td class="negative">${float(self.result.avg_loss):,.2f}</td></tr>
            <tr><td>盈亏比</td><td>{self.result.profit_factor:.2f}</td></tr>
            <tr><td>平均持仓时间</td><td>{self.result.avg_holding_period_hours:.1f} 小时</td></tr>
        </table>

        <h2>⚠️ 风险指标</h2>
        <table>
            <tr><th>指标</th><th>数值</th><th>说明</th></tr>
            <tr><td>夏普比率</td><td>{self.result.sharpe_ratio:.2f}</td><td>{'优秀' if self.result.sharpe_ratio > 2 else '良好' if self.result.sharpe_ratio > 1 else '一般'}</td></tr>
            <tr><td>索提诺比率</td><td>{self.result.sortino_ratio:.2f}</td><td>只考虑下行风险</td></tr>
            <tr><td>最大回撤</td><td>{float(self.result.max_drawdown):.2%}</td><td>持续 {self.result.max_drawdown_duration_days} 天</td></tr>
        </table>

        <p style="text-align: center; color: #666; margin-top: 40px;">
            Generated by Trading AI System | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </div>
</body>
</html>
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"HTML报告已保存: {filepath}")

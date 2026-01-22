# Trading Risk Control Skills

量化交易风控规则，基于 `risk/manager.py` 提取。

## 核心风控参数

```yaml
止损 (Stop Loss):      -2.0%    # 亏损超过2%立即平仓
止盈 (Take Profit):    +1.5%    # 盈利达到1.5%止盈
单笔仓位 (Position):   30%      # 最多投入可用资金的30%
最大杠杆 (Leverage):   1x       # 保守策略，不使用杠杆
最大持仓数:            3        # 同时最多3个仓位
每日亏损限制:          -5%      # 当日亏损超5%停止交易
最小订单价值:          10 USDT  # 过滤小额噪音订单
```

## 仓位计算公式

```python
position_size = (available_balance * position_size_pct * leverage) / price
```

示例: 余额1000U，价格50000，仓位比例30%，杠杆1x
- 仓位价值 = 1000 × 0.3 × 1 = 300 USDT
- 开仓数量 = 300 / 50000 = 0.006 BTC

## 风控检查流程

```
1. 开仓前检查
   ├─ 交易是否启用 (每日亏损限制)
   ├─ 持仓数量是否达到上限
   └─ 余额是否足够最小订单价值

2. 持仓中监控
   ├─ 实时计算未实现盈亏
   ├─ 检查止损线 (-2%)
   └─ 检查止盈线 (+1.5%)

3. 平仓时处理
   ├─ 更新每日盈亏统计
   ├─ 注销持仓记录
   └─ 检查是否触发每日限制
```

## 盈亏计算

```python
# 多仓盈亏
pnl_pct = (current_price - entry_price) / entry_price

# 空仓盈亏
pnl_pct = (entry_price - current_price) / entry_price
```

## 风险等级定义

| 等级 | 触发条件 | 动作 |
|------|----------|------|
| LOW | 止盈触发 | 平仓获利 |
| MEDIUM | 接近止损线 | 告警 |
| HIGH | 止损触发 | 立即平仓 |
| CRITICAL | 每日亏损限制 | 停止所有交易 |

## 资金费率策略特殊规则

```yaml
做空阈值: 0.5%   # 费率 > 0.5% 时做空
做多阈值: -0.3%  # 费率 < -0.3% 时做多
退出阈值: ±0.1%  # 费率回归中性时平仓
价格止盈: 1%     # 持空时价格盈利超1%平仓
```

## 使用示例

```python
from risk.manager import RiskManager

rm = RiskManager(
    stop_loss_pct=0.02,
    take_profit_pct=0.015,
    position_size_pct=0.30,
    max_leverage=1,
)

# 计算开仓数量
qty = rm.calculate_position_size(balance=1000, price=50000)

# 检查持仓风险
signal = rm.check_position(position)
if signal:
    # 触发止盈止损，需要平仓
    pass
```

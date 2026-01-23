# Trading AI System v1.0

一个基于量化策略的加密货币交易系统，专注于低风险套利策略的开发与实盘部署。

## 🎯 项目简介

本项目实现了多种量化交易策略，包括资金费率套利和现货期货套利。系统支持历史数据回测、参数优化和实盘交易。

### 核心特性

- ✅ **多策略支持**：资金费率套利、现货期货套利
- ✅ **完整回测引擎**：支持止损止盈、风险控制
- ✅ **参数优化**：网格搜索最优参数组合
- ✅ **实盘部署**：OKX交易所API集成
- ✅ **风险控制**：最大回撤控制、仓位管理
- ✅ **实时监控**：交易信号监控、收益追踪

## 📊 策略概览

### 1. 资金费率套利策略

通过捕捉永续合约的资金费率机会进行套利。

**策略表现**（90天回测）：
- 年化收益：7.1%
- 最大回撤：-2.3%
- 胜率：52.1%
- 交易次数：24笔

📖 详细说明：[资金费率策略文档](docs/funding_rate_strategy.md)

### 2. 现货期货套利策略

利用现货与期货价差进行对冲套利，市场中性策略。

**预期指标**：
- 年化收益：12-24%
- 胜率：70-90%
- 最大回撤：<5%
- 夏普比率：>2.0

📖 详细说明：[现货期货套利文档](docs/spot_futures_arbitrage.md)

## 🚀 快速开始

### 环境要求

- Python 3.8+
- 依赖包见 `requirements.txt`

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/trading-ai-system.git
cd trading-ai-system

# 安装依赖
pip install -r requirements.txt

# 配置API密钥（复制示例配置）
cp config/exchanges/okx.yaml.example config/exchanges/okx.yaml
# 编辑 okx.yaml 填入你的API密钥
```

### 配置API

编辑 `config/exchanges/okx.yaml`：

```yaml
api_key: "your-api-key"
secret_key: "your-secret-key"
passphrase: "your-passphrase"
```

### 运行回测

```bash
# 资金费率策略回测
python test_90d.py

# 现货期货套利回测
python spot_futures_arbitrage_strategy.py
```

### 实盘运行

```bash
# 启动实盘交易机器人
python live_funding_bot_fixed.py
```

## 📁 项目结构

```
trading-ai-system/
├── README.md                          # 项目主说明
├── requirements.txt                   # Python依赖
├── main.py                           # 主入口程序
│
├── config/                           # 配置文件
│   ├── settings.yaml                 # 全局配置
│   └── exchanges/                    # 交易所配置
│       └── okx.yaml                  # OKX API配置
│
├── core/                             # 核心模块
│   ├── backtest_engine.py           # 回测引擎
│   └── position_manager.py          # 仓位管理
│
├── strategies/                       # 策略模块
│   ├── funding_rate/                # 资金费率策略
│   └── spot_futures/                # 现货期货套利
│
├── exchanges/                        # 交易所接口
│   └── okx/                         # OKX交易所
│
├── risk/                            # 风险控制
│   └── risk_manager.py              # 风险管理器
│
├── monitoring/                      # 监控模块
│   └── performance/                 # 性能监控
│
├── data/                            # 数据目录
│   ├── market/                      # 市场数据
│   └── backtest/                    # 回测结果
│
├── scripts/                         # 工具脚本
│   ├── download_data.py            # 数据下载
│   ├── optimize_parameters.py      # 参数优化
│   └── analyze_basis_spread.py     # 价差分析
│
├── tests/                          # 测试文件
│   ├── test_backtest.py           # 回测测试
│   ├── test_strategy_v2.py        # 策略测试
│   └── test_connection.py         # 连接测试
│
└── docs/                           # 项目文档
    ├── funding_rate_strategy.md   # 资金费率策略
    ├── spot_futures_arbitrage.md  # 现货期货套利
    └── parameter_optimization.md  # 参数优化指南
```

## 🔧 开发指南

### 数据下载

```bash
# 下载历史数据（默认90天）
python scripts/download_data.py --days 90 --symbol BTC-USDT

# 下载现货+期货双边数据
python scripts/download_data_v2.py --days 90
```

### 参数优化

```bash
# 运行参数网格搜索
python scripts/optimize_parameters.py

# 查看优化结果
cat data/backtest/optimization_results.json
```

### 实时监控

```bash
# 监控价差机会
python scripts/monitor_basis_spread.py

# 检查当前市场状态
python scripts/check_basis_now.py
```

## 📈 回测结果

### 资金费率策略 V2（最新）

**测试周期**：2024年10月 - 2025年1月（90天）

| 指标 | 数值 |
|------|------|
| 总收益 | +1.78% |
| 年化收益 | **7.1%** |
| 最大回撤 | -2.3% |
| 夏普比率 | 1.12 |
| 胜率 | 52.1% |
| 盈亏比 | 0.42 |
| 交易次数 | 24笔 |

**优化参数**：
- 趋势阈值：0.35
- 止损：1.5%
- 止盈：2.5%
- 成交量确认：1.2x
- 波动率阈值：3.0%

## ⚠️ 风险提示

1. **历史表现不代表未来收益**：回测结果基于历史数据，实盘可能有差异
2. **市场风险**：加密货币市场波动大，可能面临极端行情
3. **技术风险**：API故障、网络中断可能影响交易执行
4. **资金管理**：建议单策略资金不超过总资金的30%
5. **严格止损**：设置止损线，避免单笔损失过大

## 📝 开发计划

- [x] 资金费率策略回测验证
- [x] 参数优化系统
- [x] 实盘部署框架
- [ ] 现货期货套利完整实现
- [ ] 多交易所支持（Binance, Bybit）
- [ ] Web监控面板
- [ ] 风险预警系统

## 📖 文档

- [资金费率策略详解](docs/funding_rate_strategy.md)
- [现货期货套利说明](docs/spot_futures_arbitrage.md)
- [参数优化指南](docs/parameter_optimization.md)

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 License

MIT License

## 📧 联系方式

如有问题，请提交Issue或联系项目维护者。

---

**免责声明**：本项目仅供学习和研究使用，不构成投资建议。使用本系统进行实盘交易的风险由使用者自行承担。

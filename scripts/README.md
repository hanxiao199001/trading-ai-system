# Scripts 工具脚本目录

这个目录包含各种辅助工具脚本。

## 📁 文件说明

### 数据下载

- **download_data.py** - 单边数据下载（期货或现货）
- **download_data_v2.py** - 双边数据下载（现货+期货）
- **fetch_basis_data.py** - 获取基差数据

### 数据分析

- **analyze_basis_spread.py** - 分析基差走势
- **check_basis_now.py** - 检查当前市场基差
- **monitor_basis_spread.py** - 实时监控基差机会

### 参数优化

- **optimize_parameters.py** - 参数优化主脚本（集成版）
- **optimize_params_standalone.py** - 参数优化独立版
- **optimize_v2.py** - 优化脚本 V2
- **optimize_v3.py** - 优化脚本 V3

### 实盘机器人

- **live_funding_bot.py** - 资金费率机器人旧版（已废弃，保留参考）

## 🚀 常用命令

```bash
# 下载数据
python scripts/download_data.py --days 90 --symbol BTC-USDT-SWAP

# 参数优化
python scripts/optimize_parameters.py

# 监控基差
python scripts/monitor_basis_spread.py

# 检查当前市场
python scripts/check_basis_now.py
```

## 📝 注意事项

1. 运行脚本前确保在项目根目录
2. 确保已安装所有依赖：`pip install -r requirements.txt`
3. 配置好API密钥（如果需要实时数据）

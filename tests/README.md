# Tests 测试目录

这个目录包含各种测试脚本。

## 📁 文件说明

### 回测测试

- **test_90d.py** - 90天回测测试（资金费率策略）
- **test_backtest.py** - 回测引擎测试
- **test_real_backtest.py** - 真实回测测试

### 策略测试

- **test_strategy_v2.py** - 策略V2测试
- **test_strategy_v2_tune.py** - 策略V2参数调优测试

### 连接测试

- **test_connection.py** - API连接测试

## 🚀 运行测试

```bash
# 运行90天回测
python tests/test_90d.py

# 测试API连接
python tests/test_connection.py

# 测试策略V2
python tests/test_strategy_v2.py
```

## 📊 测试结果

测试结果通常保存在以下位置：
- 回测结果：`data/backtest/`
- 日志文件：项目根目录或指定的日志目录

## 📝 注意事项

1. 测试前确保数据已下载到 `data/` 目录
2. API测试需要配置 `config/exchanges/okx.yaml`
3. 回测测试可能需要几分钟时间

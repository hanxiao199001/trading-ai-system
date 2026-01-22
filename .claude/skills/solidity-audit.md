# Solidity Smart Contract Audit Checklist

智能合约安全审计清单模板。

## 审计等级

- **P0 Critical**: 可直接导致资金损失
- **P1 High**: 严重逻辑漏洞
- **P2 Medium**: 潜在风险
- **P3 Low**: 代码优化建议

---

## 1. 重入攻击 (Reentrancy)

```solidity
// ❌ 危险模式
function withdraw(uint amount) external {
    require(balances[msg.sender] >= amount);
    (bool success, ) = msg.sender.call{value: amount}("");
    balances[msg.sender] -= amount;  // 状态更新在外部调用之后
}

// ✅ 安全模式 (CEI: Checks-Effects-Interactions)
function withdraw(uint amount) external {
    require(balances[msg.sender] >= amount);
    balances[msg.sender] -= amount;  // 先更新状态
    (bool success, ) = msg.sender.call{value: amount}("");
    require(success);
}
```

检查项:
- [ ] 外部调用前更新状态
- [ ] 使用 ReentrancyGuard
- [ ] 避免 `call` 的返回值被忽略

---

## 2. 整数溢出/下溢

```solidity
// Solidity 0.8+ 自动检查，但 unchecked 块需注意
unchecked {
    uint8 x = 255;
    x++;  // 溢出为 0，不会 revert
}
```

检查项:
- [ ] Solidity 版本 >= 0.8.0
- [ ] `unchecked` 块中的算术运算
- [ ] 类型转换（大转小）

---

## 3. 访问控制

```solidity
// ❌ 缺少权限检查
function setPrice(uint _price) external {
    price = _price;
}

// ✅ 正确的权限控制
function setPrice(uint _price) external onlyOwner {
    price = _price;
}
```

检查项:
- [ ] 敏感函数有 `onlyOwner` / `onlyRole`
- [ ] `initialize()` 只能调用一次
- [ ] 代理合约的 admin 函数保护

---

## 4. 预言机操纵

```solidity
// ❌ 单一来源，易被操纵
uint price = uniswapPair.getReserves();

// ✅ 使用 TWAP 或多预言机
uint price = chainlinkOracle.latestAnswer();
```

检查项:
- [ ] 价格来源的可靠性
- [ ] 是否使用 TWAP
- [ ] 闪电贷攻击防护

---

## 5. 前端运行 (Front-running)

检查项:
- [ ] 敏感操作是否可被抢跑
- [ ] 是否需要 commit-reveal 模式
- [ ] 滑点保护参数

---

## 6. 拒绝服务 (DoS)

```solidity
// ❌ 循环中的外部调用
for (uint i = 0; i < users.length; i++) {
    users[i].transfer(amounts[i]);  // 一个失败全部回滚
}

// ✅ Pull 模式
mapping(address => uint) public pendingWithdrawals;
function withdraw() external {
    uint amount = pendingWithdrawals[msg.sender];
    pendingWithdrawals[msg.sender] = 0;
    payable(msg.sender).transfer(amount);
}
```

检查项:
- [ ] 数组长度限制
- [ ] 使用 Pull 而非 Push
- [ ] 避免依赖外部调用成功

---

## 7. 签名相关

检查项:
- [ ] 签名重放保护 (nonce)
- [ ] 链ID检查
- [ ] 签名过期时间
- [ ] `ecrecover` 返回地址零检查

---

## 8. 代理合约

检查项:
- [ ] 存储槽冲突
- [ ] `selfdestruct` 风险
- [ ] 实现合约初始化
- [ ] 升级权限控制

---

## 9. 代码质量

检查项:
- [ ] 事件日志完整性
- [ ] 错误信息清晰
- [ ] NatSpec 文档
- [ ] 测试覆盖率 > 90%

---

## 审计报告模板

```markdown
## 发现 #1: [标题]

**严重程度**: P0/P1/P2/P3
**位置**: `Contract.sol:L42`
**描述**: ...
**影响**: ...
**建议修复**: ...
**状态**: 待修复 / 已修复 / 已确认风险
```

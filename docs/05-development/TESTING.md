# ICYQuant Testing

> 本文档描述 ICYQuant 的测试体系。

---

## 1. 测试分层

```text
Unit Test
    ↓
Component Test
    ↓
Integration Test
    ↓
Domain Test
    ↓
Event Test
    ↓
Recovery Test
    ↓
End-to-End Test
```

---

## 2. 重点测试场景

```text
正常交易
拒单
风控拒绝
重复事件
事件丢失
状态重建
账实不一致
Recovery
Replay
Idempotency
```

> **对于 ICYQuant 来说：Recovery Test 的重要性不低于 Happy Path Test。**

---

## 3. 测试规模

- `tests/` 242 个测试文件
- 数千用例
- 覆盖全部业务域

---

## 4. 运行测试

```bash
# 全部
pytest tests/

# 指定域
pytest tests/risk/
pytest tests/control_plane/

# 指定文件
pytest tests/risk/test_risk_decision_trace.py
```

---

## 5. 测试类型说明

| 类型 | 说明 |
|------|------|
| Unit Test | 单类 / 单函数 |
| Component Test | 组件内协作 |
| Integration Test | 跨组件 / 跨域 |
| Domain Test | 领域规则与状态机 |
| Event Test | 事件发布 / 订阅 / 重放 |
| Recovery Test | 恢复、修复、重建、幂等 |
| E2E Test | 全链路 |

---

## 6. 测试数据

- 内存 / SQLite 存储用于测试
- 事件总线使用 In-memory 实现
- 确定性数据（固定种子）

---

## 7. 相关文档

- 开发指南：[DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md)
- 代码风格：[CODE_STYLE.md](./CODE_STYLE.md)
- 最终发布检查清单：[../07-release/FINAL_RELEASE_CHECKLIST.md](../07-release/FINAL_RELEASE_CHECKLIST.md)

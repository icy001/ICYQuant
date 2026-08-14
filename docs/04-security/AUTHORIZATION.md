# ICYQuant Authorization

> 本文档描述 ICYQuant 的授权机制（RBAC 与权限判定）。

---

## 1. 职责

Authorization 负责**授权判定**：确认"你能做什么"。

```text
认证通过的身份
    ↓
角色（Role）
    ↓
权限（Permissions）
    ↓
操作是否允许
```

---

## 2. 角色与权限分离

| 角色 | 权限范围 |
|------|----------|
| ADMIN | 全部权限 |
| RESEARCHER | 研究 / 回测 / 分析 |
| TRADER | 订单 / 执行 |
| RISK | 风险政策 / 决策 / 恢复请求 |
| OPERATOR | 部署 / 监控 / 恢复 |
| READ_ONLY | 只读访问 |

---

## 3. 授权判定组件

- `services/control_plane/authorizer.py` — 授权器
- 控制网关（ALLOW / REDUCE_ONLY / BLOCK）操作需授权
- 治理审批（四眼审批 / 职责分离）

---

## 4. 关键授权规则

- 控制网关切换需高权限（四眼审批）
- 风险策略变更需 RISK / ADMIN
- 审计日志只能追加（不可修改）

---

## 5. 职责分离（SoD）

- 创建交易与批准交易分离
- 风控决策与执行分离
- 防止单一角色滥用

---

## 6. 相关文档

- 安全架构：[SECURITY_ARCHITECTURE.md](./SECURITY_ARCHITECTURE.md)
- 认证：[AUTHENTICATION.md](./AUTHENTICATION.md)
- Auth/RBAC 技术设计：[../02-technical/AUTH_RBAC.md](../02-technical/AUTH_RBAC.md)

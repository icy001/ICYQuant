# ICYQuant Auth & RBAC

> 本文档描述 ICYQuant 的认证与授权（RBAC）设计。

---

## 1. 安全链路

ICYQuant 已建立完整安全链路：

```text
Authentication
       ↓
Authorization
       ↓
RBAC
       ↓
Audit
       ↓
Rate Limit
```

---

## 2. 权限模型

权限模型采用**角色与权限分离**：

```text
Role（角色）
   └── has
          ↓
      Permissions（权限集合）
```

- 用户 → 角色 → 权限
- 权限决定操作是否允许

---

## 3. 典型角色

```text
ADMIN          系统管理员（全部权限）
RESEARCHER     研究员（研究 / 回测 / 分析）
TRADER         交易员（订单 / 执行）
RISK           风控（风险政策 / 决策 / 恢复）
OPERATOR       运维（部署 / 监控 / 恢复）
READ_ONLY      只读（报表 / 审计查看）
```

---

## 4. 授权机制

- `services/control_plane/authorizer.py` — 授权器
- 控制网关权限（ALLOW / REDUCE_ONLY / BLOCK 操作授权）
- 治理审批（四眼审批 / 职责分离）

---

## 5. 认证

- Authentication 服务负责身份认证
- 认证成功后才进入授权判定

---

## 6. 与审计结合

- 每次授权决策可进入审计记录
- 职责分离（SoD）：同一用户不能同时拥有冲突角色

---

## 7. 相关文档

- 安全架构：[../04-security/SECURITY_ARCHITECTURE.md](../04-security/SECURITY_ARCHITECTURE.md)
- 认证：[../04-security/AUTHENTICATION.md](../04-security/AUTHENTICATION.md)
- 授权：[../04-security/AUTHORIZATION.md](../04-security/AUTHORIZATION.md)

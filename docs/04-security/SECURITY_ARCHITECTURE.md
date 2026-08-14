# ICYQuant Security Architecture

> 本文档描述 ICYQuant 的安全架构。

---

## 1. 安全链路

ICYQuant 已建立：

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

## 2. 安全分层

| 层 | 能力 |
|----|------|
| 传输安全 | HTTPS / 安全连接 |
| 认证 | 身份认证（Authentication） |
| 授权 | 权限判定（Authorization / RBAC） |
| 审计 | 操作记录（Audit，不可变） |
| 限流 | 滥用防护（Rate Limit） |
| 数据安全 | 密钥加密、敏感信息脱敏 |

---

## 3. 角色与权限分离

```text
用户 → 角色 → 权限
```

典型角色：

```text
ADMIN / RESEARCHER / TRADER / RISK / OPERATOR / READ_ONLY
```

---

## 4. 最小权限原则

- 服务只拥有完成任务所需权限
- Risk 只判断不修改交易状态（减少写权限）
- 控制网关操作需授权

---

## 5. 职责分离（SoD）

- 关键操作需四眼审批（Four-Eyes Approval）
- 同一用户不能同时拥有冲突角色

---

## 6. 安全审计

- 敏感操作进入审计
- 审计记录不可变
- 详见 [AUDIT_POLICY.md](./AUDIT_POLICY.md)

---

## 7. 相关文档

- 认证：[AUTHENTICATION.md](./AUTHENTICATION.md)
- 授权：[AUTHORIZATION.md](./AUTHORIZATION.md)
- 审计策略：[AUDIT_POLICY.md](./AUDIT_POLICY.md)
- 安全检查清单：[SECURITY_CHECKLIST.md](./SECURITY_CHECKLIST.md)
- Auth/RBAC 技术设计：[../02-technical/AUTH_RBAC.md](../02-technical/AUTH_RBAC.md)

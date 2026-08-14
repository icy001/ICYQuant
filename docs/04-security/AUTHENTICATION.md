# ICYQuant Authentication

> 本文档描述 ICYQuant 的认证机制。

---

## 1. 职责

Authentication 负责**身份认证**：确认"你是谁"。

```text
请求 → 认证 → 身份凭据 → 进入授权判定
```

---

## 2. 认证方式

| 方式 | 说明 |
|------|------|
| Token 认证 | API 请求携带 Token |
| Session 认证 | 管理端会话 |
| 服务间认证 | 服务账户 / 凭据 |

---

## 3. 认证端点保护

- 认证端点（登录等）使用更严格 Rate Limit
- 防暴力破解
- 登录失败记录安全日志

---

## 4. 认证失败处理

- 统一错误响应
- 记录安全审计
- 连续失败触发限流 / 锁定

---

## 5. 凭据管理

- 密码 / 密钥加密存储
- 密钥管理（配置中的 `SECRET_*`）
- 不在日志中输出凭据

---

## 6. 相关文档

- 安全架构：[SECURITY_ARCHITECTURE.md](./SECURITY_ARCHITECTURE.md)
- 授权：[AUTHORIZATION.md](./AUTHORIZATION.md)
- 限流：[../02-technical/RATE_LIMIT.md](../02-technical/RATE_LIMIT.md)

# ICYQuant Rate Limit

> 本文档描述 ICYQuant 的限流（Rate Limit）设计。

---

## 1. 用途

Rate Limit 用于：

- API Abuse Protection（API 滥用防护）
- Request Flood Protection（请求洪峰防护）
- Resource Protection（资源保护）
- Authentication Endpoint Protection（认证端点保护）

---

## 2. 限流维度

| 维度 | 说明 |
|------|------|
| 用户维度 | 按用户 / 账户限流 |
| IP 维度 | 按来源 IP 限流 |
| 端点维度 | 按 API 端点限流 |
| 全局维度 | 全局限流（保护系统） |

---

## 3. 实现

- 基于 Redis 的滑动窗口 / 令牌桶
- 认证端点采用更严格阈值（防暴力破解）
- 与 Auth / RBAC 链结合

---

## 4. 超限行为

- 返回 `429 Too Many Requests`
- 记录审计 / 日志
- 可触发告警

---

## 5. 相关文档

- 安全架构：[../04-security/SECURITY_ARCHITECTURE.md](../04-security/SECURITY_ARCHITECTURE.md)
- 安全检查清单：[../04-security/SECURITY_CHECKLIST.md](../04-security/SECURITY_CHECKLIST.md)
- 监控：[../03-operations/MONITORING.md](../03-operations/MONITORING.md)

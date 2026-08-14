# ICYQuant Configuration

> 本文档描述 ICYQuant 的配置体系。

---

## 1. 配置来源

配置优先级（高 → 低）：

```text
环境变量
    ↓
configs/ 下的 YAML 文件
    ↓
默认值
```

---

## 2. 配置文件

`configs/` 目录包含 50+ YAML 配置：

| 分类 | 示例 |
|------|------|
| 服务配置 | 服务端口、超时、重试 |
| 数据库 | 连接、池大小 |
| 消息队列 | Kafka 配置 |
| 日志 | 级别、格式 |
| 特性开关 | Feature Flag |
| 风控 | 风险政策、限额默认值 |

---

## 3. 关键环境变量

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | 数据库连接串 |
| `REDIS_URL` | Redis 连接串 |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka 地址 |
| `LOG_LEVEL` | 日志级别 |
| `ENV` | 环境（dev / test / prod） |
| `SECRET_*` | 密钥相关 |

---

## 4. 配置管理原则

- 敏感信息不写入代码库（使用密钥管理）
- 环境隔离（dev / test / prod 配置分离）
- 配置变更可审计
- 启动时校验配置合法性

---

## 5. 配置校验

系统启动时校验：

- 必填项是否齐全
- 值是否合法（端口、URL、级别）
- 数据库可连接性
- 依赖服务可达性

---

## 6. 相关文档

- 部署：[DEPLOYMENT.md](./DEPLOYMENT.md)
- 数据库：[DATABASE.md](./DATABASE.md)
- 日志：[LOGGING.md](./LOGGING.md)

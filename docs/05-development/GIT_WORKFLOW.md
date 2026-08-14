# ICYQuant Git Workflow

> 本文档描述 ICYQuant 的分支与提交流程。

---

## 1. 分支模型

```text
main / master（发布分支）
    │
    └── develop（开发主线）
            │
            └── feature/*（功能分支）
            └── fix/*（修复分支）
```

---

## 2. 当前状态

- 开发主线：`develop`
- 当前版本：`v0.4.0-alpha2`
- 最新提交：`Commit 41`

---

## 3. 提交规范

```text
1. 一个逻辑变更一个提交
2. 变更前运行测试
3. 提交 message 清晰描述变更
4. 不提交临时文件
```

### Commit 命名约定

项目历史采用 `Commit N` 序列：

```text
Commit 1
Commit 2
...
Commit 41
```

> 特别澄清：`Commit 41 Part 1.1 ~ 1.5` 是同一个 Commit 的 5 个部分，不是 5 个 Commit。

---

## 4. 冻结约定（正式）

自 v0.4.0-alpha2 / Commit 41 起，**停止无限 Commit 扩张**。

除非进入新的产品版本，否则不再以 Commit 序列方式开发。

---

## 5. Review 流程

```text
开发 → 自测 → 提交分支 → Review → 合并到 develop → 回归 → 发布
```

---

## 6. 相关文档

- 开发指南：[DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md)
- 提交历史：[../07-release/COMMIT_HISTORY.md](../07-release/COMMIT_HISTORY.md)
- 版本管理：[../07-release/VERSIONING.md](../07-release/VERSIONING.md)

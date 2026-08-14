# ICYQuant Contributing

> 本文档是 ICYQuant 的贡献指南。

---

## 1. 项目状态说明

ICYQuant 当前处于 **Documentation Freeze / Development Phase Concluded** 状态。

**原则上不再接受新功能 Commit**，除非：

- 缺陷修复（Bug Fix）
- 文档修正（Documentation Fix）
- 进入新的产品版本（v0.5.0+）

---

## 2. 贡献流程

```text
1. 阅读开发指南与代码风格
2. 明确变更范围
3. 实现 + 测试
4. 运行回归
5. 提交 PR 供 Review
```

---

## 3. 贡献类型

| 类型 | 说明 |
|------|------|
| Bug Fix | 缺陷修复（欢迎） |
| 文档 | 文档修正（欢迎） |
| 测试 | 补充测试（欢迎） |
| 新功能 | 需经评审，仅在进入新版本后 |

---

## 4. 质量要求

- 代码通过全部相关测试
- 遵循代码风格
- 类型注解完整
- 幂等 / 可重放约束不破坏

---

## 5. 相关文档

- 开发指南：[DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md)
- 代码风格：[CODE_STYLE.md](./CODE_STYLE.md)
- 测试：[TESTING.md](./TESTING.md)
- 项目状态：[../00-project/PROJECT_STATUS.md](../00-project/PROJECT_STATUS.md)

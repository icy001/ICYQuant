# ICYQuant Versioning

> 本文档定义 ICYQuant 的版本管理策略。

---

## 1. 版本格式

遵循语义化版本（SemVer）：

```text
MAJOR.MINOR.PATCH[-PRERELEASE]
```

当前版本：

```text
v0.4.0-alpha2
```

| 部分 | 值 | 说明 |
|------|----|------|
| MAJOR | 0 | 尚未到 1.0（早期产品） |
| MINOR | 4 | 平台迭代版本 |
| PATCH | 0 | 补丁版本 |
| PRERELEASE | alpha2 | 预发布（alpha 阶段） |

---

## 2. 阶段定义

| 阶段 | 含义 |
|------|------|
| alpha | 内部验证，功能可能不完整 |
| beta | 外部验证，功能基本完整 |
| rc | 发布候选 |
| GA | 正式发布 |

---

## 3. 版本历史

| 版本 | 阶段 | 说明 |
|------|------|------|
| v0.4.0-alpha1 | 平台起步 | 11 核心模块 GA 前身 |
| v0.4.0-alpha1 GA | GA | 11 模块正式发布（2026-07-30） |
| v0.4.0-alpha2 | 交易域收口 | Commit 1~41，当前版本 |

---

## 4. 版本冻结约定

- 当前 `v0.4.0-alpha2` 为 **Documentation Freeze** 基线
- 除非进入新版本（v0.5.0 等），不再持续发版
- 新版本发布需：功能完成 → 测试通过 → 评审 → 文档更新

---

## 5. 相关文档

- 发布说明：[RELEASE_NOTES.md](./RELEASE_NOTES.md)
- 变更日志：[CHANGELOG.md](./CHANGELOG.md)
- 最终发布检查清单：[FINAL_RELEASE_CHECKLIST.md](./FINAL_RELEASE_CHECKLIST.md)

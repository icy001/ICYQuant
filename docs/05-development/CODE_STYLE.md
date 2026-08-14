# ICYQuant Code Style

> 本文档定义 ICYQuant 的代码风格规范。

---

## 1. 语言与版本

- Python 3.12+
- 类型注解（Type Hints）必须完整

---

## 2. 代码风格

- 遵循 PEP 8
- 使用 `ruff` / `black` 风格格式化
- 行宽 ≤ 100（推荐）
- 命名：
  - 类：`PascalCase`
  - 函数 / 变量：`snake_case`
  - 常量：`UPPER_SNAKE_CASE`
  - 私有成员：前缀 `_`

---

## 3. 类型与数据类

- 领域对象优先使用 `dataclass`
- 不可变对象使用 `@dataclass(frozen=True)`
- 明确类型注解（`str`、`int`、`datetime`、自定义类型）

---

## 4. 领域编码规范

| 规范 | 说明 |
|------|------|
| 显式状态机 | 状态用枚举 / 常量表示，不做魔法字符串 |
| 幂等键 | 使用决策 ID / 事件 ID 作为幂等键 |
| 不可变审计 | 审计对象 frozen |
| 事件驱动 | 状态变更发布事件，不直接跨域调用 |

---

## 5. 测试规范

- 测试文件位于 `tests/` 对应目录
- 命名：`test_<模块>.py`
- 覆盖：正常 / 异常 / 幂等 / 重放 / 恢复

---

## 6. 文档规范

- 模块 docstring 说明职责
- 公共类 / 方法有文档注释
- 不写无意义注释

---

## 7. 相关文档

- 开发指南：[DEVELOPMENT_GUIDE.md](./DEVELOPMENT_GUIDE.md)
- 测试：[TESTING.md](./TESTING.md)

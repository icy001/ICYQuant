# ICYQuant Development Record

## 2026-07-03

### V1 Database Scope

，V1 只建 6 张核心表：

- User
- Account
- Position
- Order
- Trade
- Instrument

### Implementation Notes

- 为避免和常见数据库保留字冲突，实际建表名称使用复数形式。
- 对应关系如下：
  - `User -> users`
  - `Account -> accounts`
  - `Position -> positions`
  - `Order -> orders`
  - `Trade -> trades`
  - `Instrument -> instruments`

### Deliverables

- 开发记录文档：`docs/development-record.md`
- 建表脚本：`scripts/init_v1_schema.sql`

# EURUSD Historical Data Source Connectivity Audit

- **审计时间**: 2026-10-09 09:20 ~ 10:00 (UTC+8)
- **环境**: macOS arm64 (Mac mini M4 Pro), 无代理环境变量, 无 VPN
- **范围**: 只读探测。未修改任何策略/回测代码，未修改现有数据集，未批量下载。
- **网络基线（同时段对照）**: baidu.com 200/0.27s · github.com 200/1.27s · pypi.org 200/15.0s（跨境链路整体拥塞）

---

## 1. Dukascopy — datafeed.dukascopy.com

| 检查项 | 结果 |
|---|---|
| DNS 解析 | ✅ 成功 → `65.49.26.99` |
| TCP 443 | ✅ 可连接 |
| HTTPS (curl, 20s, IPv4 强制) | ❌ `code=000`, TLS 握手超时 |
| 纯 HTTP (非 TLS) | ❌ `code=000`, 20s 超时 |
| 结论 | **当前网络环境不可达**（TCP 层通、TLS 层被阻断/超时；与 metatrader5.com / phillipnova.com.sg 同模式） |

**判定依据**: 连接在 TCP 握手后、TLS 握手阶段失败（`connect=0.000s` + 20s 总超时，非 DNS、非 IPv6 路由问题）。不判定为"数据源不存在"，仅判定为**当前网络不可达**。

---

## 2. HistData.com — www.histdata.com

### 2.1 连通性

| 检查项 | 结果 |
|---|---|
| DNS 解析 | ✅ 成功 → `51.77.23.84` |
| TCP/HTTPS | ✅ 稳定（主页 200/0.85s，内页 200/1.3~1.8s） |
| TLS 证书 | ✅ 正常（Apache/2.4.6 CentOS, PHP/7.4.6） |

### 2.2 数据覆盖（页面实测确认）

- EURUSD 数据入口存在：`/download-free-forex-data/?/ascii/1-minute-bar-quotes/EURUSD`
- 覆盖年份：**2000 – 2026**，每币种每年/每月一个 `.zip`（页面链接实测列出，如 `eurusd/2026/10`、`eurusd/2000`）
- 两种数据形态：**M1 分钟线**（1-minute-bar-quotes）与 **Tick 数据**（tick-data-quotes 入口存在）
- 另有 FTP/SFTP 通道（`/download-by-ftp/`）——**需 PayPal 付费**，未测试

### 2.3 下载流程逆向（实测）

```
GET  月份页 (?/ascii/1-minute-bar-quotes/eurusd/2024/1)
     → 表单 POST /get.php（字段: tk, date, datemonth, platform=ASCII, timeframe=M1, fxpair=EURUSD）
     → 表单 POST /getStatus.php（同字段）
     → tk 隐藏域服务端渲染即为空值 value=""
```

| 端点 | 结果 |
|---|---|
| `POST /getStatus.php` | ✅ **成功**。返回 `HISTDATA_COM_ASCII_EURUSD_M1202401.txt`（10,418 字节, `application/octet-stream`） |
| `POST /get.php` | ❌ **HTTP 200 + 0 字节空响应**。以下四种方式全部复现：① curl（含完整浏览器头/Origin/Sec-Fetch）② 真实 Chromium 点击官方下载链接 ③ stealth 模式（隐藏 `navigator.webdriver`）④ 浏览器上下文内 `fetch()` |

**getStatus.php 返回内容（真实样本，证明服务端存在数据文件）**:

```
HistData.com (c) 2012
File: DAT_ASCII_EURUSD_M1_202401.csv Status Report

Gap of 70s found between 20240102012026 and 20240102012143.
...（共 10KB 的 gap 统计，2024-01-02 至 2024-01-30）...
Gap of 72s found between 20240126163202 and 20240126163320.

Average tick interval: 5396 miliseconds.
Maximum tick interval found: 3597641 miliseconds.
```

**tk token 调查（穷尽）**:
- 页面所有内联 JS（9 段）无 tk 填充逻辑
- 外部 JS（jquery.js 96KB / jquery-migrate / cookie-law-info-public / 主题 script.js 14KB）均无 `tk` 引用
- 真实浏览器加载后 DOM 中 `#tk.value` = `""`（空）
- 点击提交→刷新页面后 tk 仍为空（排除两段式 token）
- stealth 后仍 0 字节（排除 headless 检测）

**推测（未确证）**: `get.php` 对当前出口 IP 或会话不返回数据体（可能的 IP 级限流/风控），或服务端按 IP 地域区分。**不猜测接口地址，仅记录实际行为**。

### 2.4 数据格式（基于页面声明与 status 报告，未取得文件级样本）

| 项 | 值 |
|---|---|
| M1 分钟线字段 | `timestamp, open, high, low, close, volume`（ASCII CSV） |
| 报价类型 | 单边价（HistData 约定为 **Bid 基准**）——**无 Ask、无 spread** |
| 时间戳时区 | **EST/EDT（美东）**，非 UTC |
| Tick 数据 | 有独立入口（tick-data-quotes），文件级未验证 |
| 数据源质量 | status 报告显示 2024-01 平均 tick 间隔 5.4s，最大 gap 3597s（周末/收盘），存在少量 60-90s 短 gap |

### 2.5 使用限制（页面声明）

- 免费数据限个人使用；商业使用需授权
- 批量下载/FTP 通道需 PayPal 付费
- 下载端点有反自动化机制（tk/会话校验，详见 2.3）

---

## 3. 汇总

```
DATA_SOURCE_CANDIDATES:
  Dukascopy (datafeed.dukascopy.com)   → 网络不可达 (TLS 层超时)
  HistData.com (www.histdata.com)      → 网站可达, 数据确认存在, 文件下载端点返回空

REAL_SAMPLE_OBTAINED:
  HistData getStatus 报告 (10,418 B, 2024-01 EURUSD M1 gap 统计)   ✅ 部分
  HistData M1 完整数据文件 (DAT_ASCII_EURUSD_M1_202401.zip)        ❌ 未取得
  Dukascopy 任意样本                                                ❌ 未取得

SPREAD_AVAILABLE:    ❌ HistData M1 无 Bid/Ask 双边价, 无历史 spread（常数假设不可当真实值）
TICK_AVAILABLE:      入口存在, 文件级未验证
TIMEZONE:            HistData = EST/EDT（需转换为 UTC/交易所时间）
```

## 4. 最终状态

# CONNECTIVITY_PARTIAL

理由：网站可访问（HistData 全部页面 200 且响应快），服务端数据文件**确认存在**（getStatus.php 返回了 2024-01 的真实 gap 报告），但**样本数据文件的下载端点 `get.php` 返回 200 + 0 字节空响应**（四种客户端方式复现），样本下载未确认。

## 5. 尚未解决的问题

1. `get.php` 空响应的根因（IP 限流 / 地域限制 / 服务端故障 / 未知的 token 机制）——未确证
2. HistData tick 数据文件是否含 Bid/Ask 双边价——文件级未验证
3. Dukascopy 在其他网络环境（代理/VPN）下的可达性——未测试
4. 本机网络对境外金融数据站点的 TLS 层阻断范围（metatrader5.com / mql5.com / datafeed.dukascopy.com 同模式超时）——未确证根因

## 6. 下一步建议（等批准，不自动执行）

1. **用户人工浏览器验证**（零成本，决定性）：在您自己的浏览器（有代理/VPN 时）打开
   `https://www.histdata.com/download-free-forex-historical-data/?/ascii/1-minute-bar-quotes/eurusd/2024/1`
   点击 "HISTDATA_COM_ASCII_EURUSD_M1_202401.zip"。
   - 若能下载 → 确认为 IP/地域限制，走"用户人工下载 → 放入仓库 → 程序验证解析"路线
   - 若同样空响应 → HistData 端问题，换源
2. **代理测试**：若本机有可用代理（clash 等），告知 `host:port`，我配置后重试 `get.php` 与 Dukascopy
3. **数据充分性预警**：HistData M1 是单边 Bid 分钟线，无 spread——对 EURUSD_Reversal_V1 的 spread/成本建模仍不足；若需真实 Bid/Ask + tick，Dukascopy（需可达网络）或 Phillip 实盘/模拟账户数据是更完整的源，建议长期规划

---
*本报告由只读探测生成；未修改任何策略、回测代码或现有数据集。原始探测证据存于 /tmp/histdata_audit/（会话临时目录）。*

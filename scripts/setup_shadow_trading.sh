#!/bin/bash
# ICYQuant 影子交易一键安装（MT5 装好后运行）
# 完成：定位 MT5 数据目录 → 拷贝 EA → 提示编译与挂载步骤 → 启动 runner
set -e

REPO="/Users/xuehairong/CodeBuddy/20260817155030/ICYQuant"

# 1. 定位 MT5 数据目录（Mac 版 MT5 的 Files 在 Wine 容器里）
MT5_FILES=$(find ~/Library/Application\ Support -type d -name "Files" -path "*MetaTrader*" 2>/dev/null | head -1)
if [ -z "$MT5_FILES" ]; then
    # CrossOver/其他安装方式的常见路径
    MT5_FILES=$(find ~/Library/Application\ Support -type d -name "MQL5" 2>/dev/null | head -1)
    [ -n "$MT5_FILES" ] && MT5_FILES="$(dirname "$MT5_FILES")/Files"
fi
if [ -z "$MT5_FILES" ]; then
    echo "❌ 找不到 MT5 数据目录。请先在 MT5 里打开一次：菜单 文件 -> 打开数据文件夹，"
    echo "   然后把那个路径告诉我。"
    exit 1
fi
echo "MT5 Files 目录: $MT5_FILES"

# 2. 拷贝 EA
MQL5_EXPERTS="$(dirname "$MT5_FILES")/MQL5/Experts"
mkdir -p "$MQL5_EXPERTS"
cp "$REPO/mt5/M1_Exporter.mq5" "$MQL5_EXPERTS/"
echo "✓ EA 已拷贝到 MQL5/Experts/"

# 3. 预建输出目录
mkdir -p "$MT5_FILES/ICYQuant"
echo "✓ 输出目录已建: $MT5_FILES/ICYQuant/"

cat <<EOF

────────────────────────────────────────────
EA 已放置。现在检查这台 Mac 的 MT5 是否自带 MetaEditor（编译器）…
────────────────────────────────────────────
EOF

# 3.5 尝试在 MT5.app 包内找到 MetaEditor 并命令行编译（新版 Mac MT5 自带 Wine 版 MetaEditor）
MT5_APP=$(mdfind "kMDItemKind == 'Application'" 2>/dev/null | grep -i "MetaTrader 5" | head -1)
if [ -z "$MT5_APP" ]; then MT5_APP="/Applications/MetaTrader 5.app"; fi
ME64=$(find "$MT5_APP" -name "metaeditor64.exe" 2>/dev/null | head -1)
WINE=$(find "$MT5_APP" -name "wine64" -o -name "wine64" 2>/dev/null | head -1)

COMPILED=0
if [ -n "$ME64" ] && [ -n "$WINE" ]; then
    echo "找到 MetaEditor: $ME64 —— 命令行编译中…"
    "$WINE" "$ME64" /compile:"$MQL5_EXPERTS/M1_Exporter.mq5" /log 2>&1 | tail -3 || true
    if [ -f "$MQL5_EXPERTS/M1_Exporter.ex5" ]; then
        echo "✓ 编译成功: M1_Exporter.ex5"
        COMPILED=1
    fi
fi

if [ "$COMPILED" = "0" ]; then
cat <<EOF
⚠ 未找到可调用的 MetaEditor。改用「免编译方案」：
  影子期只需要 M1 行情，不需要 EA 编译。两个替代数据源任选一：
  A) OANDA 免费模拟账户的 REST API（5 秒级 K 线，Mac 直读，最准）
  B) Twelve Data 免费额度（1 分钟 K 线，800 次/天够用）
  告诉我你选哪个，我把 runner 的数据源接上（价格与 MT5 券商
  会有零点差级差异，EURUSD 这种品种影响极小，但对 0.18 pip/笔
  的策略要在成本复核时单独核对）。
EOF
fi

cat <<EOF

────────────────────────────────────────────
最后在 MT5 里做两步（GUI）：
  1. 打开 EURUSD 的 M1 图表
  2. 从导航器把 M1_Exporter 拖到图上 → 确定
看到 Experts 日志打印 "M1_Exporter ready" 即成功。

然后启动影子 runner（另开终端）：

  cd "$REPO"
  python3 -m research.live.shadow_runner \\
      --csv "$MT5_FILES/ICYQuant/EURUSD_M1_live.csv" \\
      --server-offset-hours 2

如果信号时间差 1 小时，把 --server-offset-hours 改成 3
（券商服务器时区随夏令时切换；runner 日志打印的服务器时间
和手机上的北京时间对一下即可确认）。
EOF

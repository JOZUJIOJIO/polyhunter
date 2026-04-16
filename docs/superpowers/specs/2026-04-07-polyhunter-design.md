# PolyHunter - Polymarket 量化交易系统设计文档

**日期**: 2026-04-07
**状态**: Draft
**版本**: 1.0

---

## 1. 项目概述

### 1.1 目标

构建一个 Polymarket 预测市场的量化交易系统（代号 PolyHunter），支持套利交易和量化预测下注两种策略方向。系统分两阶段推进：Phase 1 实现信号发现 + 半自动交易 + Web 仪表盘；Phase 2 集成 AI 预测能力并实现全自动交易。

### 1.2 约束

- **资金规模**: <$5K 探索性资金
- **用户经验**: 有 Polymarket 手动交易经验，无程序化交易经验
- **自动化路径**: 先半自动（信号提醒 + 手动确认），后全自动

### 1.3 技术栈

| 层级 | 技术选型 | 理由 |
|------|---------|------|
| 后端 | Python 3.11+ / FastAPI | 生态丰富，py-clob-client 官方支持 |
| 前端 | Next.js (React) | 轻量 SSR，开发效率高 |
| 数据库 | SQLite (→ PostgreSQL) | 小资金阶段足够，后期可迁移 |
| 交易 SDK | py-clob-client | Polymarket 官方 Python SDK |
| 任务调度 | APScheduler | 内嵌调度，无需外部依赖 |
| 通知 | Telegram Bot (可选) | 移动端实时推送 |

### 1.4 外部 API 依赖

| API | 用途 | 认证 |
|-----|------|------|
| Gamma API (`gamma-api.polymarket.com`) | 市场发现与元数据 | 无需认证 |
| CLOB API (`clob.polymarket.com`) | 价格/订单簿/交易 | 交易需 HMAC + 私钥签名 |
| CLOB WebSocket | 实时订单簿/价格推送 | 公开频道无需认证 |
| Data API (`data-api.polymarket.com`) | 持仓/交易分析 | 无需认证 |

---

## 2. 系统架构

```
┌──────────────────────────────────────────────────┐
│                   PolyHunter                      │
├──────────────────────────────────────────────────┤
│                                                   │
│  ┌────────────────────────────────────────────┐  │
│  │          Web Dashboard (Next.js)            │  │
│  │  概览 | 市场 | 信号 | 持仓 | 历史 | 设置    │  │
│  └────────────────┬───────────────────────────┘  │
│                   │ REST API                      │
│  ┌────────────────┴───────────────────────────┐  │
│  │         FastAPI Backend (Python)            │  │
│  │                                             │  │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐      │  │
│  │  │ Crawler  │→│ Signal  │→│ Trader  │      │  │
│  │  │ 数据采集 │ │ 信号引擎 │ │ 交易执行 │      │  │
│  │  └─────────┘ └─────────┘ └─────────┘      │  │
│  │       ↓           ↓           ↓             │  │
│  │  ┌──────────────────────────────────┐      │  │
│  │  │         SQLite Database          │      │  │
│  │  └──────────────────────────────────┘      │  │
│  │                                             │  │
│  │  Phase 2: ┌──────────┐                     │  │
│  │           │ AI Pred.  │ (可插拔)            │  │
│  │           └──────────┘                     │  │
│  └─────────────────────────────────────────────┘ │
│                                                   │
│  可选: Telegram Bot 通知                          │
└──────────────────────────────────────────────────┘
```

### 2.1 设计原则

- **模块化**: 每个组件独立，可单独测试和替换
- **Phase 分层**: Phase 1 不依赖 AI，Phase 2 的 AI 模块是可插拔增强层
- **数据优先**: 所有信号和交易持久化，为后期分析和 AI 训练积累数据
- **安全第一**: 私钥仅在本地，API 密钥通过环境变量管理

---

## 3. 核心模块设计

### 3.1 数据采集模块 (Crawler)

**职责**: 持续采集 Polymarket 市场数据，写入数据库。

**子模块**:

- **MarketCrawler**: 定期调用 Gamma API `/events` 端点，发现和更新活跃市场的元数据（问题描述、分类、到期时间、token ID 等）。频率：每 10 分钟全量同步。

- **PriceCrawler**: 调用 CLOB API 获取价格、订单簿、价差数据。对关注列表中的市场以更高频率采集（每 30 秒），其余市场较低频率（每 5 分钟）。

- **WebSocketClient**: 连接 CLOB WebSocket（`wss://ws-subscriptions-clob.polymarket.com/ws/market`）订阅高关注市场的实时 Level 2 订单簿数据。最多同时订阅 10 个市场（API 限制）。

**数据流**: API/WebSocket → 数据清洗 → SQLite

### 3.2 信号引擎 (Signal Engine)

**职责**: 分析市场数据，生成交易信号。

#### Phase 1 信号类型

**ARBITRAGE（套利信号）**:
- **YES/NO 定价偏差**: 当某市场 YES 价 + NO 价 ≠ $1.00，且偏差扣除手续费后仍有利润时触发。例如 YES=$0.45 + NO=$0.53 = $0.98，买入两边锁定 $0.02 利润。
- **跨市场套利**: 同一事件在不同表述的市场中存在定价不一致。例如市场 A "X 获胜" 的 YES=$0.60，市场 B "X 不获胜" 的 YES=$0.45，理论上应互补为 $1.00 但实际总价 $1.05。
- **最小 edge 阈值**: 扣除 Polymarket 手续费（约 2%）后，净利润 > 1% 才触发。

**PRICE_ANOMALY（价格异动信号）**:
- 短时间内（5 分钟）价格偏离 24 小时均价超过指定标准差倍数（默认 2σ）
- 结合成交量验证：异动期间成交量需高于均值，排除低流动性噪音

#### Phase 2 信号类型

**AI_PREDICTION（AI 预测信号）**:
- 输入：市场描述 + 相关新闻/数据 → LLM（Claude API）→ 输出概率估计 + 推理过程
- 与当前市场价对比，当 |AI 概率 - 市场价| > 阈值（默认 10%）时触发
- 信号附带置信度评分（0-100）
- 仅在 Phase 1 信号体系验证有效后启用

**信号生命周期**: NEW → ACTED（已执行）/ EXPIRED（过期）/ DISMISSED（用户忽略）

### 3.3 交易执行模块 (Trader)

**职责**: 根据信号执行交易，管理持仓和风控。

#### 3.3.1 订单执行器 (Executor)

**Phase 1 - 半自动流程**:
1. 信号引擎产生信号
2. 推送到 Web Dashboard 信号中心 + Telegram 通知
3. 用户在 Dashboard 查看信号详情（市场、方向、建议仓位、预期收益）
4. 用户点击"确认下单" → 系统通过 py-clob-client 提交订单
5. 订单状态同步更新到 Dashboard

**Phase 2 - 全自动流程**:
- 策略规则引擎：信号满足预设条件（如置信度 > 80，edge > 5%）自动执行
- 用户可为不同信号类型设置不同的自动化级别

**订单类型**: 默认使用 GTC（Good Till Cancelled）限价单。套利信号使用 FOK（Fill or Kill）确保原子执行。

#### 3.3.2 风控管理器 (Risk Manager)

| 规则 | 默认值 | 说明 |
|------|--------|------|
| 单笔限额 | 总资金 10% | 单笔交易不超过总资金的比例 |
| 日亏损上限 | 总资金 5% | 触发后暂停当日所有交易 |
| 持仓集中度 | 总资金 20% | 单市场持仓不超过总资金的比例 |
| 最小 edge | 1% | 套利信号扣费后净利润门槛 |
| 到期保护 | 24 小时 | 市场到期前不开新仓 |
| 最大同时持仓 | 10 个市场 | 避免过度分散 |

所有参数通过 Web Dashboard 设置页面可配置。

#### 3.3.3 持仓追踪器 (Position Tracker)

- 实时追踪所有持仓的浮盈浮亏
- 通过 CLOB API 获取当前市场价计算未实现盈亏
- 市场结算后自动计算已实现盈亏
- 每日生成 PnL 快照

### 3.4 Web Dashboard

**技术**: Next.js App Router + shadcn/ui 组件库 + Tailwind CSS

**页面设计**:

| 页面 | 核心功能 |
|------|---------|
| 概览 (/) | 总资产、今日 PnL 图表、活跃持仓数、最新信号摘要 |
| 市场 (/markets) | 活跃市场列表，支持按分类/成交量/流动性筛选和搜索 |
| 信号 (/signals) | 实时信号流，每条信号附带详情和"一键下单"按钮 |
| 持仓 (/positions) | 当前持仓详情、浮盈浮亏、市场到期时间 |
| 历史 (/history) | 历史交易记录、胜率、累计 PnL 曲线 |
| 设置 (/settings) | 风控参数、API 密钥管理、通知配置、自动化规则 |

**交互流程（信号→下单）**:
1. 信号卡片展示：市场问题、信号类型、方向、建议价格和仓位、预期 edge
2. 点击"下单" → 确认弹窗（显示订单详情 + 风控检查结果）
3. 确认后提交 → 显示订单状态（PENDING → FILLED / CANCELLED）

### 3.5 通知模块 (Notifier) — 可选

- Telegram Bot 推送新信号、订单成交、风控告警
- 支持 Telegram 内联按钮快速操作（确认/忽略信号）
- 非核心模块，可后期添加

---

## 4. 数据模型

### 4.1 markets 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 市场 ID |
| condition_id | TEXT | 链上条件 ID |
| token_id_yes | TEXT | YES token ID |
| token_id_no | TEXT | NO token ID |
| question | TEXT | 市场问题描述 |
| slug | TEXT | URL slug |
| category | TEXT | 分类标签 |
| end_date | DATETIME | 市场到期时间 |
| active | BOOLEAN | 是否活跃 |
| last_price_yes | REAL | YES 最新价格 |
| last_price_no | REAL | NO 最新价格 |
| volume_24h | REAL | 24 小时成交量 |
| liquidity | REAL | 流动性 |
| updated_at | DATETIME | 最后更新时间 |

### 4.2 signals 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| market_id | TEXT FK | 关联市场 |
| type | TEXT | ARBITRAGE / PRICE_ANOMALY / AI_PREDICTION |
| source_detail | TEXT | 信号来源细节（JSON） |
| current_price | REAL | 触发时市场价 |
| fair_value | REAL | 估计公允价值 |
| edge_pct | REAL | 预期 edge 百分比 |
| confidence | INTEGER | 置信度 0-100 |
| status | TEXT | NEW / ACTED / EXPIRED / DISMISSED |
| created_at | DATETIME | 创建时间 |

### 4.3 trades 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| signal_id | INTEGER FK | 关联信号 |
| market_id | TEXT FK | 关联市场 |
| token_id | TEXT | 交易的 token ID |
| side | TEXT | BUY / SELL |
| price | REAL | 成交价 |
| size | REAL | 成交量 |
| cost | REAL | 总成本（含手续费） |
| status | TEXT | PENDING / FILLED / CANCELLED |
| order_id | TEXT | CLOB 订单 ID |
| pnl | REAL | 已实现盈亏（结算后填入） |
| created_at | DATETIME | 创建时间 |

### 4.4 positions 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| market_id | TEXT FK | 关联市场 |
| token_id | TEXT | 持仓 token ID |
| side | TEXT | YES / NO |
| avg_entry_price | REAL | 平均入场价 |
| size | REAL | 持仓数量 |
| current_price | REAL | 当前市场价 |
| unrealized_pnl | REAL | 未实现盈亏 |
| created_at | DATETIME | 建仓时间 |

### 4.5 pnl_snapshots 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增 ID |
| date | DATE | 快照日期 |
| total_value | REAL | 总资产价值 |
| realized_pnl | REAL | 累计已实现盈亏 |
| unrealized_pnl | REAL | 当日未实现盈亏 |
| num_trades | INTEGER | 当日交易笔数 |
| win_rate | REAL | 累计胜率 |

---

## 5. 项目目录结构

```
polyhunter/
├── backend/
│   ├── main.py                  # FastAPI 入口 + 启动调度器
│   ├── config.py                # 配置管理（Pydantic Settings）
│   ├── db/
│   │   ├── database.py          # SQLite 连接管理
│   │   └── models.py            # SQLAlchemy ORM 模型
│   ├── crawler/
│   │   ├── market_crawler.py    # Gamma API 市场采集
│   │   ├── price_crawler.py     # CLOB API 价格/订单簿采集
│   │   └── websocket_client.py  # CLOB WebSocket 实时数据
│   ├── signals/
│   │   ├── base.py              # 信号基类 + 注册机制
│   │   ├── arbitrage.py         # 套利信号检测
│   │   ├── anomaly.py           # 价格异动信号
│   │   └── ai_predictor.py      # Phase 2: AI 预测信号
│   ├── trader/
│   │   ├── executor.py          # 订单执行（py-clob-client 封装）
│   │   ├── risk_manager.py      # 风控规则引擎
│   │   └── position_tracker.py  # 持仓追踪 + PnL 计算
│   ├── api/
│   │   ├── routes/
│   │   │   ├── markets.py       # 市场相关 API
│   │   │   ├── signals.py       # 信号相关 API
│   │   │   ├── trades.py        # 交易相关 API
│   │   │   ├── positions.py     # 持仓相关 API
│   │   │   └── settings.py      # 设置相关 API
│   │   └── schemas.py           # Pydantic 请求/响应 schemas
│   └── notifier/
│       └── telegram.py          # Telegram Bot 通知
├── frontend/
│   ├── app/
│   │   ├── layout.tsx           # 全局布局（侧边栏导航）
│   │   ├── page.tsx             # 概览页
│   │   ├── markets/page.tsx     # 市场浏览
│   │   ├── signals/page.tsx     # 信号中心
│   │   ├── positions/page.tsx   # 持仓管理
│   │   ├── history/page.tsx     # 交易历史
│   │   └── settings/page.tsx    # 设置
│   ├── components/
│   │   ├── ui/                  # shadcn/ui 组件
│   │   ├── signal-card.tsx      # 信号卡片组件
│   │   ├── pnl-chart.tsx        # PnL 图表组件
│   │   └── order-confirm.tsx    # 下单确认弹窗
│   └── lib/
│       └── api.ts               # 后端 API 客户端
├── .env.example                 # 环境变量模板
├── pyproject.toml               # Python 依赖管理
├── package.json                 # 前端依赖
└── README.md
```

---

## 6. 环境变量

```env
# Polymarket
POLYMARKET_PRIVATE_KEY=         # Ethereum 钱包私钥（用于签名交易）
POLYMARKET_API_KEY=             # CLOB API 密钥
POLYMARKET_API_SECRET=          # CLOB API 密钥签名

# Database
DATABASE_URL=sqlite:///./polyhunter.db

# Telegram (可选)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Phase 2: AI
ANTHROPIC_API_KEY=              # Claude API 密钥

# 风控
RISK_MAX_SINGLE_BET_PCT=10     # 单笔限额百分比
RISK_MAX_DAILY_LOSS_PCT=5      # 日亏损上限百分比
RISK_MAX_POSITION_PCT=20       # 单市场持仓上限百分比
RISK_MIN_EDGE_PCT=1            # 最小 edge 百分比
```

---

## 7. Phase 划分

### Phase 1 — MVP（信号 + 半自动交易 + Dashboard）

交付物:
1. 数据采集模块：Gamma API 市场同步 + CLOB API 价格采集
2. 套利信号 + 价格异动信号检测
3. FastAPI 后端 API
4. Web Dashboard（概览、市场、信号、持仓、历史、设置）
5. 半自动交易（Dashboard 一键确认下单）
6. 基础风控（单笔限额、日亏损上限、持仓集中度）

### Phase 2 — AI 增强 + 全自动

交付物:
1. AI 预测信号模块（Claude API 集成）
2. WebSocket 实时数据流
3. 全自动交易规则引擎
4. Telegram 通知集成
5. 高级风控（动态仓位、止损止盈）

---

## 8. 已知风险和限制

- **API 限速**: CLOB API 有速率限制（9000 req/10s），需合理控制采集频率
- **WebSocket 限制**: 最多同时订阅 10 个市场
- **流动性风险**: 小资金在低流动性市场可能面临滑点
- **套利窗口**: 纯 YES/NO 套利机会稀少且利润薄，主要价值在于发现跨市场定价偏差
- **市场结算延迟**: 市场结算时间不确定，影响资金周转效率
- **监管风险**: 需关注 Polymarket 的监管合规动态

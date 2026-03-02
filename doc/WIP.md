# AIDE — 开发进度 WIP

> 最后更新：2026-03-02

---

## 总体进度概览

| 阶段 | 规划内容 | 完成度 | 状态 |
|------|----------|--------|------|
| Phase 1：基础架构 | Docker、FastAPI、DB、Blackboard、WS | ~85% | ✅ 基本完成 |
| Phase 2：多智能体核心 | 5 Agent + Orchestrator 主循环 | ~70% | 🔧 核心跑通，缺关键智能 |
| Phase 3：高级研究能力 | 语义检索、真实 RAG、论文导出 | ~20% | ⚠️ 大部分未实现 |
| Phase 4：产品打磨 | 智能推荐、实验追踪、协作 | ~5% | ❌ 几乎未开始 |

---

## Phase 1：基础架构（~85%）

### ✅ 已完成
- Docker Compose 4 服务（backend、frontend、postgres、chromadb）
- FastAPI 后端框架 + Alembic 数据库迁移
- PostgreSQL 数据模型：Project、Paper、TokenUsage
- Blackboard 文件系统存储（`workspace/projects/{id}/`）
- WebSocket 实时推送（`api/ws.py`）
- REST API：项目 CRUD、论文管理、检查点、设置
- Next.js 15 + Tailwind CSS 4 前端基础框架
- 项目创建/列表/详情页
- L0/L1/L2 上下文分级架构（数据结构已定义）
- 设置持久化（`workspace/settings_overrides.json`）

### ❌ 未完成
- L0/L1/L2 `ContextBuilder` 的实际按 token 预算裁剪逻辑（当前所有 agent 获得完整 L2 dump）
- 前端错误边界 / 全局错误处理 UI

---

## Phase 2：多智能体核心（~70%）

### ✅ 已完成
- 5 个 Agent：Director、Scientist、Librarian、Writer、Critic（Jinja2 模板驱动）
- OrchestrationEngine 主循环（plan → dispatch → validate → convergence → loop）
- OrchestratorPlanner（LLM 驱动的 next-action 选择）
- ConvergenceDetector（Critic 评分阈值 + stable rounds）
- BacktrackController（矛盾时回退阶段）
- HeartbeatMonitor（崩溃恢复）
- CheckpointManager（关键节点暂停等待用户审批）
- SubAgentPool（并行子任务分发）
- WriteBackGuard（防止 agent 写入越权 artifact）
- LLM Router（DeepSeek + OpenRouter 双 provider + fallback）
- TokenUsage 跟踪（`tracker.py`）
- **研究主题注入修复**：6 层注入链（DB→Board→Planner→BaseAgent→Jinja2→Engine per-iter 检查）
- **主题漂移检测**：`_check_on_topic()` + `TopicDriftWarning` WS 事件
- **前端运行状态指示器**：ping 动画横幅、iteration 计数、当前 agent 状态、漂移警告 Toast

### ❌ 未完成
- **LLM Planner 降级**：`plan_next_action()` 在 LLM 解析失败时直接抛异常，缺乏 rule-based fallback
- **LLM Dedup**：`dedup_check()` 目前是简单字符串哈希比较，非语义去重
- **Challenge 解决机制**：`ChallengeRaised` 事件广播了，但 orchestrator 没有自动解决 challenge 的逻辑（只广播不处理）
- **Agent 输出结构化验证**：仅靠 JSON parse，无 Pydantic schema 强校验
- **Phase COMPLETE 的后处理**：研究完成后没有触发论文导出/存储流程

---

## Phase 3：高级研究能力（~20%）

### ✅ 已完成
- ChromaDB 集成（服务已运行，基础 client 存在）
- Librarian agent 模板（定义了搜索行为）

### ❌ 未完成
- **真实语义检索**：Librarian 目前调用 LLM 生成"假"检索结果，没有真正查询 ChromaDB 或外部 API
- **arXiv / Semantic Scholar API 集成**：`papers.py` 存在 REST 端点但无实际爬取逻辑
- **PDF 解析 + 向量化**：无论文全文提取和入库
- **混合检索（BM25 + 向量）**：计划中，未实现
- **引用图谱构建**：未实现
- **论文导出（PDF/LaTeX）**：`papers.py` 有草稿，无渲染引擎
- **前端论文编辑器**：未实现

---

## Phase 4：产品打磨（~5%）

### ✅ 已完成
- 基础设置页面（LLM provider 选择、token 预算配置）

### ❌ 未完成
- 智能研究方向推荐
- 实验追踪与可视化（假设演化树、证据网络图）
- 多用户协作
- 研究模板库
- 一键导出完整研究报告

---

## Bug Fixes 历史（各 session 已修复）

| Session | 修复内容 |
|---------|----------|
| Session 2 | `tracker.py` ORM 双重定义冲突、`async_sessionmaker` 误用 `await`、列名错误（model→model_name, cost→cost_usd） |
| Session 2 | `factory.py` CheckpointManager 注册表；`ws.py` checkpoint 响应用错实例；`checkpoints.py` REST 路由实现 `apply_user_response()` |
| Session 3 | 设置持久化：`.env` 宿主机问题，改为写 `/app/workspace/settings_overrides.json`，lifespan 恢复 |
| Session 4 | 研究主题 6 层注入链修复（核心缺陷：topic 从未传给任何 agent） |
| Session 4 | 前端无运行状态指示器；添加 ping 动画横幅、iteration 计数、TopicDriftWarning Toast |

---

## 优先级待办（Next Steps）

### P0 — 阻塞核心功能
- [ ] LLM Planner fallback：解析失败时降级到 rule-based 策略，防止主循环崩溃
- [ ] Challenge 自动解决：orchestrator 在下次迭代让 Critic/Director 处理未解决的 challenge
- [ ] Phase COMPLETE 触发论文存储/导出

### P1 — 让研究真正有用
- [ ] Librarian 真实检索：接入 arXiv API 或 Semantic Scholar，结果入 ChromaDB
- [ ] PDF 解析 + 向量化入库（基础 RAG 闭环）
- [ ] L1/L2 ContextBuilder 按 token 预算裁剪（防止大项目 context 爆炸）

### P2 — 用户体验
- [ ] 前端 Blackboard 详情视图（展示各 artifact 完整内容）
- [ ] 论文编辑器（渲染 Writer 的 draft artifact）
- [ ] Agent 详细日志面板（可展开每次迭代的 reasoning_summary）

### P3 — 长期完善
- [ ] LLM 语义去重（替换当前哈希 dedup）
- [ ] Agent 输出 Pydantic schema 强校验
- [ ] 多用户 / 协作功能
- [ ] 研究可视化（假设演化、证据图）

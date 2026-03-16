# AIDE — 开发进度 WIP

> 最后更新：2026-03-16（Session 12）

---

## 总体进度概览

| 阶段 | 规划内容 | 完成度 | 状态 |
|------|----------|--------|------|
| Phase 1：基础架构 | Docker、FastAPI、DB、Blackboard、WS | ~90% | ✅ 基本完成 |
| Phase 2：多智能体核心 | 6 Agent + Orchestrator 主循环 + 并行 Lane | **100%** | ✅ 审计 10 项残留全部修复，E2E 全链路验证通过 |
| Phase 3：高级研究能力 | 语义检索、真实 RAG、论文导出 | **100%** | ✅ safe_json_loads 统一 + arXiv/S2 入 ChromaDB |
| Phase 4：产品打磨 | 智能推荐、实验追踪、协作 | ~40% | 🔧 Indigo 主题 + 研究流水线 + Sidebar + 全面测试 + 审计修复 |

---

## Phase 1：基础架构（~90%）

### ✅ 已完成
- Docker Compose 4 服务（backend、frontend、postgres、chromadb）
- FastAPI 后端框架 + Alembic 数据库迁移
- PostgreSQL 数据模型：Project、Paper、TokenUsage
- Blackboard 文件系统存储（`workspace/projects/{id}/`）
- WebSocket 实时推送（`api/ws.py`）
- REST API：项目 CRUD、论文管理、检查点、设置
- Next.js 15 + Tailwind CSS 4 前端基础框架
- 项目创建/列表/详情页
- L0/L1/L2 上下文分级架构（数据结构 + LLM 生成逻辑已完整）
- 设置持久化（`workspace/settings_overrides.json`）
- **ContextBuilder**（`context_builder.py`）：L2→L1→L0 自动降级到 30K token 预算内

### ❌ 未完成
- 前端错误边界 / 全局错误处理 UI

---

## Phase 2：多智能体核心（100%）

### ✅ 已完成
- **6 个 Agent**：Director、Scientist、Librarian、Writer、Critic、**Synthesizer**（Session 7 新增）
- OrchestrationEngine 主循环（plan → dispatch → validate → convergence → loop）
- **OrchestratorPlanner（LLM 动态调度 + 规则 fallback）**（Session 11）：LLM 根据 board 状态选择 agent，Critic guarantee 每 3 轮，Challenge routing 优先调度被质疑 agent
- ConvergenceDetector（per-phase Critic 评分阈值 + max-iteration 保护）
- BacktrackController（矛盾时回退阶段）
- HeartbeatMonitor（崩溃恢复，stale 阈值可配置 360s）
- CheckpointManager（关键节点暂停等待用户审批，WS + REST 双路响应）
- SubAgentPool（并行子任务分发）
- WriteBackGuard（markdown fence 剥离 + 输入截断降噪）
- **LLM Router（DeepSeek + OpenRouter + Anthropic 三 provider + fallback）**（Session 7）
- **Anthropic/Claude Provider**（Session 7）：支持 claude-opus-4-6/sonnet-4-6，可配 base_url 代理
- **Per-role 模型分配**（Session 7）：推理角色→deepseek-reasoner，工具角色→deepseek-chat，用户可在 settings 覆盖为 Claude
- **并行 Lane 架构**（Session 7）：1-5 独立研究 lane，asyncio.gather 并行执行，合成阶段汇总
- **6 阶段研究流程**：EXPLORE → HYPOTHESIZE → EVIDENCE → COMPOSE → [SYNTHESIZE] → COMPLETE
- **Claude JSON 输出强制**（Session 7）：base.py 对 Claude 模型追加 JSON 格式指令，消除 non-JSON 问题
- TokenUsage 跟踪（`tracker.py`）
- 研究主题 6 层注入链（DB→Board→Planner→BaseAgent→Jinja2→Engine per-iter 检查）
- 主题漂移检测：`_check_on_topic()` + `TopicDriftWarning` WS 事件
- 前端运行状态指示器（ping 动画、iteration 计数、当前 agent、漂移 Toast）
- Challenge 自动 dismiss（`phase_iters > 2` 时自动解决）
- Phase COMPLETE 论文导出（`_on_research_complete()` → `exports/paper.md` + `ResearchCompleted` WS）
- Critic 分数提取链路：用 `agent_role == CRITIC` 替代不可靠的 artifact_type 字符串匹配
- L1 JSON 生成加固：markdown fence 剥离 + 强化 system prompt
- SPAWN_SUBAGENT handler：消除 "Unhandled action type" 警告

- **Token 计费全链路**（Session 8）：`base.py` 传递 `project_id`/`agent_role` 到 `generate()`，所有 6 agent 记录每次 LLM 调用费用
- **Token 费用 API + 前端展示**（Session 8）：`GET /api/projects/{id}/usage` 返回分模型统计（USD/RMB），完成后 banner 显示费用
- **Artifact Jaccard 去重**（Session 8）：`dedup_check()` 改为 Jaccard 词集相似度（阈值 0.6），替代直通空操作
- **引用图谱构建**（Session 8）：Librarian 检索后自动构建 NetworkX DiGraph + `GET /api/projects/{id}/citation-graph` API
- **论文编辑与 PDF 导出**（Session 8）：前端论文编辑模式 + `PUT /export/paper` 保存 + `GET /export/paper/html` 浏览器打印导出
- **前端 ResearchCompleted 处理**（Session 8）：WS 事件触发完成 banner + 自动加载 token 费用
- **并行 Lane 前端进度指示**（Session 8）：LanesStarted/LaneCompleted/SynthesisStarted WS 事件处理 + 进度可视化
- **Agent action_type 容错**（Session 8）：`_fuzzy_match_action_type()` 模糊匹配 + target 自动填充

- **Planner LLM 动态调度**（Session 11）：`_llm_select()` 根据 board 状态 + 可用 agent + 缺失 artifact + open challenge 选择下一个 agent，`_PHASE_SEQUENCES` 降级为 fallback
- **Agent Context 按 Role 定制**（Session 11）：`_build_state_summary(role=)` 只传入 agent 的 `primary_artifact_types` + `dependency_artifact_types` 对应的 artifact
- **Challenge 响应路由**（Session 11）：open challenge 有 `target_agent` 时优先调度该 agent，challenge 内容注入 prompt 醒目位置，`_CHALLENGE_AUTO_DISMISS_AFTER` 2→5
- **Challenge resolve 后验证**（Session 12）：dispatch 后检查 response 中是否包含 `RESOLVE_CHALLENGE` action，未 resolve 则 log warning
- **收敛多维度化**（Session 11）：per-phase 差异化阈值（EXPLORE=6.0, HYPOTHESIZE=6.5, EVIDENCE=7.0, COMPOSE=7.5）+ artifact coverage 检查
- **Critic EMA 评分**（Session 12）：算术平均→指数移动平均（α=0.4），解决早期低分永久拖拽问题
- **偏题检测三层 fallback**（Session 11）：Embedding 余弦相似度 → jieba 中文分词 → 关键词匹配，阈值 0.2→0.4
- **偏题注入 agent prompt**（Session 12）：检测到漂移时将 `[⚠️ TOPIC DRIFT WARNING]` 注入下一个 agent 的 task description
- **WriteBackGuard 规则驱动重写**（Session 11）：从 LLM-based 改为规则检查 agent 是否产出期望 artifact type
- **记忆机制**（Session 11）：研究完成后 `_generate_lessons_learned()` 生成经验总结，启动时 `_inject_lessons_learned()` 注入最近 5 个项目的经验
- **Blackboard 内存缓存**（Session 11）：artifact meta 缓存 + write-through
- **Blackboard L0 + version 缓存**（Session 12）：`_l0_cache` 缓存 L0 内容 + `_version_cache` 缓存版本号，避免文件系统扫描
- **中文关键词检测**（Session 12）：`has_contradictory_evidence()`/`has_logic_gaps()`/`has_direction_issues()` 支持矛盾/冲突/漏洞/逻辑/偏离/偏题等中文关键词
- **Agent 非 JSON 重试**（Session 12）：`execute()` 检测到非 JSON 响应后追加 `[RETRY]` 指令重试一次
- **Critic 依赖 artifact 类型补全**（Session 12）：增加 EVIDENCE_GAPS、EXPERIMENT_GUIDE、TREND_SIGNALS
- **artifact_type 三层防御**（Session 12）：Prompt 模板加 `artifact_type` 字段 + Planner 任务描述加指令 + `actions.py` `_ROLE_ALLOWED_TYPES` 白名单校验
- **Lane artifact 截断改善**（Session 12）：3000→6000 字符 + 按 artifact type 分组
- **Lane async I/O**（Session 12）：`_collect_lane_artifacts()` 改为 aiofiles 异步读取
- **Lane 研究视角分化**（Session 11）：5 条 `_LANE_PERSPECTIVES`（理论/实证/批评/跨学科/方法创新），每条 lane 注入不同视角
- **json_mode 支持**（Session 11）：`generate()` 传入 `json_mode=True`，DeepSeek 使用 `response_format={"type": "json_object"}`

### ❌ 未完成
- **Agent 输出 Pydantic schema 强校验**：仅靠 JSON parse
- **Function calling / tool use**：Agent 输出仍为自由格式 JSON，未使用 provider 的 structured output schema

---

## Phase 3：高级研究能力（~60%）

### ✅ 已完成
- ChromaDB + BM25 集成（服务运行，hybrid search 已实现）
- PDF 上传 → 解析（PyMuPDF/pdfplumber）→ 分块 → 嵌入（text-embedding-3-small）→ ChromaDB + BM25 入库（完整流水线）
- Librarian 真实 arXiv + Semantic Scholar 检索：`WebRetriever` 双源 fallback
- **S2 429 冷却期**（Session 7）：429 后 5 分钟内跳过 S2 直接走 arXiv，避免无效重试
- **Query 缓存归一化**（Session 7）：排序去重关键词作 cache key，翻译结果微差不再导致缓存未命中
- **Librarian 本地知识检索完善**（Session 7）：无 OpenAI key 时跳过 Hybrid search 避免 SSL 错误；BM25 fallback 现在返回 doc_texts 内容
- **论文导出增强**（Session 7）：`export_paper()` 除 DRAFT 外补充 HYPOTHESES/EVIDENCE/DIRECTIONS/OUTLINE，产出从 2 section→11 section、6.5KB→62KB
- **arXiv/S2 检索结果持久化到 BM25**（Session 8）：`_persist_web_papers()` 将检索论文自动入库项目级 BM25 索引
- **引用图谱构建与 API**（Session 8）：`_update_citation_graph()` 构建 NetworkX DiGraph；`GET /api/projects/{id}/citation-graph` 返回节点/边数据
- **论文编辑模式**（Session 8）：前端可编辑论文内容 + `PUT /api/projects/{id}/export/paper` 保存
- **论文 HTML/PDF 导出**（Session 8）：`GET /api/projects/{id}/export/paper/html` 返回可打印 HTML（含 CSS 排版），浏览器 print 导出 PDF

- **统一 `safe_json_loads()`**（Session 9）：`backend/utils/json_utils.py` 集中 markdown fence 剥离 + JSON 解析，替换 levels.py/base.py/write_back_guard.py 中的重复逻辑
- **arXiv/S2 检索结果入 ChromaDB**（Session 9）：`_persist_to_chromadb()` 在 OpenAI key 可用时自动入库向量数据库，含去重检查

### ❌ 未完成
- （Phase 3 全部完成）

---

## Phase 4：产品打磨（~35%）

### ✅ 已完成
- 基础设置页面（LLM provider 选择、token 预算配置）
- **Anthropic 配置 UI**（Session 7）：API Key + Base URL 输入、Claude 模型选项
- **项目创建 concurrency 滑块**（Session 7）：1-5 并行 lane 选择
- **Synthesize 阶段标签**（Session 7）：前端 PHASES 显示 6 个阶段
- **Token 费用展示**（Session 8）：完成 banner 显示总 token/USD/RMB，论文弹窗显示分模型明细
- **Lane 进度可视化**（Session 8）：LanesStarted/LaneCompleted/SynthesisStarted 事件处理
- **引用图谱弹窗**（Session 8）：前端可查看检索到的论文列表

#### Session 9 — 前端重构
- **Indigo 主色迁移**：`globals.css` 从蓝色系切换到 Indigo 系，含深浅双模式完整色阶（primary-50~900）
- **设计系统升级**：新增 scale-in/slide-in-left 动画、stagger 动画类、card-hover/btn-primary-glow/page-title/sidebar-item/input-focus-ring 工具类
- **UI 组件升级**：Button（outline/success variant + glow）、Card（hoverable prop + rounded-xl）、Badge（rounded-full 药丸形 + indigo agent variant）、Modal（size prop sm/md/lg/xl/full + scale-in 动画）、Input（h-10 + focus ring）
- **Sidebar 重写**：240px/64px 收起展开 + localStorage 持久化 + 项目内 5 section 导航（Overview/Blackboard/Messages/Knowledge/Paper）
- **ProjectSidebarContext**：跨组件共享项目导航状态
- **Layout 适配**：响应 sidebar 宽度的 margin 切换 + 过渡动画
- **Dashboard 改版**：page-title 渐变下划线 + stagger 进入动画 + hoverable 卡片 + 运行项目 indigo 侧边条 + Modal 子组件提取
- **项目详情页分解**（1298 行 → 容器 200 行 + 5 section）：
  - `formatters.ts`：常量 + 工具函数提取
  - `useProjectState.ts`：全部状态 + WS + 轮询 + action handlers
  - `OverviewSection.tsx`：研究流水线节点图（6 色阶段卡 + 展开产出 + timeline 连接线 + lane 进度 + token/time 信息卡 + 活动流）
  - `BlackboardSection.tsx`：全宽 3 列 artifact 网格（按类型分组 + 折叠 + hoverable 卡片）
  - `MessagesSection.tsx`：双栏（消息流含角色过滤 + Challenge 面板含状态过滤）
  - `KnowledgeSection.tsx`：双栏（PapersPanel + 引用图谱内联展示）
  - `PaperSection.tsx`：论文编辑/预览 + token 统计 + 导出按钮
- **Settings 改版**：page-title + hoverable Card + 分组 colored label + sticky 保存按钮 + stagger 动画
- **PaperEditor 颜色适配**：slate-* → aide-* CSS 变量
- **清理 10 个废弃组件**：BoardView/ChallengePanel/MessageStream/PhaseIndicator/SpiralVisualizer/PDFUploader/SearchTester/CitationGraph/CheckpointModal/AdjustEditor

### ❌ 未完成
- 智能研究方向推荐
- 实验追踪与可视化（假设演化树、证据网络图）
- 多用户协作
- 研究模板库

---

## Bug Fixes 历史（各 session 已修复）

| Session | 修复内容 |
|---------|----------|
| Session 2 | `tracker.py` ORM 双重定义冲突、`async_sessionmaker` 误用 `await`、列名错误 |
| Session 2 | `factory.py` CheckpointManager 注册表；`ws.py` checkpoint 响应用正确实例；`checkpoints.py` REST 实现 |
| Session 3 | 设置持久化：改为写 `/app/workspace/settings_overrides.json`，lifespan 恢复 |
| Session 4 | 研究主题 6 层注入链修复（topic 从未传给任何 agent） |
| Session 4 | 前端运行状态指示器（ping、iteration、TopicDriftWarning Toast） |
| Session 5 | Challenge 自动 dismiss（>2 iters 自动解决，解除收敛阻塞） |
| Session 5 | Phase COMPLETE 论文导出（`exports/paper.md` + `ResearchCompleted` WS） |
| Session 5 | Librarian 接入真实 arXiv API（5 篇论文注入 context） |
| Session 5 | ContextBuilder token 预算（L2→L1→L0 自动降级） |
| Session 6 | **Critic 分数链路修复**：`agent_role == CRITIC` 替代 artifact_type 字符串匹配（**P0**） |
| Session 6 | **L1 JSON 生成加固**：markdown fence 剥离 + 强化 prompt |
| Session 6 | **critic.j2 输出格式明确 artifact_type: review** |
| Session 6 | **WriteBackGuard 降噪**：fence 剥离 + 输入截断 3000 字符 |
| Session 6 | **Librarian 本地知识检索 SSL fallback**：Hybrid→BM25 graceful 降级 |
| Session 6 | **S2 限流优化**：重试 3 次 + Retry-After header + query 去重缓存 |
| Session 6 | **SPAWN_SUBAGENT handler**：消除 "Unhandled action type" 警告 |
| Session 6 | **Heartbeat stale 阈值**：180s→360s 可配置 |
| **Session 7** | **Anthropic/Claude Provider**：新增 `AnthropicProvider`，支持代理 base_url |
| **Session 7** | **Per-role 模型分配**：推理角色→reasoner，工具角色→chat |
| **Session 7** | **并行 Lane 架构**：concurrency 1-5，独立 workspace，asyncio.gather |
| **Session 7** | **SynthesizerAgent**：跨 lane 综合分析，SYNTHESIZE 阶段 |
| **Session 7** | **Claude non-JSON 修复**：base.py JSON 强制指令 + max_tokens 4096→8192 |
| **Session 7** | **Query 缓存归一化**：`_normalize_cache_key()` 排序去重关键词 |
| **Session 7** | **S2 429 冷却期**：5 分钟冷却后直接走 arXiv，省去无效重试 |
| **Session 7** | **Hybrid search 智能跳过**：无 OpenAI key 时直接 BM25，避免 SSL 错误 |
| **Session 7** | **BM25 fallback 返回内容**：从 `_doc_texts` 读取文本，不再返回空 |
| **Session 7** | **论文导出增强**：补充 hypotheses/evidence/directions，11 sections 62KB |
| **Session 8** | **Token 计费链路修复（P0）**：`base.py` 未传 `project_id`/`agent_role` 给 `generate()`，导致 `record_usage()` 从未被调用 |
| **Session 8** | **factory.py 所有 agent 传入 project_id**：修复前仅 Librarian 有 project_id |
| **Session 8** | **Token 费用 API**：`GET /usage` 返回 by_model 分模型统计 + USD/RMB 换算 |
| **Session 8** | **Artifact Jaccard 去重**：替换直通 dedup，Jaccard 词集相似度阈值 0.6 |
| **Session 8** | **引用图谱**：Librarian 检索后构建 NetworkX DiGraph + REST API |
| **Session 8** | **论文编辑与导出**：前端编辑模式 + PUT 保存 + HTML 可打印导出 |
| **Session 8** | **action_type 容错**：模糊匹配 + target 自动填充，减少 LLM 输出格式错误 |
| **Session 8** | **前端 ResearchCompleted/Lane 事件处理**：完成 banner、token 费用、lane 进度 |
| **Session 11** | **Planner LLM 动态调度**：`_llm_select()` + Critic guarantee + Challenge routing + artifact coverage override |
| **Session 11** | **Agent context 按 role 定制**：`_build_state_summary(role=)` 只含 agent 关注的 artifact types |
| **Session 11** | **Challenge 响应路由**：target_agent 优先调度 + challenge 注入 prompt + auto-dismiss 2→5 轮 |
| **Session 11** | **收敛多维度化**：per-phase 阈值 + artifact coverage 必需检查 |
| **Session 11** | **偏题检测三层 fallback**：embedding → jieba → keyword，阈值提高到 0.4 |
| **Session 11** | **WriteBackGuard 规则驱动重写**：不再调用 LLM，改为检查 agent 是否产出期望 artifact |
| **Session 11** | **记忆机制**：`_generate_lessons_learned()` + `_inject_lessons_learned()` 跨项目经验传递 |
| **Session 11** | **Blackboard artifact meta 缓存**：write-through 模式 |
| **Session 11** | **Lane 视角分化**：5 条 `_LANE_PERSPECTIVES` 注入不同研究视角 |
| **Session 11** | **json_mode 支持**：`generate(json_mode=True)` 减少格式问题 |
| **Session 12** | **Critic EMA 评分（P0）**：算术平均→指数移动平均（α=0.4），解决早期低分拖拽 |
| **Session 12** | **Agent 非 JSON 重试**：检测到非 JSON 响应后追加 [RETRY] 指令重试一次 |
| **Session 12** | **Challenge resolve 后验证**：dispatch 后检查 RESOLVE_CHALLENGE actions |
| **Session 12** | **中文关键词检测**：challenge 分类支持矛盾/冲突/漏洞/逻辑/偏离/偏题等中文词 |
| **Session 12** | **偏题注入 agent prompt**：`[⚠️ TOPIC DRIFT WARNING]` 直接注入 task description |
| **Session 12** | **Blackboard L0 + version 缓存**：`_l0_cache` + `_version_cache` write-through |
| **Session 12** | **Critic 依赖类型补全**：增加 EVIDENCE_GAPS/EXPERIMENT_GUIDE/TREND_SIGNALS |
| **Session 12** | **artifact_type 三层防御**：模板 + planner 指令 + `_ROLE_ALLOWED_TYPES` 运行时白名单 |
| **Session 12** | **Lane artifact 改善**：截断 3000→6000 字符 + 按类型分组 + aiofiles 异步 I/O |

---

## 性能基线

### Session 6（纯 DeepSeek，2026-03-11）

| 指标 | 数据 |
|------|------|
| 总耗时 | 33 分 51 秒 |
| 总迭代数 | 14 轮 |
| 模型 | deepseek-chat + deepseek-reasoner |
| 论文产出 | ~6KB |

### Session 7 Run 1（DeepSeek + Claude 混合，修复前，2026-03-11）

| 指标 | 数据 |
|------|------|
| 总耗时 | 23 分 09 秒（**-32%**） |
| 总迭代数 | 14 轮 |
| Anthropic 调用 | 7 次 |
| non-JSON 警告 | **5 次** |
| S2 429 失败 | 8 次 |
| 论文产出 | 2 sections, 6.5KB |

### Session 7 Run 2（修复后验证，2026-03-11）

| 指标 | 数据 |
|------|------|
| 总耗时 | 27 分 25 秒 |
| 总迭代数 | 14 轮 |
| Anthropic 调用 | 7 次（全部成功） |
| non-JSON 警告 | **0 次** |
| S2 429 失败 | **0 次** |
| Query 缓存命中 | 3 次 |
| Critic 分数提取 | 10 次（6.0-9.0） |
| 论文产出 | **11 sections, 62KB** |

### Session 8 Run 1（Token 计费修复后，2026-03-11）

| 指标 | 数据 |
|------|------|
| 总耗时 | 30 分 29 秒 |
| 总迭代数 | 14 轮 |
| 总 Token | 115,842 |
| 总费用 | $0.8201 USD / 5.9378 RMB |
| 模型分布 | claude-sonnet-4-6: 7 calls $0.66 / deepseek-chat: 5 calls $0.06 / deepseek-reasoner: 2 calls $0.10 |

### Session 8 Run 2（最终验证，2026-03-11）

| 指标 | 数据 |
|------|------|
| 总耗时 | ~37 分钟 |
| 总迭代数 | 14 轮 |
| 总 Token | 104,719 |
| 总费用 | $0.7712 USD / 5.5834 RMB |
| 模型分布 | claude-sonnet-4-6: 7 calls $0.62 / deepseek-chat: 5 calls $0.05 / deepseek-reasoner: 2 calls $0.10 |
| 论文产出 | 22,086 字符，9 sections |

详细踩坑记录见 [doc/devrec.md](devrec.md)。

### Session 12 E2E（审计修复后验证，2026-03-16）

| 指标 | 数据 |
|------|------|
| 总耗时 | ~30 分钟 (11:12 - 11:42) |
| 总迭代数 | ~12 轮 |
| 总 Token | 51,522 |
| 总费用 | $0.017 / ¥0.12 |
| 模型 | deepseek-chat + deepseek-reasoner |
| 论文产出 | 11 sections |
| EMA 验证 | α=0.4 正确：7.0→5.80→6.28 |
| artifact_type 白名单拦截 | 2 次 `trend_signals→hypotheses` |
| 阶段收敛 | 4/4 全部 critic 质量收敛（无 max_iterations 兜底） |

---

## 当前待办（Next Steps）

### P1 — 架构提升（review 中期目标）
- [ ] Agent 间 request-response 协议（Agent 输出 `REQUEST_COLLABORATION` action）
- [ ] Function calling / tool use 替代自由格式 JSON
- [ ] Planner LLM 增加最近调度历史记忆

### P1 — 并行 Lane
- [ ] 创建 concurrency=3 项目测试多 lane 并行 + 合成阶段
- [x] 前端 Lane 进度可视化（Session 8 完成）
- [ ] Synthesizer 输出质量评估
- [ ] Lane 间中间交换（阶段结束时交换摘要）

### P2 — 用户体验
- [x] 前端 `ResearchCompleted` 处理（Session 8 完成）
- [ ] 前端 Blackboard 详情视图：点击 artifact 卡片展开 L1/L2 完整内容
- [x] 论文预览页 + 编辑 + PDF 导出（Session 8 完成）

### P3 — 长期完善
- [ ] Agent 输出 Pydantic schema 强校验
- [ ] 多用户 / 协作功能
- [ ] 研究可视化（假设演化、证据图）
- [ ] Reactive Blackboard 触发机制（KS 激活条件）
- [ ] Agent-level 记忆（few-shot example 池）
- [ ] Adversarial lanes（正反方辩证）

---

## Session 10（2026-03-13）— 全面质量验证

### 测试执行与结果

#### 后端单元测试
- Ruff Lint: 0 issues
- Ruff Format: 6 files 需格式化（非阻塞，均为已改动文件的格式差异）
- Pytest: 17/17 全部通过（`test_json_utils.py` TestSafeJsonLoads 套件）

#### REST API 集成测试（10 个端点）
- `/health`、`/api/projects` CRUD、`/api/settings` GET/PUT、`/usage`、`/citation-graph`、`/export/paper/html`、DELETE：全部返回预期状态码
- 发现：创建项目字段为 `name`（非 `title`）；设置更新方法为 PUT（非 POST）

#### WebSocket 连通测试
- 连接 `ws://localhost:8000/ws/projects/{id}` 成功，稳定保持 3 秒
- 无研究运行时无广播消息（预期行为）

#### 并发压力测试
- 120 请求 / 0.35s = **341 req/s**，**0 错误**
- `GET /health` p50=4.7ms / p99=13.3ms
- `GET /api/projects` p50=196.5ms / p99=205.1ms
- `POST /api/projects` p50=111.6ms / p99=115.7ms

#### 前端页面渲染测试
- Dashboard / Settings / 项目详情页：全部 HTTP 200
- 7 个 JS chunk 全部加载正常
- CSS 79KB + 字体预加载正常
- SSR 输出含正确的页面结构和组件引用

#### 全链路 E2E 测试
- 创建项目 → 启动研究 → 引擎运行（Planner 分配 Librarian/Director）
- arXiv 检索成功（5 篇论文），S2 触发 429 后 backoff 正常
- **3 个 artifact 产出**（directions/evidence_findings/trend_signals），L0/L1/L2 三级全部生成
- **Token 计费正常**：8,923 tokens / $0.059 / 0.43 RMB / 3 次 LLM 调用
- 引用图谱：5 节点正确入库
- 暂停/恢复：正常
- 前端渲染 E2E 项目页面：正常

### 测试后清理
- 删除 29 个测试/压力测试项目，数据库恢复干净状态

---

## Session 11-12（2026-03-15~16）— 二次审计修复 + 全链路验证

### 审计背景

`doc/review.md` 二次审计（2026-03-15）对 10 个批判点逐条复查，发现：
- 7/10 短期目标已达成
- 3/10 部分达成
- 4 个新引入问题（N1-N4）
- 多个残留问题

### Session 11 修复（审计首次修复轮）

**P0 — Planner 动态调度**
- `planner.py` 重写：`_llm_select()` 向 LLM 发送 board 状态 + 可用 agent + 缺失 artifact，返回 `{agent, task, rationale}`
- `_CRITIC_GUARANTEE_INTERVAL = 3`：每 3 轮至少调用一次 Critic
- Challenge routing：open challenge 有 target_agent 时覆盖 LLM 选择
- Artifact coverage override：缺失 artifact 时调度能产出该类型的 agent
- `enable_llm_planner` 配置开关，`_PHASE_SEQUENCES` 保留为 fallback

**P0 — Agent Context 按 Role 定制**
- `engine.py _build_state_summary(role=)`：从 agent 的 dependency_artifact_types 构建 relevant type set
- `board.py get_state_summary(relevant_types=)`：只扫描匹配的 artifact type
- Planner 仍看全量 context（role=None）

**P1 — Challenge 响应路由 + 收敛多维度化 + 偏题检测**
- Challenge：target_agent 字段 + 优先调度 + prompt 注入 + auto-dismiss 2→5
- 收敛：per-phase 阈值（6.0/6.5/7.0/7.5）+ `_check_artifact_coverage()` 必需 artifact 检查
- 偏题：embedding → jieba → keyword 三层 fallback，阈值 0.2→0.4

**P1 — Blackboard 缓存 + WriteBackGuard + 记忆机制**
- Blackboard artifact meta 缓存（write-through）
- WriteBackGuard 改为规则驱动，不再调用 LLM
- `_generate_lessons_learned()` + `_inject_lessons_learned()` 跨项目经验

**其他**
- Lane 视角分化（5 条 `_LANE_PERSPECTIVES`）
- json_mode 支持（`generate(json_mode=True)`）

### Session 12 修复（审计残留问题 + 新问题）

**P0 — Critic EMA 评分（N3）**
- `board.py set_phase_critic_score()`：算术平均→EMA（α=0.4）
- 实测验证：7.0→5.80→6.28，早期低分不再永久拖拽

**P0 — Agent 非 JSON 重试**
- `base.py execute()`：检测到非 JSON 响应后追加 `[RETRY]` 指令重试一次

**P1 — 审计残留修复**
- Challenge resolve 后验证：dispatch 后检查 `RESOLVE_CHALLENGE` actions，未 resolve 则 log warning
- 中文关键词检测：矛盾/冲突/不一致/相悖/反驳/漏洞/逻辑/缺失/不完整/推理/方向/偏离/偏题/跑偏/离题
- 偏题注入 agent prompt：`[⚠️ TOPIC DRIFT WARNING]` 直接注入 task description
- Blackboard L0 + version 缓存：`_l0_cache` + `_version_cache` write-through
- Critic 依赖类型补全：+EVIDENCE_GAPS/EXPERIMENT_GUIDE/TREND_SIGNALS

**P0 — artifact_type 三层防御**（修复 Scientist 在 hypothesize 阶段写错 artifact_type 的 bug）
- Layer 1：4 个 prompt 模板增加 `artifact_type` 字段示例 + IMPORTANT 规则
- Layer 2：planner 任务描述追加 `artifact_type` 指令
- Layer 3：`actions.py _ROLE_ALLOWED_TYPES` 运行时白名单校验 + 强制修正

**N4 — Lane async I/O**
- `_collect_lane_artifacts()`：sync `read_text()` → aiofiles 异步读取
- Lane artifact 截断 3000→6000 字符 + 按 artifact type 分组

### E2E 全链路测试（Session 12）

| 测试项 | 结果 |
|--------|------|
| Ruff Lint | 0 issues |
| Pytest | 77/77 PASS |
| REST API 集成 | 10/10 PASS |
| WebSocket | 连接成功 |
| 并发压力 | 150 req / 0.43s = 351 req/s, 0 错误 |
| 前端 SSR | 3 页面正常渲染 |
| **E2E 研究管道** | **4 阶段全部 critic 质量收敛，无 max_iterations 兜底** |

E2E 关键验证：
- EXPLORE→HYPOTHESIZE→EVIDENCE→COMPOSE→COMPLETE 全链路通过
- EMA 评分正确运作（7.0→5.80→6.28）
- artifact_type 白名单 2 次拦截 `trend_signals→hypotheses`
- hypotheses 目录有 2 个 artifact（之前为 0）
- 51,522 tokens / $0.017 / ¥0.12 正确记录
- 11 sections 论文导出到 `exports/paper.md`

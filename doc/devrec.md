# AIDE 开发踩坑与经验总结

> 记录开发过程中最值得复盘的问题、根因分析和设计教训。

---

## 1. Critic 分数始终为 0 — 一条隐蔽的级联故障链

**现象**：研究阶段永远无法通过质量评判收敛，只能靠 `max_iterations` 超时强制推进。整个研究流程形同虚设。

**根因链**：
```
Critic LLM 输出的 artifact_type 字段值不可靠（UUID、乱字符串等）
    ↓
actions.py fallback 到 "review" → artifact 正确写入 blackboard
    ↓
但 engine.py:294 用 action.content.get("artifact_type") 判断
    ↓
拿到的是 LLM 原始输出的错误值，不等于 "review"
    ↓
分数提取逻辑被跳过 → critic_score 永远 = 0.0
    ↓
convergence 条件永远不满足 → 只能靠 max_iterations 超时
```

**修复**：改用 `action.agent_role == AgentRole.CRITIC` 判断（角色是确定性的，不依赖 LLM 输出）。

**教训**：
- **永远不要信任 LLM 输出的元数据字段做控制流判断**。LLM 生成的 `artifact_type`、`action_type` 等字段值不可靠，应该用请求侧已知的确定性信息（如 agent 角色）。
- 这种 bug 极难发现：actions.py 的 fallback 掩盖了错误（artifact 能正确写入），但 engine.py 用了 **原始值** 而非 fallback 后的值。两个组件各自"正确"，组合起来却失败。
- **级联故障的特征**：单看任何一个组件都没 bug，问题出在组件间的数据流断裂。

---

## 2. LLM 返回 Markdown fence 包裹 JSON — DeepSeek 的普遍行为

**现象**：`levels.py` 的 `generate_l1()` JSON 解析频繁失败；`WriteBackGuard` JSON 解析也频繁失败。

**根因**：DeepSeek 即使 system prompt 说 "output JSON only"，仍然高概率返回：
````
```json
{"score": 7, "summary": "..."}
```
````

**修复**：在所有 `json.loads()` 前加 `_strip_markdown_fences()` 预处理。

**教训**：
- **与 LLM 交互的 JSON 解析必须加 fence 剥离作为标准步骤**，不能假设 LLM 会遵守 "no markdown" 指令。这不是 prompt 能解决的——即使加了明确指令，DeepSeek 仍有概率输出 fence。
- 建议：封装一个统一的 `safe_json_loads(text)` 工具函数，所有 LLM→JSON 的路径都走它。

---

## 3. Semantic Scholar API 429 限流 — 无 API key 的免费额度极低

**现象**：S2 API 首次请求几乎必定 429，需要 3 次重试（15s+30s+45s backoff）才能成功，单次文献检索耗时 ~97 秒。

**修复**：
- `_MAX_RETRIES` 2→3，`_RATE_LIMIT_BACKOFF` 10→15s
- 读取 `Retry-After` header 动态 backoff
- Librarian 层加 query 去重缓存，同一 query 不重复请求

**教训**：
- **学术 API 的免费额度远比想象的低**。S2 无 key 大约 1 req/min。如果要做严肃的文献检索，必须申请 API key 或实现本地缓存。
- 重试策略中，**读取 `Retry-After` header 是必须的**，固定 backoff 可能太短也可能太长。

---

## 4. Docker 内 SSL 证书验证失败 — OpenAI Embedding API 不可用

**现象**：`[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: Hostname mismatch`，Librarian 的本地知识检索直接返回空。

**根因**：Docker 容器内的 CA 证书链不完整或宿主机代理劫持了 HTTPS 流量。

**修复**：重构 `_search_local_knowledge()` 为两层 try/except：先尝试 Hybrid search（vector+BM25），SSL 失败时 graceful fallback 到纯 BM25。

**教训**：
- **依赖外部 API 的功能必须有 fallback 路径**。embedding 服务不可用时，BM25 虽然效果差一些，但总比返回空好。
- Docker 容器内的网络环境（代理、DNS、SSL 证书）跟宿主机完全不同，开发时容易忽略。

---

## 5. BM25Store 方法名不匹配 — 接口假设导致运行时崩溃

**现象**：BM25 fallback 报 `'BM25Store' object has no attribute 'search'`。

**根因**：`librarian.py` 调用 `bm25_store.search(query, top_k=5)`，但 `BM25Store` 的实际方法名是 `query(query_text, n_results=10)`，参数名也不同。

**修复**：改为 `bm25_store.query(query, n_results=5)`，并适配返回类型（`list[tuple[str, float]]` 而非 `list[dict]`）。

**教训**：
- **没有类型检查或接口测试的代码，方法名拼错只有运行时才能发现**。Python 的 duck typing 在这类场景是劣势。
- 写 fallback 代码后**必须立刻测试 fallback 路径**。很多 fallback 从未被触发过，第一次触发就崩溃。

---

## 6. Heartbeat 误报 — stale 阈值与 agent 超时不匹配

**现象**：Librarian 做文献检索时（含 S2 重试 ~97s + LLM 调用），heartbeat 报 stale 状态。

**根因**：stale 阈值硬编码为 `interval * 3 = 180s`，而 agent 正常执行可达 2-4 分钟（特别是 Librarian）。

**修复**：改为可配置的 `heartbeat_stale_threshold_seconds = 360`。

**教训**：
- **监控阈值必须大于被监控操作的最大正常耗时**。hardcode 的 magic number 迟早会在某个场景下错误触发。

---

## 7. 性能基线数据（首次实测 2026-03-11）

完整研究流程实测（英文课题，deepseek-chat + deepseek-reasoner 混合）：

| 指标 | 数据 |
|------|------|
| 总耗时 | 33 分 51 秒 |
| 总迭代数 | 14 轮 |
| 阶段推进方式 | 全部通过 Critic 质量评判（7.0-8.0 分） |
| 估算费用 | ~$1.0-1.5（¥7-11） |

各 Agent 单次调用耗时：

| Agent | 耗时 | 瓶颈 |
|-------|------|------|
| Librarian（首次） | ~4min 20s | S2 429 重试 97s |
| Librarian（后续） | ~2min | LLM 调用 |
| Scientist | ~3min | deepseek-reasoner thinking chain |
| Director | ~1min 45s | deepseek-reasoner |
| Critic | ~2min 30s | 多个 review artifact |
| Writer | ~2min 15s | 含 SubAgent 并行 |

---

## 架构设计反思

### 做得好的
- **Protocol-based 依赖注入**：Board/LLMRouter 用 Protocol 定义接口，factory.py 组装。测试和替换都很容易。
- **研究主题 6 层注入链**：虽然实现复杂，但确实解决了 LLM 跑偏问题——每一层都有独立的主题强调。
- **per-phase critic score**：避免旧阶段高分导致新阶段秒收敛。

### 需要改进的
- **LLM 输出解析缺乏统一层**：fence 剥离、JSON 解析、score 提取散落在各处。应该有一个统一的 `LLMOutputParser` 处理所有 LLM→结构化数据的转换。
- **fallback 代码从未被测试**：每次写 fallback 都是"写完就忘"，直到生产环境触发才发现崩溃。需要对 fallback 路径做专门的测试。
- **Magic numbers 太多**：300s 超时、180s stale、30K token budget、3000 字符截断——应该全部收进 `config.py` 统一管理。

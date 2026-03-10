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

**修复（Session 6）**：
- `_MAX_RETRIES` 2→3，`_RATE_LIMIT_BACKOFF` 10→15s
- 读取 `Retry-After` header 动态 backoff
- Librarian 层加 query 去重缓存，同一 query 不重复请求

**进一步修复（Session 7）**：
- 429 后设 5 分钟冷却期（`_S2_COOLDOWN_SECONDS = 300`），冷却期间跳过 S2 直接走 arXiv
- Query 缓存 key 归一化：`_normalize_cache_key()` 对翻译结果排序去重关键词，避免 `"Agent engineering, memory system"` 与 `"Agent engineering memory system"` 被视为不同 query
- **效果**：S2 429 从 8 次降到 0 次，缓存命中从 1 次升到 3 次

**教训**：
- **学术 API 的免费额度远比想象的低**。S2 无 key 大约 1 req/min。如果要做严肃的文献检索，必须申请 API key 或实现本地缓存。
- 重试策略中，**读取 `Retry-After` header 是必须的**，固定 backoff 可能太短也可能太长。
- **冷却期优于无限重试**：首次 429 后，同一会话内 S2 几乎不可能恢复。设一个长冷却期直接跳过，比每次都重试 4 轮（累计 ~105s）高效得多。

---

## 4. Docker 内 SSL 证书验证失败 — OpenAI Embedding API 不可用

**现象**：`[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed`，Librarian 的本地知识检索直接返回空。

**根因**：Docker 容器内的 CA 证书链不完整或宿主机代理劫持了 HTTPS 流量。

**修复（Session 6）**：重构 `_search_local_knowledge()` 为两层 try/except：先尝试 Hybrid search（vector+BM25），SSL 失败时 graceful fallback 到纯 BM25。

**进一步修复（Session 7）**：
- 检测 OpenAI API key 是否配置，未配置则跳过 Hybrid search（避免必然失败的网络调用）
- BM25 fallback 从 `_doc_texts` 读取文本内容（之前只返回 doc_id+score，content 为空）
- **效果**：SSL 错误从每次都报降到 0 次

**教训**：
- **依赖外部 API 的功能必须有 fallback 路径**。embedding 服务不可用时，BM25 虽然效果差一些，但总比返回空好。
- **前置检查优于后置捕获**：与其每次都发 HTTP 请求然后捕获 SSL 异常，不如先检查 API key 是否存在。没 key = 必然失败，不用浪费时间尝试。

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

## 7. Claude 模型不遵循 JSON 输出格式 — 不同 LLM 的行为差异

**现象（Session 7）**：将 Scientist/Librarian 切换到 `claude-sonnet-4-6` 后，5/7 次调用返回自然语言散文而非 JSON，被 `base.py` 包装为 summary（`non-JSON response, wrapping as summary`）。同时 `compl_tok=4096` 每次都被截断。

**根因**：
1. Claude 比 DeepSeek 更"有主见"，倾向于用自然语言写出完整的研究分析，而非遵循模板中的 JSON schema 要求
2. Anthropic provider 默认 `max_tokens=4096`，Claude 的长文本输出被截断，导致 JSON 不完整
3. Claude 偶尔会在 `artifact_type` 字段输出 UUID（如 `54a5f3e8-763e-...`）而非枚举值

**修复**：
1. `anthropic.py`: `max_tokens` 从 4096 提高到 8192
2. `base.py`: 对 Claude 模型（`model.startswith("claude-")`）追加 JSON 强制指令：
   ```
   CRITICAL INSTRUCTION: You MUST respond with a single valid JSON object...
   Start your response with `{` and end with `}`.
   ```
3. actions.py 的 fallback 机制处理 UUID 等非法 artifact_type（已有，继续生效）

**效果**：non-JSON 从 5/7 次降到 **0/7 次**。

**教训**：
- **不同 LLM 对同一 prompt 的遵循度差异巨大**。DeepSeek 经过 fence 剥离后基本能输出 JSON，但 Claude 需要更强的格式强制（独立的 CRITICAL INSTRUCTION 段落 + 明确的"以 `{` 开头"指令）。
- **max_tokens 要留余量**。Claude 的输出天然比 DeepSeek 长（更详细的推理），4096 对 Claude 不够用，8192 是合理的默认值。
- **多 provider 支持时，每个 provider 需要独立的适配层**。不能假设"能跑 DeepSeek 的 prompt 就能跑 Claude"。

---

## 8. 论文导出只有 2 个 section — export_paper 只收 DRAFT

**现象（Session 7）**：研究完成后 `export_paper()` 只输出 2 sections（6.5KB），远少于预期。

**根因**：`export_paper()` 只收集 `ArtifactType.DRAFT` 类型的 artifact。但实际运行中：
- Claude 的 non-JSON 输出被包装为 summary（不产生 write_artifact action），导致很多有价值的内容没有写成 DRAFT
- 即使修复 non-JSON 后，evidence_findings、hypotheses 等有价值的中间产物也没被纳入论文

**修复**：`export_paper()` 在收集 DRAFT 后，补充收集 HYPOTHESES、EVIDENCE_FINDINGS、DIRECTIONS、OUTLINE 类型的 artifact 作为补充 section。

**效果**：从 2 sections 6.5KB → **11 sections 62KB**。

**教训**：
- **"最终产物"不应该只依赖最后一步的输出**。研究过程中的中间产物（假设、证据、方向）本身就有价值，应该纳入最终论文。
- 这也暴露了一个架构问题：Writer 只在 COMPOSE 阶段运行 1-2 轮，产出有限。更好的设计是让 Writer 在每个阶段都生成对应的 draft section。

---

## 9. Query 缓存不稳定 — LLM 翻译的非确定性

**现象（Session 7）**：Librarian 的 query 去重缓存在第二次调用时未命中，导致重复搜索 S2 API（又一轮 429 重试）。

**根因**：翻译同一个中文 query 两次，DeepSeek 返回了略有不同的英文：
- 第一次：`"Agent engineering, memory system, optimization techniques"`
- 第二次：`"Agent engineering memory system optimization techniques"`（没有逗号）

缓存 key 用的是 `en_query.lower().strip()`（完整字符串），标点差异导致未命中。

**修复**：`_normalize_cache_key(query)` 提取纯字母单词，排序去重后作为 cache key：
```python
def _normalize_cache_key(query: str) -> str:
    words = re.findall(r"[a-zA-Z]+", query.lower())
    return " ".join(sorted(set(words)))
```

**教训**：
- **LLM 输出不是确定性的，即使同一输入也可能有微小差异**。用 LLM 输出作缓存 key 时，必须做归一化处理。
- 更一般地：**任何用于比较/去重的字符串，如果来源于 LLM，都需要归一化**。

---

## 性能基线对比

### Session 6 vs Session 7

| 指标 | Session 6 (纯 DeepSeek) | Session 7 Run 2 (Claude+DS 混合) |
|------|-------------------------|----------------------------------|
| 总耗时 | 33m51s | 27m25s (**-19%**) |
| 迭代数 | 14 | 14 |
| non-JSON | 0 | 0 |
| S2 429 | ~4 次 | 0 次 |
| 论文大小 | ~6KB | **62KB (+854%)** |
| Critic 分数范围 | 6.0-8.0 | 6.0-9.0 |

各 Agent 单次调用耗时（Session 7，Claude 混合模式）：

| Agent | 模型 | 耗时 | 备注 |
|-------|------|------|------|
| Librarian（首次） | claude-sonnet-4-6 | ~1min 40s | 含 S2 查询 + arXiv fallback |
| Librarian（后续） | claude-sonnet-4-6 | ~1min 20s | query 缓存命中，跳过检索 |
| Scientist | claude-sonnet-4-6 | ~1min 10s | 比 deepseek-reasoner 快 |
| Director | deepseek-reasoner | ~1min | reasoning chain |
| Critic | deepseek-chat（用户覆盖） | ~40s | 比 reasoner 快很多 |
| Writer | deepseek-chat | ~1min | 含 SubAgent 并行 |

---

## 架构设计反思

### 做得好的
- **Protocol-based 依赖注入**：Board/LLMRouter 用 Protocol 定义接口，factory.py 组装。测试和替换都很容易。
- **研究主题 6 层注入链**：虽然实现复杂，但确实解决了 LLM 跑偏问题——每一层都有独立的主题强调。
- **per-phase critic score**：避免旧阶段高分导致新阶段秒收敛。
- **多 provider fallback chain**（Session 7 新增）：任何一个 provider 失败都能自动降级到其他 provider。
- **S2 冷却期设计**（Session 7）：用类变量共享冷却状态，所有 Librarian 实例都能受益。

### 需要改进的
- **LLM 输出解析缺乏统一层**：fence 剥离、JSON 解析、score 提取散落在各处。应该有一个统一的 `LLMOutputParser` 处理所有 LLM→结构化数据的转换。
- **fallback 代码从未被测试**：每次写 fallback 都是"写完就忘"，直到生产环境触发才发现崩溃。需要对 fallback 路径做专门的测试。
- **Magic numbers 太多**：300s 超时、360s stale、30K token budget、3000 字符截断、5min S2 cooldown——应该全部收进 `config.py` 统一管理。
- **不同 LLM 的适配层不够**：Claude 和 DeepSeek 对 JSON 格式指令的遵循度差异很大，当前的适配是在 `base.py` 里硬编码的 `if model.startswith("claude-")`，不够优雅。应该在 provider 层或 router 层做模型族级别的适配。

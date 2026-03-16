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

## 10. Token 计费器始终为 0 — generate() 未传递追踪参数

**现象（Session 8）**：前端 Token 费用显示全部为 0，DB 中 `token_usage` 表为空。但 `TokenTracker.record_usage()` 机制本身正常（手动调用可写入）。

**根因链**：
```
BaseAgent.execute() 调用 self._llm_router.generate(model, prompt)
    ↓
generate() 签名有 project_id=None, agent_role=None（可选参数）
    ↓
但 execute() 没有传递这两个参数
    ↓
router.py:133 条件 if self._tracker and project_id and agent_role 永远为 False
    ↓
record_usage() 从未被调用 → token_usage 表永远为空
```

**进一步发现**：`factory.py` 构造 agent 时，仅 `LibrarianAgent` 传入了 `project_id`，其余 5 个 agent 的 `project_id` 为空字符串。

**修复（4 个文件）**：
1. `base.py`：Protocol 定义增加 `project_id`/`agent_role` 可选参数；`execute()` 传递 `project_id=self._project_id, agent_role=self.role`
2. `librarian.py`：翻译查询的 `generate()` 调用也传入追踪参数
3. `subagent.py`：Protocol 定义同步更新
4. `factory.py`：所有 6 个 agent 构造时传入 `project_id=str(project_id)`

**验证**：两次完整研究运行（14 轮迭代），14 次 LLM 调用全部正确记录到 DB，分模型费用计算准确。

**教训**：
- **可选参数的默认值 None 是隐形的功能开关**。`project_id=None` 作为默认值，意味着"不传就不记录"——而调用方恰好全都没传。这种 bug 不会报错，只会静默丢失数据。
- **跨层传参链必须端到端验证**。从 `factory.py` 构造 agent → `base.py` 存储 `_project_id` → `execute()` 传给 `generate()` → `router.py` 传给 `record_usage()`，任何一环断裂都会导致功能失效。单元测试无法覆盖这种跨层问题，必须做集成测试。
- **"只有一个地方传了参数"是强信号**。6 个 agent 中只有 Librarian 传了 `project_id`，说明其他 5 个是复制粘贴时漏掉的。

---

## 性能基线对比

### Session 6 vs Session 7 vs Session 8

| 指标 | Session 6 (纯 DeepSeek) | Session 7 Run 2 (Claude+DS) | Session 8 Run 2 (计费修复后) |
|------|-------------------------|----------------------------|------------------------------|
| 总耗时 | 33m51s | 27m25s | ~37min |
| 迭代数 | 14 | 14 | 14 |
| 总 Token | 未记录 | 未记录 | **104,719** |
| 总费用 | 未记录 | 未记录 | **$0.77 / 5.58 RMB** |
| non-JSON | 0 | 0 | 0 |
| S2 429 | ~4 次 | 0 次 | ~4 次（首次冷启动） |
| 论文大小 | ~6KB | 62KB | 22KB |
| Critic 分数范围 | 6.0-8.0 | 6.0-9.0 | 7.0 |

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
- **三层防御模式**（Session 12）：artifact_type 用 Prompt+Planner+Runtime 三层控制，每层独立有效且互相兜底。可推广到其他 LLM 输出控制场景。
- **EMA 替代算术平均**（Session 12）：α=0.4 让最近评分权重更高，解决了早期低分永久拖拽收敛的问题。
- **审计驱动开发**（Session 11-12）：系统性的 review.md 审计报告→逐条修复→E2E 验证闭环，比零散修 bug 高效得多。

### 需要改进的
- ~~**LLM 输出解析缺乏统一层**~~（Session 9 已解决：`safe_json_loads()` 统一了所有 JSON 解析入口）
- ~~**Claude non-JSON hack**~~（Session 11 已解决：`json_mode=True` 替代了 `if model.startswith("claude-")` 硬编码）
- **fallback 代码从未被测试**：每次写 fallback 都是"写完就忘"，直到生产环境触发才发现崩溃。需要对 fallback 路径做专门的测试。
- **Magic numbers 太多**：300s 超时、360s stale、30K token budget——应该全部收进 `config.py` 统一管理（3000→6000 截断已在 Session 12 修复）。
- **可选参数默认 None 的隐形风险**（Session 8 教训）：`generate(project_id=None)` 导致计费从未触发。关键功能参数不应该用 None 默认值静默跳过，应该至少产生一条 warning 日志。
- **跨文件复制粘贴遗漏**（Session 8 教训）：factory.py 中 6 个 agent 构造只有 1 个传了 project_id，是典型的复制粘贴遗漏。批量构造应考虑用循环或 factory 函数统一参数。
- **中期架构挑战仍在**（Session 12 审计总结）：agent 间无法直接通信、Blackboard 是被动 CRUD、Lane 完全隔离——这些需要架构级变动，不是修 bug 能解决的。

---

## 11. Session 10 全面测试 — 质量验证基线

**测试日期**：2026-03-13

### 测试覆盖与结论

| 测试类型 | 范围 | 结果 |
|----------|------|------|
| Ruff Lint | 全量 backend/ | 0 issues |
| Pytest 单元测试 | 17 cases (json_utils) | 17/17 PASS |
| REST API 集成 | 10 个端点 | 10/10 PASS |
| WebSocket 连通 | 连接 + 保持 | PASS |
| 并发压力 | 120 req (50+50+20) | 341 req/s, 0 error |
| 前端渲染 | 3 页面 + 7 JS chunk + CSS | 全部 200 |
| 全链路 E2E | 创建→启动→Agent→Artifact→Token→暂停→前端 | 10/10 PASS |

### 关键发现
1. **API 性能稳定**：50 并发 GET 请求 p99 仅 205ms，POST p99 仅 116ms，FastAPI async 栈无压力
2. **全链路完整**：从项目创建到 Agent 执行到 Artifact 产出到 Token 计费，每一环都正常工作
3. **S2 限流处理有效**：429 触发后 backoff + arXiv fallback 正确执行，不影响研究流程
4. **L0/L1/L2 多分辨率正常**：3 个 artifact 每个都生成了三级摘要
5. **Ruff 格式化差异**：6 个已改动文件有格式差异，非阻塞但建议统一

### 教训
- **宿主机 localhost 可能被代理拦截**：测试脚本应从容器内执行（`docker compose exec`），避免 502 误报
- **压力测试应自带清理**：20 个 POST 请求创建了 20 个 Stress 项目，需要手动清理。建议压力测试脚本自带 teardown
- **ruff/pytest 未安装在 Docker 镜像中**：需要手动 pip install，应加入 pyproject.toml dev 依赖或 Dockerfile

---

## 12. Scientist 写错 artifact_type — Agent 角色不控制其写入目标

**现象（Session 12）**：在多通道项目中，Lane 2 的 hypothesize 阶段产出为 0。Critic 反复指出"不存在任何 hypotheses 工件"，4 轮迭代全部失败，靠 `max_iterations` 超时强推。

**根因链**：
```
Scientist.j2 模板没有 artifact_type 字段示例
    ↓
LLM 输出 JSON 中不含 artifact_type 或随意填了 "directions"
    ↓
actions.py:119 fallback 到 action.target（可能是 "directions"）
    ↓
ArtifactType("directions") 合法 → 写入 directions/ 目录
    ↓
hypotheses/ 目录始终为空 → 后续阶段全部质量极低
```

**对比**：Critic.j2 和 Synthesizer.j2 **已经有** `artifact_type` 字段（`"review"` / `"draft"`），所以不出问题。Director、Scientist、Writer、Librarian 的模板全部缺失。

**修复（三层防御）**：
1. **Prompt 模板**：4 个模板增加 `artifact_type` 字段示例 + IMPORTANT 规则
2. **Planner 任务描述**：追加 `"You MUST write artifacts with artifact_type='hypotheses'"` 指令
3. **Runtime 白名单**：`actions.py _ROLE_ALLOWED_TYPES` 定义每个 agent 角色允许写入的 artifact type，不在白名单内则强制修正

**实测验证**：Layer 3 在 E2E 测试中 2 次拦截 Scientist 尝试写入 `trend_signals`，自动修正为 `hypotheses`。

**教训**：
- **Agent 角色 ≠ 写入控制**。系统没有任何机制阻止 Scientist 写入 `directions`（那是 Director 的产物）。当 LLM 输出错误的 `artifact_type` 时，系统会忠实地执行——这是一个**权限模型缺失**的问题。
- **三层防御比单层可靠**。Prompt 是"建议"（LLM 可能忽略），Planner 任务描述是"强调"（仍可能被忽略），Runtime 白名单是"强制"（不可绕过）。只做 Prompt 层不够，只做 Runtime 层会产生大量修正日志。三层结合：大部分由 Prompt 解决（最佳质量），少量由 Runtime 兜底（最终安全网）。
- **bug 的可见性很低**。`directions/` 目录有内容（来自 Director 和被错误写入的 Scientist 产出），`hypotheses/` 为空容易被忽略。只有当 Critic 反复抱怨才会注意到。

---

## 13. 累积平均分的惯性陷阱 — 早期低分永久拖拽收敛

**现象（Session 12 审计 N3）**：EXPLORE 阶段前 4 轮 critic 分数 4、5、5、8，算术平均 = 5.5 < 阈值 6.0，阶段不收敛，被 `max_iterations` 兜底推进。第 4 轮质量已经达标（8 分），但被早期低分"污染"。

**根因**：`set_phase_critic_score()` 使用简单算术平均 `(old_avg * count + score) / (count + 1)`，每个历史分数权重相等。改进后的高分被稀释。

**修复**：改为**指数移动平均（EMA）** α=0.4：
```python
new_ema = alpha * score + (1 - alpha) * old_ema
```
α=0.4 表示新分数权重 40%，历史权重 60%。3 轮后历史影响衰减到 21.6%（0.6³），有效窗口约 3-4 轮。

**实测**：EMA 下 7.0→5.80→6.28（第 3 轮即超过 6.0 阈值收敛），算术平均下同样的分数 7.0→5.5→5.67（第 3 轮仍不够）。

**教训**：
- **评分聚合方式直接影响系统行为**。算术平均适合"所有历史等权"的场景，但质量评判需要"最近改进更重要"——EMA 或滑动窗口更合适。
- **α 值选择是 trade-off**：α 太大（如 0.8）相当于只看最近一次分数，波动大；α 太小（如 0.1）和算术平均差不多。0.3-0.5 是合理范围。

---

## 14. 二次审计的系统性复盘

**审计日期**：2026-03-15（`doc/review.md`）

### 审计覆盖了什么
10 个批判点（Planner 调度、Blackboard 架构、Agent context、Challenge、收敛检测、偏题检测、并行 Lane、Structured output、记忆机制、WriteBackGuard），每个点都从"修复了什么"和"残留什么"两个维度分析。

### 修复统计

| 类别 | 数量 | 说明 |
|------|------|------|
| 审计项总数 | 10 个原始 + 4 个新引入 = 14 项 |  |
| 已修复 | 13 项 | 包括所有 P0/P1 残留 |
| 已缓解 | 1 项 | N1 prompt 注入（低风险） |
| 中期目标未实现 | ~6 项 | agent 间通信、reactive blackboard、lane 交换等 |

### 关键设计教训

1. **三层防御优于单层修复**：artifact_type 问题用 Prompt + Planner + Runtime 三层解决，每层独立有效且互相兜底。这个模式可以推广到其他 LLM 输出控制问题。

2. **确定性信息优先于 LLM 输出**：Critic 分数提取用 `agent_role`（确定性）而非 `artifact_type`（LLM 输出）；artifact_type 白名单用 agent 角色（确定性）而非 LLM 输出的 type 字段。**凡是可以用请求侧信息替代 LLM 输出的，都应该替代**。

3. **审计+修复+验证 的闭环**：首次审计→修复→二次审计→残留修复→E2E 验证。没有 E2E 验证的修复不算完成——Session 12 的全链路测试发现了 Layer 3 实际拦截行为，确认修复有效。

4. **短期止血 vs 中期架构的权衡**：审计列出了明确的短/中/长期目标。当前全部短期目标已完成，但中期目标（agent 间通信、reactive blackboard、tool use）需要更大的架构变动，不适合在修复轮中做。

---

## 性能基线对比（更新）

### Session 6 vs Session 8 vs Session 12

| 指标 | Session 6 (纯 DeepSeek) | Session 8 Run 2 (计费修复后) | Session 12 (审计修复后) |
|------|-------------------------|------------------------------|------------------------|
| 总耗时 | 33m51s | ~37min | ~30min |
| 迭代数 | 14 | 14 | ~12 |
| 总 Token | 未记录 | 104,719 | 51,522 |
| 总费用 | 未记录 | $0.77 / 5.58 RMB | $0.017 / 0.12 RMB |
| non-JSON | 0 | 0 | 0 |
| 阶段收敛 | 靠 max_iterations | 混合（部分质量/部分超时） | **4/4 全部质量收敛** |
| artifact_type 错误 | 未检测 | 未检测 | 2 次拦截并修正 |
| 论文产出 | ~6KB | 22KB 9 sections | 11 sections |

**关键改进**：Session 12 是首次 4 个阶段全部通过 Critic 质量评判收敛（无 `max_iterations` 兜底），验证了 EMA + per-phase 阈值 + artifact coverage 三重收敛机制的有效性。

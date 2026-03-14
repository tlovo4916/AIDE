# AIDE Multi-Agent System 架构批判与改进路线

> 审查日期：2026-03-14
> 审查范围：`backend/orchestrator/`、`backend/agents/`、`backend/blackboard/`、`backend/types.py`

---

## 一、核心批判

### 1. 伪 Multi-Agent：本质是带角色扮演的单线程 for 循环

`planner.py:18-55` 的 `_PHASE_SEQUENCES` 硬编码了每个阶段的 agent 调用顺序。Planner 构造函数接收 `llm_router` 但**从未使用**（注释原文："llm_router kept for interface compatibility but not used"）。

系统运行逻辑等价于：
```python
for phase in [EXPLORE, HYPOTHESIZE, EVIDENCE, COMPOSE]:
    for agent in fixed_sequence[phase]:  # 写死的
        context = serialize_entire_blackboard()
        output = llm.generate(agent.prompt_template, context)
        write_to_filesystem(output)
```

**不存在的东西：**
- Agent 之间的动态协商、辩论、分工
- Agent 主动请求另一个 Agent 协作（"Scientist 发现线索 → 主动召唤 Librarian 验证"）
- 基于 board 状态的自适应调度

**对比标杆：** AutoGen 的 GroupChat 允许 agent 动态发言；CrewAI 支持 task delegation；MetaGPT 有 SOP 驱动但允许角色间消息传递。AIDE 的 agent 互相不知道对方的存在，只看到一个序列化的全局 context 字符串。

**改进方向：**
- **短期**：让 Planner 用 LLM 根据 board 状态动态选择下一个 agent 和任务描述，而非固定轮转。`_PHASE_SEQUENCES` 降级为 fallback
- **中期**：引入 agent 间的 request-response 协议——agent 输出中可以包含 `REQUEST_COLLABORATION` action，指定目标 agent 和具体问题，engine 立即调度目标 agent 响应
- **长期**：实现 reactive blackboard，agent 注册"兴趣模式"（如 Scientist 关注新的 `evidence_findings`），board 变更时自动激活匹配的 agent

---

### 2. Blackboard 有名无实：只是一个 JSON 文件柜

经典 Blackboard 架构（Hearsay-II, 1977）的三要素：
1. **共享数据空间** — 有
2. **Knowledge Source 的激活条件** — **没有**
3. **Focus of Attention 控制** — **没有**

AIDE 的 Blackboard 退化为一个文件系统 CRUD 层。`board.py` 的 750 行代码中，80% 是文件读写，没有任何数据驱动的触发逻辑。

**性能问题：** `get_state_summary()` 每次调用都遍历所有 `ArtifactType` 的所有 artifact 目录（`board.py:360-376`），逐文件读 JSON。14 轮迭代后 artifacts 堆积，I/O 成本线性增长。没有内存缓存、没有索引、没有增量更新。

**改进方向：**
- **短期**：在 `Blackboard` 中加内存缓存（`_artifact_cache: dict`），写入时更新缓存，读取时优先走缓存。`get_state_summary()` 使用增量构建而非全量遍历
- **中期**：实现 KS 激活条件——每个 agent 声明自己关注的 artifact types，`apply_action()` 写入新 artifact 后检查是否有 agent 应被唤醒，返回激活建议给 engine
- **长期**：将 board 从文件系统迁移到内存数据结构 + WAL（Write-Ahead Log），文件系统仅作持久化备份

---

### 3. Agent 交互 = 给 LLM 塞一个巨大字符串

`engine.py:402`：每个 agent 执行前，调用 `_build_state_summary(board)` 将**整个 blackboard** 序列化为字符串注入 prompt。

**问题链：**
1. **Context 膨胀无法根治**：L0/L1/L2 三级 + 30K token 预算只是 workaround。Agent 需要的是**选择性注意力**——Scientist 不需要看 Writer 的 draft，Critic 不需要看 Librarian 的原始检索结果
2. **信息损失不可逆**：L2→L1→L0 的 LLM 摘要如果遗漏关键信息，下游 agent 永远看不到原始数据。没有"按需展开"机制
3. **Agent 无法提问**：Writer 想了解 Scientist 某个假设的细节？不行，只能看到被截断到 500 字符的摘要
4. **重复传输**：每轮迭代重新序列化整个 board 的未变更部分，浪费 token

**改进方向：**
- **短期**：按 agent role 定制 context——每个 agent 只看到自己的 `dependency_artifact_types` 对应的 artifacts，而非全量 board state
- **中期**：实现 artifact 引用机制——agent 输出中可以引用 `@artifact_id`，engine 按需注入被引用 artifact 的完整内容（类似 RAG 的 retrieval）
- **长期**：用 embedding 相似度计算 task description 与各 artifact 的相关性，动态选择最相关的 N 个 artifact 注入 context

---

### 4. Challenge 机制：设计精巧，实现报废

Challenge 是整个系统最有潜力的特性——允许 Critic 对其他 agent 的产出提出结构化质疑。但当前实现让这个机制完全失效：

1. **自动 dismiss 太激进**：`_CHALLENGE_AUTO_DISMISS_AFTER = 2`（`engine.py:33`），challenge 存活不超过 2 轮就被丢弃。这意味着 challenge 从来不会产生任何修复行为
2. **无响应路由**：没有任何逻辑让被 challenge 的 agent 看到 challenge 并回应。Challenge 写入文件系统后被所有 agent 平等地淹没在 context 中
3. **质量检测靠关键词**：`has_contradictory_evidence()` 就是 `"contradict" in ch.argument.lower()`（`board.py:551`），`has_logic_gaps()` 就是检查 `"gap"` 或 `"logic"`。中文 challenge 内容直接失效
4. **Challenge 不影响收敛逻辑**：唯一的作用是 `open_challenges > 0` 延迟收敛。2 轮后 auto-dismiss，延迟效果微乎其微

**改进方向：**
- **短期**：Challenge 指定 `target_agent`，engine 在下一轮**优先调度**该 agent 并将 challenge 内容注入其 prompt 的醒目位置。被 challenge 的 agent 必须在 response 中包含 `RESOLVE_CHALLENGE` action
- **短期**：将 `_CHALLENGE_AUTO_DISMISS_AFTER` 提高到 4-6，给 agent 足够的响应窗口
- **中期**：challenge 不只是文本——包含具体的修改建议和期望的验证标准。Critic 复查修改结果后决定是否 resolve
- **长期**：实现 multi-round debate——被 challenge 的 agent 回应后，原 challenger 评估回应质量，可以 escalate 或 resolve

---

### 5. 收敛检测：Critic 打分当圣旨

`convergence.py:83-102` 的收敛逻辑：
```python
no_open = signals.open_challenges == 0
score_ok = signals.critic_score >= self._min_critic_score
return no_open and score_ok
```

**问题：**
1. **Critic 是唯一裁判**：一个 LLM 角色扮演的打分，一致性和可靠性完全不可控。同样的内容换个措辞，分数可能差 2-3 分
2. **没有跨阶段追溯**：EVIDENCE 阶段打了 8 分收敛了，COMPOSE 阶段发现证据不充分——没有机制回退 EVIDENCE 的评分
3. **`max_iterations` 才是真正的终止条件**：从实测数据看，EXPLORE 阶段 4 轮时 critic=7.0 刚好触发收敛，但如果 critic 给了 6.5，就会等到 `max_iterations` 超时。质量控制实际上被 max_iterations 兜底了
4. **分数阈值一刀切**：`convergence_min_critic_score` 对所有阶段相同，但 EXPLORE（文献调研）和 COMPOSE（论文撰写）的质量标准显然不同

**改进方向：**
- **短期**：per-phase 差异化阈值——EXPLORE 可以低一些（6.0），COMPOSE 和 EVIDENCE 应该更高（7.5+）
- **短期**：多次 critic 评审取平均分或中位数，减少单次评分的随机性
- **中期**：引入第二个评估维度——不只是 critic 打分，还包括 artifact 覆盖度（是否所有必需的 artifact type 都已产出且非空）
- **长期**：用 LLM-as-Judge 的 pairwise comparison 替代绝对打分——对比当前产出和上一轮产出，判断是否有实质性改进

---

### 6. 偏题检测：玩具级别

`engine.py:598-630` 的 `_check_on_topic()`：
```python
topic_words = set(self._research_topic.lower().split())
topic_words = {w for w in topic_words if len(w) > 2}
matched = sum(1 for w in topic_words if w in summary_lower)
match_ratio = matched / len(topic_words)
```

**致命缺陷：**
1. **中文完全失效**：`"大语言模型推理优化".split()` → `["大语言模型推理优化"]`，只有一个词，匹配率要么 0% 要么 100%
2. **语义盲**：课题是 "LLM inference optimization"，summary 在讲 "transformer attention mechanism acceleration"——高度相关但关键词不匹配，会误报
3. **反过来也有问题**：summary 出现了 "LLM" 和 "optimization" 但在讲 "LLM training optimization"（不是 inference），不会报警
4. **20% 阈值太低**：5 个关键词只需匹配 1 个就不报警

**改进方向：**
- **短期**：用 `jieba` 或类似分词器处理中文课题；提高阈值到 40%
- **中期**：用 embedding 余弦相似度替代关键词匹配——将 research_topic 和 state_summary 分别编码，相似度低于阈值时报警
- **中期**：偏题检测不只是报警——触发 Director agent 重新审视研究方向，或直接将偏题信息注入下一个 agent 的 prompt

---

### 7. 并行 Lane：隔离太彻底，Synthesis 太粗暴

`factory.py:439-499` 的 multi-lane 设计意图是好的（ensemble/debate），但：

1. **Lane 完全隔离**：N 条 lane 各跑各的，中间没有交叉验证。Lane 0 可能已经证伪了某个假设，Lane 1 还在基于同一假设继续研究
2. **Synthesis 信息损失严重**：lane artifacts 只取 L2 前 3000 字符（`factory.py:283`），大量细节被截断
3. **Synthesis 是全新 engine**（`factory.py:316`）：创建全新 board、全新 agent 集合，lane context 通过 meta JSON 字符串注入。Synthesizer 看到的是文本 dump，不是结构化数据
4. **没有 lane 多样性保证**：所有 lane 使用相同的 prompt 和 planner，可能产生高度相似的研究路径

**改进方向：**
- **短期**：给不同 lane 注入不同的研究角度偏好（在 task description 中加入 "focus on X methodology" / "prioritize Y perspective"）
- **中期**：lane 中间检查点——每个阶段结束时，lane 之间交换摘要，让各 lane 的 Director 了解其他 lane 的方向，避免重复或遗漏
- **中期**：Synthesis 阶段的 context 注入改为结构化数据——按 artifact type 分组，保留完整的 hypothesis/evidence 对应关系，而非纯文本 dump
- **长期**：实现 adversarial lanes——一条 lane 做 pro（寻找支持证据），一条做 contra（寻找反驳证据），synthesis 做辩证综合

---

### 8. Agent 输出解析：永远在和 LLM 的格式问题搏斗

`base.py:167-221` 的 `_parse_response()` 是整个系统最脆弱的环节——从 `safe_json_loads()` 的 markdown fence 剥离，到 `_fuzzy_match_action_type()` 的模糊匹配，到 target 自动填充，到 Claude 模型的特殊 prompt 后缀（`base.py:104-112`）。

**这暴露了根本问题：让 LLM 自由生成 JSON 是反模式。**

**改进方向：**
- **短期**：使用 LLM provider 的 structured output / JSON mode（DeepSeek 支持 `response_format={"type": "json_object"}`，Anthropic 支持 tool use 强制 JSON schema）
- **中期**：将 agent 输出格式从自由 JSON 改为 function calling / tool use——定义 `write_artifact`, `post_message`, `raise_challenge` 等 tool schema，LLM 通过 tool call 返回结构化数据
- **长期**：引入 output validator 层——agent 输出后不直接写入 board，先经过 schema 验证 + 语义检查（内容是否与 task 相关），不合格则 retry 并将错误信息反馈给 agent

---

### 9. 没有记忆和学习机制

整个系统是无状态的——每次研究从零开始。跑完一个课题积累的经验（哪些检索策略有效、哪些假设模式容易得高分、哪些写作结构 critic 偏好）全部丢失。

**改进方向：**
- **短期**：在 project 完成时，让 Director 生成一份 "lessons learned" artifact，存入全局知识库
- **中期**：实现 agent-level 记忆——每个 agent 维护一个 few-shot example 池，从历史成功案例中检索相关的 example 注入 prompt
- **长期**：用 RLHF 或 DPO 对 critic 的评分进行校准，让 critic 的打分标准从人类反馈中学习

---

### 10. WriteBackGuard 的定位尴尬

`WriteBackGuard` 的职责是"检查 agent 输出是否遗漏了应该写回 board 的内容"。但：
- 它用另一个 LLM 调用来检查 LLM 的输出——可靠性存疑
- 输入被截断到 3000 字符，可能看不到完整 context
- CLAUDE.md 直接写了 "WriteBackGuard 效果待验证"

**改进方向：**
- **短期**：评估 WriteBackGuard 的实际 ROI——统计它产生的 extra actions 中有多少被 dedup 过滤、有多少实际有价值。如果价值不高，直接移除以节省 LLM 调用成本
- **中期**：如果保留，改为规则驱动——检查 agent 是否产出了其 `primary_artifact_types` 要求的 artifact，缺失则发出警告或重试，不需要 LLM

---

## 二、改进优先级排序

| 优先级 | 改进项 | 预期收益 | 工作量 |
|--------|--------|----------|--------|
| P0 | Planner 动态调度（LLM-based） | 从假 MAS 变成半真 MAS | 中 |
| P0 | Agent context 按 role 定制 | 减少 token 浪费 + 提高 agent 输出质量 | 小 |
| P0 | 使用 structured output / tool use | 消灭 JSON 解析问题 | 中 |
| P1 | Challenge 响应路由 | 让 challenge 机制真正产生修复行为 | 中 |
| P1 | 偏题检测改 embedding | 支持中文 + 语义级检测 | 小 |
| P1 | 收敛检测多维度化 | 减少对单一 critic 分数的依赖 | 中 |
| P1 | Blackboard 内存缓存 | 减少文件 I/O，提高迭代速度 | 小 |
| P2 | Lane 间中间交换 | 避免 lane 重复研究 | 大 |
| P2 | Agent-level 记忆 | 跨项目知识积累 | 大 |
| P2 | Reactive Blackboard 触发机制 | 实现真正的 Blackboard 架构 | 大 |
| P3 | WriteBackGuard 评估/重构 | 节省 LLM 调用成本 | 小 |
| P3 | Adversarial lanes | 提高研究的辩证深度 | 大 |

---

## 三、一句话总结

**AIDE 当前不是 multi-agent system，而是 multi-role LLM pipeline with shared filesystem state。** Agent 之间没有交互、没有协商、没有动态分工——只有一个固定轮转表驱动的 for 循环，每次把整个文件系统的 JSON dump 塞给一个带不同 system prompt 的 LLM。要成为真正的 MAS，需要从 Planner 动态调度和 Agent 间通信协议两个方向同时突破。

# AIDE Multi-Agent System 架构审计

> 首次审计：2026-03-14 | 二次审计：2026-03-15 | 三次审计：2026-03-16

---

## 一、核心架构批判（10 项）

### 1. 伪 Multi-Agent：本质是带角色扮演的单线程 for 循环

系统运行逻辑等价于：
```python
for phase in [EXPLORE, HYPOTHESIZE, EVIDENCE, COMPOSE]:
    for agent in fixed_sequence[phase]:
        output = llm.generate(agent.prompt_template, serialize_entire_blackboard())
        write_to_filesystem(output)
```

**不存在的东西：** Agent 间动态协商/辩论/分工、Agent 主动请求协作、基于 board 状态的自适应调度。

**改进方向：**
- 短期：Planner 用 LLM 动态选择 agent（`_PHASE_SEQUENCES` 降级为 fallback）✅ 已修复
- 中期：Agent 间 request-response 协议（`REQUEST_COLLABORATION` action）❌ 未实现
- 长期：Reactive blackboard（agent 注册兴趣模式，board 变更时自动激活）❌ 未实现

### 2. Blackboard 有名无实：只是一个 JSON 文件柜

经典 Blackboard 三要素：共享数据空间（有）、KS 激活条件（**无**）、Focus of Attention（**无**）。Board 退化为文件系统 CRUD 层。

**改进方向：**
- 短期：内存缓存（write-through） ✅ 已修复（meta + version + L0 缓存）
- 中期：KS 激活条件 ❌ 未实现
- 长期：内存数据结构 + WAL ❌ 未实现

### 3. Agent 交互 = 给 LLM 塞一个巨大字符串

每轮把整个 blackboard 序列化注入 prompt。L0/L1/L2 三级摘要只是 workaround，不解决选择性注意力问题。

**改进方向：**
- 短期：按 agent role 定制 context ✅ 已修复（ArtifactType 级别过滤）
- 中期：Artifact 引用机制（`@artifact_id` 按需展开）❌ 未实现
- 长期：Embedding 相关性动态选择 ❌ 未实现

### 4. Challenge 机制：设计精巧，闭环缺失

Challenge 允许 Critic 对产出提出结构化质疑，但执行链不完整。

**改进方向：**
- 短期：Challenge 指定 target_agent + 注入 prompt + auto-dismiss 提高到 5 轮 ✅ 已修复
- 短期：中文关键词检测 ✅ 已修复
- ⚠️ **Post-check 仅打日志，不触发重试/升级** — Agent 可无后果地忽略 challenge
- 中期：Challenge 含修改建议和验证标准 ❌ 未实现

### 5. 收敛检测：Critic 打分当圣旨

单一 LLM 角色扮演的打分决定阶段收敛，一致性不可控。

**改进方向：**
- 短期：Per-phase 差异化阈值 + EMA 平滑 + Artifact 覆盖度检查 ✅ 已修复
- ⚠️ **EMA 无异常值防护** — `score` 未 clip 到 [0, 10]，LLM 输出极端值会破坏 EMA
- 长期：LLM-as-Judge pairwise comparison ❌ 未实现

### 6. 偏题检测

从纯关键词匹配进化到三层 fallback（embedding → jieba → keyword），偏题信息已注入 agent task。

**改进方向：**
- 短期：三层 fallback + 注入 agent prompt ✅ 已修复
- ⚠️ **`_topic_drift_detected` 全局 flag 无 per-iteration 重置** — 异常跳过时 stale flag 导致错误 warning

### 7. 并行 Lane：隔离太彻底，Synthesis 太粗暴

Lane 完全隔离无交叉验证，Synthesis 通过文本 dump 注入。

**改进方向：**
- 短期：Lane 视角分化 + 异步 I/O + 截断提升到 6000 字符 ✅ 已修复
- 中期：Lane 间中间交换 / 结构化 synthesis context ❌ 未实现
- 长期：Adversarial lanes ❌ 未实现

### 8. Agent 输出解析：永远在和 LLM 格式搏斗

让 LLM 自由生成 JSON 是反模式。`json_mode` 只是 workaround，`_fuzzy_match_action_type()` 等防御代码仍全部存在。

**改进方向：**
- 短期：json_mode ✅ 部分修复
- 中期：Function calling / tool use ❌ 未实现
- 长期：Output validator 层 + retry ❌ 未实现

### 9. 没有记忆和学习机制

项目完成后生成 lessons learned 存入全局知识库，但无课题相关性筛选。

**改进方向：**
- 短期：Lessons learned 生成 + 注入 ✅ 已修复
- ⚠️ **最近 5 个项目无条件注入，不做相关性匹配**
- 中期：Agent-level few-shot pool ❌ 未实现

### 10. WriteBackGuard

已从 LLM-based 改为规则驱动（检查 `_ROLE_PRIMARY_TYPES`），轻量有效。Warning-only 但有 convergence artifact coverage 间接兜底。 ✅ 已修复

---

## 二、三次审计汇总表

| 编号 | 问题 | 状态 |
|------|------|------|
| #1 | Planner 动态调度 + 历史记忆 | ✅ |
| #2 | Blackboard 缓存（meta/version/L0） | ✅ |
| #3 | Agent context 按 role 定制 | ✅（ArtifactType 级别） |
| #4 | Challenge 路由 + 中文关键词 + post-check | ⚠️ post-check 仅日志 |
| #5 | 收敛检测（per-phase 阈值 + EMA + coverage） | ✅ |
| #6 | 偏题检测（三层 fallback + agent 注入） | ✅ |
| #7 | 并行 Lane（视角分化 + async I/O + 6000 字符） | ✅ |
| #8 | Structured output (json_mode) | ⚠️ 部分，未用 tool use |
| #9 | Lessons learned | ✅（无相关性筛选） |
| #10 | WriteBackGuard 规则驱动 | ✅ |
| N1 | Planner prompt 注入 | ✅ 已缓解（`<context>` 标签） |
| N2 | Model resolution chain | ✅ |
| N3 | Critic EMA 替代算术平均 | ✅ |
| N4 | Lane artifacts async I/O | ✅ |

---

## 三、当前待修复项

### 立即修复（5 分钟）

**T1. EMA 异常值防护：** `board.py` `set_phase_critic_score()` 入口加 `score = max(0.0, min(10.0, score))`。LLM 输出极端值会破坏 EMA。

**T3. `_topic_drift_detected` 每轮重置：** `engine.py` 主循环开头加 `self._topic_drift_detected = False`。防止 `_check_on_topic()` 异常跳过时 stale flag 导致错误 warning。

### 短期修复（P1）

**T2. Challenge post-check 行为闭环：** `engine.py:509-518` post-check 失败时注入 escalation 信息到下一轮 task description，形成压力递增，而非仅打 warning。

**R8. Structured output → function calling：** 用 provider 的 tool use schema 替代自由 JSON 生成，消灭 `_fuzzy_match_action_type()` 等防御性代码。

### 中期目标

| 改进项 | 预计工作量 |
|--------|-----------|
| Agent context 按单 artifact 级别过滤（embedding 相关性） | 1-2 天 |
| Lessons learned 按课题相关性筛选 | 半天 |
| Lane synthesis 结构化 context | 1 天 |
| Agent 间 request-response 协议 | 3-5 天 |
| Reactive Blackboard（KS 激活条件） | 3-5 天 |

---

## 四、总结

**系统从 "multi-role LLM pipeline" 进化到 "半自主 multi-agent system"。** Planner 动态调度、Challenge 路由、Context 定制、偏题三层检测、EMA 收敛——短期止血全部到位。

**架构天花板已从 "能不能跑" 变为 "agent 间能不能真正协作"。** 下一阶段突破点：function calling（消灭 JSON 解析）+ agent 间通信协议（从共享文件系统进化到消息驱动协作）。

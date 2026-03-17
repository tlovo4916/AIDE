## AIDE 代码级缺陷清单

---

### 1. "多智能体"是营销话术，代码里只有一个函数

六个 Agent 的 Python 实现**在代码层面完全等价**：

```python
prompt = template.render(context, task)
response = await llm.generate(prompt)
return parse_json(response)
```

Director、Scientist、Writer、Critic、Synthesizer——除了类名和模板路径不同，**没有一行差异化逻辑**。这不是六个智能体，这是一个 `call_llm()` 函数配了六个 prompt 文件。把它们合并成 `GenericAgent(template_name)` 不会丢失任何功能。"多智能体架构"在代码层面是**零成本抽象的反面**——零收益抽象。

---

### 2. "黑板架构"是文件夹 + JSON dump

学术文献里的 Blackboard Architecture 核心特征是：**知识源之间通过共享数据结构触发响应式协作**。AIDE 的"黑板"是：

```
os.makedirs("artifacts/hypotheses/hyp_001/v1")
json.dump(content, open("l2.json", "w"))
```

没有订阅机制、没有触发器、没有反应式更新。Agent A 写了文件，Agent B 下次被轮到时才**被动地**读取全量状态。这是一个**文件系统 CRUD store**，硬贴了"黑板"的标签。真正的黑板系统应该有 Agent 注册感兴趣的 artifact 类型并在变更时被唤醒——这里完全没有。

---

### 3. "规划器"是 for 循环取模

```python
EXPLORE: [LIBRARIAN, DIRECTOR, LIBRARIAN, CRITIC]
agent = sequence[(iteration - 1) % len(sequence)]
```

这不是规划，这是数组下标循环。LLM-based planner 是装饰品——失败了直接 fallback 到上面的硬编码序列，而且代码里没有任何机制评估 LLM planner 的选择是否比固定序列更好。**你甚至无法证明打开 LLM planner 比关掉它效果更好，因为没有 A/B 对比，没有 metric，没有 evaluation。**

更致命的是：planner 不看 agent 产出的内容，不看 artifact 质量，不看研究进展。它看的是 `iteration % len(sequence)`。如果 Scientist 产出了垃圾，下一轮照样轮到 Director，Director 照样基于垃圾 context 继续生成。**没有任何纠错反馈回路。**

---

### 4. 收敛检测是自我欺骗

```python
converged = (open_challenges == 0) and (critic_score >= 7.0) and (all_artifacts_exist)
```

三个问题：

- **critic_score 来自 LLM 自评**。让生成内容的模型给自己打分，这在评估方法论上就是无效的。LLM 倾向于给高分（讨好偏差）。（**勘误**：实测数据显示 EXPLORE 阶段跑了 4 轮才收敛、critic=7.0，并非"第一轮给 8 分立刻收敛"——EMA 和 stable_rounds=3 确实起到了缓冲。但这不改变核心结论：LLM 自评在方法论上是无效的，缓冲的是噪声，不是有效信号。）
- **"all_artifacts_exist" 只检查存在性，不检查质量**。Scientist 写了一句 `"hypothesis: TBD"` 也算 artifact 存在。
- **EMA 平滑 (alpha=0.4) 解决的是错误问题**。问题不是"分数波动大"，问题是"分数本身就没有意义"。你在对噪声做移动平均。

这意味着：**系统没有任何能力判断研究是否真的在进步。** 它只是在数文件和读 LLM 吐出的数字。

---

### 5. 6 层 research_topic 注入链 = 6 次补丁

`factory.py → board.py → planner.py → base.py → .j2 → engine.py`

在六个不同的位置、用六种不同的方式注入同一个字符串。这不是"深度集成"，这是**设计时没想清楚数据流，事后在每个出口打补丁**。一个设计良好的系统只需在 context 构建时统一注入一次。六层注入意味着：改一个地方漏另一个地方会导致 topic drift——而这正是当初的 bug 来源。**修复方式本身就证明了原始架构的失败。**

---

### 6. "Topic Drift 检测"是字符串匹配

```python
keywords = research_topic.split()
match_ratio = sum(1 for kw in keywords if kw in artifact_text) / len(keywords)
if match_ratio < 0.2: warn()
```

三层 fallback：embedding cosine → jieba 分词 → 空格 split。听起来层次分明，但：

- embedding 需要 OpenAI key，大多数用户没配，直接跳过
- jieba 分词后还是做关键词匹配，不是语义匹配
- 最终 fallback 是 `str.split()` + `in` 操作符

**一个研究"量子计算在药物发现中的应用"的项目，如果 agent 输出了"quantum computing for drug discovery"（英文），而 topic 是中文，这个检测直接失效。** 跨语言场景下整个 drift 检测形同虚设。

---

### 7. Artifact 去重只防复读机，不防换皮

```python
new_words = set(text.lower().split())
existing_words = set(existing.lower().split())
jaccard = len(intersection) / len(union)
if jaccard >= 0.6: skip()
```

Jaccard 词集交集。**LLM 重新组织语句、换几个同义词，相似度立刻降到 0.3 以下。** 这个去重只能防止 LLM 原封不动复读——而 LLM 原封不动复读的概率本来就极低。它防的是一个几乎不存在的问题，对真正的语义重复毫无作用。

---

### 8. Librarian 是唯一有真逻辑的 Agent，但也是最脆弱的

462 行代码，真实的网络检索 + BM25 + ChromaDB。但：

- **S2 API 频率限制**：靠内存变量 `_s2_cooldown_until` 追踪，容器重启后丢失，重启后会立刻被 rate limit
- **300s Agent 超时 vs Librarian 理论 240s 执行时间**：只差 60 秒 buffer，S2 多重试几次就超时
- **查询去重用 normalized string cache**：`"quantum computing" == "quantum  computing"` 但 `"quantum computing" != "computing quantum"`——顺序不同就重复查询
- **ChromaDB embedding 依赖 OpenAI key**：没配就静默跳过，用户根本不知道向量检索没生效

---

### 9. 测试全是 mock，没有一个跑真实 LLM

876 行测试，全部 mock 掉了 LLM 调用。这意味着：

- **从未验证 prompt 模板是否产出可解析的 JSON**
- **从未验证 agent 序列是否真的能推进研究**
- **从未验证收敛检测在真实 critic 输出下是否合理**
- **从未验证去重在真实 agent 输出下的准确率**

你在测试的是"如果 LLM 返回完美 JSON，系统能处理"——但系统存在的全部困难就在于 **LLM 不返回完美 JSON**。这就是为什么需要 `_fuzzy_match_action_type()`、`safe_json_loads()`、三层 artifact_type 防御——而这些容错逻辑的有效性**从未被真实输入验证过**。

（**勘误**：Session 10 跑过全链路 E2E 测试——真实 LLM 调用，14 轮完整研究，创建项目→arXiv 检索→Artifact 产出→Token 计费→前端渲染。所以并非"从未跑过真实 LLM"。但问题在于：这些 E2E 测试不在 CI 里，不可重复，没有断言，只是手动观察了一次"看起来能跑"。这比"从未测试"稍好，但也好不了多少——人工跑一次不等于验证体系。）

---

### 10. 没有任何 evaluation 证明系统有效

整个项目**没有一个 benchmark、没有一组 evaluation metric、没有一次对比实验**。

- 6 agent 螺旋迭代 vs 1 个大 prompt 一次生成，哪个好？**不知道。**
- 开 LLM planner vs 关 LLM planner，哪个好？**不知道。**
- 3 轮迭代 vs 20 轮迭代，边际收益？**不知道。**
- 多 lane 并行 + synthesize vs 单 lane，质量差异？**不知道。**

一个声称能"做研究"的系统，自己对自己的效果没有做过任何研究。**这是整个项目最根本的缺陷：你不知道它到底有没有用，而且代码里没有任何机制能帮你回答这个问题。**

---

### 11. 架构层面的根本矛盾

项目用了 Protocol-based 依赖注入、factory 模式、adapter 模式、策略模式——这些都是**管理复杂业务逻辑**的模式。但实际业务逻辑只有一个：**拼 prompt → 调 LLM → 解析 JSON → 写文件**。

结果就是：用管理 10 万行代码的架构去组织 1300 行核心逻辑。`BoardAdapter` 可能是死代码，`BacktrackManager` 在真实运行中几乎不触发，`WriteBackGuard` 的效果"unverified"（文档原话）。**代码库里充满了为未来预留的扩展点，但这些扩展点从未被使用。**

这是典型的**架构宇航员综合征（Architecture Astronaut Syndrome）**：在解决一个简单问题之前，先构建一个能解决所有问题的框架。

---

### 12. Settings 持久化方案是 hack

```python
json.dump(settings, open("/app/workspace/settings_overrides.json", "w"))
```

不用数据库（已经有 PostgreSQL），不用 Redis，用 Docker volume 上的裸 JSON 文件。原因是"容器内没有 .env 文件可写"——这是对容器化的理解不足导致的 workaround。**settings 应该一开始就在数据库里，而不是先存 .env，发现容器里不能写，再 patch 一个 JSON 文件方案。**

---

### 13. Challenge 系统是半成品

文档自己承认："full raise→respond→resolve flow untested"。代码里 auto-dismiss after 5 iterations 的逻辑存在，但这意味着：**如果 agent 提出了一个有效质疑，系统等 5 轮无人响应后自动忽略它。** 这不是"容错"，这是"把异议扔进垃圾桶"。

---

### 14. 前端复杂度与后端不成比例

前端 14 种 WS 事件、5 个功能区、pipeline 可视化、lane 切换、PDF 导出——这些 UI 功能暗示后端有丰富的交互逻辑。但后端实际只是：轮流调 LLM → 写文件 → 数数 → 推进 phase。**前端的复杂度远超后端能提供的信息密度。** 大量 UI 元素在展示的是同一个 LLM 调用链的不同视角。

---

### 总结：核心问题

这个项目的根本缺陷不在任何单个 bug，而在于**它用工程复杂度替代了算法深度**。

多 agent 不等于多 prompt。黑板架构不等于文件夹。螺旋迭代不等于 for 循环。收敛检测不等于数字比较。**当你把这些概念的学术含义剥掉，剩下的就是：一个带有精致 UI 的 LLM prompt 轮转调用器，它不知道自己产出的研究是好是坏。**

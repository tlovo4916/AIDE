## AIDE 遗留问题清单

> 更新日期：2026-03-18

---

### 未修复问题

| ID | 严重度 | 位置 | 描述 |
|----|--------|------|------|
| D03 | P1 | `evaluation/convergence.py:20-42` | 信息增益用 Jaccard 词集合计算，非语义级。换措辞表达同一观点会被误判为"新信息"。需改为 embedding cosine distance。 |
| D04 | P1 | `evaluation/convergence.py:86-94` | 环路检测用 Jaccard 词集合相似度。语义相同但措辞不同的输出不会被检测为循环。需改为 embedding。 |
| TD-15 | P2 | 系统级 | 论文理解仅处理摘要和元数据，无法理解全文方法论、实验表格、公式、图表。属 LLM 技术限制。 |
| D12 | P3 | `evaluation/evaluator.py:223-257` | 多维评估串行 for 循环（6 维 = 6 次串行 LLM 调用）。应改为 `asyncio.gather` 并行。 |
| D14 | P3 | `benchmarks/scorer.py:53` | F1 阈值硬编码 `0.5`，无配置项，无 baseline 对比说明。 |
| F03 | P3 | `api/checkpoints.py`, `api/papers.py` | `list_projects` 已有分页；checkpoints 和 papers 的 list 端点仍无 skip/limit。 |
| P07 | P3 | `agents/director.py:70-88`, `agents/synthesizer.py:92-120` | Director 和 Synthesizer 的 `post_execute()` 检测到问题后仅 log，不创建 InfoRequest 或注入 action。（Scientist/Writer/Critic 已修复） |
| V06 | P3 | `frontend/.../EvaluationSection.tsx` ClaimsPanel | Claims 面板为 filterable list，架构要求 knowledge graph 可视化。架构标注 Optional。 |
| TD-11 | P3 | `frontend/.../formatters.ts` | `getArtifactDisplay()` 10 层 if/else 猜测数据结构，无 schema 验证。需 artifact schema map。 |
| TD-12 | P3 | `frontend/.../BlackboardSection.tsx` | 残留少量 `as unknown as` 类型转换。主要的已修复，此处为剩余项。 |

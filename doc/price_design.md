# AIDE 模型定价与预设方案设计

> 最后更新：2026-03-13
> 基于 2026 年 2-3 月全球主要 LLM 厂商最新模型的全面调研

---

## 一、全厂商模型定价总表

所有价格单位：**USD per 1M tokens**（括号内为人民币参考，汇率 1 USD = 7.24 RMB）。

### 超值档（Output < $0.50/M）

| 模型 | 厂商 | Input $/M | Output $/M | Context | 速度 | 核心优势 |
|---|---|---|---|---|---|---|
| `deepseek-chat` | DeepSeek 直连 | $0.28 (2元) | $0.41 (3元) | 128K | ~100t/s | 最便宜的高质量模型 |
| `deepseek-reasoner` | DeepSeek 直连 | $0.28 (2元) | $0.41 (3元) | 128K | ~50t/s | 同底座 V3.2，思考模式 |
| `stepfun/step-3.5-flash` | 阶跃星辰 | $0.10 | $0.30 | 256K | **147t/s** | AIME 97.3% #1，有免费档 |
| `bytedance-seed/seed-1.6-flash` | 字节跳动 | $0.075 | $0.30 | 262K | ~100t/s | 超低价 |
| `openai/gpt-5-nano` | OpenAI | $0.05 | $0.40 | 400K | ~200t/s | 最便宜的 OpenAI |
| `z-ai/glm-4.7-flash` | 智谱 | $0.06 | $0.40 | 203K | ~80t/s | 免费版可用 |
| `x-ai/grok-4.1-fast` | xAI | $0.20 | $0.50 | **2M** | 127t/s | 最长 context，近 frontier |
| `xiaomi/mimo-v2-flash` | 小米 | $0.09 | $0.29 | 262K | - | 超低价新秀 |

### 高性价比档（Output $0.50-$2.50/M）

| 模型 | 厂商 | Input $/M | Output $/M | Context | 速度 | 核心优势 |
|---|---|---|---|---|---|---|
| `meta-llama/llama-4-maverick` | Meta | $0.15 | $0.60 | 1M | ~100t/s | 开源 1M context |
| `minimax/minimax-m2.5` | MiniMax | $0.27 | $0.95 | 1M | 100t/s | **SWE-bench 80.2% #1**，131K 最大输出 |
| `deepseek/deepseek-v3.2-speciale` | DeepSeek (仅OR) | $0.40 | $1.20 | 164K | ~80t/s | 推理超 GPT-5，IMO 金牌 |
| `qwen/qwen3.5-flash-02-23` | 阿里 | $0.10 | $0.40 | 1M | 极快 | Qwen 3.5 经济版 |
| `qwen/qwen3.5-plus-02-15` | 阿里 | $0.26 | $1.56 | **1M** | **~150t/s** | 指令遵循 #1，201 语言，多模态 |
| `moonshotai/kimi-k2.5` | 月之暗面 | $0.45 | $2.20 | 262K | ~70t/s | HumanEval 99% #1，1T MoE |
| `z-ai/glm-5` | 智谱 | $0.72 | $2.30 | 203K | 74t/s | **Chatbot Arena #1**，最强中文 |
| `qwen/qwen3.5-397b-a17b` | 阿里 | $0.39 | $2.34 | 262K | ~45t/s | 开源 Qwen 顶配 |

### Frontier 档（Output > $5/M）

| 模型 | 厂商 | Input $/M | Output $/M | Context | 核心优势 |
|---|---|---|---|---|---|
| `anthropic/claude-opus-4-6` | Anthropic | $5.00 | $25.00 | 200K | 写作+推理综合最强 |
| `anthropic/claude-sonnet-4-6` | Anthropic | $3.00 | $15.00 | 200K | 性价比 frontier |
| `openai/gpt-5.4` | OpenAI | $2.50 | $15.00 | 1M | Intelligence Index 57 |
| `google/gemini-3.1-pro` | Google | $2.00 | $12.00 | 1M | GPQA 94.3% #1 |
| `x-ai/grok-4` | xAI | $3.00 | $15.00 | 256K | Arena 92.7% |
| `openai/gpt-5.4-pro` | OpenAI | $30.00 | $180.00 | 1M | OpenAI 最强 |

---

## 二、DeepSeek 官网直连定价（重要）

> 来源：https://api-docs.deepseek.com/zh-cn/quick_start/pricing

DeepSeek 直连走官网 API（`https://api.deepseek.com`），**不经过 OpenRouter**，价格以人民币计算。

| 模型 | 底层 | Input（缓存未命中） | Input（缓存命中） | Output | Context |
|---|---|---|---|---|---|
| `deepseek-chat` | V3.2 非思考模式 | **2 元/M** ($0.28) | **0.2 元/M** ($0.028) | **3 元/M** ($0.41) | 128K |
| `deepseek-reasoner` | V3.2 思考模式 | **2 元/M** ($0.28) | **0.2 元/M** ($0.028) | **3 元/M** ($0.41) | 128K |

关键要点：
- 两个模型**价格完全统一**，都是 V3.2 底座
- 缓存命中时 input 降至 **0.2 元/M**（节省 90%）
- `deepseek-v3.2-speciale` **官网不提供**，只能通过 OpenRouter 访问（$0.40/$1.20 per M）

### tracker.py 价格修正记录

| 模型 | tracker.py 旧值 ($/M) | 实际官网 ($/M) | 偏差倍数 |
|---|---|---|---|
| deepseek-chat input | $1.40 | $0.28 | 高估 **5x** |
| deepseek-chat output | $2.80 | $0.41 | 高估 **7x** |
| deepseek-reasoner input | $5.50 | $0.28 | 高估 **20x** |
| deepseek-reasoner output | $21.90 | $0.41 | 高估 **53x** |

---

## 三、Embedding 模型对比

| 模型 | Context | 价格/M tokens | 维度 | 推荐度 |
|---|---|---|---|---|
| `nvidia/llama-nemotron-embed-vl-1b-v2:free` | **131K** | **$0 免费** | 2048 | 省钱首选 |
| `qwen/qwen3-embedding-8b` | 32K | $0.01 | - | 中文最佳 |
| `qwen/qwen3-embedding-4b` | 32K | $0.02 | - | 轻量中文 |
| `openai/text-embedding-3-small` | 8K | $0.02 | 1536 | 成熟稳定（旧默认） |
| `openai/text-embedding-3-large` | 8K | $0.13 | 3072 | 质量最高 |
| `google/gemini-embedding-001` | 20K | $0.15 | 3072 | 最贵 |

> 注意：切换 embedding 模型会改变向量维度，已有 ChromaDB 数据需要重新索引。建议新项目直接用新模型，老项目保持不变。

---

## 四、关键维度冠军

| 维度 | 冠军模型 | 数据 |
|---|---|---|
| **推理能力** | DeepSeek V3.2 Speciale | 超 GPT-5，IMO/ICPC 金牌 |
| **数学竞赛** | Step 3.5 Flash | AIME 97.3% |
| **代码能力** | MiniMax M2.5 | SWE-bench 80.2% |
| **指令遵循** | Qwen 3.5 Plus | IFBench 76.5 |
| **中文质量** | GLM-5 | Chatbot Arena #1 (1451), C-Eval 最高 |
| **最长 Context** | Grok 4.1 Fast | 2,000,000 tokens |
| **最快速度** | Step 3.5 Flash | 147 t/s |
| **最低成本** | DeepSeek V3.2 | 混合 ~$0.30/M |
| **JSON 可靠性** | Qwen 3.5 / GLM-5 | 原生 JSON mode |
| **多语言** | Qwen 3.5 Plus | 201 种语言 |

---

## 五、五档预设方案

### Tier 1: `Free` — 零成本体验

> 适合：初次体验、教学演示、预算为零的探索性研究

| Agent | 模型 | 通道 |
|---|---|---|
| **Director** | `step-3.5-flash:free` | OpenRouter 免费 |
| **Scientist** | `step-3.5-flash:free` | OpenRouter 免费 |
| **Critic** | `step-3.5-flash:free` | OpenRouter 免费 |
| **Librarian** | `step-3.5-flash:free` | OpenRouter 免费 |
| **Writer** | `step-3.5-flash:free` | OpenRouter 免费 |
| **Synthesizer** | `step-3.5-flash:free` | OpenRouter 免费 |
| **Embedding** | `nvidia/llama-nemotron-embed-vl-1b-v2:free` | OpenRouter 免费 |

| 指标 | 值 |
|---|---|
| 单次研究成本 | **0 元** |
| 速率限制 | 20 req/min, 200 req/day |
| 中文质量 | 可用（Step 是中国公司） |
| 推理深度 | 中等 |
| 适用场景 | 试用、教学、非正式探索 |

---

### Tier 2: `Economy` — 极致性价比

> 适合：日常研究、高频使用、个人开发者

| Agent | 模型 | 通道 | 价格 (元/M) |
|---|---|---|---|
| **Director** | `deepseek-reasoner` | 直连官网 | 2 / 3 |
| **Scientist** | `deepseek-reasoner` | 直连官网 | 2 / 3 |
| **Critic** | `deepseek-reasoner` | 直连官网 | 2 / 3 |
| **Librarian** | `deepseek-chat` | 直连官网 | 2 / 3 |
| **Writer** | `deepseek-chat` | 直连官网 | 2 / 3 |
| **Synthesizer** | `deepseek-reasoner` | 直连官网 | 2 / 3 |
| **Embedding** | `nvidia/llama-nemotron-embed-vl-1b-v2:free` | OpenRouter 免费 | 0 |

| 指标 | 值 |
|---|---|
| 单次研究成本 | **~0.3 元 ($0.04)** |
| 速率限制 | 无（直连官网） |
| 中文质量 | 优秀 |
| 推理深度 | 强（V3.2 思考模式） |
| 缓存命中 | 0.2 元/M（省 90%） |
| 适用场景 | 日常研究、批量跑实验 |

---

### Tier 3: `Balanced` — 多厂商混搭最优解

> 适合：正式研究项目、追求质量与成本平衡
> **通用推荐方案**

| Agent | 模型 | 通道 | 价格 (元/M) | 选择理由 |
|---|---|---|---|---|
| **Director** | `deepseek-reasoner` | 直连官网 | 2 / 3 | 战略规划，V3.2 推理足够 |
| **Scientist** | `deepseek-reasoner` | 直连官网 | 2 / 3 | 假设生成，思考模式 |
| **Critic** | `qwen3.5-plus` | OpenRouter | 1.88 / 11.3 | **指令遵循 #1**，JSON 评分更可靠 |
| **Librarian** | `step-3.5-flash:free` | OpenRouter 免费 | **0** | 免费 + 最快 147t/s + 256K context |
| **Writer** | `qwen3.5-plus` | OpenRouter | 1.88 / 11.3 | **最强中文写作** + 1M context |
| **Synthesizer** | `minimax-m2.5` | OpenRouter | 1.95 / 6.88 | 1M context + **131K 最大输出** |
| **Embedding** | `nvidia/llama-nemotron-embed-vl-1b-v2:free` | OpenRouter 免费 | 0 | 免费 + 131K context |

| 指标 | 值 |
|---|---|
| 单次研究成本 | **~0.7-1.5 元 ($0.10-0.20)** |
| 厂商多样性 | 4 家（DeepSeek + Qwen + Step + MiniMax） |
| 中文质量 | 优秀（Writer/Critic 用 Qwen） |
| 推理深度 | 强 |
| 抗风险 | 高（单一厂商挂了其他继续工作） |
| 适用场景 | **日常推荐**，质量与成本最佳平衡 |

---

### Tier 4: `Quality` — 最强中文研究质量

> 适合：严肃学术研究、论文产出、企业报告

| Agent | 模型 | 通道 | 价格 (元/M) | 选择理由 |
|---|---|---|---|---|
| **Director** | `glm-5` | OpenRouter | 5.2 / 16.7 | **Chatbot Arena #1**，最强中文战略规划 |
| **Scientist** | `deepseek-v3.2-speciale` | OpenRouter | 2.9 / 8.7 | **推理超 GPT-5**，IMO 金牌 |
| **Critic** | `glm-5` | OpenRouter | 5.2 / 16.7 | 最强中文评审 + C-Eval 最高 |
| **Librarian** | `qwen3.5-plus` | OpenRouter | 1.88 / 11.3 | **1M context** + 201 语言检索 |
| **Writer** | `qwen3.5-plus` | OpenRouter | 1.88 / 11.3 | 指令遵循 #1 + 最强中文写作 |
| **Synthesizer** | `minimax-m2.5` | OpenRouter | 1.95 / 6.88 | **SWE-bench 80.2% #1** + 131K 输出 |
| **Embedding** | `qwen/qwen3-embedding-8b` | OpenRouter | 0.07 | 中文 embedding 质量最佳 |

| 指标 | 值 |
|---|---|
| 单次研究成本 | **~3-6 元 ($0.40-0.80)** |
| 厂商多样性 | 5 家（GLM + DeepSeek + Qwen + MiniMax） |
| 中文质量 | **顶级**（GLM-5 Arena 冠军 + Qwen 写作） |
| 推理深度 | **顶级**（Speciale 超 GPT-5） |
| 适用场景 | 正式论文、高质量研究报告 |

---

### Tier 5: `Premium` — 全球 Frontier 旗舰

> 适合：不计成本追求极致、对标顶级会议论文

| Agent | 模型 | 通道 | 价格 (元/M) | 选择理由 |
|---|---|---|---|---|
| **Director** | `claude-opus-4-6` | 直连 Anthropic | 36.2 / 181 | **写作+推理综合最强** |
| **Scientist** | `gemini-3.1-pro` | OpenRouter | 14.5 / 86.9 | **GPQA 94.3% #1** 博士级推理 |
| **Critic** | `claude-opus-4-6` | 直连 Anthropic | 36.2 / 181 | 最严谨的质量评审 |
| **Librarian** | `qwen3.5-plus` | OpenRouter | 1.88 / 11.3 | 1M context + 最快 |
| **Writer** | `claude-sonnet-4-6` | 直连 Anthropic | 21.7 / 108.6 | **全球最佳写作质量** |
| **Synthesizer** | `gemini-3.1-pro` | OpenRouter | 14.5 / 86.9 | 1M context + GPQA #1 |
| **Embedding** | `openai/text-embedding-3-large` | OpenRouter | 0.94 | 3072 维，最高精度 |

| 指标 | 值 |
|---|---|
| 单次研究成本 | **~30-60 元 ($4-8)** |
| 中文质量 | 优秀（Claude 中文不弱） |
| 推理深度 | **全球最强** |
| 写作质量 | **全球最强** |
| 适用场景 | 顶会论文、关键研究、展示 demo |

---

## 六、五档总览对比

|  | Free | Economy | Balanced | Quality | Premium |
|---|---|---|---|---|---|
| 单次成本 | **0 元** | ~0.3 元 | ~1 元 | ~5 元 | ~45 元 |
| 月跑 30 次 | 0 元 | 9 元 | 30 元 | 150 元 | 1,350 元 |
| 推理能力 | 中 | 强 | 强 | **顶级** | **最强** |
| 中文质量 | 可用 | 优秀 | 优秀 | **顶级** | 优秀 |
| 最长 Context | 256K | 128K | 1M | 1M | 1M |
| 速度 | 最快 | 快 | 快 | 中 | 慢 |
| 厂商数 | 1 | 1 | 4 | 5 | 3 |
| Embedding 成本 | 免费 | 免费 | 免费 | $0.01/M | $0.13/M |
| 速率限制 | 有 | 无 | 部分免费有 | 无 | 无 |
| **推荐场景** | 试用 | 日常 | **通用推荐** | 正式研究 | 不计成本 |

---

## 七、代码改动清单

集成上述方案需改动以下文件：

| 文件 | 改动内容 |
|---|---|
| `backend/llm/providers/openrouter.py` | MODEL_MAP 新增 step-3.5-flash / qwen3.5-plus / minimax-m2.5 / glm-5 / v3.2-speciale / gemini-3.1-pro |
| `backend/llm/tracker.py` | **修正 DeepSeek 过时价格**（高估 5-53x）+ 新增所有新模型定价 |
| `backend/llm/router.py` | DEFAULT_AGENT_MODEL 按方案更新 + 新模型检测逻辑 |
| `backend/config.py` | embedding_model 默认值更新 |
| `backend/knowledge/embeddings.py` | _MODEL_MAP 新增 nvidia/qwen embedding + tiktoken 兼容处理 |
| `frontend/src/app/settings/page.tsx` | ALL_MODEL_OPTIONS 新增模型 + PRESET_OVERRIDES 5 档预设 |
| `frontend/src/lib/i18n.ts` | 新模型的中文标签（如有需要） |

---

## 八、数据来源

- [DeepSeek 官方定价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing) — deepseek-chat/reasoner 2/3 元/M
- [OpenRouter Models](https://openrouter.ai/models) — 全平台模型定价
- [Artificial Analysis LLM Leaderboard](https://artificialanalysis.ai/leaderboards/models) — 性能与速度基准
- [MiniMax M2.5 Official](https://www.minimax.io/news/minimax-m25) — SWE-bench 80.2%
- [MiniMax M2.5 - Artificial Analysis](https://artificialanalysis.ai/models/minimax-m2-5) — 速度与定价
- [OpenHands: M2.5 vs Claude Sonnet](https://openhands.dev/blog/minimax-m2-5-open-weights-models-catch-up-to-claude)
- [Qwen 3.5 Benchmarks Guide](https://www.digitalapplied.com/blog/qwen-3-5-medium-model-series-benchmarks-pricing-guide)
- [Qwen 3.5 Plus on OpenRouter](https://openrouter.ai/qwen/qwen3.5-plus-02-15) — $0.26/$1.56
- [DeepSeek V3.2 Speciale on OpenRouter](https://openrouter.ai/deepseek/deepseek-v3.2-speciale) — $0.40/$1.20
- [GLM-5 Intelligence Analysis](https://artificialanalysis.ai/models/glm-5) — Chatbot Arena #1
- [Step 3.5 Flash Analysis](https://artificialanalysis.ai/models/step-3-5-flash) — AIME 97.3%
- [LLM-Stats Benchmarks](https://llm-stats.com/benchmarks)
- [CostGoat OpenRouter Pricing](https://costgoat.com/pricing/openrouter)
- [PricePerToken 全模型定价](https://pricepertoken.com/)
- [中国 AI 模型 API 价格对比](https://makeronsite.com/2026-china-ai-model-api-price-comparison.html)
- [Chinese AI Models 61% Market Share](https://dataconomy.com/2026/02/25/chinese-ai-models-hit-61-market-share-on-openrouter/)

# AIDE Phase 1: Knowledge Foundation -- 知识基座

---

## 1. 目标与交付物概述

Phase 1 是 AIDE 系统的基础设施层，目标是构建一个**可运行的后端服务**，使其具备以下能力:

| 交付物               | 说明                                          |
| -------------------- | --------------------------------------------- |
| 项目骨架             | FastAPI + PostgreSQL + Docker Compose 完整开发环境 |
| PDF Ingestion Pipeline | 上传 PDF -> 提取文本 -> 分块 -> 嵌入 -> 存储       |
| 混合搜索引擎         | ChromaDB 向量检索 + BM25 关键词检索 + RRF 融合 + MMR 重排序 |
| LLM Router           | DeepSeek / OpenRouter 统一接口 + Token/Cost 追踪  |
| REST API             | PDF 上传、混合检索、项目 CRUD、API Key 管理          |

完成 Phase 1 后，用户可以通过 API 上传 PDF 论文语料库，并对其进行混合语义检索，同时 LLM 多模型路由已就绪。

---

## 2. 项目骨架

### 2.1 pyproject.toml 依赖说明

项目使用 `pyproject.toml` 管理依赖，通过 `pip install -e .` 可编辑安装。核心依赖如下:

| 依赖包           | 用途                     |
| ---------------- | ------------------------ |
| fastapi          | Web 框架                 |
| uvicorn          | ASGI 服务器              |
| sqlalchemy       | ORM 数据库操作           |
| alembic          | 数据库迁移               |
| asyncpg          | PostgreSQL 异步驱动      |
| pydantic-settings| 配置管理                 |
| chromadb         | 向量数据库               |
| rank-bm25        | BM25 关键词索引           |
| pymupdf          | PDF 文本提取 (主)        |
| pdfplumber       | PDF 文本提取 (降级方案)  |
| tiktoken         | Token 计数               |
| httpx            | 异步 HTTP 客户端         |
| websockets       | WebSocket 支持           |
| networkx         | 引用图计算               |

### 2.2 Docker Compose 服务架构

```mermaid
flowchart LR
    subgraph docker ["Docker Compose"]
        BE["backend\n(FastAPI)\nPort 8000"]
        PG["postgres\n(PostgreSQL 16)\nPort 5432"]
        CH["chromadb\n(ChromaDB)\nPort 8001"]
        FE["frontend\n(Next.js)\nPort 3000"]
    end

    BE --> PG
    BE --> CH
    FE --> BE
```

四个服务的角色:

| 服务     | 镜像/运行时          | 端口  | 职责                     |
| -------- | -------------------- | ----- | ------------------------ |
| backend  | Python 3.12 + FastAPI | 8000  | API 服务、业务逻辑        |
| postgres | PostgreSQL 16         | 5432  | 项目元数据、检查点、Token 用量 |
| chromadb | ChromaDB              | 8001  | 向量嵌入存储与检索        |
| frontend | Next.js 15            | 3000  | Web 交互界面 (Phase 3)   |

### 2.3 FastAPI 应用结构

```
aide/backend/
  main.py             # FastAPI app entry, lifespan 管理
  config.py           # Settings (Pydantic BaseSettings)
  models/             # SQLAlchemy DB models
  api/                # REST + WebSocket endpoints
  knowledge/          # PDF 处理 + 检索引擎
  llm/                # LLM Router
```

**main.py** 的 `lifespan` 上下文管理器负责:

1. 启动时: 初始化数据库连接池、连接 ChromaDB、加载 BM25 索引
2. 运行时: FastAPI 应用服务请求
3. 关闭时: 释放数据库连接、关闭 ChromaDB 客户端

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await init_db()
    init_chromadb()
    load_bm25_index()
    yield
    # shutdown
    await close_db()
```

**路由注册**采用模块化挂载:

```python
app.include_router(projects_router, prefix="/api/projects")
app.include_router(papers_router, prefix="/api/papers")
app.include_router(checkpoints_router, prefix="/api/checkpoints")
app.include_router(settings_router, prefix="/api/settings")
```

### 2.4 配置系统

`config.py` 使用 Pydantic BaseSettings，支持从环境变量和 `.env` 文件读取:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    # 数据库
    database_url: str = "postgresql+asyncpg://aide:aide@localhost:5432/aide"

    # ChromaDB
    chromadb_host: str = "localhost"
    chromadb_port: int = 8001

    # LLM API Keys
    deepseek_api_key: str = ""
    openrouter_api_key: str = ""

    # 嵌入模型
    embedding_model: str = "text-embedding-3-small"

    # 工作区路径
    workspace_path: str = "./workspace"
```

环境变量命名规则: 字段名大写即为对应的环境变量名，例如 `DATABASE_URL`、`DEEPSEEK_API_KEY`。

---

## 3. 数据模型

Phase 1 定义三个核心 SQLAlchemy 模型，映射到 PostgreSQL 数据库表。

### 3.1 Project 模型

项目是 AIDE 的顶层实体，对应一个完整的研究任务。

| 字段             | 类型         | 说明                                   |
| ---------------- | ------------ | -------------------------------------- |
| id               | UUID         | 主键                                   |
| name             | String       | 项目名称                               |
| description      | Text         | 研究问题描述                           |
| status           | Enum         | idle / running / paused / completed    |
| current_phase    | Enum         | explore / hypothesize / evidence / compose |
| iteration_count  | Integer      | 当前迭代轮次                           |
| settings         | JSON         | 项目级别配置 (模型偏好、检查点超时等)  |
| created_at       | DateTime     | 创建时间                               |
| updated_at       | DateTime     | 最后更新时间                           |

### 3.2 Checkpoint 模型

检查点记录用户在研究循环中的审核决策。

| 字段             | 类型         | 说明                                   |
| ---------------- | ------------ | -------------------------------------- |
| id               | UUID         | 主键                                   |
| project_id       | UUID (FK)    | 关联项目                               |
| phase            | Enum         | 触发检查点的阶段                       |
| status           | Enum         | pending / approved / adjusted / skipped |
| summary          | Text         | 当前阶段成果摘要                       |
| user_feedback    | Text         | 用户调整意见 (adjust 时填写)           |
| created_at       | DateTime     | 创建时间                               |
| resolved_at      | DateTime     | 决策完成时间                           |

### 3.3 TokenUsage 模型

追踪每次 LLM 调用的 Token 消耗和成本。

| 字段             | 类型         | 说明                                   |
| ---------------- | ------------ | -------------------------------------- |
| id               | UUID         | 主键                                   |
| project_id       | UUID (FK)    | 关联项目                               |
| agent_role       | String       | 调用的 Agent 角色                      |
| model            | String       | 使用的模型名                           |
| provider         | String       | 提供商 (deepseek / openrouter)         |
| prompt_tokens    | Integer      | 输入 Token 数                          |
| completion_tokens| Integer      | 输出 Token 数                          |
| total_tokens     | Integer      | 总 Token 数                            |
| cost_usd         | Float        | 估算费用 (USD)                         |
| created_at       | DateTime     | 调用时间                               |

### 3.4 数据库迁移策略

使用 Alembic 管理数据库 schema 变更:

```bash
# 初始化 Alembic
alembic init alembic

# 生成迁移脚本
alembic revision --autogenerate -m "initial tables"

# 执行迁移
alembic upgrade head
```

每次模型变更后，执行 `alembic revision --autogenerate` 自动检测差异并生成迁移脚本。生产环境部署时通过 `alembic upgrade head` 应用所有未执行的迁移。

---

## 4. PDF Ingestion Pipeline

PDF Ingestion 是知识基座的核心，负责将用户上传的 PDF 论文转化为可检索的结构化知识。

### 4.1 处理流程

```mermaid
flowchart TD
    Upload["PDF 上传"] --> Extract["文本提取"]
    Extract --> PyMuPDF{"PyMuPDF\n提取成功?"}
    PyMuPDF -->|"成功"| Chunk["分块"]
    PyMuPDF -->|"失败/质量低"| Fallback["pdfplumber\n降级提取"]
    Fallback --> Chunk
    Chunk --> GenL["生成 L0/L1/L2\n多粒度表示"]
    GenL --> Embed["嵌入向量生成"]
    Embed --> Store["存储"]
    Store --> ChromaDB["ChromaDB\n(向量)"]
    Store --> BM25["BM25 Index\n(关键词)"]
    Store --> PG["PostgreSQL\n(元数据)"]
```

**详细步骤**:

1. **文本提取**: 首选 PyMuPDF (`fitz`)，能高效提取文本和表格。若提取质量低 (如扫描件)，降级到 pdfplumber
2. **分块 (Chunking)**: 按段落边界分割，受 Token 限制约束
3. **L0/L1/L2 生成**: 对每个块/每篇文档自动生成三级摘要
4. **嵌入生成**: 调用 embedding 模型生成向量
5. **存储**: 向量存入 ChromaDB，关键词索引存入 BM25，元数据存入 PostgreSQL

### 4.2 分块策略

分块策略以保留语义完整性为目标:

| 参数               | 值    | 说明                         |
| ------------------ | ----- | ---------------------------- |
| max_chunk_tokens   | 1000  | 单块最大 Token 数             |
| overlap_tokens     | 200   | 相邻块重叠 Token 数           |
| separator          | 段落  | 优先按段落边界切分            |

**分块算法流程**:

1. 将提取文本按段落 (双换行符) 分割
2. 顺序合并段落，直到达到 `max_chunk_tokens` 限制
3. 到达限制后，从当前位置回退 `overlap_tokens` 作为下一块的起始
4. 保留每块在原文中的页码、起止位置等元数据

### 4.3 元数据提取

对每篇 PDF 使用启发式规则提取结构化元数据:

| 字段   | 提取策略                                           |
| ------ | -------------------------------------------------- |
| 标题   | 首页最大字号文本 / PDF metadata 中的 Title 字段     |
| 作者   | 标题后首个段落匹配人名模式 / PDF metadata Author    |
| 年份   | 正则匹配四位数字 (优先正文尾部/首页)               |
| 摘要   | "Abstract" 关键词后的段落 / 首个长段落              |

提取的元数据存入 PostgreSQL 的 PDF Metadata Index，支持按作者、年份等条件精确过滤。

---

## 5. 混合搜索引擎 (Hybrid Search)

### 5.1 架构总览

```mermaid
flowchart TD
    Query["搜索查询"] --> Vec["ChromaDB\n向量检索"]
    Query --> BM25["BM25\n关键词检索"]
    Vec --> RRF["RRF\n分数融合"]
    BM25 --> RRF
    RRF --> TD["时间衰减\nTime Decay"]
    TD --> MMR["MMR\n重排序"]
    MMR --> Result["Top-K 结果"]
```

混合搜索引擎结合四种机制，解决单一检索方式的不足:

| 组件     | 解决的问题                                 |
| -------- | ------------------------------------------ |
| ChromaDB | 语义相似度检索 -- 捕捉同义表达             |
| BM25     | 关键词精确匹配 -- 捕捉专有名词、方法名、作者名 |
| RRF      | 融合两种检索结果 -- 综合语义和词汇信号     |
| 时间衰减 | 提升近期文献权重 -- 科研领域时效性重要     |
| MMR      | 去除冗余结果 -- 保证结果多样性             |

### 5.2 Reciprocal Rank Fusion (RRF)

RRF 将来自不同检索器的排名列表融合为统一分数:

```
score(doc) = sum( 1 / (k + rank_i(doc)) )  for each retriever i
```

其中:

- `k = 60` (常数，平滑排名差异)
- `rank_i(doc)` 是文档在第 i 个检索器中的排名 (从 1 开始)
- 同一文档在多个检索器中命中时分数叠加

**示例**: 某文档在向量检索中排名第 3，在 BM25 中排名第 7:

```
score = 1/(60+3) + 1/(60+7) = 0.01587 + 0.01493 = 0.03080
```

### 5.3 时间衰减 (Time Decay)

对融合后的结果施加时间衰减权重，近期文献获得更高分数:

```
score_final = score_rrf * decay ^ age_years
```

其中:

- `decay = 0.95` (每过一年分数衰减 5%)
- `age_years = (当前日期 - 发表日期).days / 365`

**示例**: 2024年的论文 (`age = 2`):

```
score_final = score_rrf * 0.95^2 = score_rrf * 0.9025
```

2020年的论文 (`age = 6`):

```
score_final = score_rrf * 0.95^6 = score_rrf * 0.7351
```

### 5.4 Maximal Marginal Relevance (MMR)

MMR 在选择结果时平衡相关性和多样性:

```
MMR(d) = lambda * Sim(d, query) - (1 - lambda) * max(Sim(d, d_j))
                                                  d_j in S
```

其中:

- `lambda = 0.7` (偏向相关性，同时保留一定多样性)
- `Sim(d, query)` 是文档与查询的相似度 (来自 RRF 分数)
- `max(Sim(d, d_j))` 是文档与已选结果集 S 中最相似文档的相似度
- 迭代选择: 每次选出 MMR 分数最高的文档加入结果集

### 5.5 实现代码结构

```python
class HybridSearchEngine:
    def __init__(self, chromadb_client, bm25_index):
        self.chromadb = chromadb_client
        self.bm25 = bm25_index

    def search(
        self,
        queries: list[str],
        top_k: int = 20,
        mmr_lambda: float = 0.7,
        time_decay_factor: float = 0.95,
    ) -> list[SearchResult]:
        # 1. 双路检索
        vec_results = self.chromadb.query(queries, n_results=top_k * 2)
        bm25_results = self.bm25.query(queries, n_results=top_k * 2)

        # 2. RRF 融合 (k=60)
        fused = reciprocal_rank_fusion(vec_results, bm25_results, k=60)

        # 3. 时间衰减
        for r in fused:
            age_years = (now() - r.publish_date).days / 365
            r.score *= time_decay_factor ** age_years

        # 4. MMR 重排序
        return mmr_rerank(fused, lambda_param=mmr_lambda, top_k=top_k)
```

---

## 6. LLM Router

### 6.1 统一接口设计

LLM Router 为上层系统提供统一的模型调用接口，屏蔽不同提供商的 API 差异:

```python
class LLMRouter:
    async def call(
        self,
        model: str,
        messages: list[dict],
        response_format: type | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        provider = self.resolve_provider(model)
        response = await provider.chat_completion(
            model=model,
            messages=messages,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        self.tracker.record(response.usage)
        return response
```

### 6.2 双提供商架构

| 提供商       | 支持模型                    | 接入方式     |
| ------------ | --------------------------- | ------------ |
| DeepSeek     | DeepSeek Reasoner           | 直连 API     |
| OpenRouter   | Gemini 3.1 Pro, GPT 5.3, Opus 4.6 | 统一网关     |

**DeepSeek Provider**: 直接调用 DeepSeek API，支持结构化输出 (Pydantic response_format)。

**OpenRouter Provider**: 通过 OpenRouter 统一网关访问多个模型。优势是单一 API Key 即可使用多种模型。

### 6.3 模型路由策略

根据 Agent 角色自动选择最适配的模型:

| AgentRole   | 首选模型              | 路由理由                         |
| ----------- | --------------------- | -------------------------------- |
| Director    | Opus 4.6              | 战略决策需要最强推理能力         |
| Scientist   | DeepSeek Reasoner     | 假设推理需要深度思考链           |
| Librarian   | Gemini 3.1 Pro        | 文献综合需要大上下文窗口         |
| Writer      | GPT 5.3               | 学术写作需要优秀的语言表达       |
| Critic      | Opus 4.6              | 质量评审需要最强批判性思维       |
| Orchestrator| Opus 4.6              | 元认知决策需要最高级别推理       |
| SubAgent    | 由父 Agent 指定       | 子任务可使用轻量模型降低成本     |

路由逻辑允许降级: 当首选模型不可用时，自动切换到备选模型。

### 6.4 Token 追踪与成本计算

每次 LLM 调用后，Router 自动记录:

```python
class TokenTracker:
    async def record(self, usage: TokenUsage):
        cost = self.calculate_cost(
            model=usage.model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
        )
        await self.db.insert(TokenUsageRecord(
            project_id=usage.project_id,
            agent_role=usage.agent_role,
            model=usage.model,
            provider=usage.provider,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            cost_usd=cost,
        ))
```

成本按模型的每百万 Token 价格计算:

```
cost = (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
```

---

## 7. REST API 端点清单

### 7.1 项目管理

| 方法   | 路径                        | 说明             |
| ------ | --------------------------- | ---------------- |
| POST   | `/api/projects`             | 创建新项目       |
| GET    | `/api/projects`             | 列出所有项目     |
| GET    | `/api/projects/{id}`        | 获取项目详情     |
| PATCH  | `/api/projects/{id}`        | 更新项目信息     |
| DELETE | `/api/projects/{id}`        | 删除项目         |
| POST   | `/api/projects/{id}/start`  | 启动研究循环     |
| POST   | `/api/projects/{id}/pause`  | 暂停研究循环     |

### 7.2 PDF 管理

| 方法   | 路径                           | 说明             |
| ------ | ------------------------------ | ---------------- |
| POST   | `/api/papers/upload`           | 上传 PDF 文件    |
| GET    | `/api/papers`                  | 列出已上传论文   |
| GET    | `/api/papers/{id}`             | 获取论文元数据   |
| DELETE | `/api/papers/{id}`             | 删除论文         |
| POST   | `/api/papers/search`           | 混合搜索         |

### 7.3 检查点

| 方法   | 路径                                    | 说明             |
| ------ | --------------------------------------- | ---------------- |
| GET    | `/api/checkpoints/{project_id}`         | 获取项目检查点列表 |
| POST   | `/api/checkpoints/{id}/approve`         | 批准检查点       |
| POST   | `/api/checkpoints/{id}/adjust`          | 调整并重试       |
| POST   | `/api/checkpoints/{id}/skip`            | 跳过检查点       |

### 7.4 设置

| 方法   | 路径                        | 说明             |
| ------ | --------------------------- | ---------------- |
| GET    | `/api/settings`             | 获取当前设置     |
| PUT    | `/api/settings`             | 更新设置         |
| POST   | `/api/settings/test-key`    | 测试 API Key 有效性 |

---

## 8. 启动与验证步骤

### 8.1 启动服务

```bash
# 1. 启动基础设施
docker-compose up -d postgres chromadb

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Keys

# 3. 安装依赖
pip install -e .

# 4. 初始化数据库
alembic upgrade head

# 5. 启动后端
uvicorn aide.backend.main:app --reload --port 8000
```

### 8.2 验证步骤

1. **健康检查**: `GET http://localhost:8000/health` 返回 200
2. **创建项目**: `POST /api/projects` 返回项目 ID
3. **上传 PDF**: `POST /api/papers/upload` 上传一篇论文，确认返回成功
4. **搜索验证**: `POST /api/papers/search` 使用论文相关关键词搜索，确认返回匹配结果
5. **LLM 验证**: 调用需要 LLM 的 API (如 L0/L1 摘要生成)，确认模型响应正常

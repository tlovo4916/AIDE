# AIDE Phase 4: Polish & Deploy -- 完善与部署

---

## 1. 目标与交付物概述

Phase 4 是 AIDE 系统的最终完善阶段，将系统从开发状态推进到生产就绪。

| 交付物             | 说明                                         |
| ------------------ | -------------------------------------------- |
| Web 文献检索       | Semantic Scholar + arXiv + CrossRef API 集成  |
| Citation Graph     | 引用图谱计算与力导向图可视化                 |
| Token 成本面板     | 按项目/Agent/模型的用量统计与可视化          |
| Docker 一键部署    | docker-compose.yml 完整生产配置              |
| E2E 测试           | 完整研究项目端到端验证                       |

---

## 2. Web 文献检索集成

### 2.1 Semantic Scholar API

Semantic Scholar 提供结构化的学术论文元数据和引用关系。

**集成端点**:

| 端点                           | 用途                         |
| ------------------------------ | ---------------------------- |
| `/paper/search`                | 关键词搜索论文               |
| `/paper/{paper_id}`            | 获取论文详情                 |
| `/paper/{paper_id}/citations`  | 获取引用该论文的论文         |
| `/paper/{paper_id}/references` | 获取该论文引用的论文         |

**返回字段**: paperId, title, abstract, year, authors, citationCount, referenceCount, fieldsOfStudy, externalIds

### 2.2 arXiv API

arXiv 提供预印本论文的全文检索和 PDF 下载。

**集成方式**: Atom feed API (`http://export.arxiv.org/api/query`)

**搜索参数**:

| 参数           | 说明                                 |
| -------------- | ------------------------------------ |
| search_query   | 搜索表达式 (支持 `au:`, `ti:`, `abs:` 前缀) |
| start          | 分页起始位置                         |
| max_results    | 最大返回数 (默认 10, 上限 100)       |
| sortBy         | 排序方式 (relevance / lastUpdatedDate / submittedDate) |

**返回字段**: id, title, summary, authors, published, updated, categories, pdf_url

### 2.3 CrossRef API (规划中)

CrossRef 提供 DOI 解析和论文元数据。规划集成但不在 Phase 4 首要优先级。

**用途**: DOI 到完整引用信息的解析, 补充 Semantic Scholar 缺失的期刊论文。

### 2.4 统一论文元数据格式

三个 API 返回的数据格式不同，系统内部使用统一的 `PaperMetadata` 结构:

```python
class PaperMetadata:
    source: Literal["semantic_scholar", "arxiv", "crossref", "local_pdf"]
    source_id: str           # 来源平台的 ID
    title: str
    authors: list[str]
    year: int | None
    abstract: str | None
    doi: str | None
    arxiv_id: str | None
    pdf_url: str | None
    citation_count: int | None
    reference_count: int | None
    fields_of_study: list[str]
```

### 2.5 速率限制策略

各 API 的速率限制不同，系统统一管理:

| API              | 速率限制                   | 系统策略                     |
| ---------------- | -------------------------- | ---------------------------- |
| Semantic Scholar | 100 req/5min (无 key)      | 令牌桶限流 + 指数退避重试    |
| arXiv            | 1 req/3s (建议)            | 固定间隔 3 秒                |
| CrossRef         | 50 req/s (polite pool)     | 令牌桶限流                   |

当 Librarian 的子代理并行检索时，每个子代理独立计数，总速率不超过限制。超限时自动排队等待。

---

## 3. Citation Graph 可视化

### 3.1 图计算 (NetworkX)

后端使用 NetworkX 构建和分析引用图:

```python
class CitationGraphBuilder:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_paper(self, paper: PaperMetadata):
        self.graph.add_node(paper.source_id, **paper.to_dict())

    def add_citation(self, citing_id: str, cited_id: str):
        self.graph.add_edge(citing_id, cited_id)
```

### 3.2 图分析功能

| 分析功能         | 算法                     | 用途                               |
| ---------------- | ------------------------ | ---------------------------------- |
| 最高引用节点     | 入度排序                 | 发现领域核心论文                   |
| 引用链追踪       | BFS/DFS 路径搜索         | 追溯知识传播路径                   |
| 桥接节点发现     | 介数中心性 (betweenness) | 发现连接不同子领域的关键论文       |
| 社区检测         | Louvain 算法             | 识别研究子领域聚类                 |
| PageRank         | PageRank 算法            | 综合评估论文影响力                 |

**输出示例**:

```python
# 最高引用节点
top_cited = sorted(
    graph.nodes(data=True),
    key=lambda x: graph.in_degree(x[0]),
    reverse=True
)[:10]

# 桥接节点
betweenness = nx.betweenness_centrality(graph)
bridge_nodes = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:5]
```

### 3.3 前端力导向图布局

前端 `CitationGraph.tsx` 使用 D3.js 力导向布局渲染引用网络:

| 视觉编码       | 映射                           |
| -------------- | ------------------------------ |
| 节点大小       | 引用数 (citation_count)        |
| 节点颜色       | 来源 (本地 PDF / Semantic Scholar / arXiv) |
| 边方向         | 箭头指向被引用论文             |
| 边粗细         | 同一对论文间的引用次数         |
| 悬停信息       | 论文标题、作者、年份、摘要     |

交互功能:

- 拖拽节点调整布局
- 滚轮缩放
- 点击节点高亮其引用链
- 框选区域放大

---

## 4. Token 成本追踪面板

### 4.1 数据维度

追踪面板提供多维度的 Token 使用统计:

| 维度     | 说明                                 |
| -------- | ------------------------------------ |
| 按项目   | 每个研究项目的总用量和成本           |
| 按 Agent | Director/Scientist/Librarian/Writer/Critic 各自用量 |
| 按模型   | DeepSeek Reasoner / Gemini / GPT / Opus 各自用量    |
| 按时间   | 每小时/每天的用量趋势                |
| 按阶段   | EXPLORE/HYPOTHESIZE/EVIDENCE/COMPOSE 各阶段用量     |

### 4.2 成本估算公式与价格表

```
cost = (prompt_tokens * input_price + completion_tokens * output_price) / 1_000_000
```

参考价格表 (USD per 1M tokens):

| 模型              | 输入价格  | 输出价格  |
| ----------------- | --------- | --------- |
| DeepSeek Reasoner | $0.55     | $2.19     |
| Gemini 3.1 Pro    | $1.25     | $5.00     |
| GPT 5.3           | $2.50     | $10.00    |
| Opus 4.6          | $15.00    | $75.00    |

(价格为示意，以实际 API 定价为准)

### 4.3 recharts 可视化图表

| 图表类型       | 展示内容                                 |
| -------------- | ---------------------------------------- |
| 堆叠柱状图     | 按 Agent 角色的每日 Token 用量           |
| 饼图           | 按模型的成本占比                         |
| 折线图         | Token 用量随迭代轮次的变化趋势           |
| 表格           | 详细的调用记录列表 (时间、Agent、模型、Token、成本) |

```mermaid
flowchart LR
    DB["PostgreSQL\ntoken_usage 表"] --> API["GET /api/stats/tokens\n聚合查询"]
    API --> FE["recharts\n可视化组件"]
```

---

## 5. Docker 一键部署

### 5.1 docker-compose.yml 服务架构

```mermaid
flowchart TB
    subgraph docker ["Docker Compose"]
        FE["frontend\nNext.js 15\nPort 3000"]
        BE["backend\nFastAPI\nPort 8000"]
        PG["postgres\nPostgreSQL 16\nPort 5432"]
        CH["chromadb\nChromaDB\nPort 8001"]
    end

    FE -->|"HTTP/WS"| BE
    BE -->|"asyncpg"| PG
    BE -->|"HTTP"| CH
```

### 5.2 服务配置详情

```yaml
# docker-compose.yml (结构说明)
services:
  postgres:
    image: postgres:16-alpine
    ports: ["5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]
    environment:
      POSTGRES_USER: aide
      POSTGRES_PASSWORD: aide
      POSTGRES_DB: aide

  chromadb:
    image: chromadb/chroma:latest
    ports: ["8001:8000"]
    volumes: ["chromadata:/chroma/chroma"]

  backend:
    build:
      context: .
      dockerfile: aide/backend/Dockerfile
    ports: ["8000:8000"]
    depends_on: [postgres, chromadb]
    volumes: ["./workspace:/app/workspace"]
    env_file: .env

  frontend:
    build:
      context: ./aide/frontend
      dockerfile: Dockerfile
    ports: ["3000:3000"]
    depends_on: [backend]
    environment:
      NEXT_PUBLIC_API_URL: http://backend:8000
```

### 5.3 Dockerfile 构建说明

**后端 Dockerfile**:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .
COPY aide/backend ./aide/backend
CMD ["uvicorn", "aide.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**前端 Dockerfile**:

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json .
CMD ["npm", "start"]
```

### 5.4 环境变量配置

`.env` 文件模板:

```bash
# 数据库
DATABASE_URL=postgresql+asyncpg://aide:aide@postgres:5432/aide

# ChromaDB
CHROMADB_HOST=chromadb
CHROMADB_PORT=8000

# LLM API Keys
DEEPSEEK_API_KEY=sk-xxx
OPENROUTER_API_KEY=sk-or-xxx

# 嵌入模型
EMBEDDING_MODEL=text-embedding-3-small

# 工作区
WORKSPACE_PATH=/app/workspace
```

### 5.5 启动命令

```bash
# 首次启动 (构建镜像 + 启动所有服务)
docker-compose up -d --build

# 查看日志
docker-compose logs -f backend

# 初始化数据库 (首次运行)
docker-compose exec backend alembic upgrade head

# 停止服务
docker-compose down

# 停止并清除数据
docker-compose down -v
```

---

## 6. E2E 测试计划

### 6.1 完整研究项目端到端验证流程

E2E 测试模拟一个完整研究项目的全生命周期:

```mermaid
flowchart TD
    T1["1. 创建项目"] --> T2["2. 上传 3-5 篇 PDF"]
    T2 --> T3["3. 验证 PDF 已被索引\n(搜索测试)"]
    T3 --> T4["4. 启动研究循环"]
    T4 --> T5["5. 观察 EXPLORE 阶段\n(Director + Librarian)"]
    T5 --> T6["6. Checkpoint 1: 选择方向"]
    T6 --> T7["7. 观察 HYPOTHESIZE 阶段\n(Scientist + Critic)"]
    T7 --> T8["8. 验证 Challenge 机制\n(至少 1 个挑战被发起和解决)"]
    T8 --> T9["9. Checkpoint 2: 确认假设"]
    T9 --> T10["10. 观察 EVIDENCE 阶段\n(Librarian SubAgents 并行)"]
    T10 --> T11["11. 观察 COMPOSE 阶段\n(Writer SubAgents 并行)"]
    T11 --> T12["12. Checkpoint 5: 最终审核"]
    T12 --> T13["13. 导出论文\n(Markdown + PDF + BibTeX)"]
    T13 --> T14["14. 验证 Token 用量记录"]
```

### 6.2 测试检查清单

**基础设施验证**:

| 检查项                       | 验证方法                           | 通过标准               |
| ---------------------------- | ---------------------------------- | ---------------------- |
| 数据库连接                   | `GET /health`                      | 返回 200               |
| ChromaDB 连接                | 上传 PDF 后查询向量                | 返回非空结果           |
| WebSocket 连接               | 前端打开项目详情页                 | 连接状态为 connected   |
| LLM API 连通性               | `POST /api/settings/test-key`      | 所有配置的 key 返回 true |

**功能验证**:

| 检查项                       | 验证方法                           | 通过标准               |
| ---------------------------- | ---------------------------------- | ---------------------- |
| PDF 上传与索引               | 上传 PDF -> 搜索关键词             | 返回相关结果           |
| 混合搜索                     | 多种查询 (语义 + 关键词)          | 两种检索器均有命中     |
| 项目创建与管理               | CRUD 操作                          | 所有操作成功           |
| 研究循环启动                 | 启动项目                           | Orchestrator 开始调度  |
| Agent 执行                   | 观察黑板产物                       | 产物按预期生成         |
| L0/L1/L2 自动生成            | 检查产物文件                       | 三级文件均存在         |
| 挑战机制                     | 观察 challenges/ 目录              | 至少 1 个挑战产生      |
| 子代理并行                   | 观察 SubAgent 状态                 | 子代理成功生成和完成   |
| 检查点交互                   | Approve / Adjust / Skip            | 三种操作均正常         |
| 回溯机制                     | 触发回溯条件                       | 系统正确回退阶段       |
| 论文导出                     | 导出完整论文                       | Markdown + BibTeX 完整 |
| Token 用量记录               | 查询 token_usage 表                | 所有调用均有记录       |

**性能验证**:

| 检查项                       | 通过标准                           |
| ---------------------------- | ---------------------------------- |
| PDF 处理时间                 | 单篇 PDF (20页) < 30 秒           |
| 混合搜索响应时间             | 单次查询 < 2 秒                   |
| WebSocket 推送延迟           | 黑板更新到前端显示 < 1 秒         |
| 完整研究循环时间             | 30-40 轮迭代在合理时间内完成       |

---

## 7. 未来扩展方向

| 方向               | 说明                                           | 优先级 |
| ------------------ | ---------------------------------------------- | ------ |
| Google Scholar 集成 | 补充 Semantic Scholar 和 arXiv 未覆盖的文献    | 高     |
| 本地模型支持       | 通过 Ollama 支持本地部署的 LLM (降低成本)      | 高     |
| 多语言论文支持     | 中文论文处理与双语摘要生成                     | 中     |
| 实验代码集成       | 集成 Jupyter Notebook 执行环境                  | 中     |
| 协作模式           | 多用户同时参与同一研究项目                     | 低     |
| 论文模板库         | 预设 IEEE / ACM / Nature 等格式模板            | 低     |
| Agent 自定义       | 用户自定义 Agent 角色和 system prompt           | 低     |
| 知识图谱           | 从论文中提取实体关系构建领域知识图谱           | 中     |
| 移动端适配         | 响应式布局支持平板设备                         | 低     |

# AIDE 构建与运行指南

---

## 1. 前置条件

唯一需要本地安装的只有 Docker。所有语言运行时、数据库、依赖均由 Docker 管理。

| 依赖             | 版本要求 | 说明                   |
| ---------------- | -------- | ---------------------- |
| Docker           | 24+      | 容器引擎               |
| Docker Compose   | 2.20+    | 多服务编排 (Docker 自带) |

验证安装:

```bash
docker --version            # Docker version 24.x.x
docker compose version      # Docker Compose version v2.2x.x
```

---

## 2. 项目结构概览

```
aide/
  backend/                    # Python 3.12 后端 (FastAPI)
    main.py                   # 应用入口
    config.py                 # 配置系统 (Pydantic BaseSettings)
    types.py                  # 共享类型定义
    models/                   # SQLAlchemy 数据库模型
    api/                      # REST + WebSocket 端点
    blackboard/               # 黑板架构
    memory/                   # 三层记忆系统
    agents/                   # Agent Pool (5 Agent + SubAgent)
    orchestrator/             # Orchestrator 螺旋研究引擎
    knowledge/                # 知识库 (PDF + 混合检索)
    llm/                      # LLM Router (DeepSeek + OpenRouter)
    checkpoint/               # 检查点系统
  frontend/                   # Next.js 15 前端
    src/
      app/                    # 页面路由 (Dashboard / Project / Settings)
      components/             # UI 组件
      hooks/                  # React Hooks (WebSocket / Blackboard)
      lib/                    # API 客户端 + 协议类型
  Dockerfile                  # 后端容器镜像
  frontend/Dockerfile         # 前端容器镜像
  docker-compose.yml          # 4 服务编排
  pyproject.toml              # Python 依赖声明
  .env                        # 环境变量 (自动创建)
  start.sh                    # 一键启动
  stop.sh                     # 一键停止
```

---

## 3. 一键启动

```bash
cd aide
./start.sh
```

首次运行时:
1. 如果 `.env` 不存在，自动从 `.env.example` 复制
2. 构建后端 Python 镜像 (安装所有 pip 依赖)
3. 构建前端 Node.js 镜像 (运行 npm install)
4. 启动 PostgreSQL、ChromaDB、Backend、Frontend 四个服务

启动完成后输出:

```
=========================================
  AIDE is running
=========================================
  Frontend:  http://localhost:3000
  Backend:   http://localhost:8000
  API Docs:  http://localhost:8000/docs
  Health:    http://localhost:8000/health
  ChromaDB:  http://localhost:8100
  Postgres:  localhost:5432
=========================================
```

---

## 4. 一键停止

```bash
./stop.sh
```

如果需要清除所有数据 (数据库、向量库、工作区):

```bash
docker compose down -v
```

---

## 5. 服务架构

| 服务     | 容器端口 | 主机端口 | 镜像/构建             | 说明                     |
| -------- | -------- | -------- | --------------------- | ------------------------ |
| backend  | 8000     | 8000     | Dockerfile (Python 3.12) | FastAPI 后端            |
| frontend | 3000     | 3000     | frontend/Dockerfile (Node 20) | Next.js 前端       |
| postgres | 5432     | 5432     | postgres:16-alpine    | 元数据存储               |
| chromadb | 8000     | 8100     | chromadb/chroma:latest | 向量数据库              |

服务依赖关系: frontend -> backend -> postgres + chromadb

---

## 6. API 密钥配置

AIDE 需要至少一个 LLM API 密钥才能运行研究循环。

### 6.1 获取密钥

| 提供商     | 获取地址                          | 用途                       |
| ---------- | --------------------------------- | -------------------------- |
| DeepSeek   | https://platform.deepseek.com/    | Scientist Agent (Reasoner) |
| OpenRouter | https://openrouter.ai/            | Director/Librarian/Writer/Critic (Gemini/GPT/Opus) |
| OpenAI     | https://platform.openai.com/      | Embedding (text-embedding-3-small) |

### 6.2 配置方式

编辑 `aide/.env` 文件:

```bash
AIDE_DEEPSEEK_API_KEY=sk-your-deepseek-key
AIDE_OPENROUTER_API_KEY=sk-or-your-openrouter-key
AIDE_OPENAI_API_KEY=sk-your-openai-key
```

修改后重启后端:

```bash
docker compose restart backend
```

也可以在 Web 界面 http://localhost:3000/settings 中配置。

---

## 7. 开发模式

Docker 已配置 volume 挂载，修改代码后自动热重载:

- 后端: `aide/backend/` 挂载到容器内 `/app/backend/`，uvicorn 带 `--reload`
- 前端: `aide/frontend/src/` 挂载到容器内 `/app/src/`，Next.js dev server 自动刷新

### 查看日志

```bash
# 全部服务
docker compose logs -f

# 仅后端
docker compose logs -f backend

# 仅前端
docker compose logs -f frontend
```

### 重启单个服务

```bash
docker compose restart backend
docker compose restart frontend
```

### 进入容器调试

```bash
# 进入后端容器
docker compose exec backend bash

# 进入前端容器
docker compose exec frontend sh
```

---

## 8. 快速验证

### Step 1: 健康检查

```bash
curl http://localhost:8000/health
```

### Step 2: 创建项目

```bash
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Project", "research_topic": "Transformer Attention Sparsification"}'
```

### Step 3: 上传 PDF

```bash
curl -X POST http://localhost:8000/api/projects/{project_id}/papers/upload \
  -F "file=@your-paper.pdf"
```

### Step 4: 搜索验证

```bash
curl "http://localhost:8000/api/projects/{project_id}/papers/search?q=transformer+attention"
```

### Step 5: 前端验证

打开浏览器访问 http://localhost:3000，确认 Dashboard 正常渲染。

---

## 9. 常见问题

### Docker 构建失败

```
ERROR: failed to solve: process "/bin/sh -c pip install --no-cache-dir ." did not complete successfully
```

检查 `pyproject.toml` 依赖版本是否有冲突。清理缓存重试:

```bash
docker compose build --no-cache backend
```

### 数据库连接失败

确认 PostgreSQL 健康:

```bash
docker compose ps postgres
docker compose logs postgres
```

### 前端无法连接后端

确认后端可访问:

```bash
curl http://localhost:8000/health
```

前端默认连接 `http://localhost:8000`。如果后端端口不同，修改 `docker-compose.yml` 中 frontend 服务的 `NEXT_PUBLIC_API_URL` 环境变量。

### 清理重来

```bash
docker compose down -v
docker system prune -f
./start.sh
```

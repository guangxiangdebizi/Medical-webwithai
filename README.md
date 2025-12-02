# MCP Web 智能助手

MCP Web 智能助手是一个集成前后端的智能问答与工具编排平台：

- **后端** 使用 FastAPI + LangChain + MCP 适配器，提供 WebSocket 实时对话、工具调用、聊天记录存储等能力。
- **前端** 为纯静态页面（HTML/JS/CSS），通过 `frontend/config.json` 动态配置后端地址，支持工具面板、历史记录管理等功能。

本仓库已经移除了任何真实密钥，使用前请先根据 `.env.example` 自行配置环境变量。

---

## 🐬 Dolphin Trinity AI™ 生态系统

### 概述

Dolphin Trinity AI™ 是一个由三位 AI Agent 组成的临床试验文档审核生态系统：

| Agent | 代号 | 角色 | 核心关注 |
|-------|------|------|----------|
| 🔵 **Dr. S** | StatGuard | 审计专家 | 合规与完整性 |
| 🟠 **Dr. M** | MediSense | 医学专家 | 安全与解读 |
| 🔷 **Dr. D** | Data Agent | 数据侦探 | 语境与证据 |

**工作流**: Check → Think → Find  
Dr. S 和 Dr. M 告诉您发生了**什么**，Dr. D 帮您找到**为什么**。

### 目录结构

```
Medical-webwithai/
├── backend/           # 原有 Dr.D (Data Agent) 后端
├── frontend/          # 原有 Dr.D 前端
├── backend1/          # 🆕 Dolphin Trinity AI™ 后端 (Dr.S + Dr.M)
├── frontend1/         # 🆕 Dolphin Trinity AI™ 前端展示页
├── .venv/             # 原有虚拟环境
├── .venv1/            # 🆕 Trinity AI 虚拟环境
├── ecosystem.config.js # 🆕 PM2 配置文件
├── nginx/trinity.conf  # 🆕 Nginx 配置片段
└── logs/              # 日志目录
```

### 快速启动 Trinity AI

#### 1. 激活虚拟环境

```bash
cd /home/ec2-user/AIWebHere/Medical-webwithai
source .venv1/bin/activate
```

#### 2. 使用 PM2 启动服务

```bash
# 启动所有服务
pm2 start ecosystem.config.js

# 或分别启动
pm2 start ecosystem.config.js --only trinity-backend
pm2 start ecosystem.config.js --only trinity-frontend

# 查看状态
pm2 status

# 查看日志
pm2 logs trinity-backend
pm2 logs trinity-frontend
```

#### 3. 配置 Nginx

将 `nginx/trinity.conf` 的内容添加到您的 `dolphincr.conf` 中：

```bash
# 编辑 nginx 配置
sudo nano /etc/nginx/conf.d/dolphincr.conf

# 在 server 块内添加 trinity.conf 的内容

# 测试配置
sudo nginx -t

# 重载 nginx
sudo nginx -s reload
```

#### 4. 访问页面

- **Trinity AI 首页**: https://dolphincr.com/trinity/
- **Dr. S 页面**: https://dolphincr.com/trinity/dr-s.html
- **Dr. M 页面**: https://dolphincr.com/trinity/dr-m.html
- **Dr. D 页面**: https://dolphincr.com/ai/ (原有)

### API 端点

#### Trinity Backend (端口 8081)

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/upload` | POST | 上传 PDF 文件 |
| `/api/analyze/dr-s` | POST | 运行 Dr.S 分析 |
| `/api/analyze/dr-m` | POST | 运行 Dr.M 分析 |
| `/api/agents` | GET | 获取 Agent 信息 |
| `/health` | GET | 健康检查 |

### 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| Trinity Backend | 8081 | Dr.S + Dr.M API |
| Trinity Frontend | 3031 | 静态页面服务 |
| 原有 AI Backend | 8080 | Dr.D API |
| 原有 AI Frontend | 3030 | Dr.D 页面 |

---

## 原有目录结构

- `backend/`：FastAPI 服务端源码，包含 MCP 代理、数据库、工具定义等。 
- `frontend/`：前端静态资源，默认通过 nginx/静态服务器托管。 
- `requirements.txt`：根目录依赖（用于完整环境）。 
- `backend/requirements.txt`：后端精简依赖列表。 
- `frontend/config.json`：前端运行时配置（部署后需修改）。 
- `README_DATABASE.md`：聊天记录数据库说明。

---

## 快速开始

### 1. 克隆仓库

```bash
git clone git@github.com:guangxiangdebizi/Medical-webwithai.git
cd Medical-webwithai
```

### 2. 准备 Python 环境

建议使用 Python 3.10+（推荐 3.11/3.12），创建虚拟环境并安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置环境变量

以 `.env.example` 为模板创建 `.env`，并填入真实密钥/连接信息：

```bash
cp .env.example .env
# 根据实际情况修改 .env
```

### 4. 启动后端服务

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8003
```

默认端口可通过 `.env` 中的 `BACKEND_PORT` 覆盖。服务启动后将提供：

- WebSocket 聊天：`ws://<host>:<port>/ws/chat`
- REST API：`http://<host>:<port>/api/...`

### 5. 配置前端

部署前修改 `frontend/config.json` 指向后端地址，例如：

```json
{
  "backend": {
    "host": "your-domain.com",
    "port": 8003,
    "protocol": "https",
    "wsProtocol": "wss"
  }
}
```

静态文件可直接通过 nginx、Vercel、静态托管平台或 FastAPI `StaticFiles` 服务。更多细节见 `frontend/配置说明.md`。

---

## 环境变量说明

参见 `.env.example`，关键变量：

- **基础**
  - `BACKEND_PORT`：FastAPI 服务端口。
- **模型配置**（可在 `.env` 中启用多个档位）
  - `LLM_PROFILES`：逗号分隔的模型标识列表，如 `DEEPSEEK,ZHIPU,OPENAI`。
  - `LLM_<PROFILE>_API_KEY` / `BASE_URL` / `MODEL` 等：各档位的密钥与模型参数。
  - `LLM_DEFAULT`：默认激活的档位 ID。
- **OpenAI 兼容变量**
  - `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL` 等，供 MCP 适配器消费。
- **数据库**
  - `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME`：医疗工具依赖的 MySQL 数据库地址。
- **会话与文件限制**
  - `HISTORY_IMAGE_MAX_FILE_BYTES`、`HISTORY_IMAGES_MAX_TOTAL` 等：历史记录多模态限制。

确保不要将真实密钥提交到仓库，GitHub Push Protection 会阻止包含密钥的提交。

---

## 前后端部署建议

- **后端**：
  - 使用 `systemd`/`supervisor` 常驻运行 uvicorn，可结合 `gunicorn` 多进程部署。
  - 如果需要 HTTPS，可放置于反向代理（Nginx/Caddy）之后。
  - 记得配置 `.env`，保证可访问 MySQL、外部模型 API。

- **前端**：
  - 构建后即为纯静态文件，无需打包工具。
  - 可挂载到同一 Nginx，下发 `config.json` 以便动态切换环境。

---

## 常见问题

1. **推送到 GitHub 被拦截**：可能检测到 `.env` 内的密钥，应移除敏感信息并重新提交。参见 [Secret Scanning 文档](https://docs.github.com/code-security/secret-scanning/working-with-secret-scanning).
2. **前端无法连接后端**：检查 `frontend/config.json` 的协议/端口配置，确保与部署环境一致，同时后端需开启 CORS。
3. **数据库连接失败**：确认 `.env` 中的 MySQL 配置正确且具有访问权限，可先测试 `mysql -h <host> -u <user> -p`。

---

## 版权与安全

- `.env` 已被列入 `.gitignore`，请勿提交真实凭据。
- 若需分享或部署演示版本，可将 `.env.example` 中的密钥留空，仅保留必要结构。

欢迎根据业务场景继续扩展 MCP 工具与前端交互。祝使用愉快！

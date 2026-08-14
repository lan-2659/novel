# 小说创作智能体

一个给小说作家使用的 Web 应用。作家输入创意，系统借助 DeepSeek LLM 逐步完成「故事设定 → 大纲 → 章节规划 → 逐章生成」，每一步结果都持久化保存，可随时中断、修改、继续写作。

**核心分工**：DeepSeek LLM 负责创作与内容决策；Python（FastAPI）负责流程控制、上下文构建、状态保存与错误处理。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3（静态产物，无构建步骤，由 FastAPI 托管） |
| 后端 | FastAPI + Uvicorn |
| 存储 | SQLite + SQLAlchemy |
| LLM | DeepSeek API（OpenAI 兼容 SDK） |
| 流式 | SSE（Server-Sent Events） |

## 目录结构

```text
project/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口，挂载静态文件与路由
│   │   ├── config.py          # 环境变量配置
│   │   ├── database.py        # SQLAlchemy 引擎与会话
│   │   ├── api/               # 路由（projects / chapters + deps）
│   │   ├── services/          # 业务逻辑与生成编排
│   │   ├── pipeline/          # 阶段状态机 + Prompt 模板
│   │   ├── llm/               # DeepSeek 客户端
│   │   ├── context_builder.py # 上下文构建（上章结尾截取）
│   │   ├── models/            # 数据模型
│   │   ├── schemas/           # Pydantic 校验
│   │   └── repositories/      # 数据访问层
|   ├── env/                       # 后端 Python 虚拟环境（已创建）       
│   ├── tests/                 # pytest 测试（含假 LLM）
│   ├── requirements.txt
│   └── .env.example           # 环境变量示例
├── frontend/
│   ├── index.html             # 单页应用模板
│   ├── app.js                 # Vue 应用逻辑（含 SSE 读取）
│   ├── style.css
│   └── vendor/vue.global.prod.js
├── 项目计划书.md
└── README.md
```

## 快速开始

### 1. 配置 API Key

在backend目录创建 `.env`（可复制 `.env.example`），填入 DeepSeek Key：

```text
DEEPSEEK_API_KEY=sk-你的key
```

### 2. 启动后端（已装好 `env` 虚拟环境）

```powershell
cd backend
.\env\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 3. 打开页面

浏览器访问 <http://127.0.0.1:8000/>（前端由 FastAPI 直接托管，无需 Node）。

## 使用流程

```text
创建项目（输入创意）
→ 生成故事设定 → 审阅/编辑 → 保存
→ 生成大纲 → 审阅/编辑 → 保存
→ 生成章节规划 → 审阅/编辑 → 保存
→ 生成下一章（流式显示）→ 编辑 → 确认
→ 下次打开继续写作 → 直至全部章节确认（已完结）
→ 导出 Markdown
```

## 核心 API

```text
POST   /api/projects                    创建项目
GET    /api/projects                    项目列表
GET    /api/projects/{id}               项目详情 + 当前阶段
POST   /api/projects/{id}/settings      生成故事设定
PUT    /api/projects/{id}/settings      保存设定
POST   /api/projects/{id}/outline       生成大纲
PUT    /api/projects/{id}/outline       保存大纲
POST   /api/projects/{id}/chapter-plan  生成章节规划
PUT    /api/projects/{id}/chapter-plan  保存规划
POST   /api/projects/{id}/chapters      生成下一章（SSE 流式）
GET    /api/projects/{id}/chapters      章节列表
PUT    /api/chapters/{id}               编辑 / 确认章节
POST   /api/chapters/{id}/regenerate    重新生成本章（SSE）
GET    /api/projects/{id}/export        导出 Markdown
GET    /api/health                      健康检查
```

## Agent 处理链路（当前实现）

MVP 不引入自主 Agent Loop，采用「用户驱动 + Python 状态机」的引导式流水线：

```text
用户操作 → 状态机阶段校验 → 构建上下文（设定+规划+上章结尾800字）
→ DeepSeek 生成 → 解析/入库 → 状态推进 → 返回给用户
```

阶段状态机：`idea → setting → outline → chapter_plan → writing → completed`。

- **Skill**：以「阶段 Prompt 模板」形式存在（`pipeline/prompts.py`），不做独立运行时。
- **Tool**：MVP 无外部工具，仅「保存到数据库」这一内部动作。
- **State**：全部持久化在 SQLite（项目阶段 + 各文档 + 章节）。
- **Memory / RAG / 多 Agent / 自动评价**：MVP 均未实现（见计划书边界）。

## 测试

```powershell
cd backend
..\env\Scripts\python.exe -m pytest -q
```

测试使用假 LLM（`tests/conftest.py`），不依赖外部 API，覆盖：健康检查、项目 CRUD、设定/大纲/规划生成、SSE 章节生成、继续写作、编辑设定、导出等，共 8 个用例。

## 当前状态

第一版（MVP）已实现并验证通过：

- [x] 创建项目 / 项目列表 / 详情
- [x] 生成 + 编辑 + 保存：故事设定、大纲、章节规划
- [x] 逐章生成（SSE 流式）、编辑、确认、重新生成
- [x] 状态机与「继续写作」（重启后可恢复进度）
- [x] 导出 Markdown
- [x] 静态前端（Vue 3，无 Node 构建）
- [x] 后端单元/集成测试（8 个用例全部通过）
- [x] 启动验证通过（健康检查 / 静态首页 / 项目创建）

## 后续计划（V2+）

人物与伏笔一致性追踪、长期 Memory 与摘要压缩、多模型路由、自动评价与修改建议、富文本编辑器、多用户与云端部署。

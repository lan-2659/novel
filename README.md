# 小说创作智能体

一个给小说作家使用的 Web 应用。作家输入创意，系统借助 DeepSeek LLM 逐步完成「故事设定 → 全书大纲 → 分卷大纲 → 分卷规划 → 逐章生成」，每一步结果都持久化保存，可随时中断、修改、继续写作。

**核心分工**：DeepSeek LLM 负责创作与内容决策；Python（FastAPI）负责流程控制、分层上下文构建、状态保存、跨卷追踪与错误处理。

支持**长篇多卷**：一本书 = 全书设定/大纲 + 若干卷，每卷有独立大纲、章节规划（15~30 章）与滚动摘要；章节确认后自动更新人物状态、伏笔与全局/卷剧情摘要，用于保持长篇一致性。

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
│   │   ├── main.py            # FastAPI 入口：挂载静态文件与路由
│   │   ├── config.py          # 环境变量配置
│   │   ├── database.py        # SQLAlchemy 引擎与会话
│   │   ├── context_builder.py # 四层上下文构建（全书/分卷/追踪/近期）
│   │   ├── api/               # 路由（projects / chapters / volumes / ideas + deps）
│   │   ├── services/          # 业务逻辑（project / generation / volume / tracking / idea）
│   │   ├── pipeline/          # 双层状态机 + Prompt 模板
│   │   ├── llm/               # DeepSeek 客户端
│   │   ├── models/            # 数据模型（含 Volume）
│   │   ├── schemas/           # Pydantic 校验
│   │   └── repositories/      # 数据访问层（含 volume_repo）
│   ├── env/                   # 后端 Python 虚拟环境（已创建）
│   ├── tests/                 # pytest 测试（含假 LLM）
│   ├── requirements.txt
│   └── .env.example           # 环境变量示例
├── frontend/
│   ├── index.html             # 单页应用模板（含分卷/追踪面板）
│   ├── app.js                 # Vue 应用逻辑（含 SSE 读取）
│   ├── style.css
│   └── vendor/vue.global.prod.js
├── changes/                   # 修改日志
├── .tasks/                    # 需求与任务追踪
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
创建项目（输入创意，可先用 ✨ 灵感创意 获取灵感）
→ 生成故事设定 → 审阅/编辑 → 保存
→ 生成全书大纲 → 审阅/编辑 → 保存（自动创建第一卷）
→ 在「卷」页选择卷：生成卷大纲 → 生成卷规划（15~30章）
→ 生成卷内下一章（流式显示）→ 编辑 → 确认（自动更新追踪）
→ 卷内章节全部确认 → 自动推进到下一卷（循环）
→ 所有卷完成 → 全书已完结
→ 导出：单卷导出 / 合并导出全部卷
```

## 核心 API

```text
POST   /api/projects                       创建项目
POST   /api/ideas/generate                 首页 AI 灵感创意生成（不建项目）
GET    /api/projects                       项目列表
GET    /api/projects/{id}                  项目详情（含卷列表、追踪字段）
POST   /api/projects/{id}/settings         生成故事设定
PUT    /api/projects/{id}/settings         保存设定
POST   /api/projects/{id}/outline          生成全书大纲（自动创建第一卷）
PUT    /api/projects/{id}/outline          保存全书大纲
POST   /api/projects/{id}/volumes          创建卷
GET    /api/projects/{id}/volumes          卷列表
GET    /api/volumes/{id}                   卷详情（含章节）
POST   /api/volumes/{id}/outline           生成卷大纲
PUT    /api/volumes/{id}/outline           保存卷大纲
POST   /api/volumes/{id}/chapter-plan      生成卷章节规划（15~30章）
PUT    /api/volumes/{id}/chapter-plan      保存卷规划
POST   /api/volumes/{id}/chapters          生成卷内下一章（SSE 流式）
GET    /api/volumes/{id}/chapters          卷内章节列表
GET    /api/projects/{id}/chapters         章节列表（volume_id 过滤 + 分页）
GET    /api/chapters/{id}                  章节详情
PUT    /api/chapters/{id}                  编辑 / 确认章节（确认后自动追踪）
POST   /api/chapters/{id}/regenerate       重新生成本章（SSE）
GET    /api/volumes/{id}/export            导出单卷 Markdown
GET    /api/projects/{id}/export           合并导出全部卷
GET    /api/health                         健康检查
```

## 处理链路

不引入自主 Agent Loop，采用「用户驱动 + Python 双层状态机」的引导式流水线：

```text
用户操作 → 状态机校验 → 分层上下文（四层）→ DeepSeek 生成 → 解析/入库 → 状态推进 → 返回
```

双层状态机（`pipeline/stages.py`）：

```text
全书阶段：idea → setting → outline → writing → completed
每卷阶段：volume_outline → volume_plan → writing → volume_completed
（全书 completed = 所有卷 completed；卷完成自动推进当前卷）
```

分层上下文（`context_builder.py`）：第一层全书级固定信息（设定/全书大纲摘要）→ 第二层分卷级信息（卷大纲/本章要点/卷滚动摘要）→ 第三层跨卷追踪（人物状态/未解伏笔/全局滚动摘要）→ 第四层近期上下文（上章结尾）。

- **Skill**：以「阶段 Prompt 模板」形式存在（`pipeline/prompts.py`），不做独立运行时。
- **Tool**：MVP 无外部工具，仅「保存到数据库」这一内部动作。
- **State**：全部持久化在 SQLite（全书阶段 + 卷内阶段 + 各文档 + 章节 + 追踪字段）。
- **Memory**：章节确认后由 `tracking_service.py` 自动提取更新人物状态/伏笔/摘要（尽力而为，不阻断确认）。未实现 RAG / 多 Agent / 自动评价。

## 主要模块

| 模块 | 作用 | 实现原理 | 对应 API |
|---|---|---|---|
| `api/` | HTTP 路由层 | 接收请求 → 校验 → 调用 Service → 返回/SSE 流式 | 全部接口 |
| `services/project_service.py` | 项目 CRUD 与详情 | 项目增删查 → 组装设定/全书大纲/卷列表/追踪字段 → 返回 | `projects` |
| `services/generation_service.py` | 全书级生成 | 创意+设定 → 生成/保存故事设定与全书大纲 → 自动创建第一卷 | `settings` / `outline` |
| `services/idea_service.py` | 首页 AI 灵感创意 | 接收 count/genre/style → 校验 → 拼创意 prompt → LLM 生成 → 归一化 ideas 返回 | `POST /api/ideas/generate` |
| `services/volume_service.py` | 卷维度业务 | 卷 CRUD → 卷大纲/卷规划生成 → 卷内章节流式生成 → 卷完成推进/全书完成 → 导出 | `volumes` / `chapters` / `export` |
| `services/tracking_service.py` | 章节确认后追踪 | 章节内容 + 当前追踪 → LLM 提取变化 → 合并写回 Project/Volume | `PUT /api/chapters/{id}`（触发） |
| `pipeline/stages.py` | 双层状态机 | 全书/卷内阶段仅前进，卷完成推进、全书完成判定 | 各生成接口 |
| `pipeline/prompts.py` | Prompt 模板 | 按阶段组装 system/user 消息（设定/大纲/卷大纲/卷规划/章节/追踪） | 各生成接口 |
| `context_builder.py` | 四层上下文 | 全书级+分卷级+追踪+上章结尾 → 结构化上下文 → 喂给章节/卷规划 prompt | `chapters` / `chapter-plan` |
| `llm/deepseek_client.py` | LLM 客户端 | 封装 DeepSeek（JSON 解析 + 重试 + 流式） | 各生成接口 |
| `models/entities.py` | 数据模型 | Project / StorySetting / StoryOutline / Volume / Chapter | 数据库 |
| `repositories/` | 数据访问层 | 封装查询与写入（分页、计数、卷内位置） | 被 Services 调用 |

## 测试

```powershell
cd backend
..\env\Scripts\python.exe -m pytest -q
```

测试使用假 LLM（`tests/conftest.py`），不依赖外部 API，覆盖：健康检查、项目 CRUD、设定/全书大纲/卷大纲/卷规划生成、卷内 SSE 章节生成、确认触发追踪、继续写作、卷完成推进下一卷、全书完成、volume 过滤与分页、单卷/合并导出、AI 灵感创意生成等，共 12 个用例。

## 当前状态

第二版（长篇多卷化）已实现并验证通过：

- [x] 卷数据结构：Volume 模型、Chapter 归属卷、分卷大纲/规划/滚动摘要
- [x] 双层状态机：全书阶段 + 卷内阶段循环，当前卷自动推进
- [x] 四层上下文构建器（全书/分卷/追踪/近期）
- [x] 章节确认后自动追踪（人物状态/伏笔/全局与卷摘要）
- [x] 按卷生成章节规划（15~30 章，可滚动、后卷呼应前卷）
- [x] 分卷浏览与写作（API + 前端卷选择器 + 当前卷标识）
- [x] 单卷导出 + 合并导出全部卷
- [x] 性能优化：章节复合索引 + 列表分页
- [x] 首页 AI 灵感创意生成（✨ 灵感创意，不自动建项目）
- [x] 静态前端（Vue 3，无 Node 构建）
- [x] 后端单元/集成测试（11 个用例全部通过）
- [x] 启动验证 + 真实 DeepSeek 端到端验证通过

## 后续计划（V4+）

多模型路由、自动评价与修改建议、追踪信息重要性评分与自动压缩、富文本编辑器、多用户与云端部署；灵感创意的题材/风格筛选 UI、换一批、用户偏好与二次扩展。


# MediaMind

基于 B 站字幕的视频知识提炼与问答 Agent。输入视频链接后，MediaMind 获取带时间戳的字幕，生成摘要、关键词和章节，再通过混合检索支持视频问答与 Word 笔记导出。


## 功能

- **视频解析**：输入带 BV 号的 B 站视频链接，生成摘要、关键词和章节目录。
- **视频问答**：结合 Chroma 向量检索、BM25 关键词检索、RRF 排名融合和大模型重排，检索视频片段后生成回答。
- **时间戳跳转**：点击回答中的时间戳或章节时间，在新标签页打开对应的视频位置。
- **连续对话**：最多携带最近 10 轮完整问答，支持普通聊天与视频内容追问。
- **笔记导出**：可整理整部视频，也可围绕最近讨论的主题生成笔记，保存为本地 `.docx` 文件。
- **重复解析更新**：再次解析同一 BV 号时，整体替换旧切片，并重建该视频的 BM25 索引。

## 技术栈与流程

| 部分 | 技术与职责 |
| --- | --- |
| 前端 | React、TypeScript、Vite、Tailwind CSS |
| 后端 | Python、FastAPI、Pydantic |
| 模型服务 | 智谱 GLM，负责蒸馏、意图判断、重排、问答和笔记生成 |
| 向量化 | 智谱 `embedding-3` 云端 API |
| 向量检索 | Chroma 本地持久化存储 |
| 关键词检索 | jieba 分词、BM25 内存索引 |
| 文档导出 | python-docx |

```text
B 站链接 → 带时间戳的字幕 → 字幕切片 → 向量入库与 BM25 索引
                       └→ 大模型蒸馏 → 摘要、关键词、章节

用户消息 → 意图判断 → CHAT：普通聊天
                  → QA：混合检索 → RRF 融合 → 大模型重排 → 带时间戳的回答
                  → EXPORT：视频素材 / 最近讨论主题 → 笔记生成 → Word 文件
```

未解析视频时直接进入普通聊天。解析后，意图判断只对当前消息分类；聊天和问答分支接收原始提问及历史。导出分支另行判断需要整理整部视频还是结合最近讨论。

## 本机部署

以下步骤用于将前后端部署在同一台电脑上。前端通过 `http://127.0.0.1:8000` 访问后端，请按下面的步骤使用 8000 端口启动后端。

### 1. 准备环境

推荐使用开发时验证过的 **Python 3.13** 和 **Node.js 24**，并确保能访问 B 站和智谱开放平台。

下载或克隆仓库后，进入项目根目录。下文的“项目根目录”指同时包含 `backend/`、`frontend/` 和本 README 的目录，文件夹名称可以不同。

目录结构：

```text
MediaMind/
├── backend/
│   ├── .env             # 唯一配置文件，填写自己的 API Key 和 SESSDATA
│   ├── requirements.txt
│   └── app/
│       ├── main.py      # HTTP 接口
│       ├── config.py    # 配置读取
│       ├── services/    # B 站字幕获取与内容蒸馏
│       ├── rag/         # 切片、向量库、混合检索、重排和问答
│       ├── agent/       # 意图路由与笔记导出
│       └── schemas/     # 请求与响应结构
└── frontend/
    ├── package.json
    ├── package-lock.json
    └── src/
```

### 2. 填写 backend/.env

项目已经提供一个 `backend/.env`，**直接在等号后填写自己的配置即可，无需复制文件或修改源码**。

```dotenv
# 填写自己的智谱 API Key；接口地址和模型通常无需修改。
ZHIPUAI_API_KEY=
ZHIPUAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
ZHIPUAI_MODEL=glm-4.7-flash

# 视频解析请填写有效的 BILIBILI_SESSDATA：登录 B 站后，从浏览器 Cookie 中复制 SESSDATA。
BILIBILI_SESSDATA=
```

| 配置项 | 填写方式 |
| --- | --- |
| `ZHIPUAI_API_KEY` | 在 [智谱开放平台](https://open.bigmodel.cn/) 获取自己的 API Key，项目启动及模型调用需要此项 |
| `ZHIPUAI_BASE_URL` | 保持默认的智谱接口地址即可 |
| `ZHIPUAI_MODEL` | 推荐保持 `glm-4.7-flash` |
| `BILIBILI_SESSDATA` | 使用视频解析功能时填写自己登录 B 站后的有效 SESSDATA |

获取 SESSDATA：

1. 在浏览器中打开并登录 [Bilibili](https://www.bilibili.com/)。
2. 打开开发者工具，在“应用程序 / Application”或“存储 / Storage”中找到 B 站域名下的 Cookie。
3. 找到名称为 `SESSDATA` 的项，只复制它的值，填写到 `BILIBILI_SESSDATA=` 后，不要复制整段 Cookie。

macOS Finder 默认隐藏 `.env`，按 **Command + Shift + .** 可以显示。修改配置后请重启后端。

**模型说明**：推荐使用智谱免费主模型 `glm-4.7-flash`，官方提供免费调用，参见 [发布说明](https://www.zhipuai.cn/zh/news/148) 与 [模型文档](https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash)。视频问答、意图判断、重排及备用调用使用 `glm-4-flash`。向量化使用 `embedding-3`，按照独立的向量接口规则计费或消耗账户额度，参见 [Embedding-3 文档](https://docs.bigmodel.cn/cn/guide/models/embedding/embedding-3)。

仓库中的 API Key 和 Cookie 均为空；上传或公开分享项目时，请保持这两项为空。

### 3. 安装后端依赖

在**项目根目录**创建并激活虚拟环境。macOS / Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

Windows 使用命令提示符（cmd）：

```bat
py -3.13 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r backend/requirements.txt
```

虚拟环境中安装了后端依赖，之后每次启动后端都要使用这个环境的 Python。

### 4. 启动后端

在刚才已激活虚拟环境的终端中，从**项目根目录**进入 `backend`：

```bash
cd backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

看到 `Application startup complete` 后，可以打开：

- [健康检查](http://127.0.0.1:8000/health)：正常时返回 `"status": "healthy"`。
- [API 文档](http://127.0.0.1:8000/docs)：查看解析和聊天接口。

请保持这个终端运行。后端必须从 `backend` 目录启动，才能按上述方式读取 `.env` 并将数据保存到预期目录。`--reload` 用于本机开发时自动重载。

### 5. 启动前端

另开一个终端，进入**项目根目录**，再进入 `frontend`：

```bash
cd frontend
npm ci
npm run dev
```

打开终端中显示的 `Local` 地址，通常为 `http://localhost:5173`。若端口被占用，Vite 可能使用其他端口，以实际输出为准。

首次运行需要 `npm ci` 安装依赖，以后可直接执行 `npm run dev`。前端不需要激活 Python 虚拟环境。使用期间，前后端两个终端都需要保持运行。

## 使用方法

### 普通聊天

打开页面即可发送消息，没有解析视频时按普通聊天处理。有关视频具体内容的问答和笔记导出，需要先解析视频。

输入中文时，回车先确认候选文字；完成选字后再按回车发送，`Shift + Enter` 换行，也可以点击发送按钮。

### 解析视频

1. 点击页面右上角的 **“解析 B 站视频”**。
2. 粘贴带 BV 号的视频完整链接。
3. 提交并等待处理完成，左侧会显示视频摘要、关键词和章节。

请选择带有可用字幕的 B 站视频，项目通过 B 站接口获取字幕进行解析。

### 视频问答与连续追问

解析完成后，可在输入框提问，例如：

```text
请总结这个视频的核心观点。
视频中提到了哪些关键数据？
刚才提到的第二个观点，具体是什么意思？
```

聊天和视频问答最多使用最近 **10 轮完整问答**；历史过长时，后端进一步裁剪到 6000 字符以内。历史用于理解指代和追问，回答仍需依据检索到的视频内容。

点击回答中的时间戳或章节时间，会在新标签页打开 B 站视频的对应位置。

对话上下文用于当前会话；切换视频、清空对话或刷新页面时，会重置上下文。

### 导出 Word 笔记

在视频解析完成后，直接发送导出要求：

```text
请整理本期视频的核心内容，导出为 视频笔记.docx
```

也可以在讨论后，围绕最近的主题导出：

```text
请把我们刚才讨论的问题整理为学习笔记，导出为 讨论笔记.docx
```

整部视频笔记依据全量视频切片生成；讨论笔记结合最近的历史理解主题与要求，并使用视频切片提供事实依据。导出讨论笔记前，先围绕该视频展开对话。

按上述方式启动后端，文档保存在：

```text
backend/data/exports/
```

回复会显示文件名、绝对路径和正文预览。文件保存在**运行后端的电脑**上，可按回复中的路径在文件管理器中打开。

## 数据与文件保存

| 内容 | 保存方式 |
| --- | --- |
| 视频切片与向量 | `backend/data/chroma_db/`，重启后仍保存在磁盘上 |
| BM25 索引 | 后端内存中，重启后清空，每次解析视频时建立 |
| 当前视频与对话 | 前端内存中，刷新页面后重置 |
| 导出的 Word 笔记 | `backend/data/exports/` |

数据目录由后端的工作目录决定，因此请按部署步骤从 `backend` 目录启动。首次运行会自动创建相应目录。发布源码不包含已有的视频切片、个人聊天记录或生成的文档。

## 前端检查

在已安装依赖的 `frontend` 目录执行：

```bash
npm run lint
npm run build
```

这两项分别用于代码检查和前端构建。

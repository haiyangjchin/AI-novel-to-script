# AI 小说转剧本工具

> 将小说文本自动转换为结构化 YAML 剧本，帮助作者快速获得可编辑、可进一步打磨的剧本初稿。

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 预览

| 源码模式 | 场景预览 | 角色关系图 |
|---------|---------|-----------|
| ![源码模式](https://via.placeholder.com/400x250/8B5E3C/FFFFFF?text=YAML+源码) | ![场景预览](https://via.placeholder.com/400x250/C4956A/FFFFFF?text=场景卡片) | ![关系图谱](https://via.placeholder.com/400x250/734D30/FFFFFF?text=关系图谱) |

---

## 目录

- [为什么做这个工具](#为什么做这个工具)
- [功能特性](#功能特性)
- [快速开始](#快速开始)
- [使用指南](#使用指南)
- [技术栈](#技术栈)
- [架构设计](#架构设计)
- [核心解决问题](#核心解决问题)
- [Schema 设计](#schema-设计)
- [项目结构](#项目结构)
- [未来规划](#未来规划)
- [贡献指南](#贡献指南)
- [许可证](#许可证)

---

## 为什么做这个工具

写小说和写剧本是两种不同的思维方式。小说有大量的心理描写、叙述性旁白，而剧本需要的是**可视化的动作、可听见的对白、明确的场景转换**。

一个作者如果想把小说改编成剧本，传统做法是：

1. 通读全文，手动提取每个场景
2. 整理所有出场角色和人物关系
3. 把叙述性文字转换成对白和动作指令

这是极度耗时的过程。这个工具的思路是——**用 AI 来自动化这个流程，把作者从繁琐的格式转换中解放出来**。

---

## 功能特性

### 📝 智能章节检测
- 自动识别「第 X 章」「Chapter X」等章节标记
- 实时统计章节数量和章节标题
- 不足 3 章时自动拦截并提示

### 🤖 AI 剧本转换
- 调用大语言模型，自动提取角色、场景、对白
- **流式输出**：SSE 实时推送，逐字显示转换过程
- **逐章转换**：支持长篇小说分章节处理，避免上下文窗口超限
- 自动合并各章节角色和场景

### 🔧 YAML 智能修复
- 自动修复 LLM 输出中的常见 YAML 语法错误
- Dialogue 内错误的 `actions:` 字段自动过滤
- 同层级重复 mapping key 自动去重
- 前端实时校验 + 后端双端兜底修复

### 👁️ 多维度预览
- **源码模式**：高亮显示 YAML 原始内容，支持在线编辑和实时校验
- **预览模式**：场景卡片式展示（环境描述、动作序列、对白气泡）
- **角色模式**：独立角色卡片（性格、外貌、关系）
- **关系图模式**：力导向图谱可视化角色关系网络（可拖拽节点）

### 📦 数据导出
- **YAML 原始文件**：供进一步程序化编辑
- **Markdown 剧本**：传统剧本格式，适合打印或导入写作软件

### 📋 历史记录
- 本地存储最近 20 次转换记录
- 一键恢复历史转换结果

---

## 快速开始

### 环境要求

- Python 3.10+
- DeepSeek / OpenAI 兼容 API Key

### 安装与运行

```bash
# 1. 克隆仓库
git clone https://github.com/haiyangjchin/AI-novel-to-script.git
cd AI-novel-to-script

# 2. 安装依赖
pip install -r requirements.txt

# 3. 设置 API Key（二选一）
# 方式 A：通过环境变量设置（推荐）
set DEEPSEEK_API_KEY=sk-your-key-here
set DEEPSEEK_BASE_URL=https://api.deepseek.com

# 方式 B：在 Web 界面输入

# 4. 启动服务
python main.py

# 5. 打开浏览器访问
open http://localhost:8000
```

### 可选：切换其他模型

本工具兼容所有 OpenAI 格式的 API，只需修改环境变量：

```bash
# 使用 GPT-4o
set DEEPSEEK_BASE_URL=https://api.openai.com/v1
set LLM_MODEL=gpt-4o

# 使用通义千问
set DEEPSEEK_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
set LLM_MODEL=qwen-plus
```

---

## 使用指南

### 基本流程

```
粘贴小说文本 → 检测章节 → 输入 API Key → 转换为剧本 → 多维度预览 → 导出
```

### 分步说明

**1. 输入文本**：粘贴小说内容（至少 3 章），支持 `.txt` 和 `.docx` 文件上传。

**2. 检测章节**：系统自动识别章节标题，显示章节数量和章节名称。

**3. 设置 API Key**：在界面右上角输入 DeepSeek（或其他兼容模型）的 API Key。

**4. 转换剧本**：

| 场景 | 推荐方式 | 说明 |
|------|---------|------|
| 短篇（3-5 章） | **一键转换** | 一次调用 LLM，流式输出完整剧本 |
| 长篇（5 章以上） | **逐章转换** | 逐章调用 LLM，避免上下文超限，实时显示每章进度 |

**5. 切换预览标签**：

| 标签 | 说明 |
|------|------|
| 源码 | YAML 原始内容，语法高亮，可直接编辑 |
| 预览 | 场景卡片——环境、动作、对白气泡 |
| 角色 | 角色卡片——性格、外貌、关系 |
| 关系图 | 力导向图谱，可拖拽节点交互 |

**6. 导出**：下载 YAML 文件或 Markdown 格式剧本。

---

## 技术栈

| 层级 | 技术选型 | 选型理由 |
|------|---------|---------|
| **Web 框架** | [FastAPI](https://fastapi.tiangolo.com/) | 异步原生，天然支持 SSE 流式输出；Pydantic 集成提供请求/响应校验 |
| **ASGI 服务器** | [Uvicorn](https://www.uvicorn.org/) | FastAPI 官方推荐，高性能 ASGI 实现 |
| **LLM 接入** | [OpenAI SDK](https://github.com/openai/openai-python) | 兼容 DeepSeek / GPT / 通义千问 等，base_url 可配置，模型无关 |
| **数据格式** | [YAML](https://pyyaml.org/) | 可读性优于 JSON，支持注释，Git diff 友好，LLM 输出成功率更高 |
| **前端** | 单文件 HTML + CSS + JS | 零构建步骤，无框架依赖，SSE 原生消费，部署极简 |
| **可视化** | Canvas API | 原生实现力导向图（库伦斥力+弹簧引力+阻尼衰减），无需 D3.js 等重量库 |
| **YAML 解析** | PyYAML（后端）+ js-yaml（前端 CDN） | 两端独立解析，互备兜底 |

### 核心依赖

```
fastapi>=0.100.0     # Web 框架，支持 SSE 流式输出
uvicorn>=0.23.0      # ASGI 服务器
openai>=1.0.0        # LLM 调用（兼容 DeepSeek/GPT 等）
pyyaml>=6.0          # YAML 解析/序列化
python-multipart     # 文件上传支持
python-docx>=1.0.0   # .docx 文件解析
js-yaml@4.1.0        # 前端 YAML 解析（CDN 引入）
```

---

## 架构设计

```
┌──────────────────────┐      SSE 流式响应       ┌──────────────────┐      HTTP POST      ┌─────────────┐
│  浏览器 (单文件HTML)  │ ◄────────────────────  │  FastAPI 后端     │ ◄────────────────  │ LLM API     │
│                      │  data: {"type":"chunk"} │  (main.py)       │                   │ (DeepSeek)  │
│  ● 文本输入          │  data: {"type":"done"}  │                  │                   │             │
│  ● 源码/预览/角色/图  │ ──────────────────────► │  ● /api/convert   │ ─────────────────► │             │
│  ● 力导向图(Canvas)  │  POST JSON              │  ● /api/convert- │                   │             │
│  ● 本地历史记录       │                        │    stream         │                   │             │
│                      │                        │  ● /api/convert-  │                   │             │
│                      │                        │    chapters       │                   │             │
│                      │                        │  ● /api/fix-yaml  │                   │             │
│                      │                        │  ● /api/convert-  │                   │             │
│                      │                        │    markdown       │                   │             │
│                      │                        │  ● /api/settings  │                   │             │
└──────────────────────┘                        └──────────────────┘                   └─────────────┘
```

### 核心工作流

```
用户输入小说文本
        │
        ▼
章节检测 (detect_chapters → 正则匹配"第X章"模式)
        │
        ▼
选择转换方式
   ├── 一键转换 (/api/convert-stream) → LLM 一次生成 → SSE 流式输出
   └── 逐章转换 (/api/convert-chapters) → 逐章 LLM 调用 → 增量合并
        │
        ▼
YAML 修复 (两阶段状态机: Pass1 过滤 + Pass2 去重)
        │
        ▼
前端渲染 (源码高亮 / 场景卡片 / 角色卡片 / 力导向图)
        │
        ▼
导出 (YAML 文件 / Markdown 剧本)
```

---

## 核心解决问题

### 1. LLM 输出 YAML 不合法

**问题**：LLM 混淆 dialogue 级的 `action`（字符串）和 scene 级的 `actions`（数组），且偶尔生成重复 mapping key。

**解决**：两阶段修复状态机

- **Pass 1**：逐行扫描，在 dialogue 上下文内识别并移除 `actions:` 及其子项（支持大小写、引号、注释等变体）
- **Pass 2**：跟踪每个缩进层级的 key，发现重复 key 时跳过该行及所有子行

两端（Python + JS）实现完全相同的修复逻辑，确保前后端解析一致。

### 2. 前后端 YAML 解析不一致

**问题**：后端 PyYAML 容忍重复 key（后出现的覆盖先出现的），前端 js-yaml 遇到重复 key 直接报错崩溃。

**解决**：
- 双端一致的修复逻辑，让修复后的 YAML 在两端的都能通过
- 前端解析失败时自动调后端 `/api/fix-yaml` 接口兜底
- Markdown 导出路径跳过前端校验，直接提交给后端

### 3. 长上下文窗口限制

**问题**：长篇小说文本可能超出 LLM 的上下文窗口（32K-128K tokens）。

**解决**：逐章转换 + 增量合并

- 按章节拆分文本
- 每章独立调用 LLM 转换
- 后台增量合并（角色去重 + 场景重新编号 + meta 合并）
- SSE 实时推送每章进度，即使某章失败也不影响其他章节

---

## Schema 设计

### 核心设计理念

**可读性优先、兼顾工具兼容性**。字段命名采用自然语言全称，结构层次模仿传统剧本格式。

### 简化结构

```yaml
meta:                    # 剧本元信息
  title: "剧本标题"
  source_novel: "原著"
  adapted_by: "AI 改编"

characters:              # 角色表（集中定义，场景中引用 id）
  - id: "CHAR_01"
    name: "角色名"
    role: "主角/配角/反派"
    personality: "性格描述"
    relationships: []

scenes:                  # 场景列表
  - id: "S01"
    location: "场景地点"
    setting: "环境描述"
    actions:             # 场景级动作/描写
      - type: "action"
        content: "动作内容"
    dialogues:           # 对白序列
      - character: "CHAR_01"
        line: "台词原文"
        emotion: "情绪"
        action: "伴随动作"    # 字符串（非数组）
    transition: "CUT TO:"
```

> 完整 Schema 定义见 [`schema/screenplay_schema.md`](schema/screenplay_schema.md)，包含详细的设计决策说明。

### 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 角色数据位置 | 独立数组 + 场景引用 | 避免重复，支持关系图谱，便于检索「某角色出现在哪些场景」 |
| emotions 类型 | 自由文本 | LLM 擅长细粒度描述，枚举会损失"压抑着愤怒的微笑"这类表达 |
| parenthetical | 保留 | 好莱坞剧本格式标准，与 emotion 互补（情绪 vs 表演指引） |
| meta 块 | 顶层字段 | 版本溯源、版权信息、工具兼容 |

---

## 项目结构

```
AI-novel-to-script/
├── main.py                  # FastAPI 后端（API 路由 + 业务逻辑）
├── requirements.txt         # Python 依赖
├── settings.json            # 持久化 API Key（自动生成）
├── README.md                # 项目说明文档
│
├── static/
│   └── index.html           # 单文件前端（CSS + JS 全部内联）
│
├── schema/
│   └── screenplay_schema.md # 剧本 YAML Schema 定义及设计决策
│
└── sample/
    └── novel.txt            # 示例小说文本（用于快速体验）
```

---

## 未来规划

- [ ] **剧本详情页**：新增独立的剧本详情展示页面，完善剧本元信息（如IP名称、场次统计等）的查看与管理
- [ ] **对话式编辑**：在预览/角色界面直接修改角色名、台词、情绪等，所见即所得
- [ ] **多格式导出**：支持导出 Fountain / Final Draft 格式
- [ ] **多轮精修**：让 AI 基于用户反馈反复修改剧本
- [ ] **场景 3D 可视化**：用 Three.js 将场景描述做简单的 3D 空间展示
- [ ] **用户系统**：多用户支持，剧本库云端存储与分享

---

## 贡献指南

欢迎贡献！请遵循以下原则：

1. **每个 PR 只做一件事** — 功能新增、Bug 修复、文档改进各自独立
2. **PR 粒度尽可能小** — 方便 review 和回滚
3. **主分支保持可运行** — 合并前确保 `python main.py` 正常启动
4. **提交信息清晰** — 使用 `feat:` / `fix:` / `docs:` / `refactor:` 前缀

---

## 许可证

[MIT License](LICENSE)

---

<p align="center">
  <b>AI 小说转剧本工具</b> — 用 AI 让创作更高效 ✍️
  <br>
  <a href="https://github.com/haiyangjchin/AI-novel-to-script">GitHub</a>
</p>

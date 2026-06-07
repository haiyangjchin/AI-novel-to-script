import io
import json
import os
import re
import yaml
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from openai import OpenAI

# 项目根目录（main.py 所在目录）
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="AI 小说转剧本工具")

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/sample", StaticFiles(directory=str(BASE_DIR / "sample")), name="sample")

# LLM 客户端（从环境变量读取配置，默认使用 DeepSeek）
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY", "sk-placeholder"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
)
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-chat")


class ConvertRequest(BaseModel):
    novel_text: str
    api_key: str = ""


class ConvertResponse(BaseModel):
    yaml_content: str
    success: bool
    error: str | None = None


SYSTEM_PROMPT = """你是一位资深的剧本分析师，擅长将小说文本转换为专业的结构化剧本。

你需要将用户提供的小说章节内容转换为 YAML 格式的剧本。请严格按照以下规则执行：

1. **角色提取**：识别所有出场角色，为每个角色分配唯一 id（CHAR_01, CHAR_02...），提取姓名、性别、年龄、性格特征、外貌描述，并分析角色之间的关系。
2. **场景划分**：根据地点变化和时间推进划分场景，每个场景包含完整的 actions 和 dialogues。
3. **对话提取**：将原文中的对话逐句提取，标注说话角色、情绪语气、括号说明。原文中的叙述性对话（如"他说：……"）也要转换为直接对话格式。
4. **动作描写**：将原文中的动作和环境描写转换为 actions 数组，保持原文的叙事节奏。
5. **字段归属规则**（非常重要）：
   - `actions`（数组）只出现在 **场景(scene)** 级别，表示场景中的动作/描写序列。
   - `action`（字符串）只出现在 **对话(dialogue)** 级别，表示对白的伴随动作。
   - **严禁**在 dialogue 条目中使用 `actions` 字段，dialogue 中只能用 `action`（单数，字符串类型）。
6. **输出格式**：只输出有效的 YAML，不要有任何额外的解释文字或 markdown 标记。YAML 结构必须符合以下模板：

```yaml
meta:
  title: "剧本标题"
  source_novel: "原著名称"
  author: "原著作者"
  adapted_by: "AI 改编"
  language: "zh"
  version: "1.0"
  created_at: "生成时间"
characters:
  - id: "CHAR_01"
    name: "角色名"
    aliases: []
    gender: "男/女"
    age: "年龄描述"
    role: "主角/配角/反派/龙套"
    personality: "性格特征"
    description: "外貌及背景描述"
    relationships: []
scenes:
  - id: "S01"
    act: 1
    location: "场景地点"
    time: "场景时间"
    setting: "环境描述"
    characters_present: ["CHAR_01"]
    actions:
      - type: "description"
        content: "环境描写内容"
      - type: "action"
        content: "动作描写内容"
    dialogues:
      - character: "CHAR_01"
        line: "台词原文"
        emotion: "正常/激动/低沉/..."
        parenthetical: "表演提示"
        action: "伴随动作"   # 注意：这里是 action（单数，字符串），不是 actions（数组）
    notes: ""
    transition: "CUT TO:"
```

确保 characters 数组中有完整角色信息，scenes 中的 characters_present 引用角色 id，dialogues 中的 character 也引用角色 id。"""


class ChapterInfo(BaseModel):
    index: int
    title: str
    start_pos: int


class ChapterDetectResponse(BaseModel):
    chapters: list[ChapterInfo]
    count: int
    meets_minimum: bool


def fix_yaml_common_errors(raw_yaml: str) -> str:
    """修复 LLM 生成的 YAML 中的常见结构错误

    单 pass 状态机：正向逐行扫描，追踪 dialogue 上下文。
    遇到 dialogue 内的 actions: 时，跳过该行及其所有更深缩进的子项。
    """
    import re

    lines = raw_yaml.split('\n')
    result = []
    in_dialogue = False
    dialogue_indent = 0
    skip_indent = -1  # > 0 时跳过所有缩进更深的行

    for line in lines:
        stripped = line.lstrip()
        indent = len(line) - len(stripped) if stripped else -1

        # 空行保持原样
        if not stripped:
            result.append(line)
            continue

        # 正在跳过 actions 子行
        if skip_indent >= 0:
            if indent > skip_indent:
                continue  # 跳过
            skip_indent = -1  # 缩进回到同级或更浅，停止跳过

        # 检测 dialogue 列表项
        if re.match(r'-\s*character:', stripped):
            in_dialogue = True
            dialogue_indent = indent
            result.append(line)
            continue

        # 检查是否退出 dialogue 块
        if in_dialogue and indent <= dialogue_indent:
            in_dialogue = False

        # 在 dialogue 块内，移除 actions: 及其子项
        if in_dialogue and re.match(r'actions:\s*$', stripped):
            skip_indent = indent  # 标记跳过后续更深缩进的行
            continue

        result.append(line)

    return '\n'.join(result)


CHAPTER_PATTERNS = [
    re.compile(r"^第[一二三四五六七八九十百千\d]+章\b.*", re.MULTILINE),
    re.compile(r"^第[一二三四五六七八九十百千\d]+卷\b.*", re.MULTILINE),
    re.compile(r"^第[一二三四五六七八九十百千\d]+回\b.*", re.MULTILINE),
    re.compile(r"^第[一二三四五六七八九十百千\d]+节\b.*", re.MULTILINE),
    re.compile(r"^(?:Chapter|CHAPTER)\s+\d+\b.*", re.MULTILINE),
]


def detect_chapters(text: str) -> list[ChapterInfo]:
    matches = []
    for pattern in CHAPTER_PATTERNS:
        for m in pattern.finditer(text):
            matches.append((m.start(), m.group().strip()))
    seen = set()
    unique = []
    for pos, title in sorted(matches, key=lambda x: x[0]):
        if pos not in seen:
            seen.add(pos)
            unique.append((pos, title))
    return [
        ChapterInfo(index=i + 1, title=title, start_pos=pos)
        for i, (pos, title) in enumerate(unique)
    ]


@app.get("/")
async def root():
    import time
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/static/index.html?v={int(time.time())}")


@app.post("/api/detect-chapters", response_model=ChapterDetectResponse)
async def detect_chapters_endpoint(req: ConvertRequest):
    """自动识别小说文本中的章节"""
    if not req.novel_text.strip():
        raise HTTPException(status_code=400, detail="小说文本不能为空")
    chapters = detect_chapters(req.novel_text)
    return ChapterDetectResponse(
        chapters=chapters,
        count=len(chapters),
        meets_minimum=len(chapters) >= 3,
    )


@app.post("/api/convert", response_model=ConvertResponse)
async def convert_novel(req: ConvertRequest):
    """将小说文本转换为剧本 YAML"""
    if not req.novel_text.strip():
        raise HTTPException(status_code=400, detail="小说文本不能为空")

    # 检查文本长度（至少需要 3 章小说的基本长度）
    chapters = detect_chapters(req.novel_text)
    if len(chapters) < 3:
        raise HTTPException(status_code=400, detail=f"检测到 {len(chapters)} 章，至少需要 3 章小说内容才能转换")

    # 使用请求中的 API Key，否则回退到环境变量
    api_key = req.api_key.strip() or client.api_key
    if api_key == "sk-placeholder":
        raise HTTPException(status_code=400, detail="请先设置 DeepSeek API Key")

    req_client = OpenAI(api_key=api_key, base_url=str(client.base_url))

    try:
        response = req_client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"请将以下小说内容转换为剧本 YAML：\n\n{req.novel_text}"},
            ],
            temperature=0.3,
            max_tokens=8192,
        )

        raw_output = response.choices[0].message.content.strip()

        # 清理可能的 markdown 代码块标记
        if raw_output.startswith("```"):
            lines = raw_output.split("\n")
            # 去掉第一行（```yaml 或 ```）
            if lines[0].startswith("```"):
                lines = lines[1:]
            # 去掉最后一行（```）
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw_output = "\n".join(lines)

        # 修复 LLM 生成的常见 YAML 错误
        raw_output = fix_yaml_common_errors(raw_output)

        # 验证是否为有效 YAML
        yaml.safe_load(raw_output)

        return ConvertResponse(yaml_content=raw_output, success=True)

    except Exception as e:
        return ConvertResponse(
            yaml_content="",
            success=False,
            error=f"转换失败: {str(e)}",
        )


@app.post("/api/convert-stream")
async def convert_novel_stream(req: ConvertRequest):
    """将小说文本转换为剧本 YAML（SSE 流式输出）"""
    if not req.novel_text.strip():
        raise HTTPException(status_code=400, detail="小说文本不能为空")

    chapters = detect_chapters(req.novel_text)
    if len(chapters) < 3:
        raise HTTPException(status_code=400, detail=f"检测到 {len(chapters)} 章，至少需要 3 章小说内容才能转换")

    api_key = req.api_key.strip() or client.api_key
    if api_key == "sk-placeholder":
        raise HTTPException(status_code=400, detail="请先设置 DeepSeek API Key")

    req_client = OpenAI(api_key=api_key, base_url=str(client.base_url))

    async def generate():
        full_content = ""
        try:
            stream = req_client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"请将以下小说内容转换为剧本 YAML：\n\n{req.novel_text}"},
                ],
                temperature=0.3,
                max_tokens=8192,
                stream=True,
            )

            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    full_content += delta.content
                    yield f"data: {json.dumps({'type': 'chunk', 'content': delta.content})}\n\n"

            # 清理 markdown 代码块
            cleaned = full_content.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines)

            # 修复 LLM 生成的常见 YAML 错误
            cleaned = fix_yaml_common_errors(cleaned)

            # 验证 YAML
            try:
                yaml.safe_load(cleaned)
                yield f"data: {json.dumps({'type': 'done', 'yaml_content': cleaned})}\n\n"
            except yaml.YAMLError as ye:
                yield f"data: {json.dumps({'type': 'done_warn', 'yaml_content': cleaned, 'warning': f'YAML 校验未通过: {str(ye)}'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


CHAPTER_CONVERT_PROMPT = """你是一位资深的剧本分析师，擅长将小说文本转换为专业的结构化剧本。

你需要将用户提供的小说章节内容转换为 YAML 格式的剧本。请严格按照以下规则执行：

1. **角色提取**：识别所有出场角色，为每个角色分配唯一 id（CHAR_01, CHAR_02...），提取姓名、性别、年龄、性格特征、外貌描述，并分析角色之间的关系。
2. **场景划分**：根据地点变化和时间推进划分场景，每个场景包含完整的 actions 和 dialogues。
3. **对话提取**：将原文中的对话逐句提取，标注说话角色、情绪语气、括号说明。
4. **动作描写**：将原文中的动作和环境描写转换为 actions 数组。
5. **字段归属规则**：actions（数组）只在场景级别，action（字符串）只在对话级别。
6. **输出格式**：只输出有效的 YAML，不要有任何额外文字。YAML 结构必须符合以下模板：

characters:
  - id: "CHAR_01"
    name: "角色名"
    aliases: []
    gender: "男/女"
    age: "年龄描述"
    role: "主角/配角/反派/龙套"
    personality: "性格特征"
    description: "外貌及背景描述"
    relationships: []
scenes:
  - id: "S01"
    act: 1
    location: "场景地点"
    time: "场景时间"
    setting: "环境描述"
    characters_present: ["CHAR_01"]
    actions:
      - type: "description"
        content: "环境描写内容"
      - type: "action"
        content: "动作描写内容"
    dialogues:
      - character: "CHAR_01"
        line: "台词原文"
        emotion: "正常/激动/低沉/..."
        parenthetical: "表演提示"
        action: "伴随动作"
    notes: ""
    transition: "CUT TO:"

确保输出的 YAML 可以被 yaml.safe_load 解析。"""


def split_text_by_chapters(text: str, chapters: list[ChapterInfo]) -> list[tuple[str, str]]:
    """将文本按章节拆分，返回 [(chapter_title, chapter_text), ...]"""
    result = []
    for i, ch in enumerate(chapters):
        start = ch.start_pos
        end = chapters[i + 1].start_pos if i + 1 < len(chapters) else len(text)
        chapter_text = text[start:end].strip()
        if chapter_text:
            result.append((ch.title, chapter_text))
    return result


def merge_chapter_yamls(yamls: list[str]) -> str:
    """将多章的 YAML 合并为一个完整的 YAML"""
    all_characters = {}
    all_scenes = []
    meta = {}

    for yml_str in yamls:
        try:
            data = yaml.safe_load(yml_str)
        except Exception:
            continue
        if not data:
            continue

        # 合并 meta（取第一个）
        if not meta and data.get("meta"):
            meta = data["meta"]

        # 合并角色（去重，以 id 为准）
        for c in data.get("characters", []):
            cid = c.get("id", "")
            if cid and cid not in all_characters:
                all_characters[cid] = c

        # 合并场景（重新编号）
        for s in data.get("scenes", []):
            all_scenes.append(s)

    # 重新编号场景 id
    for i, scene in enumerate(all_scenes):
        scene["id"] = f"S{i + 1:02d}"

    merged = {
        "meta": meta or {"title": "合并剧本", "adapted_by": "AI 改编"},
        "characters": list(all_characters.values()),
        "scenes": all_scenes,
    }
    return yaml.dump(merged, allow_unicode=True, default_flow_style=False, sort_keys=False)


@app.post("/api/convert-chapters")
async def convert_chapters_stream(req: ConvertRequest):
    """按章节逐一转换小说文本（SSE 流式输出）"""
    if not req.novel_text.strip():
        raise HTTPException(status_code=400, detail="小说文本不能为空")

    chapters = detect_chapters(req.novel_text)
    if len(chapters) < 3:
        raise HTTPException(status_code=400, detail=f"检测到 {len(chapters)} 章，至少需要 3 章")

    api_key = req.api_key.strip() or client.api_key
    if api_key == "sk-placeholder":
        raise HTTPException(status_code=400, detail="请先设置 DeepSeek API Key")

    req_client = OpenAI(api_key=api_key, base_url=str(client.base_url))
    chapter_texts = split_text_by_chapters(req.novel_text, chapters)

    async def generate():
        try:
            yield f"data: {json.dumps({'type': 'start', 'total': len(chapter_texts)})}\n\n"

            results = []
            for i, (title, text) in enumerate(chapter_texts):
                yield f"data: {json.dumps({'type': 'chapter_start', 'index': i + 1, 'title': title, 'total': len(chapter_texts)})}\n\n"

                try:
                    response = req_client.chat.completions.create(
                        model=LLM_MODEL,
                        messages=[
                            {"role": "system", "content": CHAPTER_CONVERT_PROMPT},
                            {"role": "user", "content": f"请将以下小说章节转换为剧本 YAML：\n\n{text}"},
                        ],
                        temperature=0.3,
                        max_tokens=8192,
                    )

                    raw = response.choices[0].message.content.strip()

                    # 清理 markdown 代码块
                    if raw.startswith("```"):
                        lines = raw.split("\n")
                        if lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        raw = "\n".join(lines)

                    raw = fix_yaml_common_errors(raw)
                    yaml.safe_load(raw)  # 验证
                    results.append(raw)

                    yield f"data: {json.dumps({'type': 'chapter_done', 'index': i + 1, 'title': title, 'yaml': raw})}\n\n"

                except Exception as e:
                    yield f"data: {json.dumps({'type': 'chapter_error', 'index': i + 1, 'title': title, 'error': str(e)})}\n\n"

            # 合并所有章节
            merged = merge_chapter_yamls(results)
            yaml.safe_load(merged)  # 验证合并结果

            yield f"data: {json.dumps({'type': 'done', 'yaml_content': merged, 'chapter_count': len(results)})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/fix-yaml")
async def fix_yaml_endpoint(req: ConvertRequest):
    """修复 LLM 生成的 YAML 中的常见结构错误"""
    fixed = fix_yaml_common_errors(req.novel_text)
    return {"yaml_content": fixed}


def yaml_to_markdown(yaml_content: str) -> str:
    """将 YAML 剧本转换为传统 Markdown 剧本格式"""
    data = yaml.safe_load(yaml_content)
    if not data:
        return ""

    lines = []
    meta = data.get("meta", {})
    title = meta.get("title", "未命名剧本")
    source = meta.get("source_novel", "")
    author = meta.get("author", "")

    # 标题区
    lines.append(f"# {title}")
    lines.append("")
    if source:
        lines.append(f"**原著：** {source}")
    if author:
        lines.append(f"**作者：** {author}")
    lines.append(f"**改编：** {meta.get('adapted_by', 'AI 改编')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 角色表
    characters = data.get("characters", [])
    char_map = {c["id"]: c for c in characters}
    if characters:
        lines.append("## 角色表")
        lines.append("")
        for c in characters:
            role_str = f"（{c.get('role', '')}）" if c.get("role") else ""
            gender_str = f" {c.get('gender', '')}" if c.get("gender") else ""
            age_str = f" {c.get('age', '')}" if c.get("age") else ""
            lines.append(f"- **{c['name']}**{role_str}{gender_str}{age_str}")
            if c.get("personality"):
                lines.append(f"  性格：{c['personality']}")
            if c.get("description"):
                lines.append(f"  描述：{c['description']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # 场景
    scenes = data.get("scenes", [])
    for scene in scenes:
        # 场景标题（slugline 风格）
        location = scene.get("location", "未知地点")
        time_str = scene.get("time", "")
        act = scene.get("act", "")
        scene_id = scene.get("id", "")

        # 场景头
        header = f"### {scene_id}"
        if act:
            header += f" — 第{act}幕"
        lines.append(header)
        lines.append("")

        # Slugline
        slugline = f"**{'INT.' if '内' in location or '室内' in location or '屋' in location or '厅' in location or '房' in location else 'EXT.'} {location}**"
        if time_str:
            slugline += f" — {time_str}"
        lines.append(slugline)
        lines.append("")

        # 环境描写
        if scene.get("setting"):
            lines.append(f"*{scene['setting']}*")
            lines.append("")

        # 出场角色
        if scene.get("characters_present"):
            names = []
            for cid in scene["characters_present"]:
                names.append(char_map[cid]["name"] if cid in char_map else cid)
            lines.append(f"**出场：** {', '.join(names)}")
            lines.append("")

        # 动作和对话交替（按原始顺序）
        actions = scene.get("actions", [])
        dialogues = scene.get("dialogues", [])
        action_idx = 0
        dialogue_idx = 0

        # 为了简化，先输出所有动作，再输出所有对话
        # （更复杂的交织需要额外标记，这里按场景内顺序展示）
        if actions:
            for a in actions:
                content = a.get("content", "")
                a_type = a.get("type", "action")
                if a_type == "description":
                    lines.append(f"*{content}*")
                else:
                    lines.append(content)
                lines.append("")
        if dialogues:
            for d in dialogues:
                char_id = d.get("character", "")
                speaker = char_map[char_id]["name"] if char_id in char_map else char_id
                emotion = d.get("emotion", "")
                parenthetical = d.get("parenthetical", "")
                action = d.get("action", "")
                line = d.get("line", "")

                # 角色名（居中加粗）
                lines.append(f"**{speaker}**" + (f" *（{emotion}）*" if emotion else ""))
                # 括号说明
                if parenthetical:
                    lines.append(f"（{parenthetical}）")
                # 伴随动作
                if action:
                    lines.append(f"*[{action}]*")
                # 台词
                lines.append(f"> {line}")
                lines.append("")

        # 场景备注和转场
        if scene.get("notes"):
            lines.append(f"> 📌 {scene['notes']}")
            lines.append("")
        if scene.get("transition"):
            lines.append(f"**{scene['transition']}**")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


class MarkdownRequest(BaseModel):
    yaml_content: str


@app.post("/api/convert-markdown")
async def convert_markdown(req: MarkdownRequest):
    """将 YAML 剧本转换为 Markdown 格式"""
    if not req.yaml_content.strip():
        raise HTTPException(status_code=400, detail="YAML 内容不能为空")
    try:
        md = yaml_to_markdown(req.yaml_content)
        return {"markdown": md, "success": True}
    except Exception as e:
        return {"markdown": "", "success": False, "error": str(e)}


@app.post("/api/extract-docx")
async def extract_docx(file: UploadFile = File(...)):
    """从 .docx 文件中提取纯文本"""
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="仅支持 .docx 文件")

    try:
        from docx import Document
        content = await file.read()
        doc = Document(io.BytesIO(content))
        text = '\n'.join(p.text for p in doc.paragraphs)
        return {"text": text, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件解析失败: {str(e)}")


# ========== 设置持久化 ==========

SETTINGS_FILE = BASE_DIR / "settings.json"


def _load_settings() -> dict:
    if SETTINGS_FILE.exists():
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_settings(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/api/settings")
async def get_settings():
    settings = _load_settings()
    # 返回时隐藏完整 key，只返回后四位
    api_key = settings.get("api_key", "")
    masked = ("****" + api_key[-4:]) if len(api_key) > 4 else api_key
    return {"api_key_masked": masked, "has_key": bool(api_key)}


@app.post("/api/settings")
async def save_settings(req: ConvertRequest):
    settings = _load_settings()
    if req.api_key:
        settings["api_key"] = req.api_key.strip()
        _save_settings(settings)
    return {"success": True}


@app.get("/api/settings/key")
async def get_api_key():
    """返回完整的 API Key（仅内部使用）"""
    settings = _load_settings()
    return {"api_key": settings.get("api_key", "")}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

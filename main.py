import json
import os
import re
import yaml
from pathlib import Path
from fastapi import FastAPI, HTTPException
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
    """修复 LLM 生成的 YAML 中的常见结构错误"""
    import re

    # 策略：用正则直接移除 dialogue 块中多余的 actions: 及其子项
    # 匹配 actions: 键及其下属的数组项（更深缩进的所有行）
    # 保留原有的 action: 行不动
    def remove_actions_block(match):
        return match.group(0)  # 不修改，仅用于定位

    # 更简洁的策略：逐行扫描，跳过 dialogue 内的 actions: 块
    lines = raw_yaml.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()

        # 检测 actions: 行（缩进 > 0，且不在顶层 scenes 下）
        if re.match(r'^(\s+)actions:\s*$', line):
            indent = len(line) - len(stripped)
            # 判断是否在 dialogue 上下文中：
            # 向前查找，在同缩进或更浅的行中是否有 - character:
            in_dialogue = False
            for j in range(len(result) - 1, -1, -1):
                prev = result[j]
                prev_stripped = prev.lstrip()
                prev_indent = len(prev) - len(prev_stripped)
                if prev_indent < indent:
                    if re.match(r'-\s*character:', prev_stripped):
                        in_dialogue = True
                    break
                if prev_indent == indent and re.match(r'-\s*character:', prev_stripped):
                    in_dialogue = True
                    break

            if in_dialogue:
                # 跳过 actions: 及其所有子行（缩进更深的行）
                i += 1
                while i < len(lines):
                    child = lines[i]
                    child_stripped = child.lstrip()
                    if not child_stripped:
                        i += 1
                        continue
                    child_indent = len(child) - len(child_stripped)
                    if child_indent <= indent:
                        break
                    i += 1
                continue  # 不输出 actions 块

        result.append(line)
        i += 1

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
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


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


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

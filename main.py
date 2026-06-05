import os
import yaml
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
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
5. **输出格式**：只输出有效的 YAML，不要有任何额外的解释文字或 markdown 标记。YAML 结构必须符合以下模板：

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
        action: "伴随动作"
    notes: ""
    transition: "CUT TO:"
```

确保 characters 数组中有完整角色信息，scenes 中的 characters_present 引用角色 id，dialogues 中的 character 也引用角色 id。"""


@app.get("/")
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


@app.post("/api/convert", response_model=ConvertResponse)
async def convert_novel(req: ConvertRequest):
    """将小说文本转换为剧本 YAML"""
    if not req.novel_text.strip():
        raise HTTPException(status_code=400, detail="小说文本不能为空")

    # 检查文本长度（至少需要 3 章小说的基本长度）
    if len(req.novel_text) < 500:
        raise HTTPException(status_code=400, detail="文本太短，请提供至少 3 章的小说内容")

    try:
        response = client.chat.completions.create(
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

        # 验证是否为有效 YAML
        yaml.safe_load(raw_output)

        return ConvertResponse(yaml_content=raw_output, success=True)

    except Exception as e:
        return ConvertResponse(
            yaml_content="",
            success=False,
            error=f"转换失败: {str(e)}",
        )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

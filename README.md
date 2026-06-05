# AI 小说转剧本工具

将小说文本自动转换为结构化剧本（YAML 格式），帮助作者快速获得可编辑、可进一步打磨的剧本初稿。

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

打开 http://localhost:8000 即可使用。

## 功能

- 支持 3 章以上小说文本输入
- AI 自动识别角色、场景、对白
- 输出结构化 YAML 剧本
- Web 界面预览和编辑

## 技术栈

- Python FastAPI 后端
- LLM（OpenAI 兼容 API）
- 单文件 HTML 前端

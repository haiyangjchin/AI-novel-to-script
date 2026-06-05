# 剧本 YAML Schema 定义

## 设计理念

本 Schema 的设计目标是**可读性优先、兼顾工具兼容性**。剧本转换的核心用户是小说作者，他们需要能直接读懂并编辑 YAML 文件，而非依赖专业编剧软件。因此字段命名采用自然语言全称而非缩写，结构层次模仿传统剧本格式（场景 → 动作 → 对白），降低学习成本。

---

## 完整 Schema

```yaml
# ========== 元信息 ==========
meta:
  title: string            # 剧本标题
  source_novel: string     # 原著名称
  author: string           # 原著作者
  adapted_by: string       # 改编者（AI）
  language: string         # 语言（zh/en）
  version: string          # 版本号
  created_at: string       # 生成时间 (ISO 8601)

# ========== 角色列表 ==========
characters:
  - id: string             # 角色唯一标识，如 "CHAR_01"
    name: string           # 角色姓名
    aliases: [string]      # 别名/称呼列表
    gender: string         # 性别
    age: string            # 年龄（可为范围或描述）
    role: string           # 角色定位：主角/配角/反派/龙套
    personality: string    # 性格特征简述
    description: string    # 外貌及背景描述
    relationships:         # 与其他角色的关系
      - target: string     # 目标角色 id
        relation: string   # 关系描述，如 "同事"、"恋人"
        note: string       # 补充说明

# ========== 场景列表 ==========
scenes:
  - id: string             # 场景唯一标识，如 "S01"
    act: integer           # 所属幕（可选，三幕剧中用）
    location: string       # 场景地点
    time: string           # 场景时间（上午/深夜/黄昏）
    setting: string        # 场景环境描述
    characters_present: [string]  # 出场角色 id 列表
    actions:               # 动作/描写序列
      - type: string       # 类型：action（动作）/ description（描写）/ transition（转场）
        content: string    # 内容文本
    dialogues:             # 对白序列
      - character: string  # 说话角色 id
        line: string       # 台词原文
        emotion: string    # 情绪/语气，如 "愤怒"、"低语"
        parenthetical: string  # 括号说明（对表演的提示）
        action: string     # 对白伴随动作（可选）
    notes: string          # 编剧备注
    transition: string     # 转场指示，如 "CUT TO:" / "FADE OUT"
```

---

## 设计决策说明

### 1. 为什么用 YAML 而非 JSON？

- **可读性**：YAML 不需要引号和括号，作者可以直接在文本编辑器中阅读和修改
- **注释支持**：YAML 原生支持 `#` 注释，方便编剧添加备注
- **行业惯例**：剧本工具（如 Fountain）常用缩进式结构，YAML 的缩进语法与其一致
- **Git 友好**：按行缩进，diff 更清晰

### 2. 为什么 actions 和 dialogues 是数组而非自由文本？

- **结构化编辑**：前端可针对每一条动作/对白提供独立的编辑框
- **粒度控制**：AI 可在每条对白上标注情绪和动作，信息密度更高
- **可扩展**：后续可给每条添加时间码、镜头指示等字段

### 3. 为什么 characters 独立于 scenes？

- **避免重复**：角色信息在一处定义，场景中仅引用 id
- **关系建模**：角色关系网是整个故事级别的数据，不应散落在场景中
- **检索便利**：编剧可快速查看"某个角色在哪些场景中出现"

### 4. 为什么 emotion 用自由文本而非枚举？

- **表现力**：演员的情绪表达远比枚举值丰富（"压抑着愤怒的微笑"）
- **AI 友好**：LLM 擅长生成细粒度描述，限制枚举会损失信息
- **渐进约束**：后续可通过可选字段增加标准化标签，不破坏现有结构

### 5. 为什么保留 parenthetical？

- **行业标准**：括号说明是好莱坞剧本格式的组成部分，直接对应
- **表演指导**：表达"讽刺地""低声地"等不改变台词文字的表演提示
- **与 emotion 互补**：emotion 是宏观情绪，parenthetical 是具体表演指引

### 6. 为什么设计 meta 块？

- **版本溯源**：记录 AI 生成版本，方便作者追踪修改历史
- **版权信息**：区分原著信息和改编信息
- **工具兼容**：后续导入其他剧本软件时，元信息可自动填充对应字段

---
name: text2script
description: 输入一句话故事创意、故事梗概、大纲或小说片段（.txt / .md / .docx），单次调用自动完成「文转剧本 + 分镜拆解」，输出带钩子、分镜、运镜、转场与情绪术语的分集剧本与分镜表。适用于把纯文本故事快速变成可拍摄的短剧脚本/分镜，交付 Markdown 或 JSON。
---

# Text To Script（纯文转剧本单点工具）

## 🎯 触发场景 (Usage)

### 适合使用本技能的场景：
- 用户提供了故事文本（一句话创意/梗概/大纲/小说片段），想直接生成短剧剧本 + 分镜表
- 用户描述了一个故事/创意，希望快速看到「拆成几集、每集怎么拍」的完整方案
- 用户需要剧本级别的钩子、冲突句、角色关系，以及分镜级别的景别、运镜、转场、情绪/音调术语
- 用户询问如何把一段纯文本快速变成可拍摄的短剧分镜

### 不适合使用的场景：
- 用户只想讨论剧本结构、不要求产出剧本/分镜文件
- 用户需要生成短剧视频成片（走 `baidu-drama-gen` / 视频生成技能）
- 用户需要的是完整多集小说的文学化改写，而非短剧脚本与分镜（走小说创作技能）
- 用户只有录音/音频素材（本技能不消费音频）

---

## ⚙️ 工作流 (Workflow)

### Step 1：定位输入

从用户消息中确定输入来源，二选一：

- `--text`：直接的故事文本（优先级最高，用户原话中的故事描述）
- `--file`：故事文件绝对路径（支持 `.txt` / `.md` / `.docx`；`.docx` 读取需 `python-docx`）

若用户同时给出文本与文件，以 `--text` 为准；两者都没有，则按「澄清门槛」向用户单次询问故事文本或文件路径。

### Step 2：单次调用完整产出（T17 工作流编排）

```bash
python <skill_dir>/text2script.py \
  --text "<故事创意/梗概/大纲/小说片段>" \
  [--duration <60-90，默认75>] \
  [--shots-per-minute <18-22，默认20>] \
  [--format markdown|json] \
  [--output <结果文件路径>]
```

文件模式：

```bash
python <skill_dir>/text2script.py --file "<path>" [--format json] [--output <path>]
```

单次调用内部自动串联：**输入解析（T06）→ 拆集/钩子（T07）→ 角色关系（T08）→ 分镜拆解（T11-T15）**，直接产出完整分集剧本与分镜表，无需分步调用。

> `<skill_dir>` 为本技能所在目录的绝对路径，执行前替换为实际路径。

### Step 3：读取结果

- stdout 永远是纯内容（Markdown 或 JSON），可直接重定向保存或管道解析
- 信息行（输入类型、集数、长文本分段提示、红线命中、生成提示、自检结果）全部走 stderr
- 用 `--format json` 时，JSON 顶层结构：`input_type` / `input_type_label` / `episodes` / `needs_expansion` / `sensitive_hits` / `warnings`

### Step 4：交付与必要校验

- 若用户需要文件，把 stdout 结果写入 `.md` / `.json` 文件（或用 `--output`）交付
- 校验：分镜自检（`validate_storyboard`）已内置于 stderr；若 stdout 出现"分镜自检发现问题"，需向用户说明具体问题
- 若 stderr 出现红线命中（`⚠ 命中红线类别: ...`），必须在交付说明中提示用户人工确认内容合规性
- 若输出 `needs_expansion=true`（一句话创意），提示用户可先用模板扩写为完整剧本底稿后再拆集

---

## ⚠️ 核心约束 (Guidelines)

- **NEVER** 把信息行打印到 stdout：一律走 stderr，保证 stdout 是纯 Markdown/JSON
- **NEVER** 在工具内部联网：本工具纯本地规则引擎，仅 Python 标准库（`.docx` 读取可选依赖 `python-docx`）
- **NEVER** 跳过红线提示：`sensitive_hits` 命中时必须向用户提示人工复核
- **MUST** 保持枚举约束：景别、运镜、情绪、钩子类型等枚举在 `storyboard.py` 内定义，不新增枚举项
- **MUST** 长文本走分段：清洗后超过 2000 字自动按段切分，stderr 会提示分段数，卡片不做额外截断处理
- **MUST** 空输入兜底：无 `--text/--file`、空文本、文件不存在时给出明确错误并停止，不产出空文档
- **MUST** 保留中文输出：全部内容与提示使用简体中文（文件名/路径除外）

---

## 📦 资源说明

### 产物结构

```
<skill_dir>/
├── text2script.py          ← 唯一入口（T17 工作流编排 + T18 错误处理）
├── input_parser.py         ← T06 输入解析：清洗/类型识别/长文本分段/敏感词
├── episode_splitter.py     ← T07 拆集与钩子：分集/集末钩子/冲突句
├── character_relations.py  ← T08 角色关系：出场人物/关系矩阵
├── storyboard.py           ← T11-T15 分镜拆解：镜头/景别/运镜/转场/情绪术语
├── example.py / example_episodes.py / example_relations.py / example_storyboard.py
│                           ← 各模块独立示例（演示用法）
├── examples/               ← T19 端到端示例（输入 + 输出）
└── README.md               ← 使用说明
```

### 边界说明

- 输入：一句话创意 / 故事梗概 / 大纲 / 小说片段，`.txt` / `.md` / `.docx`
- 输出：Markdown 分集剧本 + 分镜表，或 JSON；单集目标时长 60-90 秒，分镜密度 18-22 镜/分钟
- 不做：视频生成、图片/角色设定图、音频配音、文学化长篇改写（与既有视频/小说技能边界分离）

---

## 🌟 示例 (Example)

**Input:** "帮我把这句话变成短剧剧本和分镜：外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋"

```bash
python <skill_dir>/text2script.py \
  --text "外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋" \
  --format json
```

**stdout（示例节选）：**

```json
{
  "input_type": "one_line",
  "input_type_label": "一句话创意",
  "needs_expansion": true,
  "sensitive_hits": [],
  "warnings": ["输入为一句话创意，建议先按 V1 模板扩写为剧本底稿后再拆集；未定位到明显冲突句，已取首段作为核心冲突，建议人工复核"],
  "episodes": [
    {
      "episode": 1,
      "target_duration": 75,
      "core_conflict": "外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋",
      "episode_hook": "一条关于外卖小哥获得读心术后的新线索突然出现，局面再生变数",
      "hook_type": "新信息",
      "scenes": [{"id": 1, "location": "未注明地点", "time": "日", "setting": "外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋"}],
      "characters": [{"name": "主角", "role": "主角", "description": "线索推动者（待 T08 深化）"}],
      "lines": [{"speaker": "旁白", "tone": "平稳", "text": "外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋"}],
      "shots": [
        {
          "shot": 1,
          "shot_size": "远景",
          "camera": "固定",
          "camera_note": "固定机位",
          "visual": "旁白视角说出\"外卖小哥获得读心术后...\"，镜头以固定机位呈现，位置：未注明地点",
          "dialogue": "【旁白】\"外卖小哥获得读心术后...\"",
          "character": "旁白",
          "emotion": "平静",
          "expression": "神情如常",
          "tone": "平稳",
          "duration": 3,
          "transition": "电影现身开篇"
        }
      ],
      "continuity": [],
      "warnings": [],
      "source_text": "外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋",
      "relations": []
    }
  ]
}
```

**stderr（示例）：**

```
输入类型: 一句话创意 (one_line)
集数: 1
生成提示: 输入为一句话创意，建议先按 V1 模板扩写为剧本底稿后再拆集；...
分镜自检通过：字段完整、枚举合法、密度/时长达标、转场不乱用
================================================================
```
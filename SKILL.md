---
name: text2script
description: 输入一句话故事创意、故事梗概、大纲或小说片段（可上传 .docx/.txt/.md 文件，也可直接粘贴或打字输入），单次调用自动完成「文转剧本 + 分镜拆解」，输出带钩子、分镜、运镜、转场与情绪术语的分集剧本与分镜表。支持纯文字档 .txt 输出（减少不必要标点，超过 800 字按分镜节点分段落），可直接粘贴 AI 动漫工具；也支持 Markdown 表格与 JSON。 ｜ Turn a one-line story idea, synopsis, outline, or novel excerpt (upload a .docx/.txt/.md file, or paste/type directly) into a short-drama script and shot-by-shot storyboard in a single call, complete with hooks, shots, camera moves, transitions, and emotion terminology. It also supports plain-text .txt output (fewer punctuation marks, auto-paragraphed by shot above 800 characters) ready to paste into AI anime tools, as well as Markdown tables and JSON.
---

# Text To Script（纯文转剧本单点工具 ｜ Plain-Text-to-Script Single-Point Tool）

## 🎯 触发场景 ｜ Usage Scenarios

### 适合使用本技能的场景：｜ When to use this skill:

- 用户提供了故事文本（一句话创意/梗概/大纲/小说片段），想直接生成短剧剧本 + 分镜表 ｜ The user provides story text (one-line idea / synopsis / outline / novel excerpt) and wants a short-drama script plus storyboard generated directly.
- 用户上传了故事文件（.docx / .txt / .md），希望一键转成剧本与分镜 ｜ The user uploads a story file (.docx / .txt / .md) and wants it turned into a script and storyboard in one step.
- 用户直接粘贴或打字输入故事文字（普通对话框输入即可），希望快速看到「拆成几集、每集怎么拍」的完整方案 ｜ The user pastes or types the story text (plain chat input is fine) and wants a complete plan showing how many episodes there are and how each one is shot.
- 用户需要剧本级别的钩子、冲突句、角色关系，以及分镜级别的景别、运镜、转场、情绪/音调术语 ｜ The user needs script-level hooks, conflict lines, and character relations, plus storyboard-level shot sizes, camera moves, transitions, and emotion/tone terminology.
- 用户需要可直接粘贴进 AI 动漫工具的纯文字档分镜稿（.txt，无表格装饰、少标点、按分镜分段） ｜ The user needs a plain-text storyboard script (.txt, no table decoration, minimal punctuation, paragraphed by shot) that can be pasted directly into AI anime tools.
- 用户询问如何把一段纯文本快速变成可拍摄的短剧分镜 ｜ The user asks how to quickly turn a piece of plain text into a shootable short-drama storyboard.

### 不适合使用的场景：｜ When NOT to use this skill:

- 用户只想讨论剧本结构、不要求产出剧本/分镜文件 ｜ The user only wants to discuss script structure and does not require script/storyboard files.
- 用户需要生成短剧视频成片（走 `baidu-drama-gen` / 视频生成技能） ｜ The user needs a finished short-drama video (use `baidu-drama-gen` / a video-generation skill instead).
- 用户需要的是完整多集小说的文学化改写，而非短剧脚本与分镜（走小说创作技能） ｜ The user wants a literary rewrite of a full multi-episode novel rather than a short-drama script and storyboard (use a novel-writing skill instead).
- 用户只有录音/音频素材（本技能不消费音频） ｜ The user only has audio/voice recordings (this skill does not consume audio).

---

## ⚙️ 工作流 ｜ Workflow

### Step 1：定位输入（三种方式任选）｜ Step 1: Locate the input (choose any of three ways)

从用户消息中确定输入来源，三选一：｜ Determine the input source from the user's message — pick one of three:

- `--text`：直接粘贴或打字传入的故事文本（优先级最高，用户原话或输入框里的文字） ｜ `--text`: story text pasted or typed directly (highest priority — the user's own words or the text in the input box).
- `--file`：上传的故事文件（支持 `.txt` / `.md` / `.docx`；`.docx` 读取需 `python-docx`） ｜ `--file`: an uploaded story file (supports `.txt` / `.md` / `.docx`; reading `.docx` requires `python-docx`).
- 若用户消息里只有文件：优先取文件路径；同时给出文本与文件时以 `--text` 为准；两者都没有，则按「澄清门槛」向用户单次询问故事文本或文件路径。 ｜ If the message contains only a file, use its path; if both text and a file are given, `--text` wins; if neither is present, ask the user once (per the clarification threshold) for the story text or file path.

### Step 2：单次调用完整产出（T17 工作流编排）｜ Step 2: Full output in a single call (T17 workflow orchestration)

```bash
python <skill_dir>/text2script.py \
  --text "<故事创意/梗概/大纲/小说片段>" \
  [--duration <60-90，默认75>] \
  [--shots-per-minute <18-22，默认20>] \
  [--format markdown|json|text] \
  [--output <结果文件路径>]
```

文件模式（上传的 .docx/.txt/.md）：｜ File mode (uploaded .docx/.txt/.md):

```bash
python <skill_dir>/text2script.py --file "<path>" [--format json] [--output <path>]
```

纯文字档模式（推荐给 AI 动漫工具使用，输出 .txt）：｜ Plain-text mode (recommended for AI anime tools; outputs .txt):

```bash
python <skill_dir>/text2script.py --file "<path>" --format text --output out.txt
```

网页版（可选，用户要求可视化界面时提供）：｜ Web version (optional; provide it when the user asks for a visual interface):

```bash
python -m pip install -r <skill_dir>/web/requirements.txt
python <skill_dir>/web/app.py            # 默认 http://127.0.0.1:5000
```

网页版支持**上传文件 / 拖拽 / 直接粘贴输入**，一键复制或下载纯文字档 .txt；页面顶部「简 / 繁 / EN」切换器可切换**简体中文、繁体中文、英文**界面（首次按浏览器语言自动选择，手动选择本地保存），切换语言不会翻译或改写输入文本与生成内容。 ｜ The web version supports **file upload / drag-and-drop / direct paste**, with one-click copy or download of the plain-text .txt; a 「简 / 繁 / EN」 switcher at the top switches the UI among **Simplified Chinese, Traditional Chinese, and English** (auto-selected from the browser language on first visit, then saved locally once chosen), and switching the language never translates or rewrites the input text or the generated content.

单次调用内部自动串联：**输入解析（T06）→ 拆集/钩子（T07）→ 角色关系（T08）→ 分镜拆解（T11-T15）**，直接产出完整分集剧本与分镜表，无需分步调用。 ｜ A single call automatically chains: **input parsing (T06) → episode splitting / hooks (T07) → character relations (T08) → storyboard breakdown (T11-T15)**, producing the complete episode script and storyboard with no step-by-step calls.

> `<skill_dir>` 为本技能所在目录的绝对路径，执行前替换为实际路径。 ｜ `<skill_dir>` is the absolute path to this skill's directory; replace it with the real path before running.

### Step 3：读取结果 ｜ Step 3: Read the results

- stdout 永远是纯内容（Markdown / JSON / 纯文字档 text），可直接重定向保存或管道解析 ｜ stdout is always pure content (Markdown / JSON / plain text) that can be redirected to a file or piped for parsing.
- 信息行（输入类型、集数、长文本分段提示、红线命中、生成提示、自检结果、text 分段提示）全部走 stderr ｜ Informational lines (input type, episode count, long-text splitting notice, red-line hits, generation notes, self-check results, text-splitting notice) all go to stderr.
- `--format text` 时：输出纯文字档 / .txt；**减少不必要的标点符号**（无表格竖线、台词转成「角色：内容」）；**超过 800 字自动按分镜节点分段落**（每个分镜一段，空行分隔），≤800 字紧凑连排 ｜ With `--format text`: outputs a plain-text .txt; **unnecessary punctuation is reduced** (no table pipes, dialogue becomes 「character: content」); **above 800 characters it auto-paragraphs by shot** (one shot per paragraph, separated by blank lines), while ≤800 characters stay compact.
- 用 `--format json` 时，JSON 顶层结构：`input_type` / `input_type_label` / `episodes` / `needs_expansion` / `sensitive_hits` / `warnings` ｜ With `--format json`, the top-level JSON structure is: `input_type` / `input_type_label` / `episodes` / `needs_expansion` / `sensitive_hits` / `warnings`.

### Step 4：交付与必要校验 ｜ Step 4: Delivery and required checks

- 若用户需要文件，把 stdout 结果写入 `.md` / `.json` / `.txt` 文件（或用 `--output`）交付；`--format text` 输出存成 `.txt` 即为可直接粘贴 AI 动漫工具的文字档 ｜ If the user needs files, write the stdout result into a `.md` / `.json` / `.txt` file (or use `--output`) to deliver it; saving the `--format text` output as `.txt` gives a text script ready to paste into AI anime tools.
- 校验：分镜自检（`validate_storyboard`）已内置于 stderr；若 stdout 出现"分镜自检发现问题"，需向用户说明具体问题 ｜ Checks: storyboard self-check (`validate_storyboard`) is built into stderr; if stdout shows "分镜自检发现问题", explain the specific issues to the user.
- 若 stderr 出现红线命中（`⚠ 命中红线类别: ...`），必须在交付说明中提示用户人工确认内容合规性 ｜ If stderr shows a red-line hit (`⚠ 命中红线类别: ...`), you must remind the user to manually confirm content compliance in the delivery notes.
- 若输出 `needs_expansion=true`（一句话创意），提示用户可先用模板扩写为完整剧本底稿后再拆集 ｜ If the output has `needs_expansion=true` (a one-line idea), suggest expanding it into a full script draft with the template before splitting it into episodes.

---

## ⚠️ 核心约束 ｜ Core Constraints

- **NEVER** 把信息行打印到 stdout：一律走 stderr，保证 stdout 是纯 Markdown/JSON/纯文字 ｜ **NEVER** print informational lines to stdout: always use stderr so stdout stays pure Markdown/JSON/plain text.
- **NEVER** 在工具内部联网：本工具纯本地规则引擎，仅 Python 标准库（`.docx` 读取可选依赖 `python-docx`） ｜ **NEVER** access the network inside the tool: it is a purely local rule engine using only the Python standard library (with optional `python-docx` for reading `.docx`).
- **NEVER** 跳过红线提示：`sensitive_hits` 命中时必须向用户提示人工复核 ｜ **NEVER** skip the red-line notice: when `sensitive_hits` is non-empty, you must prompt the user for manual review.
- **MUST** 保持枚举约束：景别、运镜、情绪、钩子类型等枚举在 `storyboard.py` 内定义，不新增枚举项 ｜ **MUST** keep the enum constraints: enumerations such as shot size, camera move, emotion, and hook type are defined in `storyboard.py`; do not add new enum values.
- **MUST** 长文本走分段：清洗后超过 2000 字自动按段切分，stderr 会提示分段数，卡片不做额外截断处理 ｜ **MUST** split long text: after cleaning, text over 2000 characters is auto-split into segments; stderr reports the segment count, and cards are not additionally truncated.
- **MUST** text 输出按分镜节点分段：输入超过 800 字时以分镜节点（每镜）为段落单位，空行分隔，便于 AI 工具逐镜粘贴 ｜ **MUST** paragraph text output by shot: when input exceeds 800 characters, each shot is its own paragraph separated by blank lines, making it easy to paste into AI tools shot by shot.
- **MUST** 空输入兜底：无 `--text/--file`、空文本、文件不存在时给出明确错误并停止，不产出空文档 ｜ **MUST** handle empty input: with no `--text/--file`, empty text, or a missing file, raise a clear error and stop instead of producing an empty document.
- **MUST** 输入语言匹配输出（v1.2.0）：自动检测输入主要语言——中文输入 → 中文输出，英文输入 → 英文输出；不得把英文输入强行输出成中文，也不得把中文输入译成英文。网页版**界面**三语（简/繁/EN）仅切换 UI 文案，不翻译用户输入或生成内容 ｜ **MUST** match output language to input (v1.2.0): detect the input's primary language automatically — Chinese input → Chinese output, English input → English output; never force English input into Chinese or translate Chinese input into English. The web UI's trilingual interface (Simplified/Traditional/EN) only switches UI copy; it does not translate the user input or the generated content.
- **MUST** text 输出按语言渲染：英文输入时 `--format text` 输出英文分镜稿（`Storyboard script` / `Episode N` / `Narrator` 等英文框架），仍保持纯文字档无表格装饰符号 ｜ **MUST** render text output by language: for English input, `--format text` outputs an English storyboard script (English framework such as `Storyboard script` / `Episode N` / `Narrator`) while still keeping the plain-text format free of table decoration.

---

## 📦 资源说明 ｜ Resources

### 产物结构 ｜ Artifact layout

```
<skill_dir>/
├── text2script.py          ← 唯一入口（T17 工作流编排 + T18 错误处理）｜ Sole entry point (T17 workflow orchestration + T18 error handling)
├── input_parser.py         ← T06 输入解析：清洗/类型识别/长文本分段/敏感词 ｜ T06 input parsing: cleaning / type detection / long-text splitting / sensitive words
├── episode_splitter.py     ← T07 拆集与钩子：分集/集末钩子/冲突句 ｜ T07 episode splitting & hooks: episodes / episode-end hooks / conflict lines
├── character_relations.py  ← T08 角色关系：出场人物/关系矩阵 ｜ T08 character relations: characters / relationship matrix
├── storyboard.py           ← T11-T15 分镜拆解：镜头/景别/运镜/转场/情绪术语 + text 渲染 ｜ T11-T15 storyboard breakdown: shots / shot size / camera moves / transitions / emotion terms + text rendering
├── example.py / example_episodes.py / example_relations.py / example_storyboard.py
│                           ← 各模块独立示例（演示用法）｜ Standalone examples per module (usage demos)
├── examples/               ← T19 端到端示例（输入 + 输出）｜ T19 end-to-end examples (input + output)
├── web/                    ← 网页版（Flask）：上传/粘贴、三语界面、复制/下载 .txt ｜ Web version (Flask): upload/paste, trilingual UI, copy/download .txt
│   ├── app.py              ← Flask 应用（/ 与 /convert，50,000 字上限，10MB 上限）｜ Flask app (/ and /convert, 50,000-character limit, 10 MB limit)
│   ├── requirements.txt    ← flask、python-docx
│   ├── templates/index.html
│   ├── static/style.css
│   ├── static/app.js       ← 前端 + i18n 字典（简体/繁体/英文）+ 输出语言标签 ｜ Front end + i18n dictionary (Simplified/Traditional/English) + output language labels
│   └── test_webapp.py      ← 网页版自测（12 项）｜ Web-version self-test (12 items)
└── README.md               ← 使用说明 ｜ Usage guide
```

### 边界说明 ｜ Scope boundaries

- 输入：一句话创意 / 故事梗概 / 大纲 / 小说片段；文件上传 `.txt` / `.md` / `.docx`，或直接粘贴/打字 `--text` ｜ Input: one-line idea / synopsis / outline / novel excerpt; upload `.txt` / `.md` / `.docx`, or paste/type with `--text`.
- 输出：Markdown 分集剧本 + 分镜表、JSON、或纯文字档 .txt（`--format text`）；单集目标时长 60-90 秒，分镜密度 18-22 镜/分钟 ｜ Output: Markdown episode script + storyboard, JSON, or plain-text .txt (`--format text`); target episode length 60-90 seconds, shot density 18-22 shots/minute.
- 不做：视频生成、图片/角色设定图、音频配音、文学化长篇改写（与既有视频/小说技能边界分离） ｜ Not done here: video generation, images/character design sheets, audio dubbing, literary long-form rewriting (kept separate from the existing video/novel skills).

---

## 🌟 示例 ｜ Example

**输入 (Input):** "帮我把这句话变成短剧剧本和分镜：外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋"

```bash
python <skill_dir>/text2script.py \
  --text "外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋" \
  --format json
```

**stdout（示例节选 / sample excerpt）：**

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

**stderr（示例 / sample）：**

```
输入类型: 一句话创意 (one_line)
集数: 1
生成提示: 输入为一句话创意，建议先按 V1 模板扩写为剧本底稿后再拆集；...
分镜自检通过：字段完整、枚举合法、密度/时长达标、转场不乱用
================================================================
```
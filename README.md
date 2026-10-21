# 纯文转剧本单点工具（text2script） v1.3.0

把**一句话创意 / 故事梗概 / 大纲 / 小说片段**单次转换为**短剧剧本 + 分镜表**的本地规则引擎。支持**上传文件（`.txt` / `.md` / `.docx`）**或**直接粘贴/打字输入故事文字**，输出 Markdown 分集剧本与分镜表、结构化 JSON，或**纯文字档 .txt（可直接粘贴 AI 动漫工具）**。

内部自动串联四段链路，无需分步调用：

```
输入解析（T06）→ 拆集与集末钩子（T07）→ 角色关系（T08）→ 分镜拆解（T11-T15：景别/运镜/转场/情绪/音调术语）
```

## 快速开始

**环境：** Python 3.10+，仅标准库（读取 `.docx` 需额外安装 `python-docx`）。

```bash
# 方式一：直接粘贴 / 打字输入故事文本
python text2script.py --text "外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋"

# 方式二：上传读取故事文件（.txt / .md / .docx）
python text2script.py --file story.txt

# 方式三：输出 JSON，便于程序继续处理
python text2script.py --file story.txt --format json --output story.json

# 方式四：输出纯文字档 .txt（可直接粘贴 AI 动漫工具）
python text2script.py --file story.txt --format text --output story.txt
```

### 网页版

工程附带一个轻量 Flask 网页版（`web/`），支持**上传文件 / 拖拽 / 直接粘贴输入**，并一键复制或下载纯文字档 .txt：

```bash
# 安装依赖（仅网页版需要）
python -m pip install -r web/requirements.txt

# 启动（默认 http://127.0.0.1:5000）
python web/app.py
```

**界面语言（三语）：** 页面顶部提供「简 / 繁 / EN」切换器，可随时切换**简体中文、繁体中文、英文**界面；首次访问按浏览器语言自动选择，手动选择会保存在本机（localStorage），刷新后保持。切换语言只改变界面文案（标题、按钮、提示、状态标签等），**输入文本与生成的分镜稿内容不会被翻译或改写**。

**输入语言匹配（v1.2.0）：** 工具自动检测输入文本的主要语言——**中文输入 → 中文输出，英文输入 → 英文输出**。命令行与网页版均生效：输入含中文（CJK）字符较多时，剧本/分镜/钩子/转场等全部用中文术语与模板输出；输入为英文时，场景、角色、台词、景别、运镜、情绪、转场等全部使用英文术语与模板输出（如 `Episode` / `Core conflict` / `Storyboard table` / `Narrator` / `Wide` / `Close-up`），网页版结果区同时显示「中文输出 / 英文输出」标签。中英文混合文本按字符多数决定输出语言。

**网页版会员（v1.3.0）：** 网页版新增 Email＋密码注册/登录（argon2 密码哈希、短期 JWT＋HttpOnly Refresh Token），登录后每月有转换额度（Free 10 次／Pro 100 次／Studio 500 次，暂定价，正式收费待开发完成十册后依市场调查调整），并提供用量概览与历史记录仪表板；未登录时 `/convert` 会先要求登录。

**来源与转换追踪（v1.3.0）：** 落地页捕捉 UTM 来源并记录转换事件（订阅/注册/登录/转换），登录后可通过 `GET /api/tracking` 查看渠道统计，为冷启动与收费漏斗提供数据。

## 参数说明

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `--text` | 直接粘贴/打字传入故事文本（一句话/梗概/大纲/片段） | 与 `--file` 二选一 |
| `--file` | 上传读取故事文件（`.txt` / `.md` / `.docx`） | 与 `--text` 二选一 |
| `--duration` | 单集目标时长（秒），范围 60–90 | 75 |
| `--shots-per-minute` | 分镜密度（镜/分钟），范围 18–22 | 20 |
| `--format` | 输出格式：`markdown` / `json` / `text` | `markdown` |
| `--output` | 把结果写入文件；省略时输出到 stdout | 无 |

**输出约定：** stdout 只输出内容（Markdown / JSON / text），可直接管道解析；信息行（输入类型、集数、长文本分段提示、红线命中、生成提示、自检结果、text 分段提示）一律走 stderr。

### 纯文字档（--format text）规则

- 输出为 **纯文字档 / .txt**，无 Markdown 表格装饰符号，**减少不必要的标点符号**（台词转成「角色：内容」格式）
- **输入超过 800 字时自动按分镜节点分段落**：每个分镜一段，段间空行，方便 AI 动漫工具逐镜粘贴
- 输入 ≤800 字时紧凑连排，便于直接阅读

## 错误处理（T18）

| 场景 | 行为 |
| --- | --- |
| 未提供 `--text/--file` | 打印用法并退出 |
| `--text` / 文件内容为空 | 提示「输入为空，请提供至少一段故事文本」并退出 |
| 文件不存在 / 读取失败 | 提示具体路径或错误，不产出空文档 |
| 长文本超过约 2000 字 | 自动按段切分，stderr 提示分段数，逐段拆集 |
| 命中红线类别（暴力/擦边等） | stderr 输出红线提示，要求人工复核后继续 |
| 分镜枚举/时长不自检通过 | stderr 输出具体问题列表 |

`.docx` 读取依赖 `python-docx`：`python -m pip install python-docx`。

## 输出内容

**Markdown（默认）：** 分集剧本 + 分镜表。每集包含核心冲突、集末钩子（含钩子类型）、分镜表（镜号/景别/运镜/运镜术语/画面内容/台词/角色/情绪/表情/音调/时长/转场）。

**纯文字档（`--format text`）：** 可直接粘贴 AI 动漫工具的分镜稿，每条分镜包含镜号/景别/运镜/画面/台词/情绪/表情/音调/转场，无表格装饰符号；超过 800 字按分镜节点分段落。

**JSON（`--format json`）：** 顶层结构：

```json
{
  "input_type": "one_line | summary | outline | excerpt",
  "input_type_label": "一句话创意 | 故事梗概 | 大纲/分卷 | 小说片段",
  "language": "zh | en",
  "needs_expansion": true,
  "sensitive_hits": [],
  "warnings": [],
  "episodes": [
    {
      "episode": 1,
      "target_duration": 75,
      "core_conflict": "",
      "episode_hook": "",
      "hook_type": "",
      "scenes": [],
      "characters": [],
      "lines": [],
      "shots": [],
      "continuity": [],
      "warnings": [],
      "source_text": "",
      "relations": []
    }
  ]
}
```

## 目录结构

```
text2script/
├── text2script.py          ← 唯一入口（工作流编排 + 错误处理）
├── input_parser.py         ← T06 输入解析：清洗/类型识别/长文本分段/敏感词
├── episode_splitter.py     ← T07 拆集与钩子：分集/集末钩子/冲突句/台词说话人归属
├── character_relations.py  ← T08 角色关系：出场人物/关系矩阵
├── storyboard.py           ← T11-T15 分镜拆解：镜头/景别/运镜/转场/情绪术语
├── example*.py             ← 各模块独立示例
├── examples/               ← 端到端示例（输入 + 输出，3 组）
├── trials/                 ← T20-T23 真实素材试跑与质量/合规自查记录（10 素材）
├── docs/                   ← 发布/教程/市集上架材料/赞助指引/复盘模板（T24-T28）
├── web/                    ← 网页版（Flask）：上传/粘贴输入、三语界面、复制/下载 .txt
│   ├── app.py              ← Flask 应用（路由 / 与 /convert，50,000 字上限，10MB 文件上限）
│   ├── requirements.txt    ← flask、python-docx
│   ├── templates/index.html
│   ├── static/style.css
│   ├── static/app.js       ← 前端逻辑 + i18n 字典（简体/繁体/英文）+ 输出语言标签
│   └── test_webapp.py      ← 网页版自测（12 项）
├── SKILL.md                ← Skill 封装元数据与触发/执行说明
├── LICENSE                 ← MIT License
├── .gitignore              ← 排除 __pycache__ 与打包产物
└── README.md               ← 本文件
```

## 与周边能力的边界

- **只做文本 → 剧本/分镜**：不生成视频、图片、音频、角色设定图。
- **本地规则引擎**：不联网、不调用外部 AI 服务，仅 Python 标准库（网页版需 Flask；`.docx` 读取需 `python-docx`）。
- **枚举硬约束**：景别、运镜、情绪、钩子类型、场景时段等枚举在 `storyboard.py` 内定义，不随输入新增。
- **输入语言匹配输出**：命令行与网页版按输入语言决定输出语言——中文输入输出简体中文剧本/分镜，英文输入输出英文剧本/分镜；网页版**界面**支持简体/繁体/英文切换（只作用于界面文案，不翻译输入或生成内容）。

## 示例

`examples/` 下提供 3 组端到端示例（输入 → 输出）：

| 示例 | 输入类型 | 输入文件 | 输出文件 |
| --- | --- | --- | --- |
| 1 | 一句话创意 | `input-1-one-line.txt` | `output-1-one-line.md` |
| 2 | 故事梗概 | `input-2-synopsis.txt` | `output-2-synopsis.md` |
| 3 | 大纲/分卷（3 集） | `input-3-outline.txt` | `output-3-outline.md` |

## 测试

```bash
python -m unittest discover -s . -p "test_*.py" -v
```

覆盖：输入解析、拆集、角色关系、分镜拆解、端到端入口（`test_skill.py`）、中英文语言匹配（v1.2.0），核心引擎共 **184 项**。
网页版自测（web/ 下 5 个测试文件）另有 **66 项**：首页/落地页/登录/仪表板渲染、.txt/.md/.docx 上传、
粘贴输入、800 字分段、中英文输出语言匹配、会员登录与额度门控（未登录 401 / 超限 402）、
来源与转换追踪、错误兜底、超大文件 413 等。
真实素材试跑与质量/合规自查记录见 `trials/`（10 个贴近真实短剧/小说场景的素材，
覆盖四种输入类型与红线提示链路，验收指标：拆集成功率 10/10、钩子非空率 100%、
分镜核心字段完整率 100%、红线 7 类全内置命中）。

## 开源与许可

本项目以 **MIT License** 开源（见 [LICENSE](LICENSE)），可自由用于学习、商业与二次开发，仅需保留版权与许可声明。

- **版本：** v1.3.0（`python text2script.py --version`）
- **贡献：** 欢迎提交 Issue / PR；功能边界与枚举硬约束见「与周边能力的边界」。
- **免责声明：** 工具为本地规则引擎，不保证生成内容完全可用；命中红线类别的输出需人工复核后使用。

## 赞助与支持

如果 text2script 帮到了你，欢迎请我们喝杯咖啡，支持持续维护与进阶功能（分镜拆解、提示词工厂、角色一致性）：

- [爱发电](https://afdian.com/a/<你的uid>)（国内推荐，支持月费会员）
- [GitHub Sponsors](https://github.com/sponsors/<你的用户名>)（开源赞助）
- [Patreon](https://www.patreon.com/<你的创作者名>)（海外订阅，可选）

> 配置与验证方法见 [docs/sponsor-guide.md](docs/sponsor-guide.md)。目前为占位链接，待各渠道开通后替换为真实地址。
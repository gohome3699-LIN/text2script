# text2script 使用教程：把小说变成分镜（图文版）

> 适用版本：v1.0.0 ｜ 类型：本地命令行工具（无 GUI） ｜ 环境：Python 3.10+

本教程面向**短剧编剧、小说作者、短视频创作者、AI 工具爱好者**：你手上有一段故事
（一句话创意、梗概、大纲或小说片段），想快速得到「拆成几集、每集怎么拍」的完整方案
——本工具一条命令完成，本文带你 10 分钟上手。

---

## 1. 它能做什么

输入纯文本，输出**分集剧本 + 分镜表**，内部自动串联 4 段链路，无需分步调用：

```
输入解析（类型识别/清洗/红线提示/长文本分段）
  → 拆集与集末钩子
  → 角色关系
  → 分镜拆解（景别/运镜/转场/情绪/音调术语）
```

**会做的：** 一句话创意、故事梗概、大纲/分卷、小说片段 → 分集短剧剧本与分镜表；
**自动匹配输出语言（v1.2.0）**：中文输入 → 中文输出，英文输入 → 英文输出；可输出 Markdown、JSON 或纯文字档 .txt。

**不做的：** 不生成视频、图片、音频；不联网、不调用外部 AI（纯本地规则引擎）。

---

## 2. 安装

环境要求：**Python 3.10+**（只用标准库，无需第三方依赖；读取 `.docx` 需额外安装
`python-docx`）。把工程目录解压后即可使用：

```bash
# 进入工程目录（含 text2script.py 的那一层）
cd text2script

# 验证版本
python text2script.py --version
# → text2script 1.2.0
```

> 想读 Word（`.docx`）输入时，先执行：
> `python -m pip install python-docx`

---

## 3. 快速开始

### 3.1 一句话创意（最快体验）

```bash
python text2script.py --text "外卖小哥获得读心术后，在送餐途中识破一场针对富豪的绑架阴谋"
```

输出到屏幕的是 **Markdown 分集剧本 + 分镜表**；信息行（输入类型、集数、生成提示、
红线提示、自检结果）走 stderr，不影响管道解析。

### 3.2 从文件读取（.txt / .md / .docx）

```bash
python text2script.py --file story.txt
python text2script.py --file 我的小说.docx
```

### 3.3 输出 JSON 便于程序继续处理

```bash
python text2script.py --file story.txt --format json --output story.json
```

JSON 顶层结构：

```json
{
  "input_type": "one_line | summary | outline | excerpt",
  "input_type_label": "一句话创意 | 故事梗概 | 大纲/分卷 | 小说片段",
  "needs_expansion": true,
  "sensitive_hits": [],
  "warnings": [],
  "episodes": [ ... 分集数据 ... ]
}
```

---

## 4. 参数说明

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `--text` | 直接传入故事文本 | 与 `--file` 二选一 |
| `--file` | 读取故事文件（`.txt`/`.md`/`.docx`） | 与 `--text` 二选一 |
| `--duration` | 单集目标时长（秒），60–90 | 75 |
| `--shots-per-minute` | 分镜密度（镜/分钟），18–22 | 20 |
| `--format` | `markdown` 或 `json` | `markdown` |
| `--output` | 结果写入文件，省略则打印到 stdout | 无 |
| `--version` | 打印版本号 | — |

---

## 5. 输入类型：四种都能吃

工具自动识别输入属于哪一类，并对长文本自动分段：

| 类型 | 判定口径 | 典型处理 |
| --- | --- | --- |
| 一句话创意 | ≤60 字且无段落 | 提示先用模板扩写底稿；钩子取核心冲突 |
| 故事梗概 | 60–800 字 | 正常拆集、取冲突句 |
| 小说片段 | >800 字，或含对话段落 | 尽量提取台词并归属说话人 |
| 大纲/分卷 | 行首含「第X卷/章/回」 | 按卷/章拆成多集，每集带钩子 |

> 长文本（清洗后 >2000 字）会自动按段分段，stderr 会提示分段数。

---

## 6. 理解输出：一集里有什么

每集（`episodes[]`）包含：

- `episode` / `target_duration`：集号与目标时长
- `core_conflict`：本集核心冲突句
- `episode_hook` / `hook_type`：集末钩子与类型（悬念/反转/新信息/冲突升级等）
- `scenes[]`：场景（id/地点/时间/内容）
- `characters[]`：出场角色与关系（`relations[]`）
- `lines[]`：台词（说话人/情绪/音调/文本）
- `shots[]`：分镜——每镜含景别、运镜、转场、情绪、表情、音调、时长
- `warnings[]` / `continuity[]`：本集提醒与镜头连续性

**分镜自检**内置于 stderr：字段完整、枚举合法、密度/时长达标、转场不乱用，
出现「分镜自检发现问题」时按提示人工复核。

---

## 7. 红线与合规（重要）

工具内置 7 类红线清单：血腥暴力 / 低俗擦边 / 恐怖灵异 / 封建迷信 / 侮辱群体 /
虚假宣传 / 真人肖像。命中时：

- stderr 打印 `⚠ 命中红线类别: ...（请人工确认后继续）`
- JSON 的 `sensitive_hits` 非空

**必须人工复核后再使用/发布，工具不代替判断。**

---

## 8. 常见问题（FAQ）

**Q1：提示「请提供 --text 或 --file 之一」？**
两条都空。至少给一种输入。

**Q2：提示「读取 .docx 需要 python-docx」？**
执行 `python -m pip install python-docx` 后重试。

**Q3：输入是一句话，明明很短为什么说要扩写？**
一句话创意信息量有限，工具按最优路径先产出 1 集底稿并给出扩写提示；想要更完整的
剧本，建议先写成 60–800 字梗概再跑。

**Q4：我的小说片段里有对话，台词会丢吗？**
不会。工具支持中文引号（“ ” 与「」）对话识别，并尽量把台词归属到对应角色；
无明确说话人的台词保守归旁白。

**Q4.5：我输入的是英文故事，输出会怎样？**
工具自动检测输入语言：英文输入会输出英文剧本与分镜（英文术语与模板，如
`Episode 1` / `Core conflict` / `Narrator` / `Close-up`），不会强行翻译成中文；
中文输入则保持中文输出。

**Q5：为什么有的台词归了「旁白」？**
归属规则只在明确命中已知角色名时关联说话人，命中不了就保守归旁白，避免张冠李戴。

**Q6：能不能直接生成视频？**
不能。本工具只做文本 → 剧本/分镜；成片走视频生成类工具。

**Q7：deliverable 可以是 JSON 吗？**
可以，`--format json --output xxx.json` 即可，适合接脚本/程序。

---

## 9. 进阶用法

### 9.1 批量处理（shell 示例）

```bash
for f in 素材/*.txt; do
  python text2script.py --file "$f" --format json --output "分镜/$(basename "$f" .txt).json"
done
```

### 9.2 直接管道给 jq 取钩子

```bash
python text2script.py --file story.txt --format json \
  | jq -r '.episodes[].episode_hook'
```

### 9.3 回归测试

工程自带 184 项单元测试：

```bash
python -m unittest discover -s . -p "test_*.py"
```

---

## 10. 别忘了

- 输出语言随输入自动匹配（v1.2.0）：中文输入 → 简体中文剧本/分镜，适合国内平台直接使用；英文输入 → 英文剧本/分镜，覆盖海外创作者。
- 本工具是 MIT 开源项目，可自由用于学习、商业与二次开发。
- 想支持作者：见仓库 README 中的赞助说明（GitHub Sponsors / 爱发电 / Patreon）。
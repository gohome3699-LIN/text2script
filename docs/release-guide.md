# text2script GitHub 发布指引（v1.0.0）

按此清单自行把项目发布到 GitHub。总耗时约 10 分钟，全程在浏览器 + 终端完成。

## 0. 准备

- 一个 GitHub 账号（未注册：https://github.com/signup ）
- 本地已安装 git（`git --version` 验证）
- 项目源码已就绪：`text2script/` 目录（含 `LICENSE`、`README.md`、`SKILL.md`、`examples/`、`trials/`、测试文件）

## 1. 在 GitHub 网页创建空仓库

1. 打开 https://github.com/new
2. Repository name 填 `text2script`；可见性选 **Public**
3. **不要**勾选 Add a README / Add .gitignore / Choose a license（本地已带这些文件，避免冲突）
4. 点 Create repository 完成
5. 记下页面给出的仓库地址，形如：`https://github.com/<你的用户名>/text2script.git`

## 2. 本地关联远端并推送

在工程目录（`text2script/` 的上一级，即包含 `text2script/` 的目录）执行：

```bash
cd text2script
git remote add origin https://github.com/<你的用户名>/text2script.git
git branch -M main
git push -u origin main
```

> 若提示要求登录，会弹出浏览器认证窗口，用 GitHub 账号授权即可；也可提前生成
> Personal Access Token（Settings → Developer settings → Fine-grained tokens，勾选
> Contents: Read and write）在提示时粘贴。

## 3. 验证发布成功

1. 浏览器打开 `https://github.com/<你的用户名>/text2script`
2. 确认可见：README 正常渲染、`LICENSE` 显示为 MIT、`examples/` 目录存在
3. 本地执行 `git status` 应显示 `Your branch is up to date`

## 4. 打 Release 标签（推推荐）

```bash
git tag v1.0.0
git push origin v1.0.0
```

然后在 GitHub 仓库页右侧 Releases → Create a new release → 选标签 `v1.0.0`，
标题写 `v1.0.0`，说明可写：

> 纯文转剧本单点工具首个开源版本：一句话/梗概/大纲/小说片段 → 分集剧本 + 分镜表。
> 仅 Python 标准库，本地运行；161 项单元测试通过。

发布即完成。

## 5. 后续观察（对齐 M5 里程碑）

发布后 2 周内观察：**star ≥ 50 或教程播放 ≥ 1 万**（达标即进入付费版/加码决策；
不达标则保留开源版作为流量入口，转向教程与代制作服务）。数据在 T28 运营复盘时汇总。
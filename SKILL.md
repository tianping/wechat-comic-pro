---
name: "wechat-comic-pro"
description: "微信公众号漫画创作器：仅支持中文压标，修复多行文字气泡叠层问题，针对微信 2.35:1 封面与 1:1 正文优化。"
---

# WeChat Comic Pro (微信公众号专业漫画创作器)

专门为微信公众号设计的漫画创作工作流，支持高质量、角色一致的线稿风格漫画创作。

## 核心功能
- **特定比例优化**：自动生成 2.35:1 的公众号大图封面和 1:1 的正文配图。
- **角色一致性**：通过角色锚点（Character Anchors）和固定随机种子确保主角形象统一。
- **中文气泡压标**：基于 Python 的自动化文字压标，支持多行文本自动排版，避免 AI 生成乱码文字。
- **WebP 格式输出**：高质量、低带宽占用，适配公众号上传要求。
- **自动摘要与标签**：生成 `POST_INFO.md`，包含 120 字以内的摘要和 4-5 个优化标签。
- **中间文件保留**：`save_drafts=True`（默认开启）时在项目 `drafts/` 目录保存故事板、画图提示词、角色锚点，方便回溯与迭代。
- **公众号草稿箱发布**：`publish=True` 时自动适配产物并调用 `aws-wechat-article-publish` 的 `publish.py full` 将漫画推入微信公众号草稿箱；未安装该 skill 时安全跳过。
- **多风格支持**：提供热血漫画、经典线稿（Ligne-claire）、赛博朋克、中式水墨等预设。

## 环境要求
- **Python 3**：需安装 `Pillow` 和 `requests`。
- **API 密钥**：在 `openclaw.json` 中配置 NVIDIA NIM (FLUX.1-dev) 或 OpenAI (DALL-E 3)；支持本地 Ollama (x/flux2-klein:latest) 自动检测与优先调用。
- **本地 Ollama (可选)**：若要在本地绘图，请确保 Ollama 已启动且 `x/flux2-klein:latest` 已部署在 `http://127.0.0.1:11434`。可通过 `OLLAMA_HOST` 环境变量配置地址。
- **字体**：系统中需包含 `Noto Sans CJK` 或同等支持中文的字体。

## 执行流程

### 1. 策划与分析
明确核心观点与受众。
- 生成 **Storyboard** (4-8 张正文 + 1 张封面)。
- 定义 **角色锚点** (外貌特征、服装、配色)。

### 2. 风格选择
引导用户选择画风：
- **[A] 热血漫画**：高对比度、速度线、表情夸张。
- **[B] 经典线稿 (Ligne-claire)**：干净的黑边线条，平涂上色（欧漫风格）。
- **[C] 赛博朋克**：霓虹光效、深色背景、高科技感。
- **[D] 极简白描**：简单的线条，纯白背景，聚焦表情。
- **[E] 中式水墨**：传统毛笔笔触，意境深远。

### 3. 图像渲染
使用固定宽高比：
- **封面 (Page 0)**：2.35:1 (例如 1344x572)。
- **正文 (Page 1-N)**：1:1 (例如 1024x1024)。
- 要求 AI **不要生成任何文字或气泡**，保持底图纯净。

### 4. 文字压标与元数据处理
调用 Python 脚本：
- 在指定位置压入中文对话气泡（支持多行自动合并气泡）。
- 将所有图片转换为 `.webp`。
- 生成 `POST_INFO.md`。

## 中间文件保留（Drafts）

`run_workflow()` 默认 `save_drafts=True`，会在项目目录下创建 `drafts/` 文件夹，保存以下中间产物：

| 文件 | 内容 | 来源参数 |
|------|------|----------|
| `prompts.json` | 每页的画图提示词、尺寸、气泡文字、文件路径 | 自动从 `pages_data` 提取 |
| `storyboard.md` | 故事构思、故事线、分镜脚本 | `storyboard` 参数 |
| `character_anchors.md` | 角色锚点定义（外貌、服装、配色） | `character_anchors` 参数 |

调用示例：
```python
run_workflow(
    project_name="my_comic",
    pages_data=[...],
    intro_text="...",
    tags=["#tag1", "#tag2"],
    save_drafts=True,               # 设为 False 可跳过
    storyboard="# 故事构思\n...",    # 故事线 markdown
    character_anchors="# 角色锚点\n...", # 角色定义 markdown
)
```

设为 `save_drafts=False` 则不创建 `drafts/` 目录，行为与旧版一致。

## 公众号草稿箱发布（Publish）

`run_workflow()` 支持 `publish=True` 参数，画图完成后自动：

1. 将 `final/page_0.webp` 复制为项目根 `cover.webp`（封面）；
2. 将 `final/page_1..N.webp` 复制到 `imgs/` 目录（正文配图）；
3. 生成 `article.html`（简单串图 HTML，每张图 `<img>` 标签）；
4. 生成 `article.yaml`（标题、作者、摘要等元数据）；
5. 调用 `aws-wechat-article-publish/scripts/publish.py full` 推入公众号草稿箱。

**前置条件：**
- 已安装 `aws-wechat-article-publish` skill（同 `skills/` 目录下）
- 仓库根有 `aws.env`（`WECHAT_N_APPID` / `WECHAT_N_APPSECRET`）和 `.aws-article/config.yaml`（`publish_method`、微信槽位等）

**未安装时行为：** 检测不到 `publish.py` 时打印警告并跳过，不影响画图流程。

**调用方式：** 画图和发布是两个独立步骤——先跑 `run_workflow()` 生成漫画，检查满意后再调 `publish_to_wechat()` 推草稿箱。

```python
# 第一步：画图
run_workflow(
    project_name="my_comic",
    pages_data=[...],
    intro_text="...",
    tags=["#tag1"],
    save_drafts=True,
    storyboard="# 故事构思\n...",
    character_anchors="# 角色锚点\n...",
)

# 第二步：检查 final/*.webp 满意后，推草稿箱
publish_to_wechat(
    project_dir="my_comic",
    pages_data=[...],
    title="漫画标题",        # ⛔ 含固定前缀"漫画 | "后总长不超过64字符（含字母、数字、标点、空格）
    author="作者名",          # 可选
    digest="120字以内的摘要",     # ⛔ 严格限制：不超过120字符（含字母、数字、标点、空格）
    publish_account=1,       # 可选，微信槽位序号或名称
)
```
```
my_comic/
├── base/            # AI 原始底图
├── final/           # 压标后 WebP
├── drafts/          # 中间文件
├── imgs/            # ← publish 时新增：正文配图
├── article.html     # ← publish 时新增：串图 HTML
├── article.yaml     # ← publish 时新增：发布元数据
├── cover.webp       # ← publish 时新增：封面
└── POST_INFO.md
```

## 脚本参考 (scripts/processor.py)
脚本需包含 `draw_multi_line_bubble` 逻辑以防止文字气泡重叠。

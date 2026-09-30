---
name: ai-website-check-skill
description: 企业官网「AI 可读性」检测工具（B-SiteAgent AI · GooFuture 开源）。当用户要检测某个企业网站被 AI（搜索/问答/智能体）读懂的程度、生成评分与优化报告、或把检测结果提交到 GooFuture 官网公开收录时使用。纯标准库实现，零第三方依赖，可离线本地跑评分与报告，也可一键提交收录。
version: "1.0"
type: website-ai-check
---

# AI 网站检测（B-SiteAgent AI · GooFuture 开源）

本技能把 GooFuture 线上的「企业网站 AI 检测」工具做成可本地运行的开源实现。
它能在用户自己的机器上：

1. **抓取** 目标企业官网首页（带 SSRF 防护、gzip/deflate/br 自动解压）；
2. **评分** 10 个维度的「AI 可读性」，输出 0–100 综合分与评级；
3. **生成报告** 自包含 HTML / Markdown，视觉与官网报告页一致；
4. **提交收录**（可选）把检测结果回传到 GooFuture 官网 `detect.php` 的 `action=save`
   接口，由官网生成公开报告并纳入检测列表，返回公开报告链接与 SKILL 下载链接。

## 适用场景

- 用户说「帮我检测一下 xxx.com 的 AI 可读性 / AI 健康度」；
- 用户想生成一份网站 AI 优化报告或 SKILL.md；
- 用户想把某个网站的检测结果提交到 GooFuture 官网公开收录；
- 任何需要判断「官网是否被 AI 搜索、问答、智能体引用」的 B 端获客 / SEO / GEO 场景。

## 运行环境

- Python 3.8+，纯标准库，无需 `pip install` 任何依赖。
- 本技能目录下的 `ai_check/cli.py` 即可运行（也可以用 `python -m ai_check.cli`）。

## 使用流程

> 命令请在**本技能所在目录**下执行（这样 `ai_check/` 包才能被找到）。
> 若 WorkBuddy 的运行目录不是技能目录，请改用 `python3 <技能绝对路径>/ai_check/cli.py ...`。

### 1）只评分（输出 JSON，适合程序化消费）

```bash
python3 ai_check/cli.py analyze "https://example.com/"
```

返回 JSON：包含 `domain / url / score / dims(10 维) / advice / meta / extra / time`。
`extra` 含 `llms / robots / sitemap / jsonld / text_len` 等「AI 引用基建」探测结果。

### 2）生成报告

```bash
python3 ai_check/cli.py report "https://example.com/" --out ./reports --format both
```

生成 `example.com-report.html` 与 `example.com-report.md`。
HTML 报告的摘要标签（评级 / llms.txt / robots.txt / sitemap.xml / JSON-LD 的「有/无」）
与 GooFuture 官网报告页完全一致。

### 3）评分 + 报告 + 一键提交收录

```bash
# 仅本地生成报告，不提交
python3 ai_check/cli.py check "https://example.com/" --out ./reports

# 本地生成报告，并同时提交到 GooFuture 官网公开收录
python3 ai_check/cli.py check "https://example.com/" --out ./reports --submit
```

提交成功后返回：
- 公开报告页： `https://goofuture.com/company-website-ai-agent/ai-check/reports/{domain}-report.html`
- SKILL 下载： `https://goofuture.com/company-website-ai-agent/ai-check/skill.php?domain={domain}`

> **提交流程约定（避免重复提交）**
> 1. 先用 `check`（不带 `--submit`）跑出分数与本地报告，向用户展示；
> 2. **只问一次**用户「是否公开收录到 GooFuture 官网」；
> 3. 用户同意后，**只执行一次提交**，优先用 `check --submit`（它顺带把本地报告也生成好）。
>    **不要**再单独跑 `submit` 子命令——`submit` 与 `check --submit` 是同一个收录接口，
>    两个都跑会对同一域名产生两次提交（覆盖同一条记录，并触发两次企业微信通知）。
> 4. 工具已内置本地去重：同一域名 10 分钟内重复提交会自动跳过并提示；
>    若确要刷新线上报告（如改站后），加 `--force` 强制重提。

### 4）（可选）带 AI 深度解读

设置环境变量 `DEEPSEEK_API_KEY` 并加 `--ai`，会自动调用 DeepSeek 生成「AI 深度解读」，
本地报告与提交到官网的报告都会包含该解读：

```bash
export DEEPSEEK_API_KEY="你的 DeepSeek Key"
python3 ai_check/cli.py check "https://example.com/" --out ./reports --submit --ai
```

## 重要约定

1. **提交前必须征求用户同意**：把网站数据回传到 GooFuture（第三方）属于对外提交，
   动手 `submit` / `check --submit` 之前，先向用户确认「是否要把这份检测结果公开收录到 GooFuture 官网」。
   确认后**只提交一次**（推荐 `check --submit`，不要 `submit` 与 `check --submit` 都跑）。
2. **不要编造数据**：评分完全由程序对公开页面计算得出；AI 解读由 DeepSeek 生成，
   若解读中出现「作为大模型我不了解这家公司」之类的免责表述，**不要**把它写进给客户的开发信。
3. **本地与官网口径一致**：评分逻辑是 GooFuture 线上 PHP 版本的权威移植，
   本地分数与官网收录分数应当一致；若发现偏差，以本仓库 `ai_check/engine.py` 为基准。
4. 默认不对内网 / 本地 / 保留地址检测（SSRF 防护）。

## 子命令速查

| 命令 | 作用 |
|---|---|
| `analyze <url>` | 抓取 + 评分，输出 JSON |
| `report <url> [--out DIR] [--format html\|md\|both]` | 本地生成报告 |
| `submit <url> [--ai]` | 检测并提交到 GooFuture 收录 |
| `check <url> [--submit] [--ai] [--out DIR]` | 一站式：评分 + 报告 + 可选提交 |

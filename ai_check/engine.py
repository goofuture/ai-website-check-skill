"""程序化评分引擎（10 维 AI 可读性）。

本文件是 GooFuture 线上 PHP 检测逻辑（detect.php / aicheck_lib.php）的权威移植，
保证「本地检测结果」与「GooFuture 官网收录结果」口径一致。
所有函数均为纯逻辑，不触网，方便单元测试与嵌入其它工具。
"""

import html
import re

# ---------------------- 维度名称 / 默认优化建议 ----------------------

DIM_LABEL = {
    "company_info": "企业信息完整度",
    "product_info": "产品信息完整度",
    "ai_understand": "AI 可理解性",
    "structure": "内容结构化",
    "faq": "FAQ 完整度",
    "contact": "联系方式",
    "image": "图片信息识别",
    "document": "PDF / 文档利用",
    "citation": "AI 引用友好度",
    "agent": "Agent 友好度",
}

DIM_TIP = {
    "company_info": "在首屏或「关于我们」用两三句话说清：你是谁、做什么、服务谁，并补上成立时间、地址与资质荣誉。",
    "product_info": "把产品拆成独立页面，写清名称、用途、关键参数与适用场景，并配套真实案例。",
    "ai_understand": "正文内容偏少，AI 难以抽取事实。建议每个核心页面至少 300–500 字的清晰描述，少用图片替代文字。",
    "structure": "用规范的标题层级（H1/H2/H3）组织内容，把并列信息改成列表或表格，方便机器解析。",
    "faq": "增加「常见问题」页面，把客户最常问的 10 个问题写成问答对——这与 AI 问答场景天然匹配。",
    "contact": "明确列出电话、邮箱、地址与在线表单，并保持全站信息一致、可被引用。",
    "image": "给产品图、企业图补上描述性 alt 文字，让 AI 知道图里是什么，而不是 img_01.jpg。",
    "document": "把产品手册、白皮书、规格书以 PDF 等形式公开提供，便于 AI 检索与引用。",
    "citation": "补充结构化数据（JSON-LD）、规范的 meta description，并放置 llms.txt 指引 AI 如何引用你。",
    "agent": "提供 robots.txt、sitemap.xml 与开放接口 / API 文档，让智能体能稳定获取并调用你的信息。",
}

# 维度计算顺序（与线上保持一致）
DIM_ORDER = [
    "company_info", "product_info", "ai_understand", "structure", "faq",
    "contact", "image", "document", "citation", "agent",
]


def dim_label(key):
    return DIM_LABEL.get(key, key)


def dim_tip(key):
    return DIM_TIP.get(key, "持续完善该维度的公开信息。")


def level_word(v):
    if v >= 85:
        return "优秀"
    if v >= 70:
        return "良好"
    if v >= 55:
        return "中等"
    if v >= 40:
        return "偏弱"
    return "较弱"


def _has(html, pattern):
    return re.search(pattern, html, re.IGNORECASE) is not None


def dim_company(html):
    s = 0
    if _has(html, r"关于我们|公司简介|企业简介|about\s*us|aboutus"):
        s += 30
    if _has(html, r"成立于|创立于|创办于|成立时间|始创于"):
        s += 20
    if _has(html, r"地址|总部|位于|广州|北京|上海|深圳|杭州"):
        s += 20
    if _has(html, r"团队|员工|我们的故事|our\s*team|人才招聘|加入我们"):
        s += 15
    if _has(html, r"资质|荣誉|认证|iso|高新技术企业|专利"):
        s += 15
    return min(100, s)


def dim_product(html):
    s = 0
    if _has(html, r"产品中心|产品介绍|产品列表|product|all\s*products"):
        s += 25
    if _has(html, r"解决方案|solution"):
        s += 20
    if _has(html, r"服务|service"):
        s += 15
    if _has(html, r"案例|客户案例|成功案例|customer|client"):
        s += 20
    if _has(html, r"参数|规格|价格|报价|型号|配置"):
        s += 20
    return min(100, s)


def dim_understandable(text):
    length = len(text) if text else 0
    if length <= 0:
        return 0
    return min(100, int(length / 30))  # 约 3000 字满分


def dim_structure(html):
    h = len(re.findall(r"<h[1-3][^>]*>", html, re.IGNORECASE))
    lists = len(re.findall(r"<(ul|ol)[^>]*>", html, re.IGNORECASE))
    tables = len(re.findall(r"<table[^>]*>", html, re.IGNORECASE))
    ps = len(re.findall(r"<p[^>]*>", html, re.IGNORECASE))
    return min(100, h * 8 + lists * 5 + tables * 12 + ps * 2)


def dim_faq(html, text):
    if _has(html, r"常见问题|faq|帮助中心|问答|客服中心"):
        return 90
    q = text.count("？") + text.count("?")
    return min(70, q * 3)


def dim_contact(html):
    s = 0
    if _has(html, r"联系我们|联系方式|contact\s*us|contactus"):
        s += 30
    if re.search(r"(\d{3,4}-?\d{7,8}|\b1[3-9]\d{9}\b)", html):
        s += 25
    if re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", html, re.IGNORECASE):
        s += 25
    if _has(html, r"地址|location|地图|map"):
        s += 20
    return min(100, s)


def dim_image(html):
    imgs = re.findall(r"<img[^>]*>", html, re.IGNORECASE)
    if not imgs:
        return 40  # 首页无图，无法评判
    with_alt = 0
    for tag in imgs:
        m = re.search(r'alt=["\']([^"\']+)["\']', tag, re.IGNORECASE)
        if m and m.group(1).strip():
            with_alt += 1
    return int((with_alt / len(imgs)) * 100)


def dim_document(html):
    c = len(re.findall(r"\.(pdf|docx?|pptx?|xlsx?|txt)(?:[?#\"']|$)", html, re.IGNORECASE))
    return min(100, c * 25)


def dim_citation(html, has_jsonld, llms, sitemap):
    s = 0
    if _has(html, r'<meta[^>]+name=["\']description["\']'):
        s += 20
    if len(re.findall(r'property=["\']og:', html, re.IGNORECASE)) > 0:
        s += 15
    if has_jsonld:
        s += 25
    if llms:
        s += 20
    if sitemap:
        s += 20
    return min(100, s)


def dim_agent(html, robots, sitemap, has_jsonld):
    s = 0
    if robots:
        s += 15
    if sitemap:
        s += 15
    if _has(html, r"api|开放接口|开发者|developer|接口文档|开放平台"):
        s += 25
    if _has(html, r"rss|feed|订阅|atom"):
        s += 15
    if has_jsonld:
        s += 15
    if _has(html, r"mcp|model\s*context\s*protocol"):
        s += 15
    return min(100, s)


def analyze(html, text, has_jsonld, llms, robots, sitemap):
    """返回 (dims: dict, total: int)。"""
    dims = {
        "company_info": dim_company(html),
        "product_info": dim_product(html),
        "ai_understand": dim_understandable(text),
        "structure": dim_structure(html),
        "faq": dim_faq(html, text),
        "contact": dim_contact(html),
        "image": dim_image(html),
        "document": dim_document(html),
        "citation": dim_citation(html, has_jsonld, llms, sitemap),
        "agent": dim_agent(html, robots, sitemap, has_jsonld),
    }
    total = int(round(sum(dims.values()) / len(dims)))
    return dims, total


def build_advice(dims):
    """取最低的 3 项（且 < 70 分）作为优先优化建议。"""
    arr = [
        {"key": k, "name": dim_label(k), "score": min(100, max(0, int(v))), "tip": dim_tip(k)}
        for k, v in dims.items()
    ]
    arr.sort(key=lambda x: x["score"])
    low = [item for item in arr if item["score"] < 70][:3]
    return low


def extract_meta(html, final_url=""):
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    desc = ""
    m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
        html, re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*name=["\']description["\']',
            html, re.IGNORECASE,
        )
    if m:
        desc = m.group(1).strip()
    h1 = len(re.findall(r"<h1[^>]*>", html, re.IGNORECASE))
    return {
        "title": title[:120],
        "description": desc[:200],
        "h1_count": int(h1),
        "viewport": _has(html, r'name=["\']viewport["\']'),
        "html_kb": int(round(len(html) / 1024)),
        "lang": "",
    }


def build_checklist(weak_keys):
    mapping = {
        "company_info": "在「关于我们」补充：公司简介、成立时间、地址、资质荣誉（让 AI 一句话说清你是谁）。",
        "product_info": "把产品 / 服务拆成独立页面，写清名称、用途、关键参数与适用场景，并补充真实案例。",
        "ai_understand": "为核心页面补充 300–500 字清晰正文，避免只用图片传达关键信息。",
        "structure": "规范标题层级（H1/H2/H3），把并列信息改为列表或表格，方便机器解析。",
        "faq": "新增「常见问题 FAQ」页面，整理 10 个客户高频问题写成问答对。",
        "contact": "明确列出电话、邮箱、地址与在线表单，并保持全站信息一致、可被引用。",
        "image": "为产品图、企业图、Logo 补充描述性 alt 文字。",
        "document": "将产品手册、白皮书、规格书以 PDF 形式公开提供。",
        "citation": "补充 JSON-LD 结构化数据、规范的 meta description，并放置 llms.txt。",
        "agent": "提交 sitemap.xml、配置 robots.txt，并考虑开放 API / MCP 以便智能体接入。",
    }
    out = [mapping[k] for k in weak_keys if k in mapping]
    if len(out) < 3:
        out.append("补充首页与核心页面的 meta description（≤120 字，含核心关键词）。")
        out.append("部署 llms.txt，明确告诉 AI 哪些页面值得被引用。")
        out.append("保持内容更新频率，定期发布新品、案例与 FAQ，让 AI 始终读到最新信息。")
    return out


def build_skill_md(domain, result):
    """依据检测结果生成个性化 SKILL.md 文本（与线上 aicheck_lib.php 口径一致）。"""
    domain = str(domain)
    score = int(result.get("score", 0))
    time_str = result.get("time_str", "")
    ai = (result.get("ai_answer") or "").strip()
    dims = result.get("dims", {}) or {}
    advice = result.get("advice", []) or []
    mt = result.get("meta", {}) or {}
    ex = result.get("extra", {}) or {}
    lv = level_word(score)
    site_title = (mt.get("title") or "").strip()

    weak = []
    for k, v in dims.items():
        v = int(v)
        if v < 70:
            weak.append({"key": k, "score": v, "name": dim_label(k)})
    weak.sort(key=lambda x: x["score"])
    weak_keys = [w["key"] for w in weak]

    desc = '%s 官网 AI 可读性优化技能（检测得分 %d/100）。针对该站薄弱维度提供个性化修改方案，可导入 WorkBuddy 或支持 SKILL 的 AI 工具执行。' % (domain, score)

    fm = [
        "name: 网站AI优化-%s" % domain,
        'description: "%s"' % desc.replace('"', "'"),
        'version: "1.0"',
        "type: website-optimization",
        "target_site: %s" % domain,
    ]
    if site_title:
        fm.append('site_title: "%s"' % site_title.replace('"', "'"))
    fm.append("detection_score: %d" % score)
    fm.append("weak_dims: [%s]" % ", ".join(weak_keys))

    md = "---\n" + "\n".join(fm) + "\n---\n\n"
    md += "# 网站 AI 优化技能 · %s\n\n" % domain
    md += ("> 本技能由 GooFuture 网站 AI 检测（B-SiteAgent AI）依据对 %s 的真实检测结果生成，"
           "用于指导该网站提升 AI 可读性（被 AI 搜索、问答与智能体引用的能力）。\n" % domain)
    md += "> 检测时间：%s　综合 AI 健康度：%d/100（评级：%s）。\n\n" % (time_str, score, lv)

    md += "## 1. 检测概要\n"
    md += "- 被测网站：%s\n" % domain
    if site_title:
        md += "- 网站标题：%s\n" % site_title
    md += "- 综合得分：%d/100（%s）\n" % (score, lv)
    md += "- 检测时间：%s\n" % time_str
    if ex:
        md += "- AI 引用基建：llms.txt %s；robots.txt %s；sitemap.xml %s；JSON-LD %s\n" % (
            "有" if ex.get("llms") else "无",
            "有" if ex.get("robots") else "无",
            "有" if ex.get("sitemap") else "无",
            "有" if ex.get("jsonld") else "无",
        )
    if weak:
        md += "- 主要薄弱维度（得分 < 70）：\n"
        for w in weak:
            md += "  - %s：%d 分\n" % (w["name"], w["score"])
    else:
        md += "- 各维度表现良好，无显著薄弱项。\n"
    md += "\n"

    if ai:
        md += "## 2. AI 诊断（DeepSeek 生成）\n\n"
        md += ai + "\n\n"

    md += "## 3. 优先优化清单（按优先级）\n"
    if advice:
        for i, a in enumerate(advice, 1):
            a_name = a.get("name", "")
            a_score = int(a.get("score", 0))
            a_tip = a.get("tip", "")
            md += "%d. **%s（%d 分）**\n" % (i, a_name, a_score)
            md += "   - 问题：该维度得分偏低，影响 AI 对网站「%s」的理解与引用。\n" % a_name
            md += "   - 修改方案：%s\n" % a_tip
    else:
        md += "1. 维持各维度内容的持续更新，定期发布新品、案例与 FAQ，确保 AI 始终读取到最新信息。\n"
    md += "\n"

    checks = build_checklist(weak_keys)
    md += "## 4. 执行检查表\n"
    for c in checks:
        md += "- [ ] %s\n" % c
    md += "\n"

    md += "## 5. 接入与使用\n"
    md += "- 本文件可作为 WorkBuddy 等 AI 助手的 SKILL 导入，按上述清单逐步改站。\n"
    md += "- 改完后可再次运行 GooFuture 网站 AI 检测，对比得分变化。\n"
    md += "- 配合企业 AI 知识库、AI 客服、AI 导购使用，可进一步把优化结果转化为获客与转化能力。\n"
    return md


def build_prompt(domain, url, score, dims, meta, extra):
    """生成投递给 DeepSeek 的提示词（system + user），与线上完全一致。"""
    lines = ""
    for k in DIM_ORDER:
        if k in dims:
            lines += "- %s：%d 分\n" % (dim_label(k), min(100, max(0, int(dims[k]))))
    tech = [
        "页面标题：" + ("「%s」" % meta.get("title", "") if meta.get("title") else "（缺失）"),
        "页面描述：" + ("「%s」" % meta.get("description", "") if meta.get("description") else "（缺失）"),
        "llms.txt：" + ("有" if extra.get("llms") else "无"),
        "robots.txt：" + ("有" if extra.get("robots") else "无"),
        "sitemap.xml：" + ("有" if extra.get("sitemap") else "无"),
        "结构化数据 JSON-LD：" + ("有" if extra.get("jsonld") else "无"),
        "首页正文约 %d 字" % int(extra.get("text_len", 0)),
    ]
    user = (
        "请对下面这个企业官网做一次「AI 可读性」诊断。\n\n"
        "【被测网站】%s（%s）\n"
        "【程序化检测结论】综合 AI 健康度：%d/100\n"
        "分项得分：\n%s\n"
        "【页面技术信息】\n- %s\n\n"
        "请输出一份给企业老板看的诊断报告，严格使用下列 Markdown 结构（不要输出其它一级标题，不要用表格）：\n\n"
        "### 一、AI 眼中的你\n"
        "（作为大模型，你了解这家网站或公司吗？了解就说出你的认知；不了解就如实说明“不了解”，绝不编造营收、客户名、融资金额等具体事实。）\n\n"
        "### 二、这个分数说明什么\n"
        "（2–3 句，结合总分与最弱的两个维度，说明对 AI 搜索、问答与智能体引用的实际影响。）\n\n"
        "### 三、优先改这 3 件事\n"
        "1. **动作名称**：具体怎么改，越可操作越好\n"
        "2. **动作名称**：具体怎么改\n"
        "3. **动作名称**：具体怎么改\n\n"
        "### 四、做完之后的预期\n"
        "（1–2 句，讲清对获客与转化的价值。）\n\n"
        "要求：中文；专业但通俗，让老板一眼看懂；总字数 400–600 字；不要输出与上面结构无关的客套话。"
    ) % (domain, url, score, lines, "\n- ".join(tech))

    system = (
        "你是果创科技（GooFuture）的资深企业网站 AI 化顾问，擅长把技术检测结果翻译成老板能听懂的生意判断。"
        "你客观、严谨，只陈述有依据的内容，对不确定的信息明确说明不知道，绝不编造。"
    )
    return {"system": system, "user": user}

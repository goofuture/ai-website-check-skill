"""报告渲染：自包含 HTML 与 Markdown。

HTML 报告的视觉元素（摘要标签的「有/无」彩色样式、10 维评分条、评级）与
GooFuture 官网报告页保持一致，方便用户对照。
"""

import html

from . import engine

BRAND = "#4f5dff"


def _chip(text, kind=None):
    cls = "chip"
    if kind == "ok":
        cls += " ok"
    elif kind == "no":
        cls += " no"
    elif kind == "level":
        cls += " level"
    return '<span class="%s">%s</span>' % (cls, html.escape(text))


def _dim_class(score):
    if score >= 70:
        return "good"
    if score >= 55:
        return "mid"
    return "low"


def _render_md_inline(s):
    s = html.escape(s)
    s = s.replace("**", "\u0000b\u0000")  # 占位，避免与下面的替换冲突
    # 简单处理：**粗体** 与 `代码`
    import re
    s = re.sub(r"\u0000b\u0000([^\u0000]+?)\u0000b\u0000", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def render_html(r):
    domain = r.get("domain", "")
    title = (r.get("meta", {}).get("title") or "").strip()
    score = int(r.get("score", 0))
    lv = engine.level_word(score)
    dims = r.get("dims", {})
    advice = r.get("advice", [])
    meta = r.get("meta", {})
    extra = r.get("extra", {})
    ai = (r.get("ai_answer") or "").strip()
    time_str = r.get("time_str", "")

    pct = max(0, min(100, score))

    # 摘要标签：评级 → llms → robots → sitemap → JSON-LD → 首页体积 → H1 → 检测时间
    chips = [_chip("评级：%s" % lv, "level")]
    chips.append(_chip("llms.txt %s" % ("有" if extra.get("llms") else "无"),
                       "ok" if extra.get("llms") else "no"))
    chips.append(_chip("robots.txt %s" % ("有" if extra.get("robots") else "无"),
                       "ok" if extra.get("robots") else "no"))
    chips.append(_chip("sitemap.xml %s" % ("有" if extra.get("sitemap") else "无"),
                       "ok" if extra.get("sitemap") else "no"))
    chips.append(_chip("JSON-LD %s" % ("有" if extra.get("jsonld") else "无"),
                       "ok" if extra.get("jsonld") else "no"))
    if meta.get("html_kb"):
        chips.append(_chip("首页约 %d KB" % int(meta["html_kb"])))
    if meta.get("h1_count"):
        chips.append(_chip("H1 × %d" % int(meta["h1_count"])))
    chips.append(_chip("检测时间 %s" % time_str))

    # 维度条
    dim_rows = ""
    for k in engine.DIM_ORDER:
        if k not in dims:
            continue
        v = int(dims[k])
        c = _dim_class(v)
        dim_rows += (
            '<div class="dim">'
            '<div class="dim-head"><span class="dim-name">%s</span>'
            '<span class="dim-score %s">%d</span></div>'
            '<div class="dim-track"><i class="%s" style="width:%d%%"></i></div>'
            '</div>'
        ) % (html.escape(engine.dim_label(k)), c, v, c, v)

    # 建议
    advice_html = ""
    if advice:
        items = ""
        for a in advice:
            items += "<li><strong>%s（%d 分）</strong>：%s</li>" % (
                html.escape(a.get("name", "")), int(a.get("score", 0)),
                html.escape(a.get("tip", "")),
            )
        advice_html = '<div class="advice"><h3>优先优化建议</h3><ul>%s</ul></div>' % items

    ai_html = ""
    if ai:
        ai_html = ('<div class="ai"><h3>AI 深度解读</h3><div class="ai-box">%s</div></div>'
                   % _render_md_inline(ai).replace("\n", "<br>"))

    return """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%s 官网 AI 检测报告（%d 分）</title>
<style>
:root{--brand:%s;--ink:#1f2430;--soft:#6b7280;--line:#e6e8ef;--softbg:#f6f7fb}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--ink);background:#fff;line-height:1.6}
.wrap{max-width:840px;margin:0 auto;padding:28px 20px 60px}
.head{display:flex;gap:22px;align-items:center;border-bottom:1px solid var(--line);padding-bottom:22px}
.ring{flex:0 0 132px;width:132px;height:132px;border-radius:50%;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;background:conic-gradient(var(--brand) %d%%, #e9ebf2 0);position:relative}
.ring::after{content:"";position:absolute;inset:12px;border-radius:50%;background:#fff}
.ring b{position:relative;font-size:38px;line-height:1;z-index:1}
.ring small{position:relative;z-index:1;color:var(--soft);font-size:12px}
.info h1{margin:0 0 4px;font-size:22px}
.info .sub{color:var(--soft);font-size:13px;margin:0 0 10px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{font-size:12.5px;color:var(--soft);background:var(--softbg);border:1px solid var(--line);border-radius:999px;padding:4px 12px}
.chip.ok{color:#0a8f5b;background:#e7f7ef;border-color:#bce9d6}
.chip.no{color:#d23b3b;background:#fdeaea;border-color:#f3c9c9}
.chip.level{color:#7a4bff;background:#f0ecff;border-color:#d9ccff}
.sec{margin-top:30px}
.sec h2{font-size:17px;margin:0 0 14px}
.dim{padding:10px 0;border-bottom:1px solid var(--line)}
.dim-head{display:flex;justify-content:space-between;font-size:14px;margin-bottom:6px}
.dim-score{font-weight:700}
.dim-score.good{color:#0a8f5b}.dim-score.mid{color:#b07d00}.dim-score.low{color:#d23b3b}
.dim-track{height:8px;background:#eef0f5;border-radius:999px;overflow:hidden}
.dim-track i{display:block;height:100%;border-radius:999px}
.dim-track i.good{background:#0a8f5b}.dim-track i.mid{background:#e0a800}.dim-track i.low{background:#d23b3b}
.advice ul{margin:0;padding-left:18px}
.advice li{margin:6px 0}
.ai-box{background:var(--softbg);border:1px solid var(--line);border-radius:12px;padding:14px 16px;font-size:14px}
.note{margin-top:26px;font-size:12px;color:var(--soft);border-top:1px dashed var(--line);padding-top:14px}
a{color:var(--brand)}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div class="ring"><b>%d</b><small>/100</small></div>
    <div class="info">
      <h1>%s</h1>
      <p class="sub">官网 AI 健康度 · 综合 10 个维度 · 评级：%s</p>
      <div class="chips">%s</div>
    </div>
  </div>

  <div class="sec">
    <h2>分项检测结果</h2>
    %s
  </div>

  %s
  %s

  <p class="note">本报告由 GooFuture 开源 AI 网站检测工具生成（B-SiteAgent AI）。检测结果由程序化分析与 AI 参考综合生成，仅供参考。</p>
</div>
</body>
</html>
""" % (
        html.escape(domain), score,
        BRAND,
        pct,
        score, html.escape(domain), html.escape(lv), "".join(chips),
        dim_rows, advice_html, ai_html,
    )


def render_markdown(r):
    domain = r.get("domain", "")
    title = (r.get("meta", {}).get("title") or "").strip()
    score = int(r.get("score", 0))
    lv = engine.level_word(score)
    dims = r.get("dims", {})
    advice = r.get("advice", [])
    meta = r.get("meta", {})
    extra = r.get("extra", {})
    ai = (r.get("ai_answer") or "").strip()
    time_str = r.get("time_str", "")

    lines = []
    lines.append("# %s · 官网 AI 检测报告" % domain)
    if title:
        lines.append("")
        lines.append("> 网站标题：%s" % title)
    lines.append("")
    lines.append("- 综合得分：**%d / 100（%s）**" % (score, lv))
    lines.append("- 检测时间：%s" % time_str)
    lines.append("- AI 引用基建：llms.txt %s；robots.txt %s；sitemap.xml %s；JSON-LD %s" % (
        "有" if extra.get("llms") else "无",
        "有" if extra.get("robots") else "无",
        "有" if extra.get("sitemap") else "无",
        "有" if extra.get("jsonld") else "无",
    ))
    if meta.get("html_kb"):
        lines.append("- 首页体积：约 %d KB" % int(meta["html_kb"]))
    if meta.get("h1_count"):
        lines.append("- H1 标题：%d 个" % int(meta["h1_count"]))
    lines.append("")
    lines.append("## 分项检测结果")
    lines.append("")
    for k in engine.DIM_ORDER:
        if k not in dims:
            continue
        lines.append("- %s：**%d**" % (engine.dim_label(k), int(dims[k])))
    lines.append("")
    if advice:
        lines.append("## 优先优化建议")
        lines.append("")
        for i, a in enumerate(advice, 1):
            lines.append("%d. **%s（%d 分）**：%s" % (
                i, a.get("name", ""), int(a.get("score", 0)), a.get("tip", "")))
        lines.append("")
    if ai:
        lines.append("## AI 深度解读")
        lines.append("")
        lines.append(ai)
        lines.append("")
    lines.append("---")
    lines.append("本报告由 GooFuture 开源 AI 网站检测工具生成（B-SiteAgent AI），仅供参考。")
    return "\n".join(lines)

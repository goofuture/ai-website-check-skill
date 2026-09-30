#!/usr/bin/env python3
"""AI 网站检测 · 命令行入口。

子命令：
  analyze <url>            抓取并评分，输出 JSON 结果（不写文件）
  report  <url> [--out DIR] [--format html|md|both]   生成本地报告
  submit  <url> [--ai]     检测后提交到 GooFuture 官网收录（--ai 需设置 DEEPSEEK_API_KEY）
  check   <url> [--submit] [--out DIR] [--ai]         一站式：评分 + 报告 + 可选提交

零第三方依赖，Python 3.8+ 即可运行。
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request as urllib_request
from datetime import datetime, timezone, timedelta

# 允许以 `python cli.py` 或 `python -m ai_check.cli` 两种方式运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_check import engine, net, report, submit  # noqa: E402

SHANGHAI = timezone(timedelta(hours=8))


def _now_str():
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M")


def _strip_text(html):
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def run_detection(url, with_ai=False, api_key=None):
    url, domain, err = net.normalize_url(url)
    if err:
        return None, err
    html, code, final_url, ferr = net.fetch_body(url)
    if code != 200 or not html:
        return None, "无法访问该网站（HTTP %d）%s" % (code, ("：" + ferr if ferr else ""))

    from urllib.parse import urlparse
    parsed = urlparse(final_url or url)
    scheme = parsed.scheme or "https"
    root = "%s://%s/" % (scheme, parsed.hostname or domain)

    has_jsonld = "application/ld+json" in html.lower()
    llms = net.probe_reachable(root + "llms.txt")
    robots = net.probe_reachable(root + "robots.txt")
    sitemap = net.probe_reachable(root + "sitemap.xml")

    text = _strip_text(html)
    dims, total = engine.analyze(html, text, has_jsonld, llms, robots, sitemap)
    meta = engine.extract_meta(html, final_url)
    extra = {
        "llms": bool(llms),
        "robots": bool(robots),
        "sitemap": bool(sitemap),
        "jsonld": bool(has_jsonld),
        "text_len": len(text),
    }
    advice = engine.build_advice(dims)
    now = int(time.time())
    result = {
        "domain": domain,
        "url": final_url or url,
        "score": total,
        "dims": dims,
        "advice": advice,
        "meta": meta,
        "extra": extra,
        "ai_answer": "",
        "time": now,
        "time_str": _now_str(),
    }

    if with_ai and api_key:
        prompt = engine.build_prompt(domain, result["url"], total, dims, meta, extra)
        ai_text, ai_err = _call_deepseek(prompt, api_key)
        if ai_text:
            result["ai_answer"] = ai_text
        elif ai_err:
            sys.stderr.write("（AI 解读跳过：%s）\n" % ai_err)

    return result, None


def _call_deepseek(prompt, api_key):
    payload = json.dumps({
        "model": "deepseek-flash",
        "messages": [
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": prompt["user"]},
        ],
        "stream": False,
        "max_tokens": 2000,
        "temperature": 0.4,
    }, ensure_ascii=False).encode("utf-8")
    req = urllib_request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=90) as resp:
            j = json.loads(resp.read().decode("utf-8", errors="replace"))
        if j.get("choices", [{}])[0].get("message", {}).get("content"):
            return j["choices"][0]["message"]["content"].strip(), ""
        if j.get("error", {}).get("message"):
            return "", j["error"]["message"]
        return "", "AI 暂不可用"
    except Exception as e:  # noqa: BLE001
        return "", "AI 调用失败：%s" % e


def cmd_analyze(args):
    result, err = run_detection(args.url)
    if err:
        sys.stderr.write("错误：%s\n" % err)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_report(args):
    result, err = run_detection(args.url)
    if err:
        sys.stderr.write("错误：%s\n" % err)
        return 1
    out_dir = args.out or "."
    os.makedirs(out_dir, exist_ok=True)
    domain = result["domain"]
    fmt = args.format
    if fmt in ("html", "both"):
        path = os.path.join(out_dir, "%s-report.html" % domain)
        with open(path, "w", encoding="utf-8") as f:
            f.write(report.render_html(result))
        print("已生成 HTML 报告：%s" % path)
    if fmt in ("md", "both"):
        path = os.path.join(out_dir, "%s-report.md" % domain)
        with open(path, "w", encoding="utf-8") as f:
            f.write(report.render_markdown(result))
        print("已生成 Markdown 报告：%s" % path)
    return 0


def cmd_submit(args):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    result, err = run_detection(args.url, with_ai=args.ai, api_key=api_key)
    if err:
        sys.stderr.write("错误：%s\n" % err)
        return 1
    ok, data, serr = submit.submit_to_goofuture(result, force=args.force)
    if not ok:
        sys.stderr.write("提交失败：%s\n" % serr)
        return 1
    if data.get("skipped"):
        print("（该域名 %s 在 10 分钟内已提交过，已跳过重复提交，未产生重复收录/通知）" % result["domain"])
        print("  报告页：%s" % (data.get("report_url") or ""))
        print("  SKILL：%s" % (data.get("skill_url") or ""))
        return 0
    print("已提交到 GooFuture 官网收录：")
    print("  报告页：%s" % (data.get("report_url") or ""))
    print("  SKILL：%s" % (data.get("skill_url") or ""))
    return 0


def cmd_check(args):
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    result, err = run_detection(args.url, with_ai=args.ai, api_key=api_key)
    if err:
        sys.stderr.write("错误：%s\n" % err)
        return 1
    out_dir = args.out or "."
    os.makedirs(out_dir, exist_ok=True)
    domain = result["domain"]
    hpath = os.path.join(out_dir, "%s-report.html" % domain)
    mpath = os.path.join(out_dir, "%s-report.md" % domain)
    with open(hpath, "w", encoding="utf-8") as f:
        f.write(report.render_html(result))
    with open(mpath, "w", encoding="utf-8") as f:
        f.write(report.render_markdown(result))
    print("综合得分：%d / 100（%s）" % (result["score"], engine.level_word(result["score"])))
    print("网站标题：%s" % (result["meta"].get("title") or "（无）"))
    print("本地报告：%s" % hpath)
    print("本地报告：%s" % mpath)
    if args.submit:
        ok, data, serr = submit.submit_to_goofuture(result, force=args.force)
        if not ok:
            sys.stderr.write("提交失败：%s\n" % serr)
            return 1
        if data.get("skipped"):
            print("（该域名 %s 在 10 分钟内已提交过，已跳过重复提交，未产生重复收录/通知）" % result["domain"])
            print("  报告页：%s" % (data.get("report_url") or ""))
            print("  SKILL：%s" % (data.get("skill_url") or ""))
        else:
            print("已提交到 GooFuture 官网收录：")
            print("  报告页：%s" % (data.get("report_url") or ""))
            print("  SKILL：%s" % (data.get("skill_url") or ""))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="ai-website-check-skill",
        description="GooFuture 开源 AI 网站检测工具（B-SiteAgent AI）",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="抓取并评分，输出 JSON")
    a.add_argument("url")
    a.set_defaults(func=cmd_analyze)

    r = sub.add_parser("report", help="生成本地报告")
    r.add_argument("url")
    r.add_argument("--out", default=".")
    r.add_argument("--format", default="both", choices=["html", "md", "both"])
    r.set_defaults(func=cmd_report)

    s = sub.add_parser("submit", help="检测并提交到 GooFuture 收录")
    s.add_argument("url")
    s.add_argument("--ai", action="store_true", help="使用 DEEPSEEK_API_KEY 生成 AI 解读")
    s.add_argument("--force", action="store_true", help="忽略本地去重，强制重新提交（改站后刷新线上报告用）")
    s.set_defaults(func=cmd_submit)

    c = sub.add_parser("check", help="一站式：评分 + 报告 + 可选提交")
    c.add_argument("url")
    c.add_argument("--out", default=".")
    c.add_argument("--submit", action="store_true", help="同时提交到 GooFuture 收录")
    c.add_argument("--ai", action="store_true", help="使用 DEEPSEEK_API_KEY 生成 AI 解读")
    c.add_argument("--force", action="store_true", help="忽略本地去重，强制重新提交（改站后刷新线上报告用）")
    c.set_defaults(func=cmd_check)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

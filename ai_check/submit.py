"""提交检测结果到 GooFuture 官网进行公开收录。

调用的是线上 detect.php 的 `action=save` 接口（公开、无需令牌），
把本地算好的 score / dims / meta / extra 回传，由官网生成公开报告并纳入列表。
"""

import json
import os
import time
import urllib.parse
import urllib.request

# GooFuture 官网收录接口（如需自建后端，可改成你自己的 detect.php 地址）
GOOFUTURE_SAVE_URL = (
    "https://goofuture.com/company-website-ai-agent/ai-check/detect.php"
)

# 本地提交去重缓存：避免同一会话里被重复提交（例如 AI 先后调用 submit 与 check --submit）。
# 同一域名在 TTL 内再次提交会被跳过，避免对 GooFuture 官网产生重复记录与重复通知。
# 用 --force 可强制重新提交（例如改站后想刷新线上报告）。
_SUBMIT_CACHE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".submit_cache.json"
)
_SUBMIT_TTL = 10 * 60  # 10 分钟


def _load_cache():
    try:
        with open(_SUBMIT_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    try:
        with open(_SUBMIT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass


def submit_to_goofuture(result, base_url=GOOFUTURE_SAVE_URL, timeout=30, force=False):
    """把检测结果提交到 GooFuture 收录。

    参数 result 需包含：domain, url, score, dims, meta, extra, ai_answer(可选)。
    返回 (ok: bool, data: dict|None, error: str)。
    data 可能带 {"skipped": True} 表示命中本地去重、未真正提交。
    """
    domain = result.get("domain", "")

    # 本地去重：同一域名在 TTL 内已提交过则跳过，避免重复 POST（含重复企业微信通知）
    if not force:
        cache = _load_cache()
        last = cache.get(domain)
        if last and (time.time() - float(last.get("t", 0)) < _SUBMIT_TTL):
            return True, {
                "ok": True,
                "skipped": True,
                "report_url": last.get("report_url"),
                "skill_url": last.get("skill_url"),
                "domain": domain,
            }, ""

    payload = {
        "action": "save",
        "domain": domain,
        "url": result.get("url", ""),
        "score": int(result.get("score", 0)),
        "dims": json.dumps(result.get("dims", {}), ensure_ascii=False),
        "meta": json.dumps(result.get("meta", {}), ensure_ascii=False),
        "extra": json.dumps(result.get("extra", {}), ensure_ascii=False),
        "ai_answer": result.get("ai_answer", "") or "",
    }
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url, data=data,
        headers={"User-Agent": "GooFutureAIChecker/1.1", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            code = resp.getcode()
    except Exception as e:  # noqa: BLE001
        return False, None, "提交失败：%s" % e

    try:
        j = json.loads(body)
    except Exception:
        return False, None, "提交返回非 JSON（HTTP %d）：%s" % (code, body[:200])

    if j.get("ok"):
        cache = _load_cache()
        cache[domain] = {
            "t": time.time(),
            "report_url": j.get("report_url"),
            "skill_url": j.get("skill_url"),
        }
        _save_cache(cache)
        return True, j, ""
    return False, j, "提交被拒绝：%s" % (j.get("msg") or "未知错误")

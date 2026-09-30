"""提交检测结果到 GooFuture 官网进行公开收录。

调用的是线上 detect.php 的 `action=save` 接口（公开、无需令牌），
把本地算好的 score / dims / meta / extra 回传，由官网生成公开报告并纳入列表。
"""

import json
import urllib.parse
import urllib.request

# GooFuture 官网收录接口（如需自建后端，可改成你自己的 detect.php 地址）
GOOFUTURE_SAVE_URL = (
    "https://goofuture.com/company-website-ai-agent/ai-check/detect.php"
)


def submit_to_goofuture(result, base_url=GOOFUTURE_SAVE_URL, timeout=30):
    """把检测结果提交到 GooFuture 收录。

    参数 result 需包含：domain, url, score, dims, meta, extra, ai_answer(可选)。
    返回 (ok: bool, data: dict|None, error: str)。
    """
    payload = {
        "action": "save",
        "domain": result.get("domain", ""),
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
        return True, j, ""
    return False, j, "提交被拒绝：%s" % (j.get("msg") or "未知错误")

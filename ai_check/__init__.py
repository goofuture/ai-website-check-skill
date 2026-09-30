"""AI 网站检测 · 开源本地引擎包。

本包是 GooFuture「企业网站 AI 检测（B-SiteAgent AI）」的开源本地实现，
纯标准库、零第三方依赖，可在任意装了 Python 3.8+ 的机器上运行。

主要能力：
  - 抓取企业官网首页（带 SSRF 防护、gzip/deflate/br 解压）；
  - 程序化计算 10 维「AI 可读性」评分；
  - 生成自包含 HTML / Markdown 报告；
  - 可选地把检测结果提交到 GooFuture 官网进行公开收录。
"""

__version__ = "1.0.0"

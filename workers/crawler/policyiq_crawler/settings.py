BOT_NAME = "policyiq_crawler"

SPIDER_MODULES = ["policyiq_crawler.spiders"]
NEWSPIDER_MODULE = "policyiq_crawler.spiders"

# Identify honestly with a contact point, per docs/04-CRAWLER-STRATEGY.md -
# the goal is to be reachable if an insurer wants to talk to us, not to
# blend in with browser traffic. Replace the contact URL before any real
# production crawl.
USER_AGENT = (
    "PolicyIQNZBot/0.1 (+https://policyiq.nz/about-our-crawler; "
    "contact: crawler@policyiq.nz)"
)

ROBOTSTXT_OBEY = True

# Polite by default; per-insurer DOWNLOAD_DELAY override comes from
# registry.InsurerSeed.crawl_policy (see spiders/policy_document_spider.py).
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 2.0

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0

DEPTH_LIMIT = 4

# Not set anywhere before today - Scrapy's 180s default alone caused an
# 18-minute hang against a WAF-protected site (180s x 3 retries x 2 URLs)
# with zero documents to show for it. Bounded timeout lets RETRY_TIMES
# actually do its job in reasonable wall-clock time instead of accumulating
# into double-digit-minute stalls.
DOWNLOAD_TIMEOUT = 60

ITEM_PIPELINES = {
    "policyiq_crawler.pipelines.DedupeWithinRunPipeline": 100,
}

RETRY_ENABLED = True
RETRY_TIMES = 2

HTTPCACHE_ENABLED = False  # Downloader worker owns caching/versioning, not the crawler

LOG_LEVEL = "INFO"

# Playwright fallback for JS-rendered nav (see policy_document_spider.py's
# _extract_links) - per-request opt-in via meta={"playwright": True}, so
# every other request is completely unaffected by this.
DOWNLOAD_HANDLERS = {
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}  # no stealth/fingerprint args, ever
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 45_000  # ms

# scrapy-playwright does NOT read USER_AGENT above automatically - that
# setting only feeds Scrapy's own UserAgentMiddleware, which the Playwright
# download handler bypasses entirely. Without this, the browser would
# silently send its own default Chromium UA instead of our honest bot UA.
PLAYWRIGHT_CONTEXTS = {"default": {"user_agent": USER_AGENT}}


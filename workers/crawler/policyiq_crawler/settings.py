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

ITEM_PIPELINES = {
    "policyiq_crawler.pipelines.DedupeWithinRunPipeline": 100,
}

RETRY_ENABLED = True
RETRY_TIMES = 2

HTTPCACHE_ENABLED = False  # Downloader worker owns caching/versioning, not the crawler

LOG_LEVEL = "INFO"

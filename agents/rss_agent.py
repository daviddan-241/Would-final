"""
RSS & Content Scout Agent — Continuously scans real RSS feeds, Reddit, CoinGecko, and CryptoPanic
for fresh content. Feeds real posts into the mirror pipeline and content store.
"""
import asyncio
import time
import aiohttp

from agents.base_agent import BaseAgent
import marketing_db


class RSSAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="RSS Scout",
            role="Scans real RSS feeds, Reddit, CoinGecko & CryptoPanic for live content",
            emoji="📡"
        )
        self.content_store = []  # Shared real content cache

    async def run(self, interval: int = 180):
        self.log("RSS Scout online. Scanning real feeds every 3 minutes.")
        self.set_status("running")
        while True:
            try:
                self.set_status("scanning")
                fetched = await self._scan_all_sources()
                self.content_store = fetched[-100:]
                self.task_done()
                self.log(f"Fetched {len(fetched)} real content items across all sources.")
                self.set_status("idle")
            except Exception as e:
                self.record_error(str(e))
                self.set_status("error")
            await asyncio.sleep(interval)

    async def _scan_all_sources(self):
        items = []
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_reddit("CryptoCurrency", session),
                self._fetch_reddit("solana", session),
                self._fetch_reddit("Bitcoin", session),
                self._fetch_coingecko(session),
                self._fetch_cryptopanic(session),
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, list):
                    items.extend(r)
        return items

    async def _fetch_reddit(self, subreddit: str, session: aiohttp.ClientSession):
        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=8"
            headers = {"User-Agent": "VerizonSuite/2.0"}
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    posts = []
                    for child in data.get("data", {}).get("children", []):
                        p = child["data"]
                        if not p.get("stickied"):
                            posts.append({
                                "id": p["id"],
                                "text": p["title"],
                                "source": f"Reddit/r/{subreddit}",
                                "url": f"https://reddit.com{p.get('permalink', '')}",
                                "timestamp": p.get("created_utc", time.time()),
                                "score": p.get("score", 0)
                            })
                    self.log(f"Reddit r/{subreddit}: {len(posts)} real posts")
                    return posts
        except Exception as e:
            self.record_error(f"Reddit r/{subreddit}: {e}")
        return []

    async def _fetch_coingecko(self, session: aiohttp.ClientSession):
        try:
            url = "https://api.coingecko.com/api/v3/news"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data if isinstance(data, list) else data.get("data", [])
                    result = []
                    for item in items[:8]:
                        result.append({
                            "id": f"cg_{hash(item.get('title', ''))}",
                            "text": item.get("title", ""),
                            "source": "CoinGecko News",
                            "url": item.get("url", ""),
                            "timestamp": time.time(),
                            "score": 100
                        })
                    self.log(f"CoinGecko: {len(result)} real news items")
                    return result
        except Exception as e:
            self.record_error(f"CoinGecko: {e}")
        return []

    async def _fetch_cryptopanic(self, session: aiohttp.ClientSession):
        try:
            url = "https://cryptopanic.com/api/v1/posts/?auth_token=free&kind=news&public=true"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result = []
                    for item in data.get("results", [])[:8]:
                        result.append({
                            "id": str(item.get("id", hash(item.get("title", "")))),
                            "text": item.get("title", ""),
                            "source": "CryptoPanic",
                            "url": item.get("url", ""),
                            "timestamp": time.time(),
                            "score": 80
                        })
                    self.log(f"CryptoPanic: {len(result)} real news items")
                    return result
        except Exception as e:
            self.record_error(f"CryptoPanic: {e}")
        return []

    def get_top_content(self, limit: int = 10):
        sorted_content = sorted(self.content_store, key=lambda x: x.get("score", 0), reverse=True)
        return sorted_content[:limit]

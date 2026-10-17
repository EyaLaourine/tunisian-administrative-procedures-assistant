"""robots.txt policy checks, including AI-usage opt-out signals."""

import logging
from dataclasses import dataclass
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)


@dataclass
class RobotsDecision:
    allowed: bool
    reason: str
    crawl_delay: float | None = None


class RobotsPolicy:
    """Caches one parsed robots.txt per host and answers fetch-permission questions."""

    def __init__(self, client: httpx.Client, user_agent: str, ai_optout_agents: list[str]):
        self._client = client
        self._user_agent = user_agent
        self._ai_agents = ai_optout_agents
        self._cache: dict[str, RobotFileParser] = {}

    def _parser_for(self, url: str) -> RobotFileParser:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._cache:
            parser = RobotFileParser()
            try:
                resp = self._client.get(f"{origin}/robots.txt")
                ctype = resp.headers.get("content-type", "")
                if resp.status_code == 200 and "html" not in ctype:
                    parser.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    parser.disallow_all = True
                else:
                    # 404 or an HTML fallback page: no robots policy published.
                    parser.parse([])
            except httpx.HTTPError as exc:
                # Cannot read the policy: be conservative.
                log.warning("robots_fetch_failed", extra={"fields": {"origin": origin, "error": str(exc)}})
                parser.disallow_all = True
            self._cache[origin] = parser
        return self._cache[origin]

    def check(self, url: str) -> RobotsDecision:
        parser = self._parser_for(url)
        delay = parser.crawl_delay(self._user_agent) or parser.crawl_delay("*")
        if not parser.can_fetch(self._user_agent, url):
            return RobotsDecision(False, "robots.txt disallows this user agent", delay)
        blocked = [a for a in self._ai_agents if not parser.can_fetch(a, url)]
        if blocked:
            return RobotsDecision(False, f"robots.txt opts out of AI agents: {', '.join(blocked)}", delay)
        return RobotsDecision(True, "allowed", float(delay) if delay else None)

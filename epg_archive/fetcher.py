import httpx
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class EPGFetcher:
    
    def __init__(self, timeout: int = 120):
        self.timeout = timeout
    
    async def fetch(self, url: str) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                logger.debug(f"Fetching EPG from {url}")
                response = await client.get(url)
                response.raise_for_status()
                logger.debug(f"Fetched {len(response.content):,} bytes from {url}")
                return response.content
        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

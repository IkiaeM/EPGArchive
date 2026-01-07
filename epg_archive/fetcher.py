import httpx
from typing import Optional


class EPGFetcher:
    
    def __init__(self, timeout: int = 120):
        self.timeout = timeout
    
    async def fetch(self, url: str) -> Optional[bytes]:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.content
        except httpx.HTTPError:
            return None
        except Exception:
            return None

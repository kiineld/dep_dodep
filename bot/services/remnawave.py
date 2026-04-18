import aiohttp
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from bot.config import settings

logger = logging.getLogger(__name__)


class RemnaWaveClient:
    def __init__(self):
        self.base_url = settings.remnawave_api_url.rstrip("/")
        self.api_key = settings.remnawave_api_key
        self._session: Optional[aiohttp.ClientSession] = None
        self._auth_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Optional[Dict]:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        try:
            async with session.request(
                method,
                url,
                json=data,
                params=params,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                elif resp.status == 404:
                    return None
                else:
                    text = await resp.text()
                    logger.warning(f"Remnawave API {method} {path} -> {resp.status}: {text[:200]}")
                    return None
        except Exception as e:
            logger.error(f"Remnawave API error: {e}")
            return None

    # ===== USERS =====

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        result = await self._request("GET", f"/api/users/get-by-telegram-id/{telegram_id}")
        if result and "response" in result:
            return result["response"]
        return None

    async def create_user(
        self,
        telegram_id: int,
        username: str,
        traffic_limit_bytes: int,
        expire_at: str,
        description: str = "",
        squad_uuids: list = None
    ) -> Optional[Dict]:
        data = {
            "telegramId": telegram_id,
            "username": username,
            "trafficLimitBytes": traffic_limit_bytes,
            "trafficLimitStrategy": "NO_RESET",
            "expireAt": expire_at,
            "description": description,
            "internalSquads": squad_uuids or [],
            "externalSquads": [],
            "activeUserInbounds": [],
        }
        result = await self._request("POST", "/api/users", data=data)
        if result and "response" in result:
            return result["response"]
        return None

    async def update_user(self, uuid: str, **kwargs) -> Optional[Dict]:
        result = await self._request("PATCH", f"/api/users/{uuid}", data=kwargs)
        if result and "response" in result:
            return result["response"]
        return None

    async def get_user(self, uuid: str) -> Optional[Dict]:
        result = await self._request("GET", f"/api/users/{uuid}")
        if result and "response" in result:
            return result["response"]
        return None

    async def get_user_subscription_link(self, uuid: str) -> Optional[str]:
        user = await self.get_user(uuid)
        if user:
            return user.get("subscriptionUrl")
        return None

    async def enable_user(self, uuid: str) -> Optional[Dict]:
        result = await self._request("POST", f"/api/users/{uuid}/enable")
        if result and "response" in result:
            return result["response"]
        return None

    async def disable_user(self, uuid: str) -> Optional[Dict]:
        result = await self._request("POST", f"/api/users/{uuid}/disable")
        if result and "response" in result:
            return result["response"]
        return None

    async def revoke_user_subscription(self, uuid: str) -> Optional[Dict]:
        result = await self._request("POST", f"/api/users/{uuid}/revoke-subscription")
        if result and "response" in result:
            return result["response"]
        return None

    async def get_all_users(self, start: int = 0, size: int = 100) -> Optional[Dict]:
        result = await self._request("GET", "/api/users", params={"start": start, "size": size})
        if result and "response" in result:
            return result["response"]
        return None

    # ===== NODES / SQUADS =====

    async def get_nodes(self) -> Optional[List[Dict]]:
        result = await self._request("GET", "/api/nodes")
        if result and "response" in result:
            return result["response"]
        return []

    async def get_active_nodes_count(self) -> int:
        nodes = await self.get_nodes()
        if not nodes:
            return 0
        return sum(1 for n in nodes if n.get("isConnected") and n.get("isEnabled"))

    # ===== INBOUNDS =====

    async def get_inbounds(self) -> Optional[List[Dict]]:
        result = await self._request("GET", "/api/inbounds")
        if result and "response" in result:
            return result["response"]
        return []

    # ===== SYSTEM =====

    async def get_system_stats(self) -> Optional[Dict]:
        result = await self._request("GET", "/api/system/stats")
        if result and "response" in result:
            return result["response"]
        return None

    async def health_check(self) -> list:
        try:
            result = await self._request("GET", "/api/system/health")
            return result
        except Exception:
            return []


# Singleton
remnawave = RemnaWaveClient()

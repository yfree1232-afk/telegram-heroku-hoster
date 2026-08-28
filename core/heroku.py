import aiohttp
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from config import config

logger = logging.getLogger(__name__)

class HerokuAPI:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.HEROKU_API_KEY
        self.base_url = config.HEROKU_BASE_URL

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/vnd.heroku+json; version=3",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, endpoint: str, json_data: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Tuple[bool, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=self.headers, json=json_data, params=params) as resp:
                    if resp.status in [200, 201, 202, 206]:
                        data = await resp.json()
                        return True, data
                    elif resp.status == 204:
                        return True, {}
                    else:
                        try:
                            err_data = await resp.json()
                            msg = err_data.get("message", f"HTTP Error {resp.status}")
                        except Exception:
                            msg = await resp.text()
                        logger.error(f"Heroku API Error [{method} {endpoint}]: {resp.status} - {msg}")
                        return False, msg
        except Exception as e:
            logger.exception(f"Network exception calling Heroku API: {e}")
            return False, str(e)

    # --- Account & Verification ---
    async def get_account(self) -> Tuple[bool, Any]:
        """Fetch account details to verify API key validity"""
        return await self._request("GET", "/account")

    # --- App Management ---
    async def list_apps(self) -> Tuple[bool, Any]:
        """List all apps on this Heroku account"""
        return await self._request("GET", "/apps")

    async def get_app(self, app_name: str) -> Tuple[bool, Any]:
        """Get details for a specific app"""
        return await self._request("GET", f"/apps/{app_name}")

    async def create_app(self, app_name: str, region: str = "us") -> Tuple[bool, Any]:
        """Create a new Heroku application"""
        payload = {
            "name": app_name.lower().strip(),
            "region": region,
            "stack": "container" if False else "heroku-22"
        }
        return await self._request("POST", "/apps", json_data=payload)

    async def delete_app(self, app_name: str) -> Tuple[bool, Any]:
        """Delete an app completely from Heroku"""
        return await self._request("DELETE", f"/apps/{app_name}")

    # --- Dyno & Power Management ---
    async def get_dynos(self, app_name: str) -> Tuple[bool, Any]:
        """Get all dyno processes running on the app"""
        return await self._request("GET", f"/apps/{app_name}/dynos")

    async def restart_app(self, app_name: str) -> Tuple[bool, Any]:
        """Restart all dynos on the app"""
        return await self._request("DELETE", f"/apps/{app_name}/dynos")

    async def scale_dyno(self, app_name: str, dyno_type: str = "worker", quantity: int = 1, size: str = "eco") -> Tuple[bool, Any]:
        """Scale dyno up (quantity=1) or down/stop (quantity=0)"""
        payload = {
            "updates": [
                {
                    "type": dyno_type,
                    "quantity": quantity,
                    "size": size
                }
            ]
        }
        return await self._request("PATCH", f"/apps/{app_name}/formation", json_data=payload)

    # --- Config Vars (Environment Variables) ---
    async def get_config_vars(self, app_name: str) -> Tuple[bool, Any]:
        """Fetch all environment variables for the app"""
        return await self._request("GET", f"/apps/{app_name}/config-vars")

    async def update_config_vars(self, app_name: str, config_vars: Dict[str, Optional[str]]) -> Tuple[bool, Any]:
        """Update or delete environment variables (pass None value to delete a var)"""
        return await self._request("PATCH", f"/apps/{app_name}/config-vars", json_data=config_vars)

    # --- Live Logs ---
    async def get_recent_logs(self, app_name: str, lines: int = 100) -> Tuple[bool, str]:
        """Fetch the most recent log lines from Heroku logplex"""
        payload = {
            "lines": lines,
            "tail": False
        }
        ok, res = await self._request("POST", f"/apps/{app_name}/log-sessions", json_data=payload)
        if not ok:
            return False, f"Failed to open log session: {res}"
        
        logplex_url = res.get("logplex_url")
        if not logplex_url:
            return False, "No logplex URL returned by Heroku"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(logplex_url) as resp:
                    if resp.status == 200:
                        logs = await resp.text()
                        return True, logs if logs.strip() else "No logs recorded yet."
                    return False, f"Logplex returned status {resp.status}"
        except Exception as e:
            return False, f"Error fetching logs: {e}"

    # --- Build & Deploy ---
    async def deploy_from_tarball(self, app_name: str, tarball_url: str, version: str = "v1.0") -> Tuple[bool, Any]:
        """Trigger a build deploy from a tarball archive (e.g. GitHub tar.gz URL)"""
        payload = {
            "source_blob": {
                "url": tarball_url,
                "version": version
            }
        }
        return await self._request("POST", f"/apps/{app_name}/builds", json_data=payload)

    async def get_build_status(self, app_name: str, build_id: str) -> Tuple[bool, Any]:
        """Check build status (pending, successful, failed)"""
        return await self._request("GET", f"/apps/{app_name}/builds/{build_id}")

heroku_client = HerokuAPI()

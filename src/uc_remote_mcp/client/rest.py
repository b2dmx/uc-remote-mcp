"""Thin async REST client for the UC Remote Core API."""

import httpx
from typing import Any, Optional


class UCClient:
    def __init__(self, host: str, port: int, api_key: str, *, tls: bool = False):
        scheme = "https" if tls else "http"
        self._base = f"{scheme}://{host}:{port}"
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def get(self, path: str, **params) -> Any:
        url = self._base + path
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, headers=self._headers, params=params or None)
            r.raise_for_status()
            return r.json()

    async def get_list(self, path: str, page_size: int = 100) -> list:
        """GET a paginated list endpoint, accumulating every page.

        Core API list endpoints (/entities, /intg/drivers, ...) default to a
        small page size (10) and silently truncate. Iterates ?page=N&limit=M
        until a short page or the Pagination-Count total is reached.
        """
        sep = "&" if "?" in path else "?"
        items: list = []
        page = 1
        async with httpx.AsyncClient(timeout=15) as c:
            while True:
                url = f"{self._base}{path}{sep}page={page}&limit={page_size}"
                r = await c.get(url, headers=self._headers)
                r.raise_for_status()
                batch = r.json()
                if not isinstance(batch, list):
                    return batch
                items.extend(batch)
                total = r.headers.get("pagination-count")
                if total is not None and len(items) >= int(total):
                    break
                if len(batch) < page_size:
                    break
                page += 1
        return items

    async def get_text(self, path: str) -> str:
        url = self._base + path
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(url, headers=self._headers)
            r.raise_for_status()
            return r.text

    @staticmethod
    def _body(r: httpx.Response) -> Any:
        """Parse a response that may be empty (204) or non-JSON."""
        if not r.content:
            return {}
        ctype = r.headers.get("content-type", "")
        if ctype.startswith("application/json"):
            return r.json()
        return r.text

    async def post(self, path: str, body: Any = None) -> Any:
        url = self._base + path
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, headers=self._headers, json=body)
            r.raise_for_status()
            return self._body(r)

    async def put(self, path: str, body: Any = None) -> Any:
        url = self._base + path
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.put(url, headers=self._headers, json=body)
            r.raise_for_status()
            return self._body(r)

    async def patch(self, path: str, body: Any = None) -> Any:
        url = self._base + path
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.patch(url, headers=self._headers, json=body)
            r.raise_for_status()
            return self._body(r)

    async def delete(self, path: str) -> Any:
        url = self._base + path
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.delete(url, headers=self._headers)
            r.raise_for_status()
            return self._body(r)

    @classmethod
    async def with_pin_auth(
        cls,
        host: str,
        port: int,
        pin: str,
        key_name: str = "uc-remote-mcp",
    ) -> tuple["UCClient", str]:
        """
        Authenticate with admin PIN via session cookie, create API key, return (client, api_key).

        Flow per spec: POST /api/pub/login → session cookie → POST /api/auth/api_keys.
        """
        base = f"http://{host}:{port}"
        async with httpx.AsyncClient(timeout=10) as c:
            # Step 1: login with PIN to get session cookie
            login = await c.post(
                f"{base}/api/pub/login",
                json={"username": "web-configurator", "password": pin},
            )
            if login.status_code == 401:
                raise ValueError("Wrong PIN — authentication failed.")
            login.raise_for_status()

            # Session cookie is set automatically; reuse same client for step 2
            r = await c.post(
                f"{base}/api/auth/api_keys",
                json={"name": key_name, "scopes": ["admin"]},
            )
            r.raise_for_status()
            data = r.json()

        api_key = data.get("api_key") or data.get("key") or data["token"]
        return cls(host, port, api_key), api_key

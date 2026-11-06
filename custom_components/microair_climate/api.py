"""HTTP client for MicroAir EasyTouch thermostats."""

from __future__ import annotations

import asyncio

from aiohttp import ClientSession

from .const import REQUEST_TIMEOUT


class MicroAirApi:
    """Thin wrapper around the thermostat's HTTP endpoints."""

    def __init__(self, session: ClientSession, ip_address: str) -> None:
        """Initialize the client."""
        self._session = session
        self._ip_addr = ip_address

    async def _async_post(self, path: str, data: str | None = None) -> str:
        url = f"http://{self._ip_addr}/{path}"
        async with asyncio.timeout(REQUEST_TIMEOUT):
            resp = await self._session.post(url, data=data)
            resp.raise_for_status()
            return (await resp.read()).decode("utf8")

    async def async_get_status(self) -> str:
        """Return the raw XML status payload."""
        return await self._async_post("ShortStatus")

    async def async_transmit(self, command: str) -> bool:
        """Send a command string, returning True if the thermostat acknowledged it."""
        content = await self._async_post("Transmission", command)
        return "<X>OK</X>" in content

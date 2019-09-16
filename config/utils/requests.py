import functools
import aiohttp
import asyncio


def error_handle(f):

    @functools.wraps(f)
    async def exception(*args, **kwargs):

        try:

            return await f(*args, **kwargs)

        except (asyncio.TimeoutError, aiohttp.InvalidURL, aiohttp.ClientConnectionError) as e:

            raise e

    return exception


class Request:
    def __init__(self, bot, session):
        __slots__ = ("loop", "session")
        self.loop = bot.loop
        self.session = session

    @staticmethod
    async def return_content(response, headers):
        if headers in ("application/json", "application/javascript", "application/javascript",
                       "application/json; charset=utf-8") or "json" in headers:
            return await response.json()

        return await response.read()

    @error_handle
    async def fetch(self, url, **kwargs):
        async with self.session.get(url, **kwargs) as response:

            headers = response.headers.get("content-type")
            return await self.return_content(response, headers)

    @error_handle
    async def post(self, url, data, **kwargs):

        async with self.session.post(url, data=data, **kwargs) as response:

            headers = response.headers.get("content-type")
            return await self.return_content(response, headers)


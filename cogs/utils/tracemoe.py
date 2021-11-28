import asyncio

from discord.ext import tasks

from cogs.error_handler import RequestFailed

BASE_URL = "https://api.trace.moe"
BASE_MEDIA_URL = "https://media.trace.moe/"

VIDEO_PREVIEW = "preview.php"
IMAGE_PREVIEW = "thumbnail.php"


class TraceMoeApi:
    def __init__(self, ctx, api_token=""):
        self.session = ctx.bot.session
        self.api_token = api_token
        self.lock = asyncio.Lock()
        self.unlocked = asyncio.Event()
        self.set_lock.start()

    @tasks.loop(seconds=1)
    async def set_lock(self):
        if self.lock.locked() is False:
            self.unlocked.set()
        else:
            self.unlocked.clear()

    async def get(self, url, params=None):

        await self.unlocked.wait()

        async with self.lock:
            if params:
                return await self.session.get(url, params=params)
            return await self.session.get(url)

    async def quota_reached(self):

        url = BASE_URL + "/me"
        params = {}
        if self.api_token:
            params["key"] = self.api_token

        response = await self.get(url)

        if response.status == 403:
            raise RequestFailed("Invalid api token.")

        js = await response.json()

        used = js["quotaUsed"]
        quota = js["quota"]
        left = quota - used

        print(f"Quota: {quota}\nQuota used: {used}\nQuota left: {left}")

        return js["quotaUsed"] == js["quota"]

    async def search(self, path, **kwargs):

        url = BASE_URL + "/search"
        params = {"url": path}

        if self.api_token:
            params["key"] = self.api_token

        if kwargs.get("cut_boards"):
            params["cutBorders"] = ""

        if kwargs.get("anilist"):
            params["anilistInfo"] = ""

        response = await self.get(url, params=params)

        if response.status == 200:
            json = await response.json()
            return json

        elif response.status == 400:
            raise RequestFailed("Image provided was empty!")

        elif response.status == 403:
            raise RequestFailed("Invalid api token.")

        elif response.status in [500, 503]:
            raise RequestFailed("Image is malformed or something went wrong")

        elif response.status == 429:
            raise RequestFailed(response.text)
        else:
            raise RequestFailed(f"Unknown error: {response.status}, {response.url}")

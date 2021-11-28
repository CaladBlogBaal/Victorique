import asyncio

from discord.ext import tasks

from python_graphql_client import GraphqlClient

from queries.seasonal import search_seasonal
from queries.schedule import search_schedule
from queries.media_search import search_media
from queries.media_rec import search_recommendations
from queries.staff import search_staff

from queries.variables.media_by_title_vars import get_by_title
from queries.variables.media_by_id_vars import get_by_id
from queries.variables.seasonal_vars import get_seasonal
from queries.variables.schedule_vars import get_schedule

ANI_LIST_URL = "https://graphql.anilist.co"


class AniListApi:

    def __init__(self):
        self.client = GraphqlClient(ANI_LIST_URL)
        self.lock = asyncio.Lock()
        self.unlocked = asyncio.Event()
        self.set_lock.start()

    @tasks.loop(seconds=1)
    async def set_lock(self):
        if self.lock.locked() is False:
            self.unlocked.set()
        else:
            self.unlocked.clear()

    async def call_anilist_api(self, query, variables=None):

        await self.unlocked.wait()

        async with self.lock:
            data = await self.client.execute_async(query=query, variables=variables)
            return data

    async def seasonal_search(self, year, season):
        if season.lower().capitalize() == "Autumn":
            season = "FALL"

        js = await self.call_anilist_api(search_seasonal(), get_seasonal(year=year, season=season))
        return js

    async def schedule_search(self, page="1"):
        js = await self.call_anilist_api(search_schedule(), get_schedule(page))
        return js

    async def anime_search(self, name):
        js = await self.call_anilist_api(search_media(), get_by_title("ANIME", name))
        return js

    async def anime_id_search(self, anime_id):
        js = await self.call_anilist_api(search_media(), get_by_id("ANIME", anime_id))
        return js

    async def anime_rec_by_title(self, name):
        js = await self.call_anilist_api(search_recommendations(), get_by_title("ANIME", name))
        return js

    async def anime_rec_by_id(self, anime_id):
        js = await self.call_anilist_api(search_recommendations(), get_by_id("ANIME", anime_id))
        return js

    async def anime_staff_by_id(self, anime_id):
        js = await self.call_anilist_api(search_staff(), get_by_id("ANIME", anime_id))
        return js

    async def anime_staff_by_title(self, name):
        js = await self.call_anilist_api(search_staff(), get_by_title("ANIME", name))
        return js

    async def manga_search(self, name):
        js = await self.call_anilist_api(search_media(), get_by_title("MANGA", name))
        return js

    async def manga_id_search(self, manga_id):
        js = await self.call_anilist_api(search_media(), get_by_id("MANGA", manga_id))
        return js

    async def manga_rec_by_title(self, name):
        js = await self.call_anilist_api(search_recommendations(), get_by_title("MANGA", name))
        return js

    async def manga_rec_by_id(self, anime_id):
        js = await self.call_anilist_api(search_recommendations(), get_by_id("MANGA", anime_id))
        return js

    async def manga_staff_by_id(self, manga_id):
        js = await self.call_anilist_api(search_staff(), get_by_id("MANGA", manga_id))
        return js

    async def manga_staff_by_title(self, name):
        js = await self.call_anilist_api(search_staff(), get_by_title("MANGA", name))
        return js


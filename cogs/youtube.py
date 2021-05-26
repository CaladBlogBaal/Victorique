import json
import re

from discord.ext import commands, tasks
from bs4 import BeautifulSoup

from config.utils.cache import cache


class Youtube(commands.Cog):
    """Some youtube related commands"""

    def __init__(self, bot):
        self.bot = bot

    @tasks.loop(hours=1)
    async def invalidate_search_cache(self):
        # periodically clear the search cache
        self.search_youtube.clear()

    @commands.Cog.listener()
    async def on_ready(self):
        await self.invalidate_search_cache.start()

    @staticmethod
    async def get_youtube_urls(contents, top=False):
        urls = []
        for dict_ in contents:
            if "videoRenderer" in dict_:
                web_cmd = dict_["videoRenderer"]["navigationEndpoint"]["commandMetadata"]["webCommandMetadata"]
                url = web_cmd.get("url")
                urls.append("https://www.youtube.com" + url)
                if top:
                    return urls

        return urls

    @cache()
    async def search_youtube(self, query, top=False):
        urls = list()
        search_url = "https://www.youtube.com/results?"
        params = {"search_query": "+".join(query.split())}
        # for the cookies and data consent forum
        cookies = {"CONSENT": "YES+srp.gws-20210330-0-RC1.en+FX+461"}
        result = await self.bot.fetch(search_url, params=params, cookies=cookies)
        soup = BeautifulSoup(result, "html.parser")
        pattern = re.compile(r"var ytInitialData = (.*);")
        scripts = soup.find_all("script")

        for script in scripts:
            if pattern.search(str(script.string)):
                data = pattern.search(script.string)
                data = json.loads(data.groups()[0])
                contents = data["contents"]["twoColumnSearchResultsRenderer"]["primaryContents"]["sectionListRenderer"][
                    "contents"]
                item_sec_contents = contents[0]["itemSectionRenderer"]["contents"]
                urls.extend(await self.get_youtube_urls(item_sec_contents, top))

        return urls

    @commands.group(invoke_without_command=True)
    async def youtube(self, ctx, *, query):
        """Search for videos on youtube"""

        await ctx.trigger_typing()

        results = await self.search_youtube(query)

        if not results:
            return await ctx.send(f":no_entry: | search failed for `{query}.`")

        pages = ctx.menu(ctx.embed_source(results))
        await pages.start(ctx)

    @youtube.command()
    async def one(self, ctx, *, query):
        """Return only one youtube video"""

        result = await self.search_youtube(query, True)
        if not result:
            return await ctx.send(f":no_entry: | search failed for `{query}.`")

        await ctx.send(*result)


def setup(bot):
    n = Youtube(bot)
    bot.add_cog(n)


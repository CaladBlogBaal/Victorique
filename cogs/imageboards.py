import random
import asyncio
import typing
import html
import re

import aiohttp.client_exceptions

from bs4 import BeautifulSoup

import discord
from discord.ext import commands


def range_check(amount):
    if amount > 20:
        return 20

    elif amount < 0:
        raise commands.BadArgument("Invalid number was passed.")

    return amount


class MoeBooruApi:

    def __init__(self, ctx):
        self.bot = ctx.bot
        self.post_url = ""

    @staticmethod
    def process_tags(tags, safe):
        if not tags:
            return None

        tags = tags.replace("||", "\u200B").replace("|", "\u200B").replace("&&", "\u200B")
        tags = list(tag.rstrip().lstrip().replace(" ", "_") for tag in tags.split("\u200B"))

        if safe and tags:
            for i, tag in enumerate(tags):
                # this would break rating:safe
                if "rating:" in tag:
                    del tags[i]

        tags = " ".join(tags)
        return tags

    def set_post_url(self, url):
        self.post_url = url

    @staticmethod
    def get_gelbooru_params(tags, safe):

        # no limit so it randomises
        params = {}
        if safe:
            params["tags"] = "rating:safe "

        # because gelbooru is likely to return nsfw images with these tags on safe rating

        try:
            current_blacklisted_tags = ("loli", "pussy")
            if safe and any(btag in tags for btag in current_blacklisted_tags):
                return False
        except TypeError:
            pass

        if tags:
            try:
                params["tags"] += tags
            except KeyError:
                params["tags"] = tags

        return params

    @staticmethod
    def get_ye_kc_params(limit, tags, safe):

        params = {
            "limit": limit,
            "tags": "order:random ",
            "page": random.randint(1, 3)

        }

        if safe:
            params["tags"] += "rating:safe "

        if tags:
            params.pop("page", None)
            params["tags"] += tags

        params["tags"] = params["tags"].rstrip()

        return params

    async def get_image(self, limit=1, tags=None, safe=True):
        # this is hacky but meh

        tags = self.process_tags(tags, safe)

        if "gelbooru" in self.post_url:
            params = self.get_gelbooru_params(tags, safe)

            if params is False:
                return set()
        else:
            params = self.get_ye_kc_params(limit, tags, safe)

        js = await self.bot.fetch(self.post_url, params=params)

        try:

            pictures = js

            if len(pictures) < 20:
                limit = len(pictures)

            pictures = random.sample(pictures, limit)

            picture_data_set = set()

            for js in pictures:
                picture_data_set.add((js.get("file_url"),
                                      js.get("source", " "),
                                      js.get("sample_url") or js.get("file_url"),
                                      js.get("tags") or js.get("tag_string")))

            return picture_data_set

        except TypeError:
            return dict()


class AnimePicturesNet:
    __slots__ = ("post_url", "session", "fetch")

    def __init__(self, ctx):
        self.post_url = "https://anime-pictures.net/pictures/view_posts/0?"
        self.session = ctx.bot.session
        self.fetch = ctx.bot.fetch

    async def post_response(self, tags=None):

        params = {"lang": "en", "order_by": "date"}

        if tags is not None:
            params["search_tag"] = tags

        else:
            self.post_url = self.post_url.replace("0", str(random.randint(0, 4)))

        response = await self.fetch(self.post_url, params=params)

        soup = BeautifulSoup(response, "html.parser")
        divs = soup.find_all('div', attrs={'style': 'text-align: center;line-height: 16px;'})
        text = [a.text for a in divs]
        amount_of_pages = int(text[0].split(" ")[2]) // 80

        if amount_of_pages >= 1 and tags:
            random_page = random.randint(0, amount_of_pages)
            self.post_url = self.post_url.replace("0", str(random_page))
            content = await self.fetch(self.post_url, params=params)

            soup = BeautifulSoup(content, "html.parser")

        list_of_urls = ["https://anime-pictures.net" + a.find("a").get("href")
                        for a in soup.find_all("span", attrs={"img_block_big"})]

        return list_of_urls

    async def post_request(self, limit, tags=None):

        if tags:
            list_of_urls = await self.post_response(tags)

        else:
            list_of_urls = await self.post_response()

        if not list_of_urls:
            return []

        async def request():
            async with self.session.get(random.choice(list_of_urls)) as response:
                if response.status == 503:
                    return await request()

                return await response.read()

        async def sources(soup_):
            source_links_ = []

            for a in soup_.find_all("div", "post_content"):

                a_s = a.find_all("a")[1:]

                for link in a_s:

                    if link is None:
                        source_links_.append("null")
                        continue

                    link = link.get("href")

                    if "anime-pictures.net" not in link and "view_" not in link:
                        source_links_.append(f"{link} ")

            return source_links_

        img_links = set()

        results = await asyncio.gather(*[request() for _ in range(limit)])

        for content in results:

            soup = BeautifulSoup(content, "html.parser")
            source_links = await sources(soup)
            source_links = " ".join(source_links)

            sample_urls = [tag.get("src") for tag in soup.find_all("img", {"id": "big_preview"})]

            if sample_urls:
                sample_url = f"https:{sample_urls[0]}"
                og_url = sample_url.replace("_bp", "")
                og_url = og_url.replace("//cdn.anime-pictures.net/jvwall_images/", "//images.anime-pictures.net/")

                img_links.add((sample_url, source_links, og_url))

        return img_links


class SafebooruAPI:
    __slots__ = ("post_url", "bot")

    def __init__(self, ctx):
        self.post_url = "https://safebooru.org/index.php?page=dapi&s=post&q=index"
        self.bot = ctx.bot

    async def post_request(self, tags=None):
        params = {}

        if tags:
            params["tags"] = tags
            content = await self.bot.fetch(self.post_url, params=params)

        else:
            params["pid"] = random.randint(1, 4)
            content = await self.bot.fetch(self.post_url, params=params)

        soup = BeautifulSoup(content, "lxml")

        return [(tag["sample_url"], tag["source"], tag["file_url"], tag["tags"].lstrip())
                for tag in soup.find_all("post")]


class ImageBoards(commands.Cog, command_attrs=dict(cooldown=commands.Cooldown(1, 3, commands.BucketType.user))):
    """Anime image boards related commands
       divide tags with | or || or && **no mixing separators**

    """

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    async def get_nsfw_channel(ctx):
        async with ctx.acquire():
            if ctx.guild:
                return await ctx.db.fetchval("SELECT nsfw_channel from guilds where guild_id = $1", ctx.guild.id)
            return True

    async def random_image(self, ctx, post_url):
        m = MoeBooruApi(ctx)
        m.set_post_url(post_url)
        results, = await m.get_image()
        await ctx.send(embed=self.embed_(*results))

    def embed_(self, image_url, source, og_url="", tags=" "):

        source = self.clean_sources(source)
        tags = self.clean_tags(tags)

        embed = discord.Embed(colour=discord.Colour.dark_magenta(),
                              description=f"{source}{tags}\n[Full size img url]({og_url})")

        embed.set_image(url=image_url)

        if og_url:
            embed.set_footer(text="preview image for discord.")

        return embed

    @staticmethod
    def clean_tags(tags):
        # to not exceed the 2048 embed text limit.
        tags = html.unescape(tags)
        if len(tags) > 1200:
            tags.split(" ")
            tags_cut = ""
            i = 0
            while len(tags_cut) != 1200:
                tags_cut += tags[i]
                i += 1
            tags = tags_cut

        return f"```{tags}```"

    @staticmethod
    def clean_sources(sources):
        cleaned_sources = sources
        urls = re.findall(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", sources)

        if urls:
            cleaned_sources = "\n".join("[Image source(%s)](%s)" % (urls.index(url) + 1, url) for url in urls[:4])

        return cleaned_sources

    async def post_request(self, ctx, amount, tags, post_url):
        amount = range_check(amount)

        await ctx.trigger_typing()
        m = MoeBooruApi(ctx)
        m.set_post_url(post_url)

        nsfw_ch_id = await self.get_nsfw_channel(ctx)
        results = await m.get_image(amount, tags, ctx.channel.id != nsfw_ch_id and nsfw_ch_id is not True)

        if results in (set(), dict()):
            return await ctx.send(":no_entry: | search failed")

        missed = amount - len(results)

        if missed > 0:
            await ctx.send(f":information_source: | {missed} results were not found.")
            await ctx.trigger_typing()

        for result in results:
            og_url, sources, url, tags = result
            if url.endswith(("jpg", "png", "gif", "jpeg")):
                await ctx.paginator_global.add_page(self.embed_(url, sources, og_url, tags))

            else:
                if sources == "":
                    sources = " "
                await ctx.paginator_global.add_page(f":information_source: | **Image source** `{sources}`\n {url}")

        await ctx.paginator_global.paginate()

    async def check_invalid_url(self, result):
        url, url2, preview, tags = result

        try:
            async with self.bot.session.get(url) as response:

                if response.status == 403:
                    return url2, url, preview, tags

                return url, url2, preview, tags

        except(aiohttp.client_exceptions.ClientConnectionError, aiohttp.client_exceptions.InvalidURL):
            return url2, url, preview

    @commands.command(aliases=["snc"])
    @commands.has_permissions(manage_channels=True)
    async def set_nsfw_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the current channel or another channel as the NSFW channel."""

        channel = channel or ctx.channel

        async with ctx.db.acquire():
            await ctx.db.execute("UPDATE guilds SET nsfw_channel = $1 where guild_id = $2", channel.id, ctx.guild.id)

        await ctx.send(f":information_source: | {channel.mention} has been set as the NSFW channel.")

    @commands.command(aliases=["dnc"])
    @commands.has_permissions(manage_channels=True)
    async def delete_nsfw_channel(self, ctx):
        """Delete's the set NSFW channel"""
        channel = await self.get_nsfw_channel(ctx)

        if channel is None:
            return await ctx.send(":no_entry: | no NSFW channel has been set.", delete_after=4)

        async with ctx.db.acquire():
            await ctx.db.fetchval("UPDATE guilds SET nsfw_channel = NULL where guild_id = $1 ", ctx.guild.id)
        channel = self.bot.get_channel(channel)
        await ctx.send(f"{channel.mention} has been removed as the NSFW channel.")

    @commands.group(invoke_without_command=True, name="sb", ignore_extra=False)
    async def sb(self, ctx):
        """
        Gets a random image from safebooru
        """

        sb = SafebooruAPI(ctx)
        await ctx.trigger_typing()
        result = await sb.post_request()
        result = await self.check_invalid_url(random.choice(result))
        await ctx.send(embed=self.embed_(*result))

    @sb.command(name="search")
    async def search_sb(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on safebooru from a random page"""

        amount = range_check(amount)
        await ctx.trigger_typing()

        tags = tags.replace("||", "\u200B").replace("|", "\u200B").replace("&&", "\u200B")
        tags = " ".join(list(tag.rstrip().lstrip().replace(" ", "_") for tag in tags.split("\u200B")))

        sb = SafebooruAPI(ctx)

        results = await sb.post_request(tags)

        if not results:
            return await ctx.send(":no_entry: | search failed")

        if len(results) >= 20:
            results = random.sample(results, amount)

        for result in results:
            await ctx.paginator_global.add_page(self.embed_(*(await self.check_invalid_url(result))))

        await ctx.paginator_global.paginate()

    @commands.group(invoke_without_command=True, ignore_extra=False)
    async def apn(self, ctx):
        """
        Gets a random image from anime-pictues.net
        """

        a = AnimePicturesNet(ctx)
        results = await a.post_request(1)
        results, = results

        await ctx.send(embed=self.embed_(*results))

    @apn.command(name="search")
    async def search_apn(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on anime pictures net
           20 is the maximum"""

        amount = range_check(amount)

        apn = AnimePicturesNet(ctx)

        results = await apn.post_request(amount, tags.replace("|", "||").replace("&&", "|"))
        if results == list():
            return await ctx.send(":no_entry: | search failed")

        missing = amount - len(results)

        if missing > 0:
            await ctx.send(f":information_source: | {missing} results were not found on this page.")
            await ctx.trigger_typing()

        for result in results:
            await ctx.paginator_global.add_page(self.embed_(*result))

        await ctx.paginator_global.paginate()

    @commands.group(invoke_without_command=True, ignore_extra=False)
    async def ye(self, ctx):
        """
        Gets a random image from yande.re
        """

        await self.random_image(ctx, "https://yande.re/post.json")

    @ye.command(aliases=["yande_search", "search"])
    async def ye_search(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on yande.re
        20 is the maximum"""

        await self.post_request(ctx, amount, tags, "https://yande.re/post.json")

    @commands.group(invoke_without_command=True, ignore_extra=False)
    async def gb(self, ctx):

        """
        Gets a random image from gelbooru
        """

        safe = False

        while not safe:
            async with self.bot.session.get("https://gelbooru.com/index.php?page=post&s=random") as r:
                id_ = "".join(c for c in str(r.url) if c.isdigit())
                params = {"id": id_}
                js = (await self.bot.fetch("http://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1",
                                           params=params))
                if not js:
                    continue
                js = js[0]
                if js["rating"] in ("s", "safe"):
                    safe = True

        url = js["file_url"]
        og_url = js["file_url"]
        source = js["source"]
        tags = js["tags"]
        await ctx.send(embed=self.embed_(url, source, og_url, tags))

    @gb.command(aliases=["gelbooru_search", "search"])
    async def gb_search(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on gelbooru
        20 is the maximum"""

        await self.post_request(ctx, amount, tags, "https://gelbooru.com/index.php?page=dapi&s=post&q=index&json=1")

    @commands.group(invoke_without_command=True, ignore_extra=False)
    async def kc(self, ctx):
        """
        Gets a random image from konochan
        """

        await self.random_image(ctx, "https://konachan.com/post.json")

    @kc.command(aliases=["konochan_search", "search"])
    async def kc_search(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on konochan
        20 is the maximum"""

        await self.post_request(ctx, amount, tags, "https://konachan.com/post.json")


def setup(bot):
    bot.add_cog(ImageBoards(bot))

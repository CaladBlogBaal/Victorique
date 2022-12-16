import typing
import discord

from io import BytesIO
from collections import namedtuple
from datetime import datetime as d
from dateutil.relativedelta import relativedelta
from bs4 import BeautifulSoup
from discord.ext import commands
from saucenao_api import AIOSauceNao, errors

from cogs.utils.anime import AniListApi
from cogs.utils.tracemoe import TraceMoeApi

from config.utils.menu import page_source
from config.utils.converters import SeasonConverter

from loadconfig import __saucenao_api_key__
from config.utils.context import Context


class Anime(commands.Cog, command_attrs=dict(cooldown=commands.CooldownMapping(commands.Cooldown(1, 4),
                                                                               type=commands.BucketType.user))):
    """Anime related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.ani_list_api = AniListApi()
        self.message = namedtuple("message", "image_url jump_url")

    @staticmethod
    @page_source(per_page=1)
    async def sauce_source(self, menu, entry):
        embed = discord.Embed(color=self.default_colors())
        embed.title = entry.title
        embed.set_image(url=entry.thumbnail)
        embed.description = "\n".join(entry.urls)
        embed.set_footer(text=f"Author/Artist: {entry.author}\npage {menu.current_page + 1} /{self.get_max_pages()}")
        return embed

    @staticmethod
    @page_source(per_page=1)
    async def tracemoe_source(self, menu, entry):
        embed = discord.Embed(color=self.default_colors(), url=f"https://anilist.co/anime/{entry['anilist']['id']}")
        embed.title = entry["anilist"]["title"]["native"]
        embed.set_image(url=entry["image"])

        start = entry["from"]
        end = entry["to"]
        # h:mm:ss
        # 0:00:00
        start = f"{start // (60 * 60)}:{start % (60 * 60) // 60:02.0f}:{start % (60 * 60) % 60:02.0f}"
        end = f"{end // (60 * 60)}:{end % (60 * 60) // 60:02.0f}:{end % (60 * 60) % 60:02.0f}"

        embed.description = f"Episode {entry['episode'] or 'NaN'}\n{start} - {end}"
        embed.set_footer(text=f"~Similarity {round(entry['similarity'], 2)}"
                              f"\npage {menu.current_page + 1} /{self.get_max_pages()}")
        return embed

    @staticmethod
    @page_source(per_page=11)
    async def schedule_source(self, menu, entries):

        timestamp = entries[0]["nextAiringEpisode"]["airingAt"]
        date = d.fromtimestamp(timestamp)
        schedule_day = date.strftime("%A")

        embed = discord.Embed(title=f"Anime schedule for {schedule_day}", color=self.default_colors())

        description = "\n".join(f"[{e['title']['romaji']}]({e['siteUrl']}): **Episodes** ({e['episodes'] or 'Unknown'})"
                                for e in entries)

        embed.description = description
        embed.set_footer(text=f"page {menu.current_page + 1} /{self.get_max_pages()}")

        return embed

    @staticmethod
    @page_source(per_page=1)
    async def staff_source(self, menu, entry):
        embed = discord.Embed(color=self.default_colors())
        embed.title = entry["name"]["full"]
        embed.url = entry["siteUrl"]
        embed.set_image(url=entry["image"]["large"])
        embed.add_field(name="Positions", value="\n".join(entry["primaryOccupations"]))
        embed.set_footer(text=f"page {menu.current_page + 1} /{self.get_max_pages()}")

        return embed

    @staticmethod
    @page_source(per_page=1)
    def default_source(self, menu, entry):
        title = f"{entry['title']['romaji']} ({entry['title']['english']})"

        embed = discord.Embed(title=f"{title} \nMAL ID: {entry['idMal']}", color=self.default_colors(),
                              url=entry["siteUrl"])
        # html.unescape refused to work
        synopsis = BeautifulSoup(entry["description"], "lxml").text
        embed.description = f":book: **Synopsis**\n{synopsis}"

        start_date = "/".join(str(x) for x in entry["startDate"].values() if x)
        end_date = "/".join(str(x) for x in entry["endDate"].values() if x)

        if entry["type"] == "ANIME":
            airing = entry.get("airing") or "False"
            embed.add_field(name=":airplane: Airing", value=airing)
            embed.add_field(name=":tv: Episodes", value=entry["episodes"])
        else:
            publishing = entry.get("publishing") or "False"
            chapters = entry.get("chapters")
            if chapters:
                embed.add_field(name=":tv: Chapters", value=entry["chapters"])
            embed.add_field(name=":airplane: Publishing", value=publishing)

        score = entry["averageScore"]

        if score is None:
            score = 0

        embed.add_field(name=":star: Rating", value=f"{score} / 100")
        embed.add_field(name=":clapper: Type", value=entry["type"])
        embed.add_field(name=":date: Start Date", value=start_date or "NaN")
        embed.add_field(name=":date: End Date", value=end_date or "NaN")

        if entry["coverImage"]["medium"]:
            embed.set_thumbnail(url=entry["coverImage"]["medium"])

        embed.set_footer(text=f"page {menu.current_page + 1} /{self.get_max_pages()}")

        return embed

    async def get_message_embed_image_url(self, message: discord.Message):

        if message.attachments:
            if "image/" not in message.attachments[0].content_type:
                return self.message(message.attachments[0].url, message.jump_url)

        elif message.embeds:
            embed = message.embeds[0]
            if embed.image:
                return self.message(embed.image.proxy_url, message.jump_url)
            # for urls that auto embed with a thumbnail
            elif embed.thumbnail:
                return self.message(embed.thumbnail.proxy_url, message.jump_url)

        return None

    async def resolve_reply_image(self, ctx):

        if ctx.message.reference:

            if ctx.message.reference.resolved:
                message = ctx.message.reference.resolved

                return await self.get_message_embed_image_url(message)

            raise commands.BadArgument("> couldn't resolve the reply.")

    async def get_recent_image_urls(self, ctx: Context, skip):

        messages = [message async for message in ctx.channel.history()
                    if message.attachments != [] or message.embeds != []]

        image_urls = []
        # ctx.history limit is 100 by default
        skip = skip if skip < 100 else 99
        # delete n elements
        del messages[:skip]

        for i, message in enumerate(messages):
            if message.attachments:
                if "image/" not in message.attachments[0].content_type:
                    del messages[i]

        for message in messages:
            if message.attachments:
                image_urls.append(self.message(message.attachments[0].proxy_url, message.jump_url))

            else:
                embed = message.embeds[0]
                if embed.image:
                    image_urls.append(self.message(embed.image.proxy_url, message.jump_url))
                # for urls that auto embed with a thumbnail
                elif embed.thumbnail:
                    image_urls.append(self.message(embed.thumbnail.proxy_url, message.jump_url))

        return image_urls

    async def build_urls(self, ctx, skip):
        urls = []

        reply = await self.resolve_reply_image(ctx)

        if reply:
            urls.append(reply)

        urls.extend(await self.get_recent_image_urls(ctx, skip))

        return urls

    async def send_og_message(self, url, ctx):
        buffer = BytesIO()
        async with self.bot.session.get(url.image_url) as resp:
            buffer.write(await resp.read())

        buffer.seek(0)

        return await ctx.send(f"Message jump url: {url.jump_url} Original image:",
                              file=discord.File(fp=buffer, filename="image.png"))

    async def get_recommendations(self, ctx: Context, js):
        title = js["data"]["Media"]["title"]["english"]
        url = js["data"]["Media"]["siteUrl"]
        await ctx.send(f"> Recommendations for {title} \n<{url}>")

        entries = [node["node"]["mediaRecommendation"] for node in js["data"]["Media"]["recommendations"]["edges"]]
        pages = ctx.menu(self.default_source(entries))
        await pages.start(ctx)

    async def get_staff(self, ctx: Context, js):
        entries = [node["node"] for node in js["data"]["Media"]["staff"]["edges"]]
        pages = ctx.menu(self.staff_source(entries))
        await pages.start(ctx)

    async def get_media(self, ctx: Context, js):
        entries = js["data"]["Page"]["media"]
        pages = ctx.menu(self.default_source(entries))
        await pages.start(ctx)

    @commands.group(invoke_without_command=True)
    async def anime(self, ctx: Context, *, anime_name):
        """Search for an anime on anilist"""
        js = await self.ani_list_api.anime_search(anime_name)
        await self.get_media(ctx, js)

    @anime.command(name="staff")
    async def anime_staff(self, ctx: Context, *, anime_name_or_id: typing.Union[int, str]):
        """Retrieves the staff for an anime from anilist using its name or id"""
        js = await self.ani_list_api.anime_staff_by_title(anime_name_or_id)
        await self.get_staff(ctx, js)

    @anime.command(name="recommendations", aliases=["r"])
    async def anime_recommendations(self, ctx: Context, *, anime_name_id: typing.Union[int, str]):
        """Returns the first 10 recommendations for an anime"""

        js = await self.ani_list_api.anime_rec_by_title(anime_name_id)
        await self.get_recommendations(ctx, js)

    @commands.group(invoke_without_command=True)
    async def manga(self, ctx: Context, *, manga_name):
        """Search for a manga on anilist"""
        js = await self.ani_list_api.manga_search(manga_name)
        await self.get_media(ctx, js)

    @manga.command(name="staff")
    async def manga_staff(self, ctx: Context, *, manga_name_id: typing.Union[int, str]):
        """Retrieves the staff for a manga from anilist using its name or id"""
        js = await self.ani_list_api.anime_staff_by_title(manga_name_id)
        await self.get_staff(ctx, js)

    @manga.command(name="recommendations", aliases=["r"])
    async def manga_recommendations(self, ctx: Context, *, manga_name_id: typing.Union[int, str]):
        """Returns the first 10 recommendations for a manga"""
        js = await self.ani_list_api.manga_rec_by_title(manga_name_id)
        await self.get_recommendations(ctx, js)

    @commands.command()
    async def seasonal(self, ctx: Context, year: typing.Optional[int] = d.now().year, season: SeasonConverter = None):
        """Get a list of anime for a year and season will default to the currently airing season."""

        if season is None:
            month_day = d.now().month - 1

            if month_day == 0:
                month_day = 1

            season = await SeasonConverter().convert(ctx, str(month_day))

        js = await self.ani_list_api.seasonal_search(year, season)
        entries = js["data"]["Page"]["media"]

        while js["data"]["Page"]["pageInfo"]["hasNextPage"]:
            js = await self.ani_list_api.seasonal_search(year, season)
            entries.extend(js)

        await ctx.send(f"Anime for {season.lower()} season of {year}.")
        pages = ctx.menu(self.default_source(entries))
        await pages.start(ctx)

    # being worked on doesn't actually await yet
    @commands.command()
    @commands.is_owner()
    async def schedule(self, ctx: Context, day=""):

        """Get a list anime based on their schedule"""

        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        page = 1
        js = await self.ani_list_api.schedule_search()
        entries = js["data"]["Page"]["media"]

        while js["data"]["Page"]["pageInfo"]["hasNextPage"]:
            page += 1
            js = await self.ani_list_api.schedule_search(str(page))
            entries.extend(js)

        for weekday in weekdays:
            if day.lower() in (weekday.lower()[:3], weekday.lower()[:4]):
                day = weekday

        for i, media in enumerate(entries):

            if not isinstance(media, dict):
                continue

            timestamp = media.get("nextAiringEpisode")

            if not timestamp:
                continue

            timestamp = timestamp["airingAt"]
            date = d.fromtimestamp(timestamp)
            schedule_day = date.strftime("%A")

            # filter out days
            if day:
                if not schedule_day.lower() != day.lower():
                    del entries[i]

        pages = ctx.menu(self.schedule_source(entries))
        await pages.start(ctx)

    @commands.command()
    async def tracemoe(self, ctx: Context, skip=0):
        """Performs a reverse image query using tracemoe on the last uploaded or embedded image
           will attempt to prune nsfw results unlike saucenao for the not set nsfw channel"""

        await ctx.typing()

        urls = await self.build_urls(ctx, skip)

        if not urls:
            return await ctx.send("> couldn't find a recent image.")

        trace = TraceMoeApi(ctx)

        if await trace.quota_reached():
            dt = d.now() + relativedelta(months=1, day=1)
            days = dt - d.now()
            days = days.days
            return await ctx.send(f"> Bot's tracemoe quota has reached for the month will reset in {days} day(s).")

        image = urls[0]

        js = await trace.search(image.image_url, anilist=True)

        safe = False

        if ctx.guild:
            nsfw_channel_id = await ctx.db.fetchval("SELECT nsfw_channel from guilds where guild_id = $1",
                                                    ctx.guild.id)
            safe = ctx.channel.id != nsfw_channel_id

        safe_results = []
        for result in js["result"]:

            if result["anilist"]["isAdult"] is False and safe:
                safe_results.append(result)

        if safe:
            js["result"] = safe_results

        if not js["result"]:
            msg = "> only nsfw results were found but can't display them outside the set nsfw channel."
            msg = f"{msg} set a nsfw channel with `{ctx.prefix}set_nsfw_channel`"
            return await ctx.send(msg, delete_after=10)

        await self.send_og_message(image, ctx)

        pages = ctx.menu(self.tracemoe_source(js["result"]))
        await pages.start(ctx)

    @commands.command()
    async def saucenao(self, ctx: Context, skip=0):
        """Performs a reverse image query using saucenao on the last uploaded or embedded image, replies also work
        skip indicates how many images to skip if there are multiple messages with embedded images"""

        await ctx.typing()

        async with AIOSauceNao(__saucenao_api_key__) as aio:

            urls = await self.build_urls(ctx, skip)

            if not urls:
                return await ctx.send("> couldn't find a recent image.")

            url = urls[0]

            try:
                # send image using BytesIO saving it to .png buffer seeking the file and sending it
                await self.send_og_message(url, ctx)
                entries = await aio.from_url(url.image_url)

            except (errors.LongLimitReachedError, errors.ShortLimitReachedError,
                    errors.BadFileSizeError, errors.UnknownClientError,
                    errors.UnknownServerError) as e:
                return await ctx.send(str(e))

            if entries.long_remaining == 0:
                return await ctx.send(f"> Bot's saucenao daily quota has reached for the day try tomorrow.")

            pages = ctx.menu(self.sauce_source(entries))
            await pages.start(ctx)


async def setup(bot):
    await bot.add_cog(Anime(bot))

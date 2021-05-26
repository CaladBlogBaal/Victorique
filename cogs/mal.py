import typing
import random

from datetime import datetime as d

from bs4 import BeautifulSoup

import discord
from discord.ext import commands

from jikanpy import AioJikan, ClientException, APIException

from config.utils.converters import SeasonConverter, MangaIDConverter, AnimeIDConverter, str_to_three_bytes
from config.utils.cache import cache
from config.utils.menu import page_source

from loadconfig import PRIVATE_GUILDS


class MyAnimeList(commands.Cog, command_attrs=dict(cooldown=commands.Cooldown(1, 4, commands.BucketType.user))):
    """MAL related commands"""
    def __init__(self, bot):
        self.bot = bot
        self.aio_jikan = AioJikan(loop=bot.loop)
        # hacky and feels dumb but shrug
        self.manga_source.aio_jikan = self.aio_jikan
        self.manga_source.person = self.aio_jikan.person
        self.recommendation_source.get_recommendation_description = self.get_recommendation_description

    @staticmethod
    @page_source(per_page=11)
    async def schedule_source(self, menu, entries):

        embed = discord.Embed(title=f"Anime schedule for {entries[0]['weekday']}", color=self.default_colors())

        description = "\n".join(f"[{e['title']}]({e['url']}): **Episodes** ({e['episodes'] or 'Unknown'})"
                                for e in entries)

        embed.description = description
        return embed

    @staticmethod
    @page_source(per_page=1)
    async def staff_source(self, menu, entry):

        embed = discord.Embed(color=self.default_colors())
        embed.title = entry["name"]
        embed.url = entry["url"]
        embed.set_image(url=entry["image_url"])
        embed.add_field(name="Positions", value=f"\n".join(f"`{pos}`" for pos in entry["positions"]))

        return embed

    @staticmethod
    @page_source(per_page=1)
    async def manga_source(self, menu, entry):
        embed = discord.Embed(color=self.default_colors())
        embed.title = entry["name"]
        embed.url = entry["url"]
        person_object = await self.person(entry["mal_id"])
        embed.set_image(url=person_object["image_url"])
        return embed

    @staticmethod
    @page_source(per_page=1)
    async def recommendation_source(self, menu, entry):
        title = f"{entry['title']}\n{entry['mal_id']}"
        embed = discord.Embed(title=title, color=self.default_colors(), url=entry["url"])
        embed.description = await self.get_recommendation_description(entry["recommendation_url"])
        embed.add_field(name="Recommendation Count", value=entry["recommendation_count"])

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, ClientException):
            await ctx.send(":no_entry: | invalid day was passed.", delete_after=3)

        if isinstance(error, APIException):
            await ctx.send(error)

    @staticmethod
    @page_source(per_page=1)
    def default_source(self, type_, result):
        embed = discord.Embed(title=f"{result['title']} \nMAL ID: {result['mal_id']}", color=self.default_colors(),
                              url=result["url"])

        synopsis = result["synopsis"]
        embed.description = f":book: **Synopsis**\n{synopsis}"

        start_date = result.get("start_date") or result.get("airing_start")
        if start_date:
            start_date = start_date[0:10]
        else:
            start_date = "NaN"

        end_date = result.get("end_date")
        if end_date:
            end_date = result["end_date"][0:10]

        else:
            end_date = "NaN"

        if type_ == "anime":
            airing = result.get("airing") or "False"
            embed.add_field(name=":airplane: Airing", value=airing)
            embed.add_field(name=":tv: Episodes", value=result["episodes"])
        else:
            publishing = result.get("publishing") or "False"
            chapters = result.get("chapters")
            if chapters:
                embed.add_field(name=":tv: Chapters", value=result["chapters"])
            embed.add_field(name=":airplane: Publishing", value=publishing)

        score = result["score"]
        if score is None:
            score = 0
        embed.add_field(name=":star: Rating", value=f"{score} / 10")

        embed.add_field(name=":clapper: Type", value=result["type"])
        embed.add_field(name=":date: Start Date", value=start_date)
        embed.add_field(name=":date: End Date", value=end_date)
        if result["image_url"]:
            embed.set_thumbnail(url=result["image_url"])

        return embed

    @cache()
    async def get_recommendation_description(self, url):
        request = await self.bot.fetch(url)
        soup = BeautifulSoup(request, "html.parser")
        description = (soup.find("span", attrs={"style": "white-space: pre-wrap;"})).text
        return description

    async def get_recommendations(self, ctx, type_: str, id_: int):

        await ctx.trigger_typing()

        if not id_:
            return None

        if type_ == "manga":
            name = await self.aio_jikan.manga(id_)
            recommendations = await self.aio_jikan.manga(id_, extension="recommendations")

        else:
            name = await self.aio_jikan.anime(id_)
            recommendations = await self.aio_jikan.anime(id_, extension="recommendations")

        url = name["url"]
        name = name["title"]

        if not recommendations["recommendations"]:
            return await ctx.send(f"> No recommendations for {name} was found.")

        await ctx.send(f"> Recommendations for {name}\n<{url}>")

        pages = ctx.menu(self.recommendation_source(recommendations["recommendations"][:10]))
        await pages.start(ctx)

    async def random_anime_manga(self, ctx, type_, genre_id=None):
        if not genre_id:
            genre_id = random.randint(1, 43)

        results = await self.aio_jikan.genre(type=type_, genre_id=genre_id)
        anime = random.choice(results[type_])
        page = ctx.menu(self.default_source([anime]))
        await page.start(ctx)

    async def seasonal_search(self, ctx, year, season):

        if season == "Autumn":
            season = "fall"

        season_ = await self.aio_jikan.season(year=year, season=season)

        pages = ctx.menu(self.default_source(season_["anime"]))

        await ctx.send(f"> Anime for {season} season of {year}.")
        await pages.start(ctx)

    async def search_mal(self, ctx, query_type, query_, return_id=False):

        if ctx.guild:

            if not ctx.channel.nsfw and ctx.guild.id not in PRIVATE_GUILDS:
                await ctx.send("> NSFW results were excluded due to the current channel not being NSFW.")
                query = await self.aio_jikan.search(search_type=query_type, query=query_,
                                                    parameters={"genre": "12", "genre_exclude": 0, "limit": 10})
            else:
                query = await self.aio_jikan.search(search_type=query_type, query=query_, parameters={"limit": 10})
        else:
            query = await self.aio_jikan.search(search_type=query_type, query=query_, parameters={"limit": 10})

        results = query["results"]

        if not results:
            await ctx.send(f":no_entry: | search failed for `{query_}`.")
            # doing this because returning a message on the convertors is a bad idea.
            return None

        if return_id:
            return results[0]["mal_id"]

        pages = ctx.menu(self.default_source(results))
        await pages.start(ctx)

    @commands.group(invoke_without_command=True)
    async def anime(self, ctx, *, anime_name: str_to_three_bytes):
        """Search for an anime on mal"""
        await self.search_mal(ctx, "anime", anime_name)

    @anime.command(name="staff")
    async def anime_staff(self, ctx, *, anime_name_or_id: AnimeIDConverter):
        """Retrieves the staff for an anime from mal using it's name or mal id"""

        anime = await self.aio_jikan.anime(anime_name_or_id, extension='characters_staff')

        if not anime:
            return

        name = (await self.aio_jikan.anime(anime_name_or_id))["title"]
        await ctx.send(f"> Staff for anime **{name}**")
        pages = ctx.menu(self.staff_source(anime["staff"]), clear_reactions_after=True)
        await pages.start(ctx)

    @anime.command(name="recommendations", aliases=["r"])
    async def anime_recommendations(self, ctx, *, anime_name_id: AnimeIDConverter):
        """Returns the first 10 recommendations for a anime"""
        await self.get_recommendations(ctx, "anime", anime_name_id)

    @commands.group(invoke_without_command=True)
    async def manga(self, ctx, *, manga_name: str_to_three_bytes):
        """Search for a manga on mal"""
        await self.search_mal(ctx, "manga", manga_name)

    @manga.command(name="staff")
    async def manga_staff(self, ctx, *, manga_name_id: MangaIDConverter):
        """Retrieves the staff for a manga from mal using it's name or mal id"""

        manga = await self.aio_jikan.manga(manga_name_id)
        name = manga["title"]
        await ctx.send(f"> Staff for manga **{name}**")

        pages = ctx.menu(self.manga_source(manga["authors"]), clear_reactions_after=True)
        await pages.start(ctx)

    @manga.command(name="recommendations", aliases=["r"])
    async def manga_recommendations(self, ctx, *, manga_name_id: MangaIDConverter):
        """Returns the first 10 recommendations for a manga"""
        await self.get_recommendations(ctx, "manga", manga_name_id)

    @manga.command(name="characters")
    @commands.is_owner()
    async def manga_characters(self, ctx, *, manga_name_id: MangaIDConverter):
        pass

    @commands.command()
    async def seasonal(self, ctx, year: typing.Optional[int] = d.now().year, season: SeasonConverter = None):
        """Get a list of anime for a year and season will default to the currently airing season."""

        archive = await self.aio_jikan.season_archive()
        archive = list(result["year"] for result in archive["archive"])
        if year not in archive:
            return await ctx.send("> MAL archives don't have this year.")

        if season is None:
            month_day = d.now().month - 1

            if month_day == 0:
                month_day = 1

            season = await SeasonConverter().convert(ctx, str(month_day))

        await self.seasonal_search(ctx, year, season)

    @commands.command()
    async def schedule(self, ctx, day=""):

        """Get a list anime based on their schedule"""

        weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

        for weekday in weekdays:
            if day.lower() in (weekday.lower()[:3], weekday.lower()[:4]):
                day = weekday

        if not day:
            scheduled = await self.aio_jikan.schedule()

        else:
            scheduled = await self.aio_jikan.schedule(day=day)

        entries = []
        for weekday in weekdays:

            if weekday in scheduled:
                results = scheduled[weekday]
                for res in results:
                    res["weekday"] = weekday

                entries.extend(results)

        pages = ctx.menu(self.schedule_source(entries))
        await pages.start(ctx)

    @commands.command(aliases=["ra"])
    async def random_anime(self, ctx):
        """Get a random anime"""
        await self.random_anime_manga(ctx, "anime")

    @commands.command(aliases=["rm"])
    async def random_manga(self, ctx):
        """Get a random manga"""
        await self.random_anime_manga(ctx, "manga")


def setup(bot):
    bot.add_cog(MyAnimeList(bot))

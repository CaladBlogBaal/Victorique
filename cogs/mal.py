import typing
import random

from datetime import datetime as d

import discord
from discord.ext import commands

from jikanpy import AioJikan, ClientException

from config.utils.paginator import Paginator
from config.utils.converters import SeasonConverter


class MyAnimeList(commands.Cog, command_attrs=dict(cooldown=commands.Cooldown(1, 4, commands.BucketType.user))):
    """MAL related commands"""
    def __init__(self, bot):
        self.bot = bot
        self.aio_jikan = AioJikan(loop=bot.loop)

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, ClientException):
            await ctx.send(":no_entry: | invalid day was passed.", delete_after=3)

    @staticmethod
    def _embed(ctx, type_, result):
        embed = discord.Embed(title=f"{result['title']} \nMAL ID: {result['mal_id']}", color=ctx.bot.default_colors(),
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

    async def random_anime_manga(self, ctx, type_, genre_id=None):
        if not genre_id:
            genre_id = random.randint(1, 43)

        results = await self.aio_jikan.genre(type=type_, genre_id=genre_id)
        anime = random.choice(results[type_])
        return self._embed(ctx, type_, anime)

    async def seasonal_search(self, ctx, year, season):
        p = Paginator(ctx)
        if season == "Autumn":
            season = "fall"

        season_ = await self.aio_jikan.season(year=year, season=season)

        for result in season_["anime"]:
            await p.add_page(self._embed(ctx, "anime", result))

        try:
            await ctx.send(f"> Anime for {season} season of {year}.")
            await p.paginate()
        except IndexError:
            await ctx.send(f":no_entry: | search failed.")

    async def search_mal(self, ctx, query_type, query_):
        p = Paginator(ctx)
        query = await self.aio_jikan.search(search_type=query_type, query=query_)

        if query is None:
            return await ctx.send(f":no_entry: | search failed for `{query}`.")

        for result in query["results"][:10]:
            await p.add_page(self._embed(ctx, query_type, result))
        try:
            await p.paginate()
        except IndexError:
            await ctx.send(f":no_entry: | search failed for `{query_}`.")

    @commands.command()
    async def anime(self, ctx, *, anime_name):
        """Search for an anime on mal"""
        await self.search_mal(ctx, "anime", anime_name)

    @commands.command()
    async def manga(self, ctx, *, manga_name):
        """Search for a manga on mal"""
        await self.search_mal(ctx, "manga", manga_name)

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
    async def schedule(self, ctx, day=None):

        """Get a list anime based on their schedule"""

        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        for weekday in weekdays:
            if day.lower() in (weekday.lower()[:3], weekday.lower()[:4]):
                day = weekday

        p = Paginator(ctx)

        if not day:
            scheduled = await self.aio_jikan.schedule()

        else:
            scheduled = await self.aio_jikan.schedule(day=day)

        for weekday in weekdays:

            if weekday.lower() in scheduled:
                results = scheduled[weekday.lower()]

                embed = discord.Embed(title=f"Anime schedule for {weekday}", color=ctx.bot.default_colors())
                embed_two = None

                title_url_episodes_list = ((a["episodes"], a["title"], a["url"]) for a in results)

                description = ""

                for tuple_ in title_url_episodes_list:
                    episodes, title, url = tuple_

                    if episodes is None:
                        episodes = "Unknown"

                    description += f"[{title}]({url}): **Episodes** ({episodes})\n"
                    embed.description = description

                if len(description) > 2048:
                    description = description.split("\n")

                    index = len(description) // 2
                    first_half = description[:index]
                    second_half = description[index:]

                    embed.description = "\n".join(a for a in first_half)

                    embed_two = discord.Embed(title=f"Anime Schedule for {weekday} continued.",
                                              color=ctx.bot.default_colors())
                    embed_two.description = "\n".join(a for a in second_half)

                await p.add_page(embed)

                if embed_two:
                    await p.add_page(embed_two)

        await p.paginate()

    @commands.command()
    async def random_anime(self, ctx):
        """Get a random anime"""
        await ctx.send(embed=await self.random_anime_manga(ctx, "anime"))

    @commands.command()
    async def random_manga(self, ctx):
        """Get a random manga"""
        await ctx.send(embed=await self.random_anime_manga(ctx, "manga"))


def setup(bot):
    bot.add_cog(MyAnimeList(bot))

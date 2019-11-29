import typing
import random

from datetime import datetime as d

from bs4 import BeautifulSoup

import discord
from discord.ext import commands

from jikanpy import AioJikan, ClientException

from config.utils.paginator import Paginator
from config.utils.converters import SeasonConverter, MangaIDConverter, AnimeIDConverter

from loadconfig import PRIVATE_GUILDS


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

    async def get_recommendations(self, ctx, type_, id_):
        p = Paginator(ctx)
        await ctx.trigger_typing()
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

        for recommendation in recommendations["recommendations"][:10]:
            title = f"{recommendation['title']}\n{recommendation['mal_id']}"
            embed = discord.Embed(title=title, url=recommendation["url"])
            embed.set_image(url=recommendation["image_url"])
            request = await self.bot.fetch(recommendation['recommendation_url'])
            soup = BeautifulSoup(request, "html.parser")
            description = (soup.find("span", attrs={"style": "white-space: pre-wrap;"})).text
            embed.description = description
            embed.add_field(name="Recommendation Count", value=recommendation["recommendation_count"])
            await p.add_page(embed)

        await ctx.send(f"> Recommendations for {name}\n:{url}")
        await p.paginate()

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

    async def search_mal(self, ctx, query_type, query_, return_id=False):
        p = Paginator(ctx)

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
            return await ctx.send(f":no_entry: | search failed for `{query_}`.")

        if return_id:
            return results[0]["mal_id"]

        for result in results:
            await p.add_page(self._embed(ctx, query_type, result))

        await p.paginate()

    @commands.group(invoke_without_command=True)
    async def anime(self, ctx, *, anime_name):
        """Search for an anime on mal"""
        await self.search_mal(ctx, "anime", anime_name)

    @anime.command(name="staff")
    @commands.is_owner()
    async def anime_staff(self, ctx, *, anime_name_or_id: AnimeIDConverter):
        """Retrieves the staff for an anime from mal using it's name or mal id"""

        p = Paginator(ctx)

        anime = await self.aio_jikan.anime(anime_name_or_id, extension='characters_staff')

        if not anime:
            return

        name = (await self.aio_jikan.anime(anime_name_or_id))["title"]
        await ctx.send(f"> Staff for anime **{name}**")

        for staff in anime["staff"]:
            embed = discord.Embed(color=self.bot.default_colors())
            embed.title = staff["name"]
            embed.url = staff["url"]
            embed.set_image(url=staff["image_url"])
            embed.add_field(name="Positions", value=f"\n".join(f"`{pos}`" for pos in staff["positions"]))
            await p.add_page(embed)

        await p.paginate()

    @anime.command(name="recommendations", aliases=["r"])
    @commands.is_owner()
    async def anime_recommendations(self, ctx, *, anime_name_id: AnimeIDConverter):
        """Returns the first 10 recommendations for a anime"""
        await self.get_recommendations(ctx, "anime", anime_name_id)

    @commands.group(invoke_without_command=True)
    async def manga(self, ctx, *, manga_name):
        """Search for a manga on mal"""
        await self.search_mal(ctx, "manga", manga_name)

    @manga.command(name="staff")
    @commands.is_owner()
    async def manga_staff(self, ctx, *, manga_name_id: MangaIDConverter):
        """Retrieves the staff for a manga from mal using it's name or mal id"""

        p = Paginator(ctx)

        manga = await self.aio_jikan.manga(manga_name_id)
        name = manga["title"]
        await ctx.send(f"> Staff for manga **{name}**")

        for author in manga["authors"]:
            embed = discord.Embed(color=self.bot.default_colors())
            embed.title = author["name"]
            embed.url = author["url"]
            person_object = await self.aio_jikan.person(author["mal_id"])
            embed.set_image(url=person_object["image_url"])
            await p.add_page(embed)

        await p.paginate()

    @manga.command(name="recommendations", aliases=["r"])
    @commands.is_owner()
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

    @commands.command(aliases=["ra"])
    async def random_anime(self, ctx):
        """Get a random anime"""
        await ctx.send(embed=await self.random_anime_manga(ctx, "anime"))

    @commands.command(aliases=["rm"])
    async def random_manga(self, ctx):
        """Get a random manga"""
        await ctx.send(embed=await self.random_anime_manga(ctx, "manga"))


def setup(bot):
    bot.add_cog(MyAnimeList(bot))

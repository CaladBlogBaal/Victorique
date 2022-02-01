import typing

import discord
from discord.ext import commands

from cogs.utils.imageboards import Moebooru, AnimePicturesNet, Safebooru


class ImageBoards(commands.Cog, command_attrs=dict(cooldown=commands.CooldownMapping(commands.Cooldown(1, 3),
                                                                                     type=commands.BucketType.user))):
    """Anime image boards related commands
       divide tags with | or || or && **no mixing separators**

    """

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def range_check(amount):
        if amount > 20:
            return 20

        elif amount < 0:
            raise commands.BadArgument("Invalid number was passed.")

        return amount

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
        channel = await ctx.db.fetchval("SELECT nsfw_channel from guilds where guild_id = $1", ctx.guild.id)

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
        s = Safebooru(ctx)
        await s.get_posts()

    @sb.command(name="search")
    async def search_sb(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on safebooru from a random page"""

        s = Safebooru(ctx)
        await s.get_posts(tags, amount)

    @commands.group(invoke_without_command=True, ignore_extra=False)
    async def apn(self, ctx):
        """
        Gets a random image from anime-pictues.net
        """
        a = AnimePicturesNet(ctx)
        await a.get_posts()

    @apn.command(name="search")
    async def search_apn(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on anime pictures net
           20 is the maximum"""

        a = AnimePicturesNet(ctx)
        await a.get_posts(tags, amount)

    @commands.group(invoke_without_command=True, ignore_extra=False)
    async def ye(self, ctx):
        """
        Gets a random image from yande.re
        """

        m = Moebooru(ctx, "yandere")
        await m.get_posts()

    @ye.command(aliases=["yande_search", "search"])
    async def ye_search(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on yande.re
        20 is the maximum"""

        amount = self.range_check(amount)
        m = Moebooru(ctx, "yandere")
        await m.get_posts(tags, amount)

    @commands.group(invoke_without_command=True, ignore_extra=False)
    async def gb(self, ctx):

        """
        Gets a random image from gelbooru
        """
        m = Moebooru(ctx, "gelbooru")
        await m.get_posts()

    @gb.command(aliases=["gelbooru_search", "search"])
    async def gb_search(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on gelbooru
        20 is the maximum"""

        amount = self.range_check(amount)
        m = Moebooru(ctx, "gelbooru")
        await m.get_posts(tags, amount)

    @commands.group(invoke_without_command=True, ignore_extra=False)
    async def kc(self, ctx):
        """
        Gets a random image from konachan
        """

        m = Moebooru(ctx, "konachan")
        await m.get_posts()

    @kc.command(aliases=["konachan_search", "search"])
    async def kc_search(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on konachan
        20 is the maximum"""

        amount = self.range_check(amount)
        m = Moebooru(ctx, "konachan")
        await m.get_posts(tags, amount)

    @commands.group(invoke_without_command=True, ignore_extra=False, name="lb")
    async def loli(self, ctx):
        """
        Gets a random image from lolibooru
        """
        m = Moebooru(ctx, "lolibooru")
        await m.get_posts()

    @loli.command(aliases=["lolibooru_search", "search"])
    async def loli_search(self, ctx, amount: typing.Optional[int] = 1, *, tags):
        """Search for a picture on lolibooru
        20 is the maximum"""

        amount = self.range_check(amount)
        m = Moebooru(ctx, "lolibooru")
        await m.get_posts(tags, amount)


def setup(bot):
    bot.add_cog(ImageBoards(bot))

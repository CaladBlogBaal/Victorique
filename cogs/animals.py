import copy
import random
import json
import typing

import discord
from discord.ext import commands

from config.utils.paginator import Paginator


class Animals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.animals = ["bird", "cat", "dog", "fox", "koala", "panda"]

    async def api_get_image(self, content, url, key, ctx, amount=1):
        p = Paginator(ctx)

        if amount < 1:
            return

        if amount > 20:
            amount = 20

        for _ in range(amount):

            js = await self.bot.fetch(url)

            while js[key].endswith(".mp4"):
                js = await self.bot.fetch(url)

            colours = [discord.Color.dark_magenta(), discord.Color.dark_teal(), discord.Color.dark_orange()]
            col = int(random.random() * len(colours))
            content = content
            embed = discord.Embed(color=colours[col],
                                  description=random.choice(content),)
            embed.set_image(url=js[key])
            await p.add_page(embed)

        await p.paginate()

    @commands.group(aliases=["a_fact"])
    async def animal_fact(self, ctx):
        """The main command for animal facts, called by itself will produce a random animal fact."""

        if ctx.invoked_subcommand:
            name = ctx.invoked_subcommand.name
            js = await self.bot.fetch(f"https://some-random-api.ml/facts/"f"{name}")
            return await ctx.send(js["fact"])

        if ctx.message.content != f"{ctx.prefix}animal_fact":
            return

        random_animal = random.choice(self.animals)
        js = await self.bot.fetch(f"https://some-random-api.ml/facts/{random_animal}")
        await ctx.send(js["fact"])

    @animal_fact.command(name="cat")
    async def cat_fact(self):
        """get a cat fact"""
        return

    @animal_fact.command(name="dog")
    async def dog_fact(self):
        """get a dog fact"""
        return

    @animal_fact.command(name="bird")
    async def bird_fact(self):
        """get a bird fact"""
        return

    @animal_fact.command(name="panda")
    async def panda_fact(self):
        """get a panda fact"""
        return

    @animal_fact.command(name="fox")
    async def fox_fact(self):
        """get a fox fact"""
        return

    @animal_fact.command(name="koala")
    async def koala_fact(self):
        """get a koala fact"""
        return

    @commands.command()
    async def fox(self, ctx, amount=1):
        """
        get a random picture of a fox
        20 is the maximum
        """
        await self.api_get_image([""], "https://randomfox.ca/floof/", "image", ctx, amount)

    @commands.command()
    async def duck(self, ctx, amount=1):
        """
        get a random picture of a duck
        20 is the maximum
        """
        await self.api_get_image([""], "https://random-d.uk/api/v2/random", "url", ctx, amount)

    @commands.command(aliases=["catto", "kitty", "cattie"])
    async def cat(self, ctx, amount=1):
        """
        get a random picture of a cat
        20 is the maximum
        """
        await self.api_get_image([""], "http://aws.random.cat/meow", "file", ctx, amount)

    @commands.command(aliases=["birb"])
    async def bird(self, ctx, amount=1):
        """
        get a random picture of a bird
        20 is the maximum
        """
        p = Paginator(ctx)
        colours = [discord.Color.dark_magenta(), discord.Color.dark_teal(), discord.Color.dark_orange()]

        for _ in range(amount):
            js = await self.bot.fetch("http://random.birb.pw/tweet.json/")
            js = json.loads(js)
            col = int(random.random() * len(colours))
            embed = discord.Embed(color=colours[col])
            embed.set_image(url="https://random.birb.pw/img/" + js["file"])
            await p.add_page(embed)

        await p.paginate()

    @commands.command(aliases=["doggo", "trooper"])
    async def dog(self, ctx, amount: typing.Optional[int]=1, breed=None):
        """
        get a random picture of a dog
        20 is the maximum
        """

        if breed:
            await self.api_get_image([""], f"https://dog.ceo/api/breed/{breed}/images/random", "message", ctx, amount)

        await self.api_get_image([""], "https://random.dog/woof.json", "url", ctx, amount)

    @commands.command()
    async def pug(self, ctx, amount):
        msg = copy.copy(ctx.message)
        msg.content = f"{ctx.prefix}dog {amount} pug"
        new_ctx = await self.bot.get_context(msg)
        # to not raise an asyncpg.exceptions._base.InterfaceError exception
        new_ctx.con = await new_ctx.con
        await new_ctx.reinvoke()

    @commands.command()
    async def lizard(self, ctx, amount=1):
        """
        get a random picture of a lizard
        20 is the maximum
        """

        await self.api_get_image([""], "https://some-random-api.ml/img/lizard", "link", ctx, amount)

    @commands.command()
    async def koala(self, ctx, amount=1):
        """
        get a random picture of a koala
        20 is the maximum
        """

        await self.api_get_image([""], "https://some-random-api.ml/img/koala", "link", ctx, amount)

    @commands.command()
    async def panda(self, ctx, amount=1):
        """
        get a random picture of a panda
        20 is the maximum
        """

        await self.api_get_image([""], "https://some-random-api.ml/img/panda", "link", ctx, amount)


def setup(bot):
    n = Animals(bot)
    bot.add_cog(n)

import copy
import random
import json
import typing

import discord
from discord.ext import commands


class Animals(commands.Cog):
    """Animal Related Commands"""
    def __init__(self, bot):
        self.bot = bot
        self.animals = ["bird", "cat", "dog", "fox", "koala", "panda"]

    async def api_get_image_repeated(self, content, url, key, ctx, amount=1):

        if amount < 1:
            return

        if amount > 20:
            amount = 20

        data = [await self.bot.api_get_image(content, url, key) for _ in range(amount)]
        
        pages = ctx.menu(ctx.list_source(data))
        await pages.start(ctx)

    @commands.group(aliases=["afact"], ignore_extra=False)
    async def animal_fact(self, ctx):
        """The main command for animal facts, called by itself will produce a random animal fact."""

        if ctx.invoked_subcommand:
            name = ctx.invoked_subcommand.name
            js = await self.bot.fetch(f"https://some-random-api.ml/facts/"f"{name}")
            return await ctx.send(f'> {js["fact"]}')

        random_animal = random.choice(self.animals)
        js = await self.bot.fetch(f"https://some-random-api.ml/facts/{random_animal}")
        await ctx.send(f'> {js["fact"]}')

    @animal_fact.command(name="cat")
    async def cat_fact(self):
        """Get a cat fact"""
        return

    @animal_fact.command(name="dog")
    async def dog_fact(self):
        """Get a dog fact"""
        return

    @animal_fact.command(name="bird")
    async def bird_fact(self):
        """Get a bird fact"""
        return

    @animal_fact.command(name="panda")
    async def panda_fact(self):
        """Get a panda fact"""
        return

    @animal_fact.command(name="fox")
    async def fox_fact(self):
        """Get a fox fact"""
        return

    @animal_fact.command(name="koala")
    async def koala_fact(self):
        """Get a koala fact"""
        return

    @commands.command()
    async def fox(self, ctx, amount=1):
        """
        Get a random picture of a fox
        20 is the maximum
        """
        await self.api_get_image_repeated([""], "https://randomfox.ca/floof/", "image", ctx, amount)

    @commands.command()
    async def duck(self, ctx, amount=1):
        """
        Get a random picture of a duck
        20 is the maximum
        """
        await self.api_get_image_repeated([""], "https://random-d.uk/api/v2/random", "url", ctx, amount)

    @commands.command(aliases=["catto", "kitty", "cattie"])
    async def cat(self, ctx, amount=1):
        """
        Get a random picture of a cat
        20 is the maximum
        """
        await self.api_get_image_repeated([""], "http://aws.random.cat/meow", "file", ctx, amount)

    @commands.command(aliases=["birb"])
    async def bird(self, ctx, amount=1):
        """
        Get a random picture of a bird
        20 is the maximum
        """
        colours = [discord.Color.dark_magenta(), discord.Color.dark_teal(), discord.Color.dark_orange()]

        for _ in range(amount):
            js = await self.bot.fetch("http://random.birb.pw/tweet.json/")
            js = json.loads(js)
            embed = discord.Embed(color=random.choice(colours))
            embed.set_image(url="https://random.birb.pw/img/" + js["file"])
            await ctx.paginator.add_page(embed)

        await ctx.paginator.paginate()

    @commands.command(aliases=["doggo", "trooper"])
    async def dog(self, ctx, amount: typing.Optional[int]=1, breed=None):
        """
        Get a random picture of a dog
        20 is the maximum
        """

        if breed:
            return await self.api_get_image_repeated(
                [""], f"https://dog.ceo/api/breed/{breed}/images/random", "message", ctx, amount)

        await self.api_get_image_repeated([""], "https://random.dog/woof.json", "url", ctx, amount)

    @commands.command()
    async def pug(self, ctx, amount):
        """Get a random picture of a pug"""
        msg = copy.copy(ctx.message)
        msg.content = f"{ctx.prefix}dog {amount} pug"
        new_ctx = await self.bot.get_context(msg)
        await new_ctx.reinvoke()

    @commands.command()
    async def lizard(self, ctx, amount=1):
        """
        Get a random picture of a lizard
        20 is the maximum
        """

        await self.api_get_image_repeated([""], "https://some-random-api.ml/img/lizard", "link", ctx, amount)

    @commands.command()
    async def koala(self, ctx, amount=1):
        """
        Get a random picture of a koala
        20 is the maximum
        """

        await self.api_get_image_repeated([""], "https://some-random-api.ml/img/koala", "link", ctx, amount)

    @commands.command()
    async def panda(self, ctx, amount=1):
        """
        Get a random picture of a panda
        20 is the maximum
        """

        await self.api_get_image_repeated([""], "https://some-random-api.ml/img/panda", "link", ctx, amount)


def setup(bot):
    n = Animals(bot)
    bot.add_cog(n)

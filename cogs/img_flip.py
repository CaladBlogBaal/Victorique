import re
import copy
import random
import typing

import discord
from discord.ext import commands

import loadconfig
from cogs.utils import memes
from config.utils.context import Context


class Imgflip:

    def __init__(self, ctx: Context, username=loadconfig.__img_flip_username__,
                 password=loadconfig.__img_flip_password__):
        self.ctx = ctx
        self.username = username
        self.password = password
        self.memes = memes.memes

    async def caption_image(self, meme, text0, text1, max_font_size=25):

        if self.username is None or self.password is None:
            await self.ctx.send("Username and password required to caption image/generate images.")
            raise RuntimeError("Username and password required to caption image.")

        params = {'username': self.username, 'password': self.password,

                  'template_id': meme,

                  'text0': text0,

                  'text1': text1,


                  'max_font_size': max_font_size}

        results = await self.ctx.bot.fetch("https://api.imgflip.com/caption_image", params=params)

        if results['success']:
            return results["data"]["url"]

        if results["error_message"] == "No texts specified. Remember, API request params are http parameters not JSON.":
            await self.ctx.send("No texts specified. or meme name/id")
            raise RuntimeError("Imgflip returned error message: " + results['error_message'])

        await self.ctx.send(results["error_message"])
        raise RuntimeError("Imgflip returned error message: " + results['error_message'])


class NekoBot:
    def __init__(self, ctx):
        self.bot = ctx.bot

    async def get_image(self, **kwargs):
        key = kwargs["key"]
        del kwargs["key"]
        js = await self.bot.fetch("https://nekobot.xyz/api/imagegen", params=kwargs)
        colours = [discord.Color.dark_magenta(), discord.Color.dark_teal(), discord.Color.dark_orange()]
        col = int(random.random() * len(colours))
        embed = discord.Embed(color=colours[col])
        embed.set_image(url=js[key])
        return embed


class ImageFlip(commands.Cog):
    """Image flip related commands divide args with | or || or &&
    **no mixing separators**"""
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def string_splice(comment, index):
        if len(comment) > index:
            return " ".join([comment[0:index]])
        return comment

    @commands.group(name="memes", aliases=["meme"])
    async def img_flip_memes(self, ctx: Context):
        """The main command for creating imgflip memes does nothing by itself"""
        
    @img_flip_memes.command(name="list", aliases=["l"])
    async def img_flip_meme_list(self, ctx: Context):
        """Get a list of valid meme templates"""

        i = Imgflip(ctx)
        results = i.memes
        entries = []
        embed = discord.Embed(color=self.bot.default_colors())
        count = 0
        for dict_ in results:
            for meme_name, meme_id in dict_.items():
                embed.add_field(name=meme_name, value=f"ID:\n{meme_id['template_id']}")
                count += 1
                if count == 5:
                    entries.append(embed)
                    embed = discord.Embed(color=self.bot.default_colors())
                    count = 0

        pages = ctx.menu(ctx.list_source(entries))
        await pages.start(ctx)

    @img_flip_memes.command(name="generate", aliases=["g"])
    async def img_flip_generate(self, ctx: Context, *, args):
        """Generate a meme as you'd if you were using imgflip make sure it exists in the list of memes
        In the format (meme name or id separator top text separator bottom text)
        do (vic meme list) for a list of possible memes to be generated
        example usage, vic meme g What Do We Want | shitty memes | now"""
        i = Imgflip(ctx)

        args = args.replace("||", "\u200B").replace("|", "\u200B").replace("&&", "\u200B")
        args = args.split("\u200B")

        meme = args[0].rstrip().lstrip()
        for js in i.memes:
            if meme.lower() in next(js.keys().__iter__()).lower():
                meme = js.get(next(js.keys().__iter__()))['template_id']
        try:
            top_text = args[1] or ""
        except IndexError:
            top_text = ""

        try:
            bottom_text = args[2]
        except IndexError:
            bottom_text = ""
        await ctx.send(await i.caption_image(meme, top_text, bottom_text))

    @img_flip_memes.command(name="format", aliases=["f"])
    async def img_flip_format(self, ctx: Context, *, name):
        """Get the format of a meme make sure it exists in the list of memes"""
        msg = copy.copy(ctx.message)
        msg.content = ctx.prefix + f"meme g {name} | | |"
        new_ctx = await self.bot.get_context(msg)
        await new_ctx.reinvoke()

    @commands.command()
    async def phc(self, ctx: Context, *, comment: commands.clean_content):
        """Generate a porn hub comment using the nekobot api"""
        comment = ctx.emote_unescape(comment)
        comment = comment.replace("&", "%26")
        n = NekoBot(ctx)

        kwargs = {"type": "phcomment",
                  "image": str(ctx.author.avatar.replace(format="png")),
                  "text": comment,
                  "username": ctx.author.name,
                  "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))

    @commands.command()
    async def tweet(self, ctx: Context, *, comment: commands.clean_content):
        """Generate a tweet using the nekobot api"""
        n = NekoBot(ctx)
        comment = ctx.emote_unescape(comment)
        comment = re.findall(r"\[[^\]]*\]|\([^)]*\)|\"[^\"]*\"|\S+", comment)

        username = [word for i, word in enumerate(comment) if word.startswith("@")]

        if username:
            comment = [word for word in comment if not word.startswith("@")]
            username = username[0]

        else:
            username = ctx.author.name

        comment = " ".join(comment)
        comment = self.string_splice(comment, 72)

        kwargs = {"type": "tweet",
                  "text": comment,
                  "username": username,
                  "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))

    @commands.command()
    async def t_tweet(self, ctx: Context, *, comment: commands.clean_content):
        """Generate a trump tweet using the neko bot api"""
        n = NekoBot(ctx)

        comment = ctx.emote_unescape(comment)
        comment = self.string_splice(comment, 72)

        kwargs = {"type": "trumptweet",
                  "text": comment,
                  "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))

    @commands.command()
    async def cmm(self, ctx: Context, *, comment: commands.clean_content):
        """Generate a change my mind image using the nekobot api."""
        await ctx.typing()
        n = NekoBot(ctx)
        comment = ctx.emote_unescape(comment)
        comment = self.string_splice(comment, 79)

        kwargs = {
            "type": "changemymind",
            "text": comment,
            "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))

    @commands.command()
    async def www(self, ctx: Context, *, member: typing.Union[discord.Member, discord.User]):
        """Generate a who would win image using the nekobot api."""

        n = NekoBot(ctx)
        kwargs = {"type": "whowouldwin",
                  "user1": str(ctx.author.avatar.replace(format="png")),
                  "user2": str(member.avatar.replace(format="png")),
                  "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))


async def setup(bot):
    n = ImageFlip(bot)
    await bot.add_cog(n)

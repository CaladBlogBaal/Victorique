import re
import copy
import random

import discord
from discord.ext import commands

import loadconfig
from config.utils.paginator import Paginator
from cogs.utils import memes


class Imgflip:

    def __init__(self, ctx, username=loadconfig.__img_flip_username__, password=loadconfig.__img_flip_password__):
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
        self.post_url = ""

    def set_post_url(self, url):
        self.post_url = url

    async def get_image(self, **kwargs):
        key = kwargs["key"]
        del kwargs["key"]
        js = await self.bot.fetch(self.post_url, params=kwargs)
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

    @commands.command(aliases=["memes", "memes_list"])
    async def img_flip_memes(self, ctx):
        p = Paginator(ctx)
        i = Imgflip(ctx)
        results = i.memes
        colours = [discord.Color.dark_magenta(), discord.Color.dark_teal(), discord.Color.dark_orange()]
        col = int(random.random() * len(colours))
        embed = discord.Embed(title=" ", description=" ", color=colours[col])
        count = 0
        for dict_ in results:
            for meme_name, meme_id in dict_.items():
                embed.add_field(name=meme_name, value=f"ID:\n{meme_id['template_id']}")
                count += 1
                if count == 5:
                    await p.add_page(embed)
                    embed = discord.Embed(title=" ", description=" ", color=colours[col])
                    count = 0
        await p.paginate()

    @commands.command(aliases=["meme_generate", "meme_g"])
    async def img_flip_generate(self, ctx, *, args):
        """Generate a meme as you'd if you were using imgflip make sure it exists in the list of memes
        In the format (meme name or id separator top text separator bottom text)
        do ?img_flip_memes for a list of possible memes to be generated
        example usage, vic meme_g What Do We Want | shitty memes | now"""
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

    @commands.command(aliases=["meme_format", "meme_f"])
    async def img_flip_format(self, ctx, *, name):
        """Get the format of a meme make sure it exists in the list of memes"""
        msg = copy.copy(ctx.message)
        msg.content = ctx.prefix + f"meme_g {name} | | |"
        new_ctx = await self.bot.get_context(msg)
        await new_ctx.reinvoke()

    @commands.command()
    async def phc(self, ctx, *, comment: commands.clean_content):
        """generate a porn hub comment using the nekobot api"""
        comment = ctx.emote_unescape(comment)
        comment = comment.replace("&", "%26")
        n = NekoBot(ctx)
        n.set_post_url("https://nekobot.xyz/api/imagegen?type=phcomment")

        kwargs = {"image": f"{ctx.author.avatar_url_as(format='png')}",
                  "text": f"{comment}",
                  "username": f"{ctx.author.name}",
                  "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))

    @commands.command()
    async def tweet(self, ctx, *, comment: commands.clean_content):
        """generate a tweet using the nekobot api"""
        n = NekoBot(ctx)
        n.set_post_url("https://nekobot.xyz/api/imagegen?type=tweet")
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

        kwargs = {"text": f"{comment}",
                  "username": f"{username}",
                  "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))

    @commands.command()
    async def t_tweet(self, ctx, *, comment: commands.clean_content):
        """generate a trump tweet using the neko bot api"""
        n = NekoBot(ctx)
        n.set_post_url("https://nekobot.xyz/api/imagegen?type=trumptweet")
        comment = ctx.emote_unescape(comment)
        comment = self.string_splice(comment, 72)

        kwargs = {"text": f"{comment}",
                  "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))

    @commands.command()
    async def cmm(self, ctx, *, comment: commands.clean_content):
        """generate a change my mind image"""
        await ctx.trigger_typing()
        n = NekoBot(ctx)
        n.set_post_url("https://nekobot.xyz/api/imagegen?type=changemymind")
        comment = ctx.emote_unescape(comment)
        comment = self.string_splice(comment, 79)

        kwargs = {
            "text": f"{comment}",
            "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))

    @commands.command()
    async def whw(self, ctx, *, member: discord.Member):
        """generate a who would win image using the nekobot api."""

        n = NekoBot(ctx)
        n.set_post_url("https://nekobot.xyz/api/imagegen?type=whowouldwin")
        kwargs = {"user1": f"{ctx.author.avatar_url_as(format='png')}",
                  "user2": f"{member.avatar_url_as(format='png')}",
                  "key": "message"}

        await ctx.send(embed=await n.get_image(**kwargs))


def setup(bot):
    n = ImageFlip(bot)
    bot.add_cog(n)

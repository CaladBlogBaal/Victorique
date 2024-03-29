import typing
import random
import math
import re
import asyncio
import dateutil.parser

import discord
from discord.ext import commands
from bs4 import BeautifulSoup

from config.utils.emojis import TRANSPARENT, EXPLOSION, FIRE_ZERO, NUKE, GUN
from config.utils.checks import private_guilds_check
from config.utils.menu import page_source
from config.utils.context import Context


class ShapeDrawing:
    def __init__(self, emotes: list, emotes_two: list, size: int):
        if not emotes:
            raise commands.BadArgument("missing emotes")
        self.emotes = emotes
        self.emotes_two = emotes_two
        self.size = size if size <= 15 else 15
        # this is crude
        if self.size <= 0:
            raise commands.BadArgument("invalid number")

    def triangle_draw(self, reverse_=False):
        message = ""
        size = self.size

        if reverse_ is True:
            size = 0
            for i in range(self.size - math.floor(self.size / 2), 0, -1):
                emote = random.choice(self.emotes)
                emote_two = random.choice(self.emotes_two)
                message += emote_two * math.floor(size / 2)
                message += emote * (2 * i - 1)
                message += emote_two * math.floor(size / 2)
                size += 2
                message += "\n"

            return message

        for i in range(self.size - math.floor(self.size / 2)):
            emote = random.choice(self.emotes)
            emote_two = random.choice(self.emotes_two)
            message += emote_two * math.floor(size / 2)
            message += emote * (1 + 2 * i)
            message += emote_two * math.floor(size / 2)
            size -= 2
            message += "\n"

        return message

    def diamond_draw(self):
        top_half = self.triangle_draw()
        bottom_half = self.triangle_draw(True)

        return top_half, bottom_half


def to_upper(argument):
    return argument.upper()


def to_lower(argument):
    return argument.lower()


def reverse(argument):
    return argument[::-1]


class Misc(commands.Cog):
    """Some misc related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.transparent = str(TRANSPARENT)
        self.explosion = str(EXPLOSION)
        self.fire_zero = str(FIRE_ZERO)
        self.nuke = str(NUKE)
        self.gun = str(GUN)
        self.lick_list = [
            "https://cdn.weeb.sh/images/Sk7xeAdwb.gif",
            "https://cdn.weeb.sh/images/HJRRyAuP-.gif",
            "https://cdn.weeb.sh/images/H1EJxR_vZ.gif",
            "https://cdn.weeb.sh/images/Syg8gx0OP-.gif",
            "https://cdn.weeb.sh/images/Bkagl0uvb.gif",
            "https://cdn.weeb.sh/images/rJ6hrQr6-.gif",
            "https://cdn.weeb.sh/images/rykRHmB6W.gif",
            "https://preview.redd.it/m6twh6h7qxx11.gif?width=500&format=mp4&s=202e9f4e030f04999041ad962e82f7533c98bd94",
            "https://i.kym-cdn.com/photos/images/original/001/063/319/24e.gif",
            "https://33.media.tumblr.com/88736039b8ce3621bbd27183c6e226ff/tumblr_nrlp9qqoHQ1t0p1pao1_500.gif",
            "https://media0.giphy.com/media/NzbcdfP2B6GKk/200.gif",
            "https://img1.ak.crunchyroll.com/i/spire2/a8a77a784ffde43c16bf7df10c447bd81437882910_full.gif",
            "https://images.rapgenius.com/abbb4fb420fb5becf35dc05ab9cdbe72.500x375x13.gif",
            "https://38.media.tumblr.com/fbb9d202ce5418fe96a8964d2cb63ac0/tumblr_nrulg4sv8l1qcsnnso1_500.gif",
            "https://38.media.tumblr.com/a6ff26b3fb8914a8aef9e3ee12b95f96/tumblr_nbjrmc3tiI1std21fo1_500.gif",
            "https://33.media.tumblr.com/cb86adbde8dd8feaa586eda4ad29d4be/tumblr_njx8yblrf51tiz9nro1_500.gif"
        ]

        # Feel like this is cleaner
        # rip Misc Help
        action_cmd_names = ["slap", "pat", "cuddle", "hug", "poke",
                            "tickle", "kiss", "dance", "nyah", "shrug", "sleep",
                            "slowclap"]
        for name in action_cmd_names:

            async def callback(ctx: Context, member: typing.Union[discord.Member, discord.User] = ""):

                if member:
                    member = member.mention

                bot_urls = {"slap": "https://giffiles.alphacoders.com/197/197854.gif",
                            "pat": "https://thumbs.gfycat.com/ClearFalseFulmar-small.gif",
                            "kiss": "https://media2.giphy.com/media/24PHsMnvGUVdS/source.gif",
                            "poke": "https://66.media.tumblr.com/b061114bf8251a4f037c651bd2a86a1c"
                                    "/tumblr_mr1bfrQ9Jb1qeysf2o3_500.gif",
                            "hug": "https://media1.tenor.com/images/ebba558cbe12af15a4422f583ef2bb86/tenor.gif"}

                if ctx.bot.user.mentioned_in(ctx.message):
                    url = bot_urls.get(ctx.command.name)
                    return await ctx.send(embed=discord.Embed(color=self.bot.default_colors()).set_image(url=url))

                action = ctx.command.name.replace("e", "", 1)

                if action.endswith("p"):
                    action = action + "p"

                elif action in "pat":
                    action = action + "t"

                content = [f"**{ctx.author.mention} is {action}ing {member}!**"]
                await ctx.send(
                    embed=await self.bot.api_get_image(content,
                                                       f"https://api.otakugifs.xyz/gif?reaction={ctx.command.name}",
                                                       "url"))

            cmd_help = name.capitalize() + " a guild member or user"
            cmd = commands.Command(callback, name=name, help=cmd_help)
            self.bot.add_command(cmd)

    @staticmethod
    def hardcoded_image_list_embed(content, list_in):
        colours = [discord.Color.dark_magenta(), discord.Color.dark_teal(), discord.Color.dark_orange()]
        col = int(random.random() * len(colours))

        embed = discord.Embed(color=colours[col], description=random.choice(content))
        embed.set_image(url=random.choice(list_in))

        return embed

    @staticmethod
    @page_source(per_page=7)
    def emote_source(self, menu, entries):
        embed = discord.Embed(title=f"{self.ctx.guild.name} emotes",
                              color=discord.Color.dark_magenta())

        for emote in entries:
            value = f"Emote {self.count}"
            embed.add_field(name=f"Emote name " f"{emote.name} : {str(emote)}",
                            value=value, inline=False)
            self.count += 1
        return embed

    @staticmethod
    @page_source(per_page=1)
    def urban_source(self, menu, entry):
        word = entry["word"]
        definition = " ".join(entry["definition"][:1024 + 1].split(' ')[0:-1]) + " ..."

        example = entry["example"]

        if example == "":
            example = "No example(s)"

        url = entry["permalink"]
        written_on = dateutil.parser.parse(entry['written_on']).strftime('%Y-%m-%d %H:%M:%S')
        author = f"written by {entry['author']} on {written_on}"

        embed = discord.Embed(title='Word/Term: ' + word,
                              description=f"**Definition**:\n{definition}",
                              color=discord.Color.dark_magenta(),
                              url=url)
        embed.add_field(name="Example", value=example)
        embed.add_field(name="Contributor", value=author, inline=False)
        embed.add_field(name="Rating", value=f"\👍**{entry['thumbs_up']}** \👎**{entry['thumbs_down']}**")
        embed.set_footer(text=f"Requested by {self.ctx.message.author.name}",
                         icon_url=self.ctx.message.author.avatar.url)
        embed.set_image(url="https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/UD_"
                            "logo-01.svg/1280px-UD_logo-01.svg.png")

        embed.timestamp = self.ctx.message.created_at
        return embed

    @commands.command()
    async def triangle(self, ctx: Context, size: typing.Optional[int] = 5, emote=":small_red_triangle:",
                       emote_two=None, reverse_triangle=False):
        """Draw a triangle
        say trans as a wild card for a transparent emote and True for a reversed triangle."""
        emote = await commands.clean_content().convert(ctx, emote)

        if emote_two is None or emote_two.lower() == "trans":
            emote_two = self.transparent

        else:
            emote_two = await commands.clean_content().convert(ctx, emote_two)

        shape = ShapeDrawing([emote], [emote_two], size)
        triangle = shape.triangle_draw(reverse_triangle)

        while len(triangle) >= 2000:
            size -= 1
            shape.size = size
            triangle = shape.triangle_draw(reverse_triangle)

        await ctx.send(shape.triangle_draw(reverse_triangle))

    @commands.command()
    async def diamond(self, ctx: Context, size: typing.Optional[int] = 5, *emotes: commands.clean_content):
        """Draw a diamond
        if more than one emote is passed will default to random emote for each row"""
        shape = ShapeDrawing(list(emotes), [self.transparent], size)

        top, bottom = shape.diamond_draw()

        while len(top) >= 2000:
            size -= 1
            shape.size = size
            top, bottom = shape.diamond_draw()
        try:

            await ctx.send(top + bottom)

        except discord.errors.HTTPException:

            await ctx.send(top)
            await ctx.send(bottom)

    @commands.dm_only()
    @commands.command()
    async def chat(self, ctx: Context, message):
        """Get a response from the bot"""

        params = {"message": message}

        result = await self.bot.fetch("https://some-random-api.ml/chatbot", params=params)
        if ctx.guild:
            await ctx.message.add_reaction("📧")
            return await ctx.author.send(result["response"])

        await ctx.typing()

        await ctx.send(result["response"])

    @commands.command()
    async def matb(self, ctx: Context, *, text: commands.clean_content = None):
        """
        Me and the boys
        by calling this command you summon the boys
        this command takes one optional parameter the text to
        accompany the boys eg ?matb posting a dead meme
        """
        if text is None:
            text = ""
        await ctx.send(f"<:me:589614537775382552>"
                       f"<:and:589614537867657235>"
                       f"<:the:589614537309945878>"
                       f"<:boys:589614537490300940> {text}")

    @commands.command()
    async def destroy(self, ctx: Context, *, message=None):
        """
        Destroy something
        """

        message = ctx.safe_everyone(message)
        message = message or ctx.author.display_name

        if self.bot.user in ctx.message.mentions:
            await ctx.send("nou")
            await asyncio.sleep(1)
            message = ctx.author.display_name

        msg = await ctx.send(f"{self.gun}{self.transparent}{message}")
        await asyncio.sleep(0.5)
        await msg.edit(content=f"{self.gun}{self.fire_zero}{message}")
        await asyncio.sleep(0.5)
        await msg.edit(content=f"{self.gun}{self.fire_zero}:boom:")
        await asyncio.sleep(0.2)
        await msg.edit(content=f"{self.gun}{self.fire_zero}{self.explosion}")
        await asyncio.sleep(2)
        await msg.edit(content=f"{self.gun}{self.fire_zero}{self.nuke}")
        await asyncio.sleep(0.2)
        await msg.edit(content=f"{self.gun}{self.fire_zero}")
        await msg.edit(content=f"Target destroyed.")

    @commands.command()
    async def clap(self, ctx: Context, *, message: commands.clean_content):
        """
        Fill your message with claps
        """
        text = re.findall(r"\[[^\]]*\]|\([^)]*\)|\"[^\"]*\"|\S+", message)
        text = " :clap: ".join(word for word in text)
        await ctx.send(text)

    @commands.command(aliases=["emotes"])
    @commands.guild_only()
    async def display_emotes(self, ctx: Context):
        """
        Display the current emojis for the guild
        """
        # for formatting
        self.emote_source.ctx = ctx
        self.emote_source.count = 1
        pages = ctx.menu(self.emote_source(ctx.guild.emojis))

        await pages.start(ctx)

    @commands.command(aliases=["l_c"], hidden=True)
    @commands.guild_only()
    @private_guilds_check()
    async def licc_calad(self, ctx: Context):
        """
        Lick calad
        """
        member = ctx.guild.get_member(295325269558951936)
        author = ctx.author.mention
        mention = member.mention

        content = [f"**woah {author} is licking {mention}**"]

        if author == mention:
            content = [f"**{author} is licking himself?**"]

        colours = [discord.Color.dark_magenta(), discord.Color.dark_teal(), discord.Color.dark_orange()]
        col = int(random.random() * len(colours))

        embed = discord.Embed(color=colours[col], description=random.choice(content))
        embed.set_image(url=random.choice(self.lick_list))

        await ctx.send(embed=embed)

    @commands.command(alasies=["genetically_engineered_cat_girls"])
    async def gecg(self, ctx: Context):
        """
        Get a random genetically engineered cat girl meme
        """
        await ctx.send(embed=await self.bot.api_get_image([""], "https://nekos.life/api/v2/img/gecg", "url"))

    @commands.command()
    async def wink(self, ctx):
        """Get a random wink"""
        await ctx.send(embed=await self.bot.api_get_image([f"{ctx.author.mention} is winking"],
                                                          "https://some-random-api.ml/animu/wink", "link"))

    @commands.command()
    async def smug(self, ctx: Context):
        """
        Get a random image to express your smugness
        """

        author = ctx.message.author.mention

        content = [f"**{author} has a smug look on their face!**",
                   f"**{author} is looking a bit smug.**",
                   f"**{author} has become one with the smug.**"]

        await ctx.send(embed=await self.bot.api_get_image(content, "https://nekos.life/api/v2/img/smug", "url"))

    @commands.command()
    async def lick(self, ctx: Context, member: typing.Union[discord.Member, discord.User]):
        """
        Lick a guild member or user
        """
        author = ctx.message.author.mention

        mention = member.mention

        content = [f"**{author} gave {mention} a lick!**",
                   f"**{author} is licking {mention} kinky.**"]

        if author == mention:
            return await ctx.send("https://m.imgur.com/gallery/Br00TCn")

        await ctx.send(embed=self.hardcoded_image_list_embed(content, self.lick_list))

    @commands.command(aliases=["tb", "rub"])
    async def tummy_rub(self, ctx: Context, member: typing.Union[discord.Member, discord.User]):
        """
        Rub a guild member's tummy or user
        """
        author = ctx.message.author.mention

        mention = member.mention

        rub_list = ["https://cdn.discordapp.com/attachments/559132081465196554/599429989821186068/20190713_034027.gif",
                    "https://giphy.com/gifs/cat-2QHLYZFJgjsFq",
                    "https://thumbs.gfycat.com/JealousLinedAcornweevil-small.gif",
                    "https://i.imgur.com/ykKX5j4.jpg",
                    "https://i.imgur.com/xvZryzl.jpg",
                    "https://i.imgur.com/6NdBtM8.png",
                    "https://i.imgur.com/mK1dzXr.png",
                    "https://i.imgur.com/tEIZhFX.png",
                    "https://i.imgur.com/5x1NCHe.png"]

        content = [f"**{author} is rubbing {mention}'s tummy.**",
                   f"**{author} gave {mention} a tummy rub kinky.**"]

        await ctx.send(embed=self.hardcoded_image_list_embed(content, rub_list))

    @commands.command(name="kemo")
    async def kemonomimi(self, ctx: Context, amount=1):
        """
        Get a random picture/pictures kemonomimis
        20 is the maximum
        """
        if amount < 1:
            return
        if amount > 20:
            amount = 20

        data = [await self.bot.api_get_image([" ", " "], "https://nekos.life/api/v2/img/kemonomimi", "url")
                for _ in range(amount)]

        pages = ctx.menu(ctx.list_source(data))
        await pages.start(ctx)

    @commands.command()
    async def funfact(self, ctx: Context):
        """
        Get a random fun fact from the nekos life api
        """
        js = await self.bot.fetch("https://nekos.life/api/v2/fact")

        if js != {}:
            await ctx.send(f":information_source: Fun fact \n{js['fact']}")

    @commands.command()
    async def say(self, ctx: Context, *, message: commands.clean_content):
        """
        Have the bot say a message
        """

        await ctx.send(message)
        try:
            await ctx.message.delete()

        except discord.Forbidden:
            pass

    @commands.command()
    async def reverse(self, ctx: Context, *, message: reverse):
        """
        Have the bot reverse a message
        """
        await ctx.send(message)

    @commands.command()
    async def uppercase(self, ctx: Context, *, message: to_upper):
        """
        Have the bot uppercase a message
        """
        await ctx.send(message)

    @commands.command()
    async def lowercase(self, ctx: Context, *, message: to_lower):
        """
        Have the bot lowercase a message
        """

        await ctx.send(message)

    @commands.command()
    async def ping(self, ctx: Context):
        """
        Check how long the bot takes to respond
        """

        await ctx.send(f":information_source: | :ping_pong: **{self.bot.latency * 1000:.0f}**ms")

    @commands.command()
    async def choose(self, ctx: Context, *, choices):
        """
        Have the bot pick an option choices separated |
        """

        choices = [option.strip() for option in choices.split("|")]

        if choices.count("") == len(choices):
            return await ctx.send(":no_entry: | invalid amount of options were passed.")

        choices = [option for option in choices if option]

        await ctx.send(f":information_source: | I choose `{random.choice(choices)}` {ctx.author.name}.")

    @commands.command()
    async def urban(self, ctx: Context, *, term):
        """
        Get the urban dictionary value of a term
        """
        params = {"term": term}

        js = await self.bot.fetch("https://api.urbandictionary.com/v0/define", params=params)

        if "list" not in js or js["list"] == []:
            return await ctx.send(":no_entry: | nothing was found.")

        self.urban_source.ctx = ctx
        pages = ctx.menu(self.urban_source(js["list"]))
        await pages.start(ctx)

    @commands.command()
    async def imgur(self, ctx: Context, *, content):
        """
        Look for an image on imgur
        """
        img_link_list = []
        params = {"q": content, "qs": "thumbs"}

        content = await self.bot.fetch("https://imgur.com/search/score/week", params=params)

        soup = BeautifulSoup(content, "html.parser")
        img_list_link = soup.find_all("a", {"class": "image-list-link"})

        for img_link in img_list_link:
            img_link_list.append(img_link.get("href"))
        try:
            await ctx.send("https://imgur.com/" + random.choice(img_link_list))

        except IndexError:
            await ctx.send(f"there's no image for {content} to be found", delete_after=4)

    @commands.command()
    @commands.bot_has_permissions(read_message_history=True)
    async def react(self, ctx: Context, *, msg: to_lower):
        """
        Place reactions on the above message
        """
        msg = ctx.emote_unescape(msg)
        reactions = []

        unicode_dict = {"a": "\U0001F1E6", "b": "\U0001F1E7",
                        "c": "\U0001F1E8", "d": "\U0001F1E9",
                        "e": "\U0001F1EA", "f": "\U0001F1EB",
                        "g": "\U0001F1EC", "h": "\U0001F1ED",
                        "i": "\U0001F1EE", "j": "\U0001F1EF",
                        "k": "\U0001F1F0", "l": "\U0001F1F1",
                        "m": "\U0001F1F2", "o": "\U0001F1F4",
                        "n": "\U0001F1F3", "p": "\U0001F1F5",
                        "q": "\U0001F1F6", "r": "\U0001F1F7",
                        "s": "\U0001F1F8", "t": "\U0001F1F9",
                        "u": "\U0001F1FA", "v": "\U0001F1FB",
                        "w": "\U0001F1FC", "x": "\U0001F1FD",
                        "y": "\U0001F1FE", "z": "\U0001F1FF"}
        for c in msg:
            if c.isalpha():
                reactions.append(unicode_dict.get(c))

            elif c.isdigit():
                reactions.append(f"{c}\N{combining enclosing keycap}")

        async for message in ctx.channel.history(limit=1, before=ctx.message):
            for reaction in reactions:
                try:
                    await message.add_reaction(reaction)

                except discord.errors.HTTPException:
                    return


async def setup(bot):
    n = Misc(bot)
    await bot.add_cog(n)

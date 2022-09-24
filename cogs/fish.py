import re
import asyncio
import typing

import discord
from discord.ext import commands

from config.utils.converters import FishNameConventer, FishRarityConventer, BaitConverter
from config.utils.emojis import C_BAIT
from config.utils.context import Context

from cogs.utils.views import InventoryView, FishBuyView, FishSellView
from cogs.utils.fish import Fishing as Fish

from loadconfig import FISH_GUILDS


class Fishing(commands.Cog):
    """Fishing game related commands"""

    def __init__(self, bot):
        self.bot = bot

    def embed(self, fish):
        fish = "\n".join(fish)
        embed = discord.Embed(title="All available fish", colour=discord.Color.dark_magenta())
        embed.add_field(name="\uFEFF", value=fish, inline=True)
        return embed

    async def cog_before_invoke(self, ctx: Context):
        # acquire a connection to the pool before every command
        await ctx.acquire()

    async def cog_command_error(self, ctx, error):

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, asyncio.TimeoutError):
            return await ctx.send(f":no_entry: | a response wasn't given in a while aborting command "
                                  f"`{ctx.command.name}`",
                                  delete_after=10)

    async def get_pages_revisions(self, ctx, chunk, url):

        titles = "|".join(js["title"] for js in chunk)

        page_params = {
            "action": "query",
            "prop": "revisions",
            "titles": titles,
            "rvprop": "content",
            "rvslots": "*",
            "formatversion": "2",
            "format": "json"
        }

        pattern = re.compile(r"\| Rarity = ([a-zA-Z]+)")
        page_results = await self.bot.fetch(url, params=page_params)
        rarity = None

        for page in page_results["query"]["pages"]:

            content = page["revisions"][0]["slots"]["main"]["content"]

            if pattern.search(content):
                rarity = pattern.search(content).group(1)

            if not rarity:
                print(f"Failed to get rarity for page: {page['title']}, might need to be manually added.")
                continue

            guild_ids = FISH_GUILDS[rarity]

            rarity_ids = {"Normal": 1,
                          "Rare": 2,
                          "Elite": 3,
                          "Super": 4,
                          "Decisive": 5,
                          "Ultra": 5,
                          "Priority": 5}

            rarity_id = rarity_ids[rarity]

            url = await self.get_icon_url(page["title"])
            kai_check = await self.get_icon_url(page["title"] + "Kai")

            await self.emote_in_fish_guild(ctx, rarity_id, guild_ids, url)

            if kai_check:
                await self.emote_in_fish_guild(ctx, rarity_id, guild_ids, kai_check)

    async def get_icon_url(self, page_title):

        params = {
            "aisort": "name",
            "action": "query",
            "format": "json",
            "aimime": "image/png",
            "list": "allimages"
        }

        page_title = f"{page_title}Icon.png"

        params["aiprefix"] = page_title.replace("_", " ")

        js = await self.bot.fetch("https://azurlane.koumakan.jp/w/api.php", params=params)

        for js in js["query"]["allimages"]:
            return js["url"]

    async def insert_fish(self, ctx, emote, rarity_id):
        await ctx.db.execute("""
            INSERT INTO fish (fish_name, rarity_id) VALUES ($1, $2) 
            ON CONFLICT (fish_name) DO UPDATE SET rarity_id = $2;""", str(emote), rarity_id)

    def check_all_emotes(self, guild_ids, emote_name) -> typing.Union[discord.Emoji, bool]:
        emotes = []
        for guild in guild_ids:
            guild = self.bot.get_guild(guild)
            for e in guild.emojis:
                emotes.append(e)

        for emote in emotes:
            if emote.name == emote_name or emote.name == re.sub(r"[^a-zA-Z0-9]", "", emote_name):
                return emote

        return False

    async def emote_in_fish_guild(self, ctx, rarity, guild_ids, icon_url):
        # this is hacky and lazy but meh

        if not icon_url:
            return
        already_emoted = False
        emote_name = icon_url.split("/")[-1].replace(".png", "")

        for guild in guild_ids:

            guild = self.bot.get_guild(guild)

            if len(guild.emojis) == 50:
                continue

            async with self.bot.session.get(icon_url) as response:
                image = await response.read()

                emote = self.check_all_emotes(guild_ids, emote_name)
                if emote:
                    # attempt to add the fish in-case the emote exists but it's not added to the database
                    await self.insert_fish(ctx, emote, rarity)
                    print(f"Inserted into database {emote.name} with emote location guild {guild.name} with id "
                          f"{guild.id}.")

                    already_emoted = True

                    continue

                try:
                    if already_emoted:
                        continue

                    emoji = await guild.create_custom_emoji(name=emote_name, image=image, reason=None)
                    print(f"Inserted into database {emote_name} and uploaded to guild {guild.name} with id {guild.id}.")
                    await self.insert_fish(ctx, emoji, rarity)

                except discord.errors.HTTPException as e:
                    if e.status == 400:
                        msg = f"at guild {guild.name} with id {guild.id} for emote {emote_name}."
                        print(f":no_entry: | an error occurred during the emote process ```{e.text}```\n{msg}.")
                    # attempting to appease the input validation by only allowing alpha
                    emote_name = re.sub(r"[^a-zA-Z0-9]", "", emote_name)
                    try:
                        emoji = await guild.create_custom_emoji(name=emote_name, image=image, reason=None)
                        await self.insert_fish(ctx, emoji, rarity)

                    except discord.errors.HTTPException as e:
                        msg = f"at guild {guild.name} with id {guild.id} for emote {emote_name}."
                        print(f":no_entry: | an error occurred during the emote process ```{e.text}```\n{msg}.")
                        print(f"Second attempt at adding {emote_name} failed dming link..... and rarity")
                        author = ctx.bot.get_user(295325269558951936)
                        message = f"Manually add {icon_url} for rarity {rarity}"
                        await author.send(message)

    @commands.group(invoke_without_command=True, ignore_extra=False)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def fish(self, ctx: Context):
        """The main command for fishing by itself fish a single random fish
           rates are as follow for fish, 10% for rare, 34% for elite, 1% for super 0.05% for legendary"""

        f = Fish(ctx)

        current_balance = await ctx.db.fetchval("SELECT credits FROM users WHERE user_id = $1", ctx.author.id)
        price = await ctx.db.fetchval("SELECT price FROM fish_bait WHERE bait_id = 1")

        if current_balance < price:
            return await ctx.send(":no_entry: | you do not have enough credits for casting..")

        data = await ctx.db.fetchrow("SELECT amount FROM fish_user_inventory WHERE user_id = $1 AND bait_id = $2",
                                     ctx.author.id, 1)

        async with ctx.db.transaction():
            if data is None or data["amount"] - 1 < 0:
                await ctx.send(f"You have 0 {C_BAIT} and thus paid {price} credits for casting.")
                await ctx.db.execute("UPDATE users SET credits = credits - $1 WHERE user_id = $2", price,
                                     ctx.author.id)

            else:
                await ctx.db.execute(
                    "UPDATE fish_user_inventory SET amount = amount - $1 WHERE user_id = $2 and bait_id = $3",
                    1, ctx.author.id, 1)

        await f.catch_fish(ctx, 1, 1)
        await f.display_fish()

    @fish.group(invoke_without_command=True, aliases=["favourite"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def favourites(self, ctx: Context):
        """View your favourite fish"""
        f = Fish(ctx)

        favourites = await f.get_fish_favourites(ctx)

        if favourites in (None, []):
            return await ctx.send(f":no_entry: | you currently have no favourite fish, {ctx.author.name}")

        fish_names = await ctx.db.fetch("SELECT fish_name from fish where fish_id = ANY($1::INT[])", favourites)
        fish_names = " ".join(fish["fish_name"] for fish in fish_names)

        await ctx.send(f"> Your current favourite fish, {ctx.author.name}\n > {fish_names}")

    @favourites.command()
    async def add(self, ctx: Context, fish_ids: commands.Greedy[FishNameConventer]):
        """Add a fish to your favorites
        separate multiple fish ids with a space"""

        f = Fish(ctx)
        await f.update_fish_favourites(ctx, fish_ids)

    @favourites.command()
    async def remove(self, ctx: Context, fish_ids: commands.Greedy[FishNameConventer]):
        """Remove a fish from your favorites
        separate multiple fish ids with a space"""

        f = Fish(ctx)
        await f.update_fish_favourites(ctx, fish_ids, True)

    @fish.group(invoke_without_command=True, name="buy", aliases=["bait_buy", "shop", "store"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def bait_buy(self, ctx: Context, amount: int = 1):
        """Buy some bait"""
        fb = FishBuyView(ctx)
        await fb.set_bait(amount)
        data = await fb.get_bait_data()

        content = "".join(f"> **{bait['bait_name']}** {bait['bait_emote']} : {bait['price']} credits\n"
                          for bait in data)

        await ctx.send(content=content, view=fb)

    @bait_buy.command(name="all")
    async def bait_buy_all(self, ctx: Context, bait_id: BaitConverter):
        """Buy all bait of a specific type of bait allowed."""

        fb = FishBuyView(ctx)
        await fb.buy_all(bait_id)

    @fish.command(aliases=["storage", "items"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def inventory(self, ctx: Context):
        """View your current bait inventory.
           Can buy or sell bait from the inventory."""
        i = InventoryView(ctx)
        await i.run()

    @fish.command()
    async def list(self, ctx, not_caught_only: typing.Optional[bool] = False,
                   rarity: typing.Optional[FishRarityConventer] = None):
        """List all available fish"""

        data = await ctx.db.fetch("""SELECT f.fish_name as name, f.fish_id, fr.rarity_name as rarity, 
                                            fuc.fish_id = f.fish_id as caught
                                     FROM fish f
                                     INNER JOIN fish_rarity fr on fr.rarity_id = f.rarity_id

                                     LEFT JOIN LATERAL
                                            (SELECT fish_id FROM fish_users_catches fuc
                                            WHERE user_id = $1) as fuc on f.fish_id = fuc.fish_id
                                     WHERE ($2::integer is null or f.rarity_id = $2::integer)
                                     GROUP BY fr.rarity_name, f.fish_name, f.fish_id, fuc.fish_id
                                     ORDER BY fr.rarity_name
                                      """, ctx.author.id, rarity)

        if not_caught_only:
            data = [f for f in data if not f["caught"]]

            if not data:
                return await ctx.send("No fish to display as you've already caught all fish.")

        data = [f"fish ID: `{fish['fish_id']}` {fish['name']} : (**{fish['rarity']}**)"
                for fish in data]

        fish_chunks = ctx.chunk(data, 10)
        entries = [embed for embed in [self.embed(fc) for fc in fish_chunks]]

        pages = ctx.menu(ctx.list_source(entries))
        await pages.start(ctx)

    @fish.command(aliases=["catch", "captures", "reels", "fishy", "stats", "collection"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def catches(self, ctx: Context, member: typing.Optional[discord.Member] = None,
                      rarity_id: FishRarityConventer = None):
        """View all the fish you've caught or someone else's
           can filter by rarity by passing in a rarity name or id 1 for common,
           2 for rare, 3 for elite, 4 for super, and 5 for legendary"""

        f = Fish(ctx)

        if member:
            await f.fish_catch_view(ctx, member.id, rarity_id, global_paginator=True)

        else:
            await f.fish_catch_view(ctx, ctx.author.id, rarity_id)

    @fish.command()
    async def sell(self, ctx: Context):
        """The command for selling fish
        sell all fish dupes, a specific fish or rarity of fish"""

        fs = FishSellView(ctx)
        await ctx.send("selling fish.", view=fs)

    @commands.command()
    @commands.is_owner()
    async def update_fish(self, ctx):

        cmcontinue = True

        params = {

            "action": "query",

            "cmtitle": "Category:Ships",

            "cmlimit": "500",

            "list": "categorymembers",

            "format": "json"

        }

        url = "https://azurlane.koumakan.jp/w/api.php"

        while cmcontinue:
            results = await self.bot.fetch(url, params=params)

            try:

                chunks = ctx.chunk(results["query"]["categorymembers"], 50)

                for chunk in chunks:
                    await self.get_pages_revisions(ctx, chunk, url)

                cmcontinue = results["continue"]["cmcontinue"]
                params["cmcontinue"] = cmcontinue

            except KeyError:
                # no more results available
                cmcontinue = ""

        print("Finished.")
        await ctx.send(f"> Finished adding images {ctx.author.mention}")


async def setup(bot):
    await bot.add_cog(Fishing(bot))

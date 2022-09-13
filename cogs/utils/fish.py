import random
import typing

import asyncpg
import numpy
import discord

from config.utils.emojis import SHYBUKI2
from config.utils.menu import page_source
from config.utils.context import Context


class Inventory:
    def __init__(self, ctx):
        self.ctx = ctx
        self.display = None

    async def embed_inventory(self) -> discord.Embed:

        embed = discord.Embed(title="Inventory")
        embed.set_author(name=self.ctx.author.name + "'s", icon_url=self.ctx.author.avatar.url)
        embed.colour = self.ctx.bot.default_colors()

        data = await self.get_inventory(self.ctx.db, self.ctx.author.id)

        if data == []:
            embed.description = "You currently have an empty storage."
        else:
            for bait in data:
                value = f"name : **{bait['bait_name']}**\n amount : **{bait['amount']}**\n price : **{bait['price']}**"
                embed.add_field(name=bait["bait_emote"], value=value, inline=False)

        return embed

    async def get_inventory(self, con: asyncpg.Connection, user_id):
        return await con.fetch("""
                                SELECT * FROM fish_user_inventory fuc 
                                INNER JOIN fish_bait fb on fb.bait_id = fuc.bait_id
                                WHERE user_id = $1""", user_id)

    async def run(self):
        embed = await self.embed_inventory()

        if not self.display:
            self.display = await self.ctx.send(embed=embed, view=self)
        else:
            await self.display.edit(embed=embed, view=self)

    @staticmethod
    async def expend_bait(con: asyncpg.Connection, amount: int, user_id: int, bait_id: int):
        await con.execute(
            "UPDATE fish_user_inventory SET amount = amount - $1 WHERE user_id = $2 AND bait_id = $3",
            amount, user_id, bait_id)

    @staticmethod
    async def get_bait(con: asyncpg.Connection, user_id: int, emoji: str):
        return await con.fetchrow(
            "SELECT amount, bait_id FROM fish_user_inventory WHERE user_id = $1 AND bait_emote = $2",
            user_id, emoji)

    @staticmethod
    async def get_bait_emoji(con: asyncpg.Connection, bait_id: int):
        return await con.fetchval("SELECT bait_emote FROM fish_bait WHERE bait_id = $1", bait_id)

    @staticmethod
    async def update_inventory(con: asyncpg.Connection, user_id: int,
                               bait_id: int, amount: int, emoji: typing.Union[discord.Emoji, discord.PartialEmoji]):
        await con.execute("""INSERT INTO fish_user_inventory (user_id, bait_id, amount, bait_emote)
                             VALUES ($1, $2, $3, $4) ON CONFLICT (user_id, bait_id) DO UPDATE SET (amount) = 
                             ROW(fish_user_inventory.amount + $3)
                          """, user_id, bait_id, amount, str(emoji))


class Fishing:
    def __init__(self, ctx):
        self.ctx = ctx
        self.fish = []
        self.rng = numpy.random.default_rng()

    @staticmethod
    @page_source(per_page=1)
    def catch_source(self, menu, entry):
        return entry

    @staticmethod
    @page_source(per_page=4)
    def view_source(self, menu, entries):

        def format_fish(fish):
            f_id = fish["fish_id"]
            emote = fish["fish_name"]
            name = emote.split("Icon")[0].replace('<', '').replace(':', '')
            rarity = fish["rarity"]
            amount = fish["amount"]

            return f"> **fish ID**: `{f_id}` {emote} (**{rarity}**) | ({amount}) : {name}\n"

        display = "\n".join(format_fish(fish) for fish in entries)

        return self.m + display

    @staticmethod
    def price_sum_setter(data: typing.Union[list, asyncpg.Record]):
        amount = 0

        for fish in data:
            rarity_id = fish["rarity_id"]

            if rarity_id == 1:
                amount += fish["sum"] * 10
            elif rarity_id == 2:
                amount += fish["sum"] * 10.6
            elif rarity_id == 3:
                amount += fish["sum"] * 60.6
            elif rarity_id == 4:
                amount += fish["sum"] * 160
            elif rarity_id == 5:
                amount += fish["sum"] * 500

        return amount

    @staticmethod
    def price_setter(rarity_id: int, amount: int):
        pay_out = 0
        if rarity_id == 1:
            pay_out = amount * 10
        elif rarity_id == 2:
            pay_out = amount * 10.6
        elif rarity_id == 3:
            pay_out = amount * 60.6
        elif rarity_id == 4:
            pay_out = amount * 160
        elif rarity_id == 5:
            pay_out = amount * 500

        return pay_out

    def filter_by_bait_id(self, bait_id: int) -> iter:

        # bait_id = 1
        # 1 - 1 = 0, 2 - 1 = 1, 3 - 1, = 2
        # common, rare, elite
        # bait_id = 2
        # 1 - 2 = -1, 2 - 2 = 0, 3 - 2 = 1, 4 - 2 = 2, 5 - 2 = 3
        # rare, elite, super
        # bait_id = 3
        # 1 - 3 = -2, 2 - 3 = -1, 3 - 3 = 0, 4 - 3 = 1, 5 - 3 = 2
        # elite, super, legendary
        # bait_id = 4
        # 1 - 4, = -3, 2 - 4, 3 - 4, 4-4 = 0, 5 - 4 = 1
        # super, legendary

        return list((f for f in self.fish if 0 <= f["rarity_id"] - bait_id))

    def format_fish(self):
        entries = []

        for fish in self.fish:
            article = "an" if fish["rarity"].startswith("E") else "a"
            entries.append(
                f"> **{self.ctx.author.name}** you caught {article} **{fish['rarity']}** {fish['fish_name']}")

        return entries

    async def numpy_draw(self, ctx: Context, fish: list[asyncpg.Record], sample: list[int],
                         amount: int, probabilities: list[float]):

        draws = self.rng.choice(sample, amount, p=probabilities)

        filtered_fish = [random.choice(list((f for f in fish if f["rarity_id"] == draw)))
                         for draw in draws if draw]

        count = sum(f["rarity_id"] == 5 for f in filtered_fish)

        if count > 0:
            await ctx.send(f"> Seems like {count} legendary fish have sneaked in here")

        return filtered_fish

    async def filter_by_probabilities(self, ctx: Context, fish: list[asyncpg.Record], bait_id: int, amount: int):

        available_fish = {1: [1, 2, 3],
                          2: [2, 3, 4],
                          3: [3, 4, 5, None],
                          4: [4, 5, None]}

        #  base rates 56% for common, 10% for elite, 34% for rare, 1% for super 0.05%
        probability_dict = {1: [0.56, 0.34, 0.1],
                            2: [0.75, 0.22, 0.03],
                            3: [0.5, 0.06, 0.005, 0.435],
                            4: [0.1, 0.05, 0.85]}

        sample = available_fish.get(bait_id, next(iter(available_fish)))
        probabilities = probability_dict.get(bait_id, next(iter(probability_dict)))

        return await self.numpy_draw(ctx, fish, sample, amount, probabilities)

    @staticmethod
    async def get_all_fish(con: asyncpg.Connection):
        return await con.fetch("""
           SELECT f.fish_id, f.fish_name, f.bait_id, f.rarity_id, fr.rarity_name as rarity 
           FROM fish f
           INNER JOIN fish_rarity fr on fr.rarity_id = f.rarity_id""")

    @staticmethod
    async def get_fish_favourites(ctx: Context):

        favourites = await ctx.db.fetchval("SELECT favourites from fish_user_inventory where user_id = $1",
                                           ctx.author.id)
        if favourites is None:
            favourites = []

        return favourites

    @staticmethod
    async def update_fish_favourites(ctx: Context, fish_ids: typing.Union[int, list], delete=False):
        fish_ids = set(fish_ids)

        if not fish_ids:
            return await ctx.send(":no_entry: | an invalid fish id was passed.")

        data = await ctx.db.fetch(
            "SELECT fish_id, fish_name FROM fish_users_catches WHERE user_id = $1 AND fish_id = ANY($2)",
            ctx.author.id, fish_ids)

        if data == []:
            return await ctx.send(f":no_entry: | you currently have no fish caught {ctx.author.name}")

        current_faves = await ctx.db.fetchval("SELECT favourites FROM fish_user_inventory WHERE user_id = $1",
                                              ctx.author.id) or {}

        current_faves = set(current_faves)

        fish_names = " ".join([fish["fish_name"] for fish in data if fish["fish_id"] in fish_ids])

        if delete is False:
            fish_ids.update(current_faves)

        else:

            fish_ids = current_faves - fish_ids

        await ctx.db.execute("UPDATE fish_user_inventory SET favourites = $1 WHERE user_id = $2", fish_ids,
                             ctx.author.id)

        if delete is False:
            return await ctx.send(f":information_source: | you added {fish_names} to your favourites {ctx.author.name}")

        await ctx.send(f":information_source: | you removed {fish_names} from your favourites, {ctx.author.name}")

    async def display_fish(self):

        entries = self.format_fish()

        if not entries:
            return await self.ctx.send("No fish were caught.")

        pages = self.ctx.menu(self.catch_source(entries))
        random.shuffle(pages.source.entries)
        await pages.start(self.ctx)

    async def randomise_fish(self, ctx: Context, amount: int):
        fish = await self.get_all_fish(ctx.db)
        # 20% for common, 10% for rare, 5% for elite, 1.5% for super, 0.00025% for legendary, 63%.475 for
        # nothing
        sample = [1, 2, 3, 4, 5, None]
        probabilities = [0.2, 0.1, 0.05, 0.015, 0.00025, 0.63475]

        return await self.numpy_draw(ctx, fish, sample, amount, probabilities)

    async def fish_catch_view(self, ctx: Context, user_id, rarity_id=None, global_paginator=False):

        menu = ctx.global_menu if global_paginator else ctx.menu

        user_name = await ctx.db.fetchval("SELECT name FROM users WHERE user_id = $1", user_id)

        message = f"""{SHYBUKI2} | **{user_name}'s current fish collection**.\n"""

        data = await ctx.db.fetch("""SELECT DISTINCT fuc.fish_id, fuc.fish_name, fr.rarity_name as rarity, 
                                        fuc.amount
                                        FROM fish_users_catches fuc
                                        INNER JOIN fish f ON
                                        fuc.fish_id = f.fish_id
                                        INNER JOIN fish_rarity fr ON f.rarity_id = fr.rarity_id
                                        WHERE fuc.user_id = $1 AND 
                                        ($2::integer is null or f.rarity_id = $2::integer)""",
                                  user_id, rarity_id)

        if rarity_id:

            rarity = data[0]["rarity"]
            message = f"""{SHYBUKI2} **{user_name}'s current {rarity} fish collection**.\n"""


        if data == []:
            return await ctx.send(message + "you currently have no fish caught.")

        # for formatting
        self.view_source.m = message

        pages = menu(self.view_source(data))
        await pages.start(ctx)

    async def get_favourites_rarity(self, ctx: Context, rarity_id: int):

        favourites = await self.get_fish_favourites(ctx)
        favourites = await ctx.db.fetch("SELECT fish_id FROM fish WHERE fish_id = ANY($1::INT[]) and rarity_id = $2",
                                        favourites, rarity_id)

        return favourites

    async def catch_fish(self, ctx: Context, bait_id: int, amount: int):

        self.fish = await self.get_all_fish(ctx.db)
        self.fish = self.filter_by_bait_id(bait_id)
        self.fish = await self.filter_by_probabilities(ctx, self.fish, bait_id, amount)

        extra_fish = await self.randomise_fish(ctx, amount)
        # self.fish = random.choices(self.fish, k=amount)

        self.fish.extend(extra_fish)
        self.fish.sort(key=lambda f: f["fish_id"])

        # to avoid deadlocks

        statement = """INSERT INTO fish_users_catches (user_id, fish_id, amount, fish_name)
                         VALUES ($1, $2, $3, $4) ON CONFLICT (user_id, fish_id) 
                         DO UPDATE SET (amount) = ROW(fish_users_catches.amount + $3)
                      """

        records = [(ctx.author.id, fish["fish_id"], 1, fish["fish_name"]) for fish in self.fish]

        await ctx.db.executemany(statement, records)

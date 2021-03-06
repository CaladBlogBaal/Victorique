import asyncio
import random
import typing
import numpy

import discord
from discord.ext import commands

from config.utils.converters import FishNameConventer, FishRarityConventer
from config.utils.emojis import FISHFOOD


class Fishing(commands.Cog):
    """Fishing game related commands"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_before_invoke(self, ctx):
        # acquire a connection to the pool before every command
        await ctx.acquire()

    async def cog_command_error(self, ctx, error):

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, asyncio.TimeoutError):
            return await ctx.send(f":no_entry: | a response wasn't given in a while aborting command "
                                  f"`{ctx.command.name}`",
                                  delete_after=10)

    async def embed_(self, ctx, current_balance, bait, cost):
        if cost > current_balance or current_balance - cost < 0:
            await ctx.send(":no_entry: | you do not have enough credits for this transaction.")
            return False

        transaction_id = random.randint(1000, 90000)
        transaction_id = str(transaction_id)

        embed = discord.Embed(content=":atm: | bait purchase",
                              description=f"{ctx.author.name} buying bait"
                                          f"\nCurrent balance {current_balance}"
                                          f"\nBalance after pet purchase {current_balance - cost}"
                                          f"\nConfirmation pin {transaction_id}"
                                          f"\n(say cancel to cancel the transaction)",
                              color=discord.Color.dark_magenta()
                              )

        await ctx.send(embed=embed)

        cancel_message = ":information_source: | {}, bait transaction has been cancelled"
        confirmation = await ctx.wait_for_input(transaction_id, cancel_message)

        if confirmation:
            await ctx.send(f":information_source: | "
                           f"{cost} credits has been deducted from your account, "
                           f"{ctx.author.name} you bought some {bait} `to use your bait do "
                           f"{ctx.prefix}fish storage use [insert amount]`")

            return cost
        return confirmation

    @staticmethod
    async def __fish_catches_view(ctx, rarity_id=None, global_paginator=False):

        if rarity_id:
            rarity_id = await FishRarityConventer().convert(ctx, rarity_id)

        if not global_paginator:
            p = ctx.paginator

        else:
            p = ctx.paginator_global

        m = f"""<:shybuki_2:595024454271238145> | **{ctx.author.name}'s current fish collection**.\n"""

        rarites = {1: "common", 2: "elite", 3: "super", -1: "legendary"}

        if rarity_id in rarites.keys():
            rariry = rarites.get(rarity_id)
            m = f"""<:shybuki_2:595024454271238145> | **{ctx.author.name}'s current {rariry} fish collection**.\n"""

        fishes = ""

        if rarity_id:
            data = await ctx.db.fetch("""SELECT DISTINCT * from fish_users_catches INNER JOIN fish on
                                          fish_users_catches.fish_id = fish.fish_id
                                          where fish_users_catches.user_id = $1 and fish.bait_id = $2""",
                                      ctx.author.id, rarity_id)

        else:

            data = await ctx.db.fetch("SELECT * from fish_users_catches where user_id = $1 ORDER BY fish_id",
                                      ctx.author.id)

        if data == []:
            return await ctx.send(m + "you currently have no fish caught.")

        data = list(ctx.chunk(data, 4))

        for fish_chunk in data:
            for fish in fish_chunk:
                name = fish['fish_name'].split("Icon")[0].replace("<", "").replace(":", "")

                fishes += f"\n> **fish ID**: `{fish['fish_id']}` {fish['fish_name']} | ({fish['amount']}) : {name} \n"

            await p.add_page(m + fishes)
            fishes = ""

        await p.paginate()

    @staticmethod
    def price_sum_setter(data):
        amount = 0

        for fish in data:
            rarity_id = fish["bait_id"]

            if rarity_id == 1:
                amount += fish["sum"] * 5
            elif rarity_id == 2:
                amount += fish["sum"] * 52
            elif rarity_id == 3:
                amount += fish["sum"] * 500
            elif rarity_id == -1:
                amount += fish["sum"] * 21000

        return amount

    @staticmethod
    def price_setter(rarity_id, amount):
        pay_out = 0
        if rarity_id == 1:
            pay_out = amount * 5
        elif rarity_id == 2:
            pay_out = amount * 52
        elif rarity_id == 3:
            pay_out = amount * 500
        elif rarity_id == -1:
            pay_out = amount * 21000

        return pay_out

    @staticmethod
    async def transaction_check(ctx):

        transaction_id = random.randint(1000, 90000)
        transaction_id = str(transaction_id)

        await ctx.send(f":information_source: | Enter in the transaction id {transaction_id} to proceed or say cancel "
                       f"to exit.")

        cancel_message = ":information_source: | {}, fish selling has been cancelled."
        confirmation = await ctx.wait_for_input(transaction_id, cancel_message)

        return confirmation

    @staticmethod
    async def __fish_get_favourites(ctx):

        favourites = await ctx.db.fetchval("SELECT favourites from fish_user_inventory where user_id = $1",
                                           ctx.author.id)
        if favourites is None:
            favourites = []

        return favourites

    @staticmethod
    async def __fish_update_favourites(ctx, fish_ids, delete=False):
        fish_ids = set(fish_ids)

        if fish_ids == []:
            return await ctx.send(":no_entry: | an invalid fish id was passed.")

        data = await ctx.db.fetch("SELECT fish_id, fish_name from fish_users_catches where user_id = $1 and fish_id = "
                                  "ANY($2)",
                                  ctx.author.id, fish_ids)

        if data == []:
            return await ctx.send(f":no_entry: | you currently have no fish caught {ctx.author.name}")

        current_favs = await ctx.db.fetchval("SELECT favourites from fish_user_inventory where user_id = $1",
                                             ctx.author.id)

        if current_favs:
            current_favs = set(current_favs)

        else:
            current_favs = {}

        fish_names = " ".join([fish["fish_name"] for fish in data if fish["fish_id"] in fish_ids])

        if delete is False:
            fish_ids.update(current_favs)

        else:

            fish_ids = current_favs - fish_ids

        await ctx.db.execute("UPDATE fish_user_inventory SET favourites = $1 where user_id = $2",
                             fish_ids, ctx.author.id)
        if delete is False:
            return await ctx.send(f":information_source: | you added {fish_names} to your favourites "
                                  f"{ctx.author.name}")

        await ctx.send(f":information_source: | you removed {fish_names} from your favourites, "
                       f"{ctx.author.name}")

    @staticmethod
    async def __fish_randomiser(ctx, amount):
        all_fishes = await ctx.db.fetch("SELECT fish_id, fish_name, bait_id from fish")

        extra_fishes = []
        fish = [2, 3, -1, None]
        probabilities = [0.1, 0.01, 0.0005, 0.8895000000000001]

        legend_count = 0

        for _ in range(amount):
            draw = numpy.random.choice(fish, p=probabilities)

            if draw is not None:
                if draw == -1:
                    legend_count += 1
                fishes = [fish for fish in all_fishes if fish["bait_id"] == draw]
                random_fish = random.choice(fishes)
                extra_fishes.append(random_fish)

        if legend_count > 0:
            await ctx.send(f"> Seems like {legend_count} legendary fish have sneaked in here")

        return extra_fishes

    @staticmethod
    def reaction_set():
        return [FISHFOOD]

    async def __fish_get_favourites_rarity(self, ctx, bait_id):

        favourites = await self.__fish_get_favourites(ctx)
        favourites = await ctx.db.fetch("SELECT fish_id from fish where fish_id = ANY($1::INT[]) and bait_id = $2",
                                        favourites, bait_id)

        return favourites

    async def __fish_catch(self, ctx, bait_id, amount):

        fishes = await ctx.db.fetch("SELECT fish_id, fish_name from fish where bait_id = $1", bait_id)

        extra_fishes = await self.__fish_randomiser(ctx, amount)

        fishes = random.choices(fishes, k=amount)
        fishes.extend(extra_fishes)

        # to avoid deadlocks
        fishes = sorted(fishes)

        statement = """INSERT INTO fish_users_catches (user_id, fish_id, amount, fish_name)
                       VALUES ($1, $2, $3, $4) ON CONFLICT (user_id, fish_id) 
                       DO UPDATE SET (amount) = ROW(fish_users_catches.amount + $3)
                    """

        records = [(ctx.author.id, fish['fish_id'], 1, fish['fish_name']) for fish in fishes]

        await ctx.db.executemany(statement, records)
        for fish in fishes:
            await ctx.paginator.add_page(f"> **{ctx.author.name}** you caught a {fish['fish_name']}")

        await ctx.paginator.shuffle_pages()
        await ctx.paginator.paginate()

    async def __fish_user_reel(self, reaction_emoji, ctx, amount):

        data = await ctx.db.fetchrow("SELECT amount, bait_id from fish_user_inventory where user_id = $1 "
                                     "and bait_emote = $2",
                                     ctx.author.id, reaction_emoji)

        if data is None:
            return await ctx.send(f":no_entry: | you do not have enough {reaction_emoji} for this action.")

        if data["amount"] < amount or data["amount"] == 0:
            return await ctx.send(f":no_entry: | you do not have enough {reaction_emoji} for this action.")

        if amount > 10000:
            await ctx.send(":information_source: | the max amount of bait you can use is 10000")
            amount = 10000

        await ctx.db.execute("UPDATE fish_user_inventory SET amount = amount - $1 WHERE user_id = $2 and bait_id = $3",
                             amount, ctx.author.id, data["bait_id"])

        await self.__fish_catch(ctx, data["bait_id"], amount)

    async def __update_fish_inventory(self, user_id, bait_id, amount, emote):

        async with self.bot.pool.acquire() as con:
            await con.execute("""INSERT INTO fish_user_inventory (user_id, bait_id, amount, bait_emote)
                                 VALUES ($1, $2, $3, $4) ON CONFLICT (user_id, bait_id) DO UPDATE SET (amount) = 
                                 ROW(fish_user_inventory.amount + $3)
                              """, user_id, bait_id, amount, emote)

    @commands.group(invoke_without_command=True, ignore_extra=False)
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def fish(self, ctx):
        """The main command for fishing by itself fishes a single random fish
           rates are as follow for fish 10% for elite 1% for super 0.05% for legendary"""

        current_balance = await ctx.db.fetchval("select credits from users where user_id = $1", ctx.author.id)
        if current_balance < 10:
            return await ctx.send(":no_entry: | you do not have enough credits for casting..")

        data = await ctx.db.fetchrow(
            "SELECT amount, bait_id from fish_user_inventory where user_id = $1 and bait_id = $2",
            ctx.author.id, 1)

        if data is None or data["amount"] == 0:
            await ctx.send(f"You have 0 <:Food1:603902930541608960> and thus paid 10 credits for casting.")
            await ctx.db.execute("UPDATE users SET credits = credits - $1 WHERE user_id = $2", 10, ctx.author.id)

        await ctx.db.execute(
            "UPDATE fish_user_inventory SET amount = amount - $1 WHERE user_id = $2 and bait_id = $3",
            1, ctx.author.id, 1)

        await self.__fish_catch(ctx, 1, 1)

    @fish.group(invoke_without_command=True, aliases=["favourite"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def favourites(self, ctx):
        """View your favourite fish"""
        favs = await self.__fish_get_favourites(ctx)

        if favs in (None, []):
            return await ctx.send(f":no_entry: | you currently have no favourite fish, {ctx.author.name}")

        fish_names = await ctx.db.fetch("SELECT fish_name from fish where fish_id = ANY($1::INT[])", favs)
        fish_names = " ".join(fish["fish_name"] for fish in fish_names)

        await ctx.send(f"> Your current favourite fish, {ctx.author.name}\n > {fish_names}")

    @favourites.command()
    async def add(self, ctx, fish_ids: commands.Greedy[FishNameConventer]):
        """Add a fish/fishes to your favorites
        separate multiple fish ids with a space"""

        await self.__fish_update_favourites(ctx, fish_ids)

    @favourites.command()
    async def remove(self, ctx, fish_ids: commands.Greedy[FishNameConventer]):
        """Remove a fish/fishes from your favorites
        separate multiple fish ids with a space"""

        await self.__fish_update_favourites(ctx, fish_ids, True)

    @fish.command(name="buy", aliases=["bait_buy", "shop", "store"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def bait_buy(self, ctx, amount: int = 1):
        """Buy some bait"""

        current_balance = await ctx.db.fetchval("select credits from users where user_id = $1", ctx.author.id)

        bait = await ctx.db.fetchrow("SELECT * from fish_bait where bait_id = 1")

        reactions = self.reaction_set()
        costs = 10 * amount

        msg = await ctx.send(f"> **{bait['bait_name']} {bait['bait_emote']}**: {bait['price']} credits")

        for reaction in reactions:
            await msg.add_reaction(reaction)

        def check(reaction, user):
            return user == ctx.author and reaction.emoji in reactions and reaction.message.id == msg.id

        while True:

            reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=check)

            if reaction.emoji in reactions:
                bait_id = 1

                cost = await self.embed_(ctx, current_balance, reaction.emoji, costs)

                if cost is False:
                    return

                await self.__update_fish_inventory(ctx.author.id, bait_id, amount, str(reaction.emoji))

                return await ctx.db.execute("UPDATE users SET credits = credits - $1 WHERE user_id = $2", cost,
                                            ctx.author.id)

    @fish.group(aliases=["storage", "items"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def inventory(self, ctx):
        """View your current bait."""
        m = f"═══════════════════\n**{ctx.author.name}'s**\n═══════════════════\n**Inventory**\n═══════════════════"
        data = await ctx.db.fetch("SELECT * from fish_user_inventory where user_id = $1", ctx.author.id)

        if data == []:
            return await ctx.send(m + "\nYou currently have an empty storage.")

        for bait in data:
            m += f"\n{bait['bait_emote']} {' ' * 20}╬{' ' * 10}{bait['amount']}\n═══════════════════"

        msg = await ctx.send(m)

        if ctx.invoked_subcommand:

            amount = 1

            try:
                amount = int(ctx.message.content.split(" ")[-1])

            except ValueError:
                pass

            if amount < 0 or amount == 0:
                await ctx.send(":no_entry: | an invalid amount of bait to use was passed.")

                return await msg.delete()

            reactions = self.reaction_set()

            for reaction in reactions:
                await msg.add_reaction(reaction)

            def check(reaction, user):
                return user == ctx.author and reaction.emoji in reactions and reaction.message.id == msg.id

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=check)

                if reaction.emoji in reactions:
                    await msg.delete()
                    await self.__fish_user_reel(str(reaction.emoji), ctx, amount)

            except asyncio.TimeoutError:
                pass

    @inventory.command()
    async def use(self, ctx, amount: int = 1):
        """Use your bait to catch a fish of specific rarity
           legendary fish can only be caught with super rare bait."""

    @fish.group(aliases=["catch", "captures", "reels", "fishy", "stats", "collection"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def catches(self, ctx, member: typing.Optional[discord.Member] = None, rarity_id=None):
        """View all the fishes you've caught or someone else's
           can filter by rarity by passing in a rarity name or id 1 for common,
           2 for elite, 3 for super, and -1 for legendary"""

        ctx.author = member or ctx.author

        if member:
            await self.__fish_catches_view(ctx, rarity_id, True)

        else:
            await self.__fish_catches_view(ctx, rarity_id)

    @fish.group(invoke_without_command=True, ignore_extra=False)
    async def sell(self, ctx):
        """The main sell command for selling fish, by it self it sells all of a specific fish or fishes
        sell all of a specific fish or fishes"""
        if ctx.message.content != f"{ctx.prefix}{ctx.command}":
            return

        await ctx.send(":information_source: | enter the fish id/name of the fish you want to sell, "
                       "or the fish ids/names separated by a space.")

        data = await ctx.db.fetch("""SELECT * from fish_users_catches WHERE user_id = $1""", ctx.author.id)

        if data is None:
            return await ctx.send(f":no_entry: | {ctx.author.name} currently have no fish caught.")

        data = {fish["fish_id"] for fish in data}

        message = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=30)

        list_of_ids = message.content.split(" ")

        fish_ids = {await FishNameConventer().convert(ctx, id_) for id_ in list_of_ids}

        if fish_ids.issubset(data) is False:
            return await ctx.send(":no_entry: | an invalid fish id was passed.")

        favourites = await self.__fish_get_favourites(ctx)

        if any(id_ in favourites for id_ in fish_ids):
            return await ctx.send(":no_entry: | a fish registered as a favourite fish was passed.")

        fish_name = await ctx.db.fetch("SELECT fish_name from fish where fish_id = ANY($1::INT[])", fish_ids)
        fish_name = " ".join(fish["fish_name"] for fish in fish_name)

        await ctx.send(f"Would you like to sell all of {fish_name} options (yes or no)")
        message = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author,
                                          timeout=30)

        if message.content.lower() == "yes":

            if await self.transaction_check(ctx) is True:
                data = await ctx.db.fetch(
                    """SELECT SUM(amount), bait_id from fish_users_catches
                       INNER JOIN fish ON fish_users_catches.fish_id = fish.fish_id 
                       WHERE user_id = $1 and fish_users_catches.fish_id = ANY($2::INT[]) GROUP BY bait_id
                    """, ctx.author.id, fish_ids)

                amount = self.price_sum_setter(data)

                await ctx.db.execute("""DELETE from fish_users_catches
                                         WHERE fish_id = ANY($1::INT[]) and user_id = $2""",
                                     fish_ids, ctx.author.id)

                await ctx.db.execute("""UPDATE users SET credits = credits + $1 where user_id = $2 """,
                                     amount, ctx.author.id)

                await ctx.send(f"Successfully sold all of {fish_name} {ctx.author.name}, "
                               f"you earned {amount} credits.")

        elif message.content.lower() == "no":
            await ctx.send(":information_source: | cancelling the fish selling.")
        else:
            await ctx.send(":no_entry: | invalid response was received cancelling the fish selling.")

    @sell.command(aliases=["dupe"])
    async def dupes(self, ctx):
        """Sell all your duplicate fish."""
        excluded_fish_ids = await self.__fish_get_favourites(ctx)

        data = await ctx.db.fetch("""SELECT DISTINCT 
                                      fuc.amount, bait_id, fuc.fish_id
                                      from fish_users_catches as fuc
                                      INNER JOIN fish ON fuc.fish_id = 
                                      fish.fish_id 
                                      WHERE user_id = $1 and NOT (fish.fish_id  = ANY ($2)) 
                                      GROUP BY bait_id, 
                                      fuc.amount, 
                                      fuc.fish_id""", ctx.author.id, excluded_fish_ids)
        if data == []:
            return await ctx.send(":no_entry: | you currently have no fish caught.")

        if await self.transaction_check(ctx) is True:
            # too lazy to rewrite this
            # to not set a fish to zero
            amount_list = [d["amount"] - 1 for d in data if d["amount"] - 1 > 0]
            bait_list = [d["bait_id"] for d in data if d["amount"] - 1 > 0]
            data = [{"bait_id": x, "sum": amount_list[i]} for i, x in enumerate(bait_list)]

            await ctx.send(":information_source: | selling all dupes.")

            amount = self.price_sum_setter(data)

            if amount == 0:
                return await ctx.send(":no_entry: | you have no duplicate fish.")

            await ctx.db.execute("""UPDATE fish_users_catches SET amount = 1 from fish where 
                                     fish_users_catches.user_id = $1 
                                     and NOT (fish_users_catches.fish_id  = ANY ($2))""",
                                 ctx.author.id, excluded_fish_ids)

            await ctx.db.execute("""UPDATE users SET credits = credits + $1 where user_id = $2 """,
                                 amount, ctx.author.id)

            await ctx.send(f":information_source: | successfully sold all dupe fish, {ctx.author.name} you gained"
                           f" {amount} credits.")

    @sell.command()
    async def all(self, ctx, rarity_id: FishRarityConventer, excluded_fish_ids: commands.Greedy[FishNameConventer]):
        """Sell all of a fish with a specified rarity id
        pass a rarity name or 1 for common, 2 for elite, 3 for super and -1 for legendary into the rarity_id
        pass into the excluded fish parameter a list of fish ids or names
        separated by a space to exclude from the selling."""

        excluded_fish_ids = set(excluded_fish_ids)
        favourites = set(fish["fish_id"] for fish in await self.__fish_get_favourites_rarity(ctx, rarity_id))
        excluded_fish_ids.update(favourites)

        data = await ctx.db.fetch("""SELECT * from fish_users_catches WHERE user_id = $1""", ctx.author.id)

        if data is None:
            return await ctx.send(f":no_entry: | {ctx.author.name} currently have no fish caught.")

        rarities = {1: "common", 2: "elite", 3: "super"}
        rarity = rarities.get(rarity_id, "legendary")

        names = await ctx.db.fetch("SELECT fish_name from fish where fish_id = ANY ($1) and bait_id = $2",
                                   excluded_fish_ids, rarity_id)

        names = " ".join(fish["fish_name"] for fish in names)

        if names:
            await ctx.send(f"> currently selling all {rarity} fish with {names} excluded {ctx.author.name}.")

        if await self.transaction_check(ctx) is True:
            await ctx.send(f"selling all fish of rarity {rarity}")

            amount = await ctx.db.fetchval("""SELECT DISTINCT SUM(fish_users_catches.amount) 
                                               from fish_users_catches 
                                               INNER JOIN fish ON fish_users_catches.fish_id = fish.fish_id 
                                               WHERE user_id = $1 and bait_id = $2 
                                               and NOT (fish.fish_id  = ANY ($3))""",
                                           ctx.author.id, rarity_id, excluded_fish_ids)

            if amount == 0 or amount is None:
                return await ctx.send(":no_entry: | you have no fish of this rarity.")

            amount = self.price_setter(rarity_id, amount)

            await ctx.db.execute("""DELETE from fish_users_catches
                                     USING fish WHERE fish_users_catches.fish_id = fish.fish_id 
                                     and bait_id = $1 and user_id = $2
                                     and NOT (fish.fish_id  = ANY ($3))""",
                                 rarity_id, ctx.author.id, excluded_fish_ids)

            await ctx.db.execute("""UPDATE users SET credits = credits + $1 where user_id = $2 """,
                                 amount, ctx.author.id)

            await ctx.send(f"Successfully sold all fish of rarity {rarity} {ctx.author.name} you gained"
                           f" {amount} credits.")

    @sell.command(name="fish")
    async def fish_sell(self, ctx, amount: int, fish_id: FishNameConventer):
        """Sell an amount of a specific fish"""

        if amount < 0:
            return await ctx.send(":no_entry: | enter in a valid amount to sell.")

        data = await ctx.db.fetch("""SELECT * from fish_users_catches WHERE user_id = $1""", ctx.author.id)

        if data is None:
            return await ctx.send(":no_entry: | you currently have no fish caught.")

        if fish_id in await self.__fish_get_favourites(ctx):
            return await ctx.send(":no_entry: | you currently have this fish registered as a favourite fish")

        data = await ctx.db.fetchrow("""SELECT amount, bait_id, fish.fish_name from fish_users_catches
                                         INNER JOIN fish ON fish_users_catches.fish_id = fish.fish_id 
                                         WHERE user_id = $1 and fish_users_catches.fish_id = $2""", ctx.author.id,
                                     fish_id)

        if data["amount"] < amount:
            return await ctx.send(f":no_entry: | you do not have enough {data['fish_name']} for this action")

        delete_check = data["amount"] == amount

        await ctx.send(f"> currently selling {data['fish_name']} {ctx.author.name}")

        if await self.transaction_check(ctx):
            rarity_id = data["bait_id"]
            pay_out = self.price_setter(rarity_id, amount)

            await ctx.db.execute("UPDATE users SET credits = credits + $1 where user_id = $2 ", pay_out, ctx.author.id)

            if delete_check is False:
                await ctx.db.execute("""UPDATE fish_users_catches SET amount = amount - $3
                                        WHERE fish_id = $1 and user_id = $2
                                          """, fish_id, ctx.author.id, amount)

            elif delete_check is True:
                await ctx.db.execute("""DELETE from fish_users_catches
                                        WHERE fish_id = $1 and user_id = $2""", fish_id, ctx.author.id)

                return await ctx.send(f"Successfully sold {data['fish_name']} {ctx.author.name}, you gained {pay_out} "
                                      f"credits.")

            await ctx.send(f"Successfully sold {amount} {data['fish_name']} {ctx.author.name} "
                           f"you gained {pay_out} credits.")


def setup(bot):
    bot.add_cog(Fishing(bot))

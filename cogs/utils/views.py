import sys
import traceback
import typing

import asyncpg
import discord

from discord.ext import commands

import cogs.utils.fish as fish

from .modals import FishModal, FishSellAllModal

from config.utils.context import Context
from config.utils.emojis import PLAT, PLATWAA
from config.utils.converters import BaitConverter, FishNameConventer, FishRarityConventer


class FishBuyView(discord.ui.View):
    def __init__(self, ctx):
        super(FishBuyView, self).__init__()
        self.ctx = ctx

    async def get_bait_data(self):
        return await self.ctx.db.fetch("SELECT * FROM fish_bait")

    async def set_bait(self, amount):
        data = await self.get_bait_data()

        for bait in data:
            btn = BaitBuyButton(self.ctx, bait["bait_id"], amount)
            btn.emoji = bait["bait_emote"]
            self.add_item(btn)

    async def buy_all(self, bait_id: BaitConverter):
        balance = await self.ctx.db.fetchval("select credits from users where user_id = $1", self.ctx.author.id)

        bait = await self.ctx.db.fetchrow("SELECT * FROM fish_bait WHERE bait_id = $1", bait_id)
        bait_price = bait["price"]
        amount = balance // bait_price

        if amount == 0:
            return await self.ctx.send("You don't have enough money to buy any bait.")

        async with self.ctx.db.transaction():
            await self.ctx.db.execute("UPDATE users SET credits = credits - $1 WHERE user_id = $2", bait_price * amount,
                                      self.ctx.author.id)

            await self.ctx.db.execute("""UPDATE fish_user_inventory SET amount = amount + $1 
                                         WHERE user_id = $2 AND bait_id = $3""", amount, self.ctx.author.id, bait_id)

        await self.ctx.send(f"You bought {amount} {bait['bait_emote']} for {bait_price * amount} credits.")


class BaseView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx

    def validate_non_negative(self, text_input: str):

        try:

            check = int(text_input)

            if check <= 0:
                raise commands.BadArgument("An invalid amount was passed.")

            return check

        except ValueError:
            raise commands.BadArgument("An invalid amount was passed.")

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

    async def on_error(self, interaction: discord.Interaction,
                       error: Exception, item: discord.ui.Item[typing.Any], /) -> None:

        if isinstance(error, commands.BadArgument):
            return await interaction.followup.send(str(error), ephemeral=True)

        author = self.ctx.bot.get_user(295325269558951936)

        error_message = traceback.format_exception(type(error), error, error.__traceback__)
        error_message = "".join(c for c in error_message)

        await interaction.followup.send(":no_entry: | an unexpected error has occurred.", ephemeral=True)
        # Make sure we know what the error actually is
        try:

            await author.send("```Python\n" + error_message + "```")

        except discord.errors.HTTPException:
            pass

        print("Ignoring exception in command {}:".format(self.ctx.command), file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


class InventoryView(BaseView, fish.Inventory):
    def __init__(self, ctx):
        super().__init__(ctx)
        self.ctx = ctx
        self.add_item(UseButton(ctx))
        self.add_item(BuyButton(ctx))
        self.display = None

    async def get_modal_data(self, interaction):
        modal = FishModal(title="Use some bait", label="bait")
        await interaction.response.send_modal(modal)

        while await modal.wait():
            pass

        amount = self.validate_non_negative(modal.amount.value)
        bait_id = await BaitConverter().convert(self.ctx, modal.id.value)
        return amount, bait_id


class FishSellView(BaseView, fish.Fishing, fish.Inventory):
    def __init__(self, ctx):
        super(FishSellView, self).__init__(ctx)
        self.ctx = ctx
        self.add_item(FishSellButton(ctx))
        self.add_item(FishSellDupes(ctx))
        self.add_item(FishSellRarity(ctx))

    async def get_modal_data(self, interaction):
        modal = FishModal(title="Sell some fish", label="fish")

        await interaction.response.send_modal(modal)

        while await modal.wait():
            pass

        amount = self.validate_non_negative(modal.amount.value)
        fish_id = await FishNameConventer().convert(self.ctx, modal.id.value)

        return amount, fish_id

    async def get_fish_catches(self):
        return await self.ctx.db.fetch("""SELECT * FROM fish_users_catches WHERE user_id = $1""", self.ctx.author.id)


class BuyButton(discord.ui.Button):
    def __init__(self, ctx: Context):
        super().__init__()
        self.ctx = ctx
        self.label = "buy"
        self.emoji = PLAT
        self.style = discord.ButtonStyle.primary

    async def update_credits(self, conn: asyncpg.pool.PoolConnectionProxy, cost, user_id):
        await conn.execute("UPDATE users SET credits = credits - $1 WHERE user_id = $2", cost, user_id)

    async def get_credits(self, user_id):
        return await self.ctx.db.fetchval("SELECT credits FROM users WHERE user_id = $1", user_id)

    async def get_cost(self, amount, bait_id):
        bait = await self.ctx.db.fetchrow("SELECT * FROM fish_bait WHERE bait_id = $1", bait_id)
        costs = bait["price"] * amount
        return costs

    async def buy_bait(self, interaction: discord.Interaction, amount: int, bait_id: int):

        emoji = await InventoryView.get_bait_emoji(self.ctx.db, bait_id)

        if not emoji:
            return await interaction.followup.send(":no_entry: | Invalid bait id was entered.", ephemeral=True)

        user_id = self.ctx.author.id

        cost = await self.get_cost(amount, bait_id)

        current_balance = await self.get_credits(user_id)

        if cost > current_balance or current_balance - cost < 0:
            return await interaction.followup.send(
                ":no_entry: | you do not have enough credits for this transaction.", ephemeral=True)

        async with self.ctx.bot.pool.acquire() as con:
            async with con.transaction():
                await self.update_credits(con, cost, user_id)

                await InventoryView.update_inventory(con, user_id, bait_id, amount, emoji)

                await interaction.followup.send(f":information_source: | "
                                                f"{cost} credits has been deducted from your account, "
                                                f"{self.ctx.author.name} you bought some {emoji} "
                                                f"`to use your bait click the use button.",
                                                ephemeral=True)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: InventoryView = self.view

        amount, bait_id = await view.get_modal_data(interaction)

        await self.buy_bait(interaction, amount, bait_id)

        await view.run()


class BaitBuyButton(BuyButton):
    def __init__(self, ctx, bait_id, amount):
        super(BaitBuyButton, self).__init__(ctx)
        self.ctx = ctx
        self.bait_id = bait_id
        self.amount = amount
        self.style = discord.ButtonStyle.primary

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        await interaction.response.defer()
        await self.buy_bait(interaction, self.amount, self.bait_id)


class FishSellDupes(discord.ui.Button):
    def __init__(self, ctx):
        super(FishSellDupes, self).__init__()
        self.ctx = ctx
        self.label = "dupes"
        self.style = discord.ButtonStyle.success

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: FishSellView = self.view

        excluded_fish_ids = await view.get_fish_favourites(self.ctx)

        data = await self.ctx.db.fetch("""SELECT DISTINCT 
                                          fuc.amount, fish.rarity_id, fuc.fish_id
                                          from fish_users_catches as fuc
                                          INNER JOIN fish ON fuc.fish_id = 
                                          fish.fish_id 
                                          WHERE user_id = $1 and NOT (fish.fish_id  = ANY ($2)) 
                                          GROUP BY fish.rarity_id, 
                                          fuc.amount, 
                                          fuc.fish_id""", self.ctx.author.id, excluded_fish_ids)
        if data == []:
            return await interaction.response.send_message(":no_entry: | you currently have no fish caught.")

        # too lazy to rewrite this
        # to not set a fish to zero
        amount_list = [d["amount"] - 1 for d in data if d["amount"] - 1 > 0]
        rarity_list = [d["rarity_id"] for d in data if d["amount"] - 1 > 0]
        data = [{"rarity_id": x, "sum": amount_list[i]} for i, x in enumerate(rarity_list)]

        amount = self.view.price_sum_setter(data)

        if amount == 0:
            return await interaction.response.send_message(":no_entry: | you have no duplicate fish.")

        async with self.ctx.bot.pool.acquire() as con:
            async with con.transaction():
                await con.execute("""UPDATE fish_users_catches SET amount = 1 from fish where 
                                             fish_users_catches.user_id = $1 
                                             and NOT (fish_users_catches.fish_id  = ANY ($2))""",
                                  self.ctx.author.id, excluded_fish_ids)

                await con.execute("""UPDATE users SET credits = credits + $1 where user_id = $2 """,
                                  amount, self.ctx.author.id)

        await interaction.response.send_message(
            f":information_source: | successfully sold all dupe fish, {self.ctx.author.name} you gained {amount} credits.")


class FishSellRarity(discord.ui.Button):
    def __init__(self, ctx):
        super(FishSellRarity, self).__init__()
        self.ctx = ctx
        self.label = "rarity"
        self.style = discord.ButtonStyle.danger

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: FishSellView = self.view

        modal = FishSellAllModal("Sell fish of rarity.")
        await interaction.response.send_modal(modal)

        while await modal.wait():
            pass

        rarity_id = await FishRarityConventer().convert(self.ctx, modal.rarity_id.value)

        excluded_fish_ids = [await FishNameConventer().convert(self.ctx, value)
                             for value in modal.fish_ids.value.split(" ") if value]

        excluded_fish_ids = set(excluded_fish_ids)
        favourites = set(f["fish_id"] for f in await view.get_favourites_rarity(self.ctx, rarity_id))
        excluded_fish_ids.update(favourites)

        data = await view.get_fish_catches()

        if data is None:
            return await interaction.followup.send(":no_entry: | you currently have no fish caught.",
                                                   ephemeral=True)

        async with self.ctx.bot.pool.acquire() as con:
            async with con.transaction():

                amount = await con.fetchval("""SELECT DISTINCT SUM(fish_users_catches.amount) 
                                                  FROM fish_users_catches 
                                                  INNER JOIN fish ON fish_users_catches.fish_id = fish.fish_id 
                                                  WHERE user_id = $1 AND rarity_id = $2 
                                                  AND NOT (fish.fish_id = ANY ($3))""",
                                            self.ctx.author.id, rarity_id, excluded_fish_ids)

                if amount == 0 or amount is None:
                    return await interaction.followup.send(":no_entry: | you have no fish of this rarity.",
                                                           ephemeral=True)

                amount = self.view.price_setter(rarity_id, amount)

                data = await con.fetch("""DELETE FROM fish_users_catches
                                          USING fish WHERE fish_users_catches.fish_id = fish.fish_id 
                                          AND rarity_id = $1 AND user_id = $2
                                          AND NOT (fish.fish_id  = ANY ($3)) RETURNING *""",
                                       rarity_id, self.ctx.author.id, excluded_fish_ids)

                rarity = await con.fetchval("SELECT rarity_name FROM fish_rarity WHERE rarity_id = $1", rarity_id)

                if excluded_fish_ids:
                    await interaction.followup.send(
                        f"> Sold all {rarity} fish with excluded fish ids {','.join(str(x) for x in excluded_fish_ids)} "
                        f"{self.ctx.author.name}.",
                        ephemeral=True)

                await con.execute("""UPDATE users SET credits = credits + $1 where user_id = $2 """,
                                  amount, self.ctx.author.id)

                await interaction.followup.send(f"Successfully sold all fish of rarity {rarity} "
                                                f"{self.ctx.author.name} "
                                                f"you gained {amount} credits.", ephemeral=True)


class FishSellButton(discord.ui.Button):
    def __init__(self, ctx):
        super(FishSellButton, self).__init__()
        self.ctx = ctx
        self.label = "fish"
        self.style = discord.ButtonStyle.primary

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: FishSellView = self.view

        amount, fish_id = await view.get_modal_data(interaction)

        if fish_id in await view.get_fish_favourites(self.ctx):
            return await interaction.followup.send(
                ":no_entry: | you currently have this fish registered as a favourite fish",
                ephemeral=True)

        data = await self.ctx.db.fetchrow("""SELECT amount, fish.rarity_id, fish.fish_name FROM fish_users_catches
                                                INNER JOIN fish ON fish_users_catches.fish_id = fish.fish_id 
                                                WHERE user_id = $1 AND fish_users_catches.fish_id = $2""",
                                          self.ctx.author.id,
                                          fish_id)
        if not data:
            return await interaction.followup.send(":no_entry: | you currently don't own that fish.",
                                                   ephemeral=True)

        if data["amount"] < amount:
            return await interaction.followup.send(
                f":no_entry: | you do not have enough {data['fish_name']} for this action")

        rarity_id = data["rarity_id"]
        pay_out = view.price_setter(rarity_id, amount)

        delete_check = data["amount"] == amount

        async with self.ctx.bot.pool.acquire() as con:
            async with con.transaction():

                if delete_check:
                    await con.execute("""DELETE FROM fish_users_catches
                                                         WHERE fish_id = $1 and user_id = $2""",
                                      fish_id, self.ctx.author.id)

                else:
                    await con.execute("""UPDATE fish_users_catches SET amount = amount - $3
                                                    WHERE fish_id = $1 and user_id = $2
                                                      """,
                                      fish_id, self.ctx.author.id, amount)

                await interaction.followup.send(
                    f"Successfully sold {amount} {data['fish_name']} {self.ctx.author.name} "
                    f"you gained {pay_out} credits.",
                    ephemeral=True)


class UseButton(discord.ui.Button):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.label = "use"
        self.emoji = PLATWAA
        self.style = discord.ButtonStyle.success

    async def get_data(self, user_id: int, bait_id: int):
        return await self.ctx.db.fetchrow(
            "SELECT amount, bait_id FROM fish_user_inventory WHERE user_id = $1 AND bait_id = $2",
            user_id, bait_id)

    def validate_data(self, data, amount) -> bool:
        if data is None:
            return False

        if data["amount"] - amount < 0:
            return False

        return True

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None
        view: InventoryView = self.view

        amount, bait_id = await view.get_modal_data(interaction)
        emoji = await view.get_bait_emoji(self.ctx.db, bait_id)

        data = await self.get_data(self.ctx.author.id, bait_id)
        check = self.validate_data(data, amount)

        if not check:
            return await interaction.followup.send(f":no_entry: | you do not have enough {emoji} for this action.",
                                                   ephemeral=True)

        async with self.ctx.bot.pool.acquire() as con:
            async with con.transaction():
                await InventoryView.expend_bait(con, amount, self.ctx.author.id, bait_id)
                f = fish.Fishing(self.ctx)
                await f.catch_fish(self.ctx, bait_id, amount)
                await f.display_fish()
                await view.run()

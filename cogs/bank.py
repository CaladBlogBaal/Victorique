import datetime
import random
import asyncio

import humanize as h
import discord
from discord.ext import commands


class Bank(commands.Cog):
    """User bank related commands"""

    def __init__(self, bot):

        self.bot = bot

    @commands.command()
    async def transfer_credits(self, ctx, member: discord.Member, amount: float):
        """
        Transfer credits to a guild member
        """

        if member == ctx.author:
            return await ctx.send(f":no_entry: | {ctx.author.name}, you can't give credits to yourself")

        if member.bot:
            return

        current_balance = await ctx.bot.db.fetchval("select credits from users where user_id = $1", ctx.author.id)

        if current_balance - amount * 1.05 < 0:
            return await ctx.send(":no_entry: | you do not have enough credits for this transaction.")

        if amount <= 0:
            return await ctx.send(f":no_entry: | {ctx.author.name} please enter in a valid "
                                  f"amount of credits to transfer")

        if amount > int(current_balance):
            return await ctx.send(f":atm: | {ctx.author.name}, do not have enough credits for this transaction,"
                                  f" the current amount of credits in your bank is "
                                  f"{current_balance}")

        transaction_id = random.randint(1000, 90000)
        transaction_id = str(transaction_id)

        embed = discord.Embed(content=":atm: | credit transfer",
                              description=f"Amount of credits to transfer {amount}"
                                          f"\nCurrent balance {current_balance}"
                                          f"\nBalance after with tax {current_balance - amount * 1.05}"
                                          f"\nConfirmation pin {transaction_id}"
                                          f"\n(say cancel to cancel the transaction)",
                              color=self.bot.default_colors()
                              )

        await ctx.send(embed=embed)

        try:
            cancel_message = ":information_source: | {}, credit transfer has been cancelled"
            confirmation = await ctx.wait_for_input(transaction_id, cancel_message)

            if confirmation:
                await ctx.send(f":information_source: | {member.mention}, "
                               f"{amount} has been transferred to your account by "
                               f"{ctx.author.name}")

                async with ctx.con.transaction():

                    await ctx.con.execute("UPDATE users SET credits = credits + $1 WHERE user_id = $2",
                                          amount, member.id)

                    await ctx.con.execute("UPDATE users SET credits = credits - $1 WHERE user_id = $2",
                                          amount * 1.05, ctx.author.id)

        except asyncio.TimeoutError:
            return await ctx.send(f":information_source: | a response wasn't given in awhile"
                                  f" cancelling the transaction")

    @commands.command()
    async def credits(self, ctx, member: discord.Member = None):
        """
        View a guild member's credits
        """
        member = member or ctx.author

        current_balance = await ctx.con.fetchval("select credits from users where user_id = $1", member.id)

        await ctx.send(
            f":credit_card: | {member.display_name}, has {round(current_balance, 2)} credits in "
            f"their account")

    @commands.command()
    async def daily(self, ctx):
        """
        Get your daily credits
        """
        statement = "UPDATE users SET daily_cooldown = $1 where user_id = $2"

        check = await ctx.con.fetchval("SELECT daily_cooldown from users where user_id = $1", ctx.author.id)

        async with ctx.con.transaction():

            if check is None:
                await ctx.con.execute(statement, ctx.message.created_at + datetime.timedelta(days=1), ctx.author.id)

            else:
                time = check
                now = datetime.datetime.utcnow()

                if time > datetime.datetime.utcnow():
                    return await ctx.send(f":information_source: | "
                                          f"you can collect your daily credits again in " + h.naturaldelta(now - time))

                await ctx.con.execute(statement, ctx.message.created_at + datetime.timedelta(days=1), ctx.author.id)

        async with ctx.con.transaction():

            await ctx.con.execute("UPDATE users SET credits = credits + $1 WHERE user_id = $2",
                                  2000, ctx.author.id)

        await ctx.send(f":atm: | 2000 credits was added to your account {ctx.author.name}")


def setup(bot):
    bot.add_cog(Bank(bot))

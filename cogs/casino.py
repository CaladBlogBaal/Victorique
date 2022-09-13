import secrets
import random

import numpy as np

from discord.ext import commands

from config.utils.context import Context


class SlotMachine:

    def __init__(self, bet):
        self.bet = bet
        self.wheel = np.random.random_integers(8, size=(3, 3))

        self.fruits = {1: ":cherries:", 2: ":lemon:", 3: ":tangerine:", 4: ":watermelon:",
                       5: ":apple:", 6: ":seven:", 7: ":100:", 8: ":flag_at:"}

    async def spin_wheel(self):
        for i in range(3):
            self.wheel[i] = np.random.random_integers(8, size=3)

    def display_wheel(self):

        board_display = ["seven", "seven", "seven",
                         "seven", "seven", "seven",
                         "seven", "seven", "seven",
                         ]

        board_flat = self.wheel.flatten()

        for i in range(0, 9):
            board_display[i] = self.fruits[board_flat[i]]

        display = ["[ :slot_machine: | SLOTS ]"
                   "\n{} {} {} "
                   "\n------------------"
                   "\n{} {} {} <"
                   "\n------------------ "
                   "\n{} {} {} ".format(*board_display)]
        return display


class PayOuts(SlotMachine):
    def __init__(self, bet):
        super().__init__(bet)
        self.payout = 0
        self.multiplier = {1: 20, 2: 30, 3: 40, 4: 40, 5: 80, 6: 100, 7: 120, 8: 600}

    def pay_out_reel(self, bet, wheel):

        rows = np.all(wheel[1, :] == wheel[1][0])

        if rows:
            value = wheel[1][0]
            self.payout += bet * self.multiplier[value]

        rows = np.all(wheel[1, :] == [7, 6, 5])
        if rows:
            self.payout += bet * 300

        return self.payout


class Casino(commands.Cog):
    """Casino games related commands"""
    def __init__(self, bot):
        self.bot = bot

    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.command(description="""```CSS
                                 ----------------------------------------------
                                |Pay Table                                     |
                                |----------------------------------------------
                                |cherries  | cherries  | cherries  |[bet * 20] |
                                |lemon     | lemon     | lemon     |[bet * 30] |
                                |orange    | orange    | orange    |[bet * 40] |
                                |watermelon| watermelon| watermelon|[bet * 40] |
                                |apple     | apple     | apple     |[bet * 80] |
                                |seven     | seven     | seven     |[bet * 100]|
                                |hundred   | hundred   | hundred   |[bet * 120]|
                                |hundred   | seven     | apple     |[bet * 300]| 
                                |flag      | flag      | flag      |[bet * 600]|
                                |----------------------------------------------
                                | .max_bet = [5000]
                                |.max_possible earnings = [3,000,000]
                                |.least_possible earnings = [300]
                                ```
                                 """,
                      aliases=["slot", "slot_machine"],
                      cooldown_after_parsing=True
                      )
    async def slots(self, ctx: Context, bet, spins: int = 6):
        """spin some slots"""
        await ctx.acquire()
        spins = int(spins)
        bet = int(bet)

        if bet > 5000:
            bet = 5000

        current_balance = await ctx.db.fetchval("select credits from users where user_id = $1", ctx.author.id)

        if bet <= 0:
            return await ctx.send(f":no_entry: | {ctx.author.name} please enter in a valid "
                                  f"amount of credits to bet")

        if bet > int(current_balance):
            return await ctx.send(f":atm: | {ctx.author.name}, do not have enough credits for this bet,"
                                  f" the current amount of credits in your bank is "
                                  f"{current_balance}")

        if spins > 9 or spins <= 0:
            spins = 9

        sm = SlotMachine(bet)

        await sm.spin_wheel()
        display = sm.display_wheel()
        msg = await ctx.send(display[0])

        for z in range(spins - 1):
            await sm.spin_wheel()
            display = sm.display_wheel()
            await msg.edit(content=display[0])

        po = PayOuts(sm)
        pay_out = po.pay_out_reel(bet, sm.wheel)
        if pay_out == 0:

            await ctx.db.execute("UPDATE users SET credits = credits - $1 WHERE user_id = $2", bet, ctx.author.id)

            await ctx.send(f":atm: | {ctx.author.name} you lost {bet} credits.")

        else:

            await ctx.db.execute("UPDATE users SET credits = credits + $1 WHERE user_id = $2", pay_out, ctx.author.id)

            await ctx.send(f":atm: | the amount of credits you gained is {pay_out} {ctx.author.name}")

        await ctx.release()

    @commands.group(invoke_without_command=True)
    async def coinflip(self, ctx: Context, times: int = 1):
        """
        Flip a coin
        """

        if times < 0:
            return

        if times > 100:
            times = 100

        heads_or_tail = ["heads", "tails"]
        results = [heads_or_tail[random.randint(0, 1)] for _ in range(times)]

        head_count = results.count("heads")
        tail_count = results.count("tails")

        results = f"> {ctx.author.name}, you flipped ({head_count}) heads and ({tail_count}) tails"

        await ctx.send(results)

    @coinflip.command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def bet(self, ctx: Context, choice, bet: int):
        """
        Flip a coin and bet the outcome choices (heads or tails)
        """

        if choice.lower() not in ("heads", "tails"):
            return await ctx.send(":no_entry: | invalid choice (heads, tails) only.")

        if bet <= 0:
            return await ctx.send(":no_entry: | please enter a valid amount of credits to bet.", delete_after=3)

        current_balance = await ctx.db.fetchval("SELECT credits from users where user_id = $1", ctx.author.id)

        if current_balance < bet:
            return await ctx.send(":no_entry: | you do not have enough credits for this bet.")
        heads_or_tail = ["heads", "tails"]

        index = secrets.randbelow(2)

        result = heads_or_tail[index]

        await ctx.send(f"The result was {result}.")

        async with ctx.acquire():
            if result == choice.lower():

                await ctx.db.execute("UPDATE users set credits = credits + $1 where user_id = $2", bet, ctx.author.id)
                await ctx.send(f":information_source: | {ctx.author.name} you've won {bet} credits")

            else:

                await ctx.db.execute("UPDATE users set credits = credits - $1 where user_id = $2", bet, ctx.author.id)
                await ctx.send(f":information_source: | {ctx.author.name} you've lost {bet} credits")


async def setup(bot):
    await bot.add_cog(Casino(bot))

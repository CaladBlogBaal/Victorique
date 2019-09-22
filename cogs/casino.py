import secrets
import asyncio
import random

import numpy as np

from discord.ext import commands

from config.utils.emojis import TRANSPARENT


class SlotMachine:

    def __init__(self, bet):
        self.bet = bet
        self.wheel = np.random.random_integers(8, size=(3, 3))

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
            if board_flat[i] == 1:
                board_display[i] = ":cherries:"
            elif board_flat[i] == 2:
                board_display[i] = ":lemon:"
            elif board_flat[i] == 3:
                board_display[i] = ":tangerine:"
            elif board_flat[i] == 4:
                board_display[i] = ":watermelon:"
            elif board_flat[i] == 5:
                board_display[i] = ":apple:"
            elif board_flat[i] == 6:
                board_display[i] = ":seven:"
            elif board_flat[i] == 7:
                board_display[i] = ":100:"
            elif board_flat[i] == 8:
                board_display[i] = ":flag_at:"

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

    def pay_out_reel(self, bet, wheel):

        rows = np.all(wheel[1, :] == wheel[1][0])
        if rows:
            value = wheel[1][0]

            if value == 1:
                self.payout += bet * 20
            elif value == 2:
                self.payout += bet * 30
            elif value == 3:
                self.payout += bet * 40
            elif value == 4:
                self.payout += bet * 40
            elif value == 5:
                self.payout += bet * 80
            elif value == 6:
                self.payout += bet * 100
            elif value == 7:
                self.payout += bet * 120
            elif value == 8:
                self.payout += bet * 600

        rows = np.all(wheel[1, :] == [7, 6, 5])
        if rows:
            self.payout += bet * 300

        return self.payout


class Tabel:
    def __init__(self):
        self.TRANSPARENT = TRANSPARENT
        self.table = np.array([[0, 0, 0, 0, 0, 0, 0, 1, 0, 0]])
        # i= 0 1 2 3 4 5 6 7 8 9
        # 0 0 0 0 0 0 0 1  0  0
        # _ _ _ _ _ _ _ | _  _|
        #               ^    ^-----.
        #               |          |
        #           pass line,  wall

        self.die = 2

    async def shoot(self, ctx, power):

        resitance = random.randint(1, 5)
        power -= resitance
        if power <= -1:
            power = 0

        if power > 1000 and power < 10000:
            return await ctx.send("The die went into orbit around planet earth.")

        if power > 10000:
            return await ctx.send("The die will venture into the vast emptiness of space")

        try:

            self.table[0][power] = self.die
            if power > 7:
                return True

            elif power <= 7:
                return await ctx.send("The die didn't pass the pass line")

        except IndexError:
            return await ctx.send("The die flew off the table")

    def display(self):
        table = self.table.flatten()

        board_display = [f"{self.TRANSPARENT}", f"{self.TRANSPARENT}",
                         f"{self.TRANSPARENT}", f"{self.TRANSPARENT}",
                         f"{self.TRANSPARENT}", f"{self.TRANSPARENT}",
                         f"{self.TRANSPARENT}", f"{self.TRANSPARENT}",
                         f"{self.TRANSPARENT}", f"{self.TRANSPARENT}", ]

        board_table = ":white_large_square:" \
                      ":white_large_square:" \
                      ":white_large_square:" \
                      ":white_large_square:" \
                      ":white_large_square:" \
                      ":white_large_square:" \
                      ":white_large_square:" \
                      ":black_large_square:" \
                      ":black_large_square:" \
                      ":white_large_square:" \
                      ":white_large_square:"

        for i in range(0, 10):
            if table[i] == self.die:
                board_display[i] = ":game_die:"

        display = ["{}{}{}{}{}{}{}{}{}{}".format(*board_display), board_table]

        return display


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
    async def slots(self, ctx, bet, spins: int = 6):
        """spin some slots"""
        spins = int(spins)
        bet = int(bet)

        if bet > 5000:
            bet = 5000

        current_balance = await ctx.con.fetchval("select credits from users where user_id = $1", ctx.author.id)

        if bet <= 0:
            return await ctx.send(f":no_entry: | {ctx.author.name} please enter in a valid "
                                  f"amount of credits to bet")

        if bet > int(current_balance):
            return await ctx.send(f":atm: | {ctx.author.name}, do not have enough credits for this bet,"
                                  f" the current amount of credits in your bank is "
                                  f"{current_balance}")

        if spins > 9:
            spins = 9

        if spins <= 0:
            spins = 9

        sm = SlotMachine(bet)

        await sm.spin_wheel()
        display = sm.display_wheel()
        msg = await ctx.send(display[0])

        for z in range(spins - 1):
            await sm.spin_wheel()
            display = sm.display_wheel()
            await msg.edit(content=display[0])
            await asyncio.sleep(0.5)

        po = PayOuts(sm)
        pay_out = po.pay_out_reel(bet, sm.wheel)
        if pay_out == 0:

            async with ctx.con.transaction():

                await ctx.con.execute("UPDATE users SET credits = credits - $1 WHERE user_id = $2",
                                      bet, ctx.author.id)

            await ctx.send(f":atm: | {ctx.author.name} you lost {bet} credits.")

        else:

            async with ctx.con.transaction():

                await ctx.con.execute("UPDATE users SET credits = credits + $1 WHERE user_id = $2",
                                      pay_out, ctx.author.id)

            await ctx.send(f":atm: | the amount of credits you gained is {pay_out} {ctx.author.name}")

    @commands.command()
    async def shoot(self, ctx, power: int):
        """shoot a dice on a carps table, pass line is the first black block"""
        table = Tabel()

        table_display = table.display()
        msg = await ctx.send(":game_die:" + " \n" + table_display[0] + "\n" + table_display[1])

        await table.shoot(ctx, power)

        table_display = table.display()
        await asyncio.sleep(0.1)
        await msg.edit(content=table_display[0] + "\n" + table_display[1])

    @commands.group(invoke_without_command=True)
    async def coinflip(self, ctx, times: int = 1):
        """
        flip a coin
        """

        if times < 0:
            return

        if times > 100:
            times = 100

        heads_or_tail = ["heads", "tail"]
        results = [heads_or_tail[random.randint(0, 1)] for _ in range(times)]

        head_count = 0
        tail_count = 0

        for result in results:
            if result == "heads":
                head_count += 1
            else:
                tail_count += 1

        results = f"> {ctx.author.name}, you flipped ({head_count}) heads and ({tail_count}) tails"

        await ctx.send(results)

    @coinflip.command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def bet(self, ctx, choice, bet: int):
        """
        flip a coin and bet the outcome choices (heads or tails)
        """

        if choice.lower() not in ("heads", "tails"):
            return await ctx.send(":no_entry: | invalid choice (heads, tails) only.")

        if bet <= 0:
            return await ctx.send(":no_entry: | please enter a valid amount of credits to bet.", delete_after=3)

        current_balance = await ctx.con.fetchval("SELECT credits from users where user_id = $1", ctx.author.id)

        if current_balance < bet:
            return await ctx.send(":no_entry: | you do not have enough credits for this bet.")
        heads_or_tail = ["heads", "tails"]

        index = secrets.randbelow(2)

        result = heads_or_tail[index]

        await ctx.send(f"The result was {result}.")
        await asyncio.sleep(1)

        if result == choice.lower():
            async with ctx.con.transaction():
                await ctx.con.execute("UPDATE users set credits = credits + $1 where user_id = $2",
                                      bet, ctx.author.id)

            await ctx.send(f":information_source: | {ctx.author.name} you've won {bet} credits")

        else:
            async with ctx.con.transaction():
                await ctx.con.execute("UPDATE users set credits = credits - $1 where user_id = $2",
                                      bet, ctx.author.id)

                await ctx.send(f":information_source: | {ctx.author.name} you've lost {bet} credits")


def setup(bot):
    bot.add_cog(Casino(bot))

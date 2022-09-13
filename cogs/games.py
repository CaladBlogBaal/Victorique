import contextlib
import asyncio
import typing

import discord
from discord.ext import commands

from games.blackjack import BlackJackPlayer
from games.tittactoe import TicTacToe
from games.trivia import Triva
from cogs.utils.games import *
from config.utils.checks import checking_for_multiple_channel_instances
from config.utils.converters import TriviaCategoryConverter, TriviaDiffcultyConventer, DieConventer
from config.utils.menu import page_source
from config.utils.context import Context


class Games(commands.Cog):
    """Some general games"""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def multiple_user_instance_set(ctx):
        if ctx.guild:
            key = str(ctx.channel.id) + ctx.command.input

            if key not in ctx.bot.channels_running_commands:
                ctx.bot.channels_running_commands[key] = []

            ctx.bot.channels_running_commands[key].append(ctx.author.id)

    async def cog_after_invoke(self, ctx):
        with contextlib.suppress(ValueError, AttributeError):
            if ctx.guild:
                key = str(ctx.channel.id) + ctx.command.name
                list_ = ctx.bot.channels_running_commands.get(key)
                list_.remove(ctx.author.id)
                ctx.bot.channels_running_commands[key] = list_
                if not list_:
                    ctx.bot.channels_running_commands.pop(key, None)

    async def cog_command_error(self, ctx, error):

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, asyncio.TimeoutError):
            await ctx.send(f"> no response was received for awhile cancelling the game for `{ctx.command.name}`",
                           delete_after=10)

        if isinstance(error, commands.CheckFailure):
            await ctx.send(f":no_entry: | only one instance of this {ctx.command.name} command per channel",
                           delete_after=3)

    @staticmethod
    @page_source()
    def trivia_source(self, menu, entries):
        res = "\n".join(f"> ID: `{result['question_id']}`: **{result['content']}**" for result in entries)
        return f"Category Name: ```{self.category}```\nAmount of questions ({self.amount})\n{res}"

    @commands.command(aliases=["8ball", "8-ball", "magic_eight_ball"])
    async def eight_ball(self, ctx: Context, *, message):
        """
        Answers from cthulu
        """

        possible_responses = [
            ":8ball: | Definitely  no",
            ":8ball: | It\'s not looking likely",
            ":8ball: | Can\'t give you an answer",
            ":8ball: | It\'s quite possible",
            ":8ball: | Definitely",
            ":8ball: | Reply hazy, try again",
            ":8ball: | Outlook not so good",
            ":8ball: | Don\'t count on it"
        ]
        shake = ":8ball:"
        msg = await ctx.send(f"{shake}ㅤ")

        for _ in range(2):
            await msg.edit(content=f"ㅤ{shake}")
            await asyncio.sleep(0.2)
            await msg.edit(content=f"{shake}ㅤ")

        await msg.edit(content=f"{random.choice(possible_responses)} {ctx.author.name}")

    @commands.command()
    async def roll(self, ctx: Context, *, dice: DieConventer):
        """
        Roll a die in a NdN+m format
        """

        rolls, limit, expression = dice

        results = [random.randint(1, limit) for _ in range(rolls)]

        for i, res in enumerate(results):
            expression.insert(0, str(res))

            results[i] = ShuntingYard(expression).evaluate()

            del expression[0]

        results = f"```py\nRolled: ({results})\n```"

        await ctx.send(results)

    @commands.group(aliases=["tri"], invoke_without_command=True)
    async def trivia(self, ctx: Context, difficulty: typing.Optional[TriviaDiffcultyConventer] = None,
                     amount: typing.Optional[int] = 5, *, category: TriviaCategoryConverter = None):
        """
        Answer some trivia questions category accepts either an id or name
        possible difficulties are easy, medium hard
        """

        if amount <= 0:
            return await ctx.send(":no_entry: | please type in a valid amount of questions.")

        triva = Triva(ctx)
        await triva.run(difficulty, amount, category)

    @trivia.group(aliases=["cat"], invoke_without_command=True)
    async def categorises(self, ctx: Context):
        """The main command for finding questions based on category by itself returns all the categories available"""

        async with ctx.acquire():
            results = await ctx.db.fetch("""
                                          SELECT c.category_id, c.name, COUNT(q.question_id) 
                                          from category as c INNER JOIN question as q on c.category_id = q.category_id
                                          GROUP BY c.category_id""")

        results = sorted(results, key=lambda res: res["category_id"])

        description = "\n".join(f"ID: `{result['category_id']}`: **{result['name']}** `({result['count']}) questions`"
                                for result in results)

        if not description:
            await ctx.send("> No categories have been set for this bot, contact the owner")

        await ctx.send(description)

    @categorises.command()
    async def search(self, ctx: Context, *, category: TriviaCategoryConverter):
        """Search returns all questions based on their category, category accepts either an id or name"""

        async with ctx.acquire():
            results = await ctx.db.fetch("""SELECT q.content, q.question_id, c.name as category_name
                                            FROM question q 
                                            INNER JOIN category c on c.category_id = q.category_id
                                            WHERE q.category_id = $1
                                            GROUP BY q.question_id, c.category_id""", category)

        self.trivia_source.category = results[0]["category_name"]
        self.trivia_source.amount = len(results)
        pages = ctx.menu(self.trivia_source(results))
        await pages.start(ctx)

    @commands.command(aliases=["ttt"])
    async def tictactoe(self, ctx: Context, member: discord.Member):
        """
        Play a game of TicTacToe
        this command is reaction based just react with
        the number you'd like to place your letter on."
        """

        if member == ctx.author:
            return await ctx.send("You can't play against yourself silly rascal")

        if member.bot:
            return await ctx.send("Bots are too much for mere humans.")

        ttt = TicTacToe()
        await ttt.run(ctx, member)

    @commands.command(aliases=["bj", "blackjack"])
    # gotta actually rewrite this
    @commands.is_owner()
    @checking_for_multiple_channel_instances()
    async def black_jack(self, ctx: Context):
        """
        Start a game of black jack
        rules for black jack are as follows taken from www.blackjackchamp.com
        ------------------------------------------------------------------------------------------------------------
        Blackjack card values:
            **Aces** are be valued at __1 or 11__.
            **Face cards** (Kings, Queens and Jacks) are valued at __10__.
            The **other cards** are valued at the __face value__ of the card. (10 points for 10, 8 points for 8 etc.)

        Two **face** up cards for the players
        One face up and one **face down** for the dealer
        A **natural blackjack** (11+10) is an obvious win
        Push – hands with equal value

        **Hit** – take more cards
        **Stand** – not taking more cards
        **Bust** – a hand over 21 (losing)
        ------------------------------------------------------------------------------------------------------------
        """
        # ill refractor this later I guess
        self.multiple_user_instance_set(ctx)
        dealer_bj = False

        deck = Deck()
        dealer = {self.bot.user.id: BlackJackPlayer()}

        host = ctx.author
        players_list = [host]
        player_dict = {host: BlackJackPlayer()}
        player_hand_value = {host: "value"}
        natrual_bj = {"player": "boolean"}

        deck.shuffle()

        for player in players_list:

            for _ in range(2):
                player_dict.get(player).add_card_to_hand(deck.pop_card())

            natrual_bj.update({player: False})

            await ctx.send(player.name + "'s hand is" + player_dict.get(player).display_hand() + "\n")

            if player_dict.get(player).calculate_winner():
                await ctx.send(f"> {player.name} has gotten a natural blackjack.")

                natrual_bj.update({player: True})

            await asyncio.sleep(2)

        for _ in range(2):
            dealer.get(self.bot.user.id).add_card_to_hand(deck.pop_card())

        dealer_first_card = dealer.get(self.bot.user.id).hand[0]

        await ctx.send(f"{self.bot.user.mention}\'s hand is " + dealer.get(self.bot.user.id).display_hand(True))

        named_cards = ["Jack", "King", "Queen"]

        if dealer_first_card == "Ace" or dealer_first_card in named_cards:
            await asyncio.sleep(1)
            await ctx.send("> The dealer is checking their face_down card..")
            await asyncio.sleep(1)
            if dealer.get(self.bot.user.id).calculate_winner():
                await ctx.send(f"> {self.bot.user.mention}\'s hand is " + dealer.get(self.bot.user.id).display_hand())
                await ctx.send("> The dealer has gotten a natural blackjack")
                dealer_bj = True

        for player in players_list:

            await asyncio.sleep(1)
            turn = True

            if not natrual_bj.get(player):
                await ctx.send(f"> It's {player.name}'s turn \nOptions: Hit or Stand")

            while turn:

                if natrual_bj.get(player):
                    break

                player_current_hand_value = player_dict.get(player).calculate_hand()

                if player_current_hand_value > 21:
                    await ctx.send(f"> {player.name} has gone bust (will automatically stand).")
                    player_hand_value.update({player: player_current_hand_value})
                    break

                message = await self.bot.wait_for('message', check=lambda m: m.author == player, timeout=60)

                if message.content.lower() == "hit":
                    card = deck.pop_card()
                    await asyncio.sleep(1)
                    await ctx.send(f"{card.print_card()}was added to your hand")
                    player_dict.get(player).add_card_to_hand(card)

                    if player_dict.get(player).calculate_winner():
                        await ctx.send(f"> {player.name}'s hand is 21 will automatically stand.")
                        player_hand_value = {player: player_dict.get(player).calculate_hand()}
                        break

                elif message.content.lower() == "stand" and not natrual_bj.get(player):

                    await asyncio.sleep(1)
                    await ctx.send("> You've chosen to stand")
                    await asyncio.sleep(1)

                    if player_current_hand_value > 21:
                        await ctx.send(f"> {player.name} has gone bust.")
                        player_hand_value.update({player: player_current_hand_value})

                    else:
                        player_hand_value.update({player: player_current_hand_value})
                        await ctx.send(f"> The value of your hand is {player_current_hand_value}")

                    turn = False

        dealers_current_hand_value = dealer.get(self.bot.user.id).calculate_hand()
        await asyncio.sleep(1)
        await ctx.send("> The dealer has finished serving")
        await asyncio.sleep(1)
        await ctx.send(f"> {self.bot.user.mention}\'s hand is " + dealer.get(self.bot.user.id).display_hand())

        if dealers_current_hand_value >= 17:
            await ctx.send("> The dealer is standing")
            await asyncio.sleep(1)

        while dealers_current_hand_value <= 17:
            dealer.get(self.bot.user.id).add_card_to_hand(deck.pop_card())
            await asyncio.sleep(1)

            card = dealer.get(self.bot.user.id).hand[-1]

            await asyncio.sleep(1)
            await ctx.send(f"> The dealer has drawn an extra card {card.print_card()}\n")
            dealers_current_hand_value = dealer.get(self.bot.user.id).calculate_hand()

            if dealers_current_hand_value > 21:
                await asyncio.sleep(1)
                await ctx.send(f"{self.bot.user.mention} has gone bust.")

        dealers_final_hand = dealer.get(self.bot.user.id).calculate_hand()

        for player in players_list:
            await asyncio.sleep(1)
            hand_value = player_hand_value[player]

            if natrual_bj.get(player) and not dealer_bj:
                await ctx.send(f"> {player.name} won.")

            elif natrual_bj.get(player) and dealer_bj or hand_value == dealers_final_hand:
                await ctx.send(f">  {player.name} has tied with the dealer")

            elif dealers_final_hand < hand_value < 21 or hand_value < dealers_final_hand < 21 and not dealer_bj:
                await ctx.send(f"> {player.name} won.")

            elif hand_value == 21 and dealers_final_hand != 21:
                await ctx.send(f"> {player.name} won.")

            else:
                await ctx.send(f"> {player.mention} has lost.")


async def setup(bot):
    n = Games(bot)
    await bot.add_cog(n)

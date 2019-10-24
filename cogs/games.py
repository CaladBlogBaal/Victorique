import copy
import contextlib
import asyncio
import random
import typing
import re

import numpy as np

import discord
from discord.ext import commands

from config.utils.checks import checking_for_multiple_channel_instances
from config.utils.paginator import Paginator
from config.utils.converters import TriviaCategoryConvertor, TriviaDiffcultyConventor, DieConventor


class Card:
    SUITS = ["Clubs", "Diamonds", "Hearts", "Spades"]
    RANK = [None, "Ace", "2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King"]

    def __init__(self, suit: 0, rank: 2):
        self.suit = suit
        self.rank = self.RANK[rank]
        self.rank_index = rank
        self.running_player_queue = None

    def print_card(self):
        return "\n{} of {} ".format(Card.RANK[self.rank_index], Card.SUITS[self.suit])

    def __it__(self, other):
        if self.suit < other.suit:
            return True

        if self.suit > other.suit:
            return False

        return self.rank < other.rank


class Deck:
    def __init__(self):
        self.cards = []
        self.removed_cards = []
        for suit in range(4):
            for rank in range(1, 14):
                card = Card(suit, rank)
                self.cards.append(card)

    def shuffle(self):
        random.shuffle(self.cards)

    def pop_card(self, i=0):
        self.removed_cards.append(self.cards[i])
        return self.cards.pop(i)

    def add_card(self, card):
        self.cards.append(card)

    def is_empty(self):
        return len(self.cards) == 0

    def add_back_removed_cards(self):
        for card in self.removed_cards:
            self.add_card(card)


class Player:

    def __init__(self):
        self.hand = []

    def add_card_to_hand(self, card):
        self.hand.append(card)

    def remove_card_to_hand(self, i):
        del self.hand[i]

    def display_hand(self, dealer=False):
        if dealer:
            return self.hand[0].print_card() + "\n**Second card is face down**"

        display = ""

        for card in self.hand:
            display += card.print_card()

        return display

    def clear_hand(self):
        self.hand = []


class BlackJackPlayer(Player):
    NAMED_CARDS = ["Jack", "King", "Queen"]

    def __init__(self):
        self.hand = []
        super().__init__()

    def calculate_winner(self):

        player_total = self.calculate_hand()

        if player_total == 21:
            return True

        if player_total > 21:
            return False

    def calculate_hand(self):

        player_total = 0

        for card in self.hand:

            if card.rank in BlackJackPlayer.NAMED_CARDS:
                player_total += 10

            if card.rank == "Ace":
                player_total += 11

            try:
                player_total += int(card.rank)

            except ValueError:
                pass

        return player_total


class QuizPoints:
    def __init__(self, name):
        self.name = name
        self.points = 0

    @property
    def score(self):
        result = f"{self.name} scored {str(self.points)} points."
        return result

    @score.setter
    def score(self, value):
        self.points += value


class Games(commands.Cog):
    """Some general games"""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def multiple_user_instance_set(ctx):
        if ctx.guild:
            key = str(ctx.channel.id) + ctx.command.name

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

        if isinstance(error, (asyncio.TimeoutError, asyncio.futures.TimeoutError)):
            await ctx.send(f"> no response was received for awhile cancelling the game for `{ctx.command.name}`",
                           delete_after=10)

        if isinstance(error, commands.CheckFailure):
            await ctx.send(f":no_entry: | only one instance of this {ctx.command.name} command per channel",
                           delete_after=3)

    @staticmethod
    async def set_questions(ctx, category, difficulty, amount_of_questions):

        if amount_of_questions > 10:
            amount_of_questions = 10

        query = "SELECT question_id from question"

        if not category and not difficulty:
            results = await ctx.con.fetch(query)

        elif category and not difficulty:
            query += " WHERE category_id = $1"
            results = await ctx.con.fetch(query, category)

        elif difficulty and not category:
            query += " WHERE difficulty = $1"
            results = await ctx.con.fetch(query, difficulty)

        else:
            query += " WHERE category_id = $1 and difficulty = $2"
            results = await ctx.con.fetch(query, category, difficulty)

        results = random.sample(results, amount_of_questions)
        return results

    @staticmethod
    def build_answers(answers):
        answers = sorted(answers, key=lambda ans: ans["is_correct"], reverse=True)
        return [ans["content"] for ans in answers]

    async def build_question(self, ctx, question_id):
        question_id = question_id["question_id"]
        data = await ctx.con.fetchrow("""SELECT content, difficulty, type 
                                          from question where question_id = $1""", question_id)

        question, difficulty, type_ = data["content"], data["difficulty"], data["type"]

        answers = await ctx.con.fetch("SELECT content, is_correct from answer where question_id = $1", question_id)
        answers = self.build_answers(answers)

        category = await ctx.con.fetchval("""
        SELECT name from category where category_id = (SELECT category_id from question where question_id = $1)""",
                                          question_id)

        return category, type_, difficulty, question, answers

    @commands.command(aliases=["8ball", "8-ball", "magic_eight_ball"])
    async def eight_ball(self, ctx, *, message):
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
    async def roll(self, ctx, *, dice: DieConventor):
        """
        Roll a die in a NdN+m format
        """

        ops = {"+": (lambda a, b: a + b),
               "-": (lambda a, b: a - b),
               "*": (lambda a, b: a * b),
               "/": (lambda a, b: a / b)}

        rolls, limit, expression = dice

        results = [random.randint(1, limit) for _ in range(rolls)]

        def is_digit(num):
            try:
                num = int(num)
            except ValueError:
                try:
                    num = float(num)
                except ValueError:
                    return False

            return num

        def peek(stack):
            return stack[-1] if stack else None

        def calculate(operators, values):
            right = values.pop()
            left = values.pop()
            values.append(ops[operators.pop()](left, right))

        def greater_precedence(op1, op2):
            precedences = {"+": 0, "-": 0, "*": 1, "/": 1}
            return precedences[op1] > precedences[op2]

        def evaluate():
            # https://en.wikipedia.org/wiki/Shunting-yard_algorithm
            # http://www.martinbroadhurst.com/shunting-yard-algorithm-in-python.html

            values = []
            operators = []
            for token in expression:
                if is_digit(token):
                    values.append(is_digit(token))
                elif token == "(":
                    operators.append(token)
                elif token == ")":
                    top = peek(operators)
                    while top not in (None, "("):
                        calculate(operators, values)
                        top = peek(operators)
                    operators.pop()

                else:
                    top = peek(operators)

                    while top not in (None, "(", ")") and greater_precedence(top, token):
                        calculate(operators, values)
                        top = peek(operators)
                    operators.append(token)

            while peek(operators):
                calculate(operators, values)

            return values[0]

        for i, res in enumerate(results):
            expression.insert(0, str(res))

            results[i] = evaluate()

            del expression[0]

        results = f"```py\nRolled: ({results})\n```"

        await ctx.send(results)

    @commands.group(aliases=["tri"], invoke_without_command=True)
    async def trivia(self, ctx, difficulty: typing.Optional[TriviaDiffcultyConventor] = None,
                     amount_of_questions: typing.Optional[int] = 5, *, category: TriviaCategoryConvertor = None):
        """
        Answer some trivia questions category accepts either an id or name
        possible difficulties are easy, medium hard
        """

        msg = await ctx.send("Starting the trivia game....")

        score_count = 0

        if amount_of_questions <= 0:
            return await ctx.send(":no_entry: | please type in a valid amount of questions.")

        time_out_count = 0

        score = QuizPoints(ctx.author.name)

        question_list = await self.set_questions(ctx, category, difficulty, amount_of_questions)

        reactions = ["🇦", "🇧", "🇨", "🇩", "⏩"]

        for reaction in reactions:
            await msg.add_reaction(reaction)

        for questiton_id in question_list:
            data = await self.build_question(ctx, questiton_id)

            correct_answer = data[4][0]
            text = f"**Category:** {data[0]}\n**Type:** {data[1]}\n**Difficulty:** {data[2]}\n**Question:** {data[3]}"
            embed = discord.Embed(title=f"Trivia Question! :white_check_mark: {amount_of_questions} questions left",
                                  color=self.bot.default_colors())
            embed.set_footer(text=f'Requested by {ctx.message.author.name}', icon_url=ctx.message.author.avatar_url)
            embed.timestamp = ctx.message.created_at
            random.shuffle(data[4])
            n = -1

            for answer in data[4]:
                n += 1
                embed.add_field(name=answer, value=reactions[n])

            await msg.edit(embed=embed, content=text)

            def check(reaction, user):
                return user == ctx.author and reaction.emoji in reactions and reaction.message.id == msg.id

            try:

                reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=check)

                with contextlib.suppress(discord.Forbidden):
                    await msg.remove_reaction(reaction, user)

            except asyncio.TimeoutError:
                time_out_count += 1

                if time_out_count >= 5:
                    with contextlib.suppress(discord.Forbidden):
                        return await msg.clear_reactions()

                s = "\n\n:information_source: | {}, you took too long to give a response this question will be skipped."
                text += s.format(ctx.author.name)
                await msg.edit(embed=embed, content=text)
                amount_of_questions -= 1
                await asyncio.sleep(3)
                continue

            else:
                reactions_copy = copy.copy(reactions)

                if len(data[4]) == 2:
                    del reactions_copy[2]
                    del reactions_copy[2]

                while True:

                    if reaction.emoji in reactions_copy:
                        index = reactions.index(reaction.emoji)

                        if reaction.emoji == reactions[-1]:

                            s = f"\n\n:information_source: | this question will be skipped, {ctx.author.name}."

                        elif data[4][index] == correct_answer:
                            score_count += 10
                            s = f"\n\n> {ctx.author.name} correct answer"

                        else:
                            score_count += -2
                            s = f"\n\n> Incorrect answer, the correct answer was `{correct_answer}` {ctx.author.name}"

                        text += s
                        await msg.edit(embed=embed, content=text)
                        amount_of_questions -= 1
                        time_out_count = 0
                        await asyncio.sleep(3)
                        break

                    else:
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=10, check=check)

        score.score = score_count
        await msg.edit(content=f"quiz finished :white_check_mark: {score.score}")

    @trivia.group(aliases=["cat"], invoke_without_command=True)
    async def categorises(self, ctx):
        """The main command for finding questions based on category by itself returns all the categories available"""
        results = await ctx.con.fetch("""
                                      SELECT c.category_id, c.name, COUNT(q.question_id) 
                                      from category as c INNER JOIN question as q on c.category_id = q.category_id
                                      GROUP BY c.category_id""")

        results = sorted(results, key=lambda res: res["category_id"])

        description = "\n".join(f"ID: `{result['category_id']}`: **{result['name']}** `({result['count']}) questions`"
                                for result in results)
        await ctx.send(description)

    @categorises.command()
    async def search(self, ctx, *, category: TriviaCategoryConvertor):
        """Search returns all questions based on their category, category accepts either an id or name"""
        p = Paginator(ctx)
        results = await ctx.con.fetch("SELECT content, question_id from question where category_id = $1", category)
        results = ctx.chunk(results, 10)

        for chunk in results:
            amt = await ctx.con.fetchval("SELECT COUNT(question_id) from question where category_id = $1", category)
            name = await ctx.con.fetchval("SELECT name from category where category_id = $1", category)
            chunk = "\n".join(f"> ID: `{result['question_id']}`: **{result['content']}**" for result in chunk)
            await p.add_page(f"Category Name: ```{name}```\nAmount of questions ({amt})\n{chunk}")

        await p.paginate()

    @commands.command(aliases=["ttt"])
    async def tictactoe(self, ctx, member: discord.Member):
        """
        Play a game of TicTacToe
        """

        default_board_np = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]])

        board_np = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])

        if member == ctx.author:
            return await ctx.send("You can't play against yourself silly rascal")

        if member.bot:
            return await ctx.send("Bots are too much for mere humans.")

        await ctx.send(f"awaiting a response from {member.display_name} (options yes or no)")

        message = await self.bot.wait_for('message', check=lambda message: message.author == member,
                                          timeout=60)

        while message.content.lower() != "yes" and message.content.lower() != "no":
            message = await self.bot.wait_for('message', check=lambda message: message.author == member, timeout=60)

        if message.content.lower() == "yes":
            pass

        elif message.content.lower() == "no":
            return await ctx.send(f":information_source: | seems like {member.display_name} doesn't want a game "
                                  f"shutting down the game...")

        def display_board():

            board_display = [":one:", ":two:", ":three:",
                             ":four:", ":five:", ":six:",
                             ":seven:", ":eight:", ":nine:"
                             ]

            board_flat = default_board_np.flatten()

            for i in range(0, 9):
                if board_flat[i] == 0:
                    board_display[i] = ":o:"

                elif board_flat[i] == -1:
                    board_display[i] = ":x:"

            display = [" {}  {}  {} \n{}  {}  {} \n{}  {}  {} ".format(*board_display)]
            return display

        def return_open_spaces():
            open_spaces = []
            check_ = (default_board_np == 1)
            flat_board_ = check_.flatten()

            for i, _ in enumerate(flat_board_):
                if flat_board_[i] == True:
                    open_spaces.append(i + 1)

            return open_spaces

        def check_winner(last_played_move):

            for i in range(3):
                rows = np.all(default_board_np[i, :] == last_played_move)
                cols = np.all(default_board_np[:, i] == last_played_move)

                if rows or cols:
                    return True

            diags1 = np.all(np.diag(default_board_np) == last_played_move)
            diags2 = np.all(np.diag(np.fliplr(default_board_np)) == last_played_move)

            if diags1 or diags2:
                return True

            check_ = return_open_spaces()

            if check_ == []:
                return False

        def place_letter(player_number, player_choice):
            index = np.where(board_np == player_choice)
            default_board_np[index] = player_number

        async def player_letter_choice():
            msg__ = await ctx.send(f"{ctx.author.mention} Do you want to be X or O ?")

            message__ = await self.bot.wait_for('message', check=lambda m: m.author == ctx.author and
                                                len(m.content) == 1, timeout=60)

            await msg__.delete()

            if message__.content.lower() == "o":
                await ctx.send(":information_source: | your letter is O")
                return 0, -1

            await ctx.send(":information_source: | your letter is X")
            return -1, 0

        def first_turn():
            if random.randint(0, 1) == 0:
                return "Player two"

            return "Player"

        def embed():
            display = display_board()

            embed__ = discord.Embed(title=f"Tic Tac Toe", description=display[0], color=self.bot.default_colors())

            embed__.set_footer(text=f'Requested by {ctx.message.author.name}')
            embed__.timestamp = ctx.message.created_at
            return embed__

        msg = await ctx.send(embed=embed())
        reactions = ["1\N{combining enclosing keycap}", "2\N{combining enclosing keycap}",
                     "3\N{combining enclosing keycap}", "4\N{combining enclosing keycap}",
                     "5\N{combining enclosing keycap}", "6\N{combining enclosing keycap}",
                     "7\N{combining enclosing keycap}", "8\N{combining enclosing keycap}",
                     "9\N{combining enclosing keycap}"]

        for emoji in reactions:
            await msg.add_reaction(emoji)

        def check(reaction, user):
            return user == ctx.author and reaction.emoji in reactions and reaction.message.id == msg.id

        def check_mention(reaction, user):
            return user == member and reaction.emoji in reactions and reaction.message.id == msg.id

        embed_ = discord.Embed(title="Tic Tac Toe Guide :information_source:",
                               description="this command is reaction based just react with"
                                           " the number you'd like to place your letter on.",
                               color=self.bot.default_colors())

        guide = await ctx.send(embed=embed_)
        await asyncio.sleep(5)
        await guide.delete()

        letter, letter2 = await player_letter_choice()

        first = first_turn()

        async def player_turn(_check, _letter, member):
            await msg.edit(embed=embed(), content=f"It's {member.name} turn")

            cancel_after = 0

            reaction, user = await self.bot.wait_for('reaction_add', timeout=60, check=_check)

            with contextlib.suppress(discord.HTTPException):
                await msg.remove_reaction(reaction, user)

            while True:

                if reactions.index(reaction.emoji) + 1 in return_open_spaces():
                    place_letter(_letter, reactions.index(reaction.emoji) + 1)
                    break

                else:
                    await msg.edit(embed=embed(),
                                   content=f":no_entry: | {member.display_name} invalid move react again")

                    reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=_check)
                    cancel_after += 1

                    if cancel_after == 5:
                        await msg.edit(embed=embed(),
                                       content=":no_entry: | too many invalid moves cancelling the game.")
                        return True

            place_letter(_letter, reactions.index(reaction.emoji) + 1)

            if check_winner(_letter):
                place_letter(_letter, reactions.index(reaction.emoji) + 1)
                await msg.edit(embed=embed(), content=f":information_source: | {member.display_name} won")
                return True

            if check_winner(_letter) is False:
                place_letter(_letter, reactions.index(reaction.emoji) + 1)
                await msg.edit(embed=embed(), content=":information_source: | The game was a draw")
                return True

            await msg.edit(embed=embed())

        while True:

            if first == "Player":

                if await player_turn(check, letter, ctx.author):
                    break
                first = ""

            else:

                if await player_turn(check_mention, letter2, member):
                    break

                first = "Player"

    @commands.command(aliases=["bj", "blackjack"])
    @checking_for_multiple_channel_instances()
    async def black_jack(self, ctx):
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
        # black jack game is written as if it's multilayer as it was converted from multilayer to a single player game
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


def setup(bot):
    n = Games(bot)
    bot.add_cog(n)

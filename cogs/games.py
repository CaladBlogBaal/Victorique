import contextlib
import asyncio
import random
import html

import numpy as np

import discord
from discord.ext import commands

from config.utils.checks import checking_for_multiple_channel_instances


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
        with contextlib.suppress(ValueError):
            if ctx.guild:
                key = str(ctx.channel.id) + ctx.command.name
                list_ = ctx.bot.channels_running_commands.get(key)
                list_.remove(ctx.author.id)
                ctx.bot.channels_running_commands[key] = list_
                if not list_:
                    ctx.bot.channels_running_commands.pop(key, None)

    @staticmethod
    def set_questions(question_json):

        category = question_json.get("category")
        _type = question_json.get("type")
        difficulty = question_json.get("difficulty")
        question = question_json.get("question")
        correct_answer = question_json.get("correct_answer")
        incorrect_answers = question_json.get("incorrect_answers")
        incorrect_answers.insert(0, correct_answer)
        answers = list(html.unescape(q) for q in incorrect_answers)

        question_list = [category, _type, difficulty,
                         html.unescape(question), answers]

        return question_list

    @commands.command(aliases=["8ball", "8-ball", "magic_eight_ball"])
    async def eight_ball(self, ctx, *, message):
        """
        answers from cthulu
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
    async def roll(self, ctx, dice: str):
        """
        Roll a die in a NdN format
        """
        _, second_word, word = dice.partition("d")

        if not second_word.startswith("d"):
            return await ctx.send(f":no_entry: | dice must be in a NdN format.")

        rolls, limit = map(int, dice.split("d"))

        results = ", ".join(str(random.randint(1, limit)) for _ in range(rolls))

        results = f"```py\nRolled: ({results})\n```"

        await ctx.send(results)

    @commands.command()
    @checking_for_multiple_channel_instances()
    async def trivia(self, ctx, amount_of_questions=5):
        """
        Answer some trivia questions
        """

        self.multiple_user_instance_set(ctx)

        score_count = 0

        if amount_of_questions <= 0:
            return await ctx.send(":no_entry: | please type in a valid amount of questions.")

        if amount_of_questions > 100:
            await ctx.send(":information_source: | the max amount of questions allowed is 100, will default to 100.")
            amount_of_questions = 100
            await asyncio.sleep(3)

        diot_keys = {'1': 9, '2': 10, '3': 11, '4': 12, '5': 13,
                     '6': 14, '7': 15, '8': 16, '9': 17, '10': 18,
                     '11': 19, '12': 20, '13': 21, '14': 22, '15': 23,
                     '16': 24, '17': 25, '18': 26, '19': 27, '20': 28,
                     '21': 29, '22': 30, '23': 31, '24': 32}

        time_out_count = 0

        embed = discord.Embed(title=f"Trivia game",
                              description="Select an option by typing it's number"
                                          "\n1) General Knowledge "
                                          "\n2) Entertainment: Books"
                                          "\n3) Entertainment: Film "
                                          "\n4) Entertainment: Music "
                                          "\n5) Entertainment: Musicals  "
                                          "\n6) Entertainment: Television "
                                          "\n7) Entertainment: Video Games "
                                          "\n8) Entertainment: Board Games "
                                          "\n9) Science & Nature "
                                          "\n10) Science: Computers "
                                          "\n11) Science: Mathematics "
                                          "\n12) Mythology "
                                          "\n13) Sports "
                                          "\n14) Geography "
                                          "\n15) History "
                                          "\n16) Politics "
                                          "\n17) Art"
                                          "\n18) Celebrities "
                                          "\n19) Animals "
                                          "\n20) Vehicles "
                                          "\n21) Entertainment: Comics "
                                          "\n22) Science: Gadgets "
                                          "\n23) Entertainment: Japanese Anime & Manga "
                                          "\n24) Entertainment: Cartoon & Animations",
                              color=self.bot.default_colors())

        embed.set_footer(text=f'Requested by {ctx.message.author.name}', icon_url=ctx.message.author.avatar_url)
        embed.timestamp = ctx.message.created_at
        msg = await ctx.send(embed=embed)

        message = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author,
                                          timeout=60)

        category_choice = diot_keys.get(message.content, None)

        if category_choice is not None:
            pass

        else:
            category_choice = ""
            await ctx.send("Number not in category options will default to random categories")

        embed = discord.Embed(title="Trivia Game Difficulty",
                              description="Choose a difficulty by saying it's name"
                              "\nEasy"
                              "\nMedium"
                              "\nHard",
                              color=self.bot.default_colors()
                              )
        embed.set_footer(text=f'Requested by {ctx.message.author.name}', icon_url=ctx.message.author.avatar_url)
        embed.timestamp = ctx.message.created_at
        await asyncio.sleep(1)
        await msg.edit(embed=embed)
        difficulty_choice = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author)
        difficulty_choice = difficulty_choice.content.lower()
        difficulties_list = ["easy", "medium", "hard"]

        if difficulty_choice.lower() in difficulties_list:
            pass

        else:
            await ctx.send("Invalid response will default to random difficulties")
            difficulty_choice = ""

        score = QuizPoints(ctx.message.author.name)
        questions_left = amount_of_questions

        question_list = []

        params = {"category": category_choice,
                  "difficulty": difficulty_choice,
                  "amount": amount_of_questions,
                  "type": "multiple"}

        results = await self.bot.fetch("https://opentdb.com/api.php", params=params)

        if results["response_code"] == 0:
            for js in results["results"]:
                question_list.append(self.set_questions(js))

        else:
            return await ctx.send(":information_source: | seems like an error occurred the api this trivia game is "
                                  "using may be experiencing some problems.")

        reactions = ["🇦", "🇧", "🇨", "🇩", "⏩"]

        for reaction in reactions:
            await msg.add_reaction(reaction)

        for data in question_list:

            correct_answer = data[4][0]
            text = f"**Category:** {data[0]}\n**Type:** {data[1]}\n**Difficulty:** {data[2]}\n**Question:** {data[3]}"
            embed = discord.Embed(title=f'Trivia Question! :white_check_mark: {questions_left} questions left',
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
                questions_left -= 1
                await asyncio.sleep(3)
                continue

            else:

                while True:

                    if reaction.emoji in reactions:
                        index = reactions.index(reaction.emoji)

                        if reaction.emoji == reactions[-1]:

                            s = f"\n\n:information_source: | this question will be skipped, {ctx.author.name}."

                        elif data[4][index] == correct_answer:
                            score_count += 10
                            s = f"\n\n> {ctx.author.name} correct answer"

                        else:
                            score_count += -2
                            s = f"\n\n> incorrect answer, the correct answer was `{correct_answer}` {ctx.author.name}"

                        text += s
                        await msg.edit(embed=embed, content=text)
                        questions_left -= 1
                        await asyncio.sleep(3)
                        time_out_count = 0
                        break

        await asyncio.sleep(2)
        score.score = score_count

        await ctx.send(f"quiz finished :white_check_mark: {score.score}")

    @commands.command(aliases=["ttt"])
    async def tictactoe(self, ctx, mention: discord.Member):
        """
        play a game of TicTacToe
        """

        default_board_np = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]])

        board_np = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])

        if mention == ctx.author:
            return await ctx.send("You can't play against yourself silly rascal")

        if mention.bot:
            return await ctx.send("Bots are too much for mere humans.")

        await ctx.send(f"awaiting a response from {mention.display_name} (options yes or no)")

        try:
            message = await self.bot.wait_for('message', check=lambda message: message.author == mention,
                                              timeout=60)

            while message.content.lower() != "yes" and message.content.lower() != "no":
                message = await self.bot.wait_for('message', check=lambda message: message.author == mention,
                                                  timeout=60)

            if message.content.lower() == "yes":
                pass

            elif message.content.lower() == "no":
                return await ctx.send(f":information_source: | seems like {mention.display_name} doesn't want a game "
                                      f"shutting down the game...")

        except asyncio.TimeoutError:
            return await ctx.send(f":no_entry: | "
                                  f"{mention.display_name} took to long to give a response shutting down the game..")

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

            check_ = return_open_spaces()

            if check_ == []:

                return False

            for i in range(3):
                rows = np.all(default_board_np[i, :] == last_played_move)
                cols = np.all(default_board_np[:, i] == last_played_move)

                if rows or cols:
                    return True

            diags1 = np.all(np.diag(default_board_np) == last_played_move)
            diags2 = np.all(np.diag(np.fliplr(default_board_np)) == last_played_move)

            if diags1 or diags2:
                return True

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

            embed__ = discord.Embed(title=f"Tic Tac Toe",
                                    description=display[0],
                                    color=self.bot.default_colors())

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
            return user == mention and reaction.emoji in reactions and reaction.message.id == msg.id

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

            turn_msg = await ctx.send(f"It's {member.name} turn")

            with contextlib.suppress(discord.HTTPException):
                cancel_after = 0
                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=_check)
                    await msg.remove_reaction(reaction, user)

                    while True:

                        if reactions.index(reaction.emoji) + 1 in return_open_spaces():
                            place_letter(_letter, reactions.index(reaction.emoji) + 1)
                            break

                        else:
                            await ctx.send(":no_entry: | " + member.name + " invalid move react again", delete_after=3)
                            reaction, user = await self.bot.wait_for('reaction_add', timeout=30, check=_check)
                            cancel_after += 1
                            if cancel_after == 5:
                                return await ctx.send(":no_entry: | too many invalid moves cancelling the game.",
                                                      delete_after=10)

                    place_letter(_letter, reactions.index(reaction.emoji) + 1)

                    if check_winner(_letter):
                        place_letter(_letter, reactions.index(reaction.emoji) + 1)
                        await msg.edit(embed=embed())
                        return await ctx.send(f":information_source: | {member.mention} won")

                    if check_winner(_letter) is False:
                        place_letter(_letter, reactions.index(reaction.emoji) + 1)
                        await msg.edit(embed=embed())
                        return await ctx.send(":information_source: | The game was a draw")

                    await msg.edit(embed=embed())
                    await asyncio.sleep(2)
                    await turn_msg.delete()

                except asyncio.TimeoutError:
                    return await ctx.send(f"took to long to give a response.... {member.name} shutting down the game.")

        while True:

            if first == "Player":

                if await player_turn(check, letter, ctx.author):
                    break
                first = ""

            else:

                if await player_turn(check_mention, letter2, mention):
                    break

                first = "Player"

    @commands.command()
    @checking_for_multiple_channel_instances()
    async def black_jack(self, ctx):
        """
        start a game of black jack
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

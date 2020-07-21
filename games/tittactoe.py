import contextlib
import random

import discord
import numpy as np


class TicTacToePlayer:
    def __init__(self, member, letter, board, board_indexes):
        self.board = board
        self.board_reactions = board_indexes
        self.member_object = member
        self.name = str(member)
        self.letter = letter
        self.winner = None

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def letter(self):
        return self._letter

    @letter.setter
    def letter(self, value):
        self._letter = value

    def won(self):
        self.winner = True

    def place_letter(self, option):
        index = np.where(self.board_reactions == option)
        self.board[index] = self.letter
        self.check_winning_move()

    def check_winning_move(self):

        for i in range(3):
            rows = np.all(self.board[i, :] == self.letter)
            cols = np.all(self.board[:, i] == self.letter)

            if rows or cols:
                self.won()

        diags1 = np.all(np.diag(self.board) == self.letter)
        diags2 = np.all(np.diag(np.fliplr(self.board)) == self.letter)

        if diags1 or diags2:
            self.won()


class TicTacToe:
    reactions = ["1\N{combining enclosing keycap}", "2\N{combining enclosing keycap}",
                 "3\N{combining enclosing keycap}", "4\N{combining enclosing keycap}",
                 "5\N{combining enclosing keycap}", "6\N{combining enclosing keycap}",
                 "7\N{combining enclosing keycap}", "8\N{combining enclosing keycap}",
                 "9\N{combining enclosing keycap}"]

    def __init__(self, ctx):
        self.board = np.array([[1, 1, 1], [1, 1, 1], [1, 1, 1]])
        self.board_reaction_index = np.array([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        self.ctx = ctx
        self.player_one = None
        self.player_two = None
        self.running = True
        self.game_embed = None
        self.current_players_turn = None

    @property
    def current_players_turn(self):
        return self._current_players_turn

    @current_players_turn.setter
    def current_players_turn(self, value):
        self._current_players_turn = value

    def display_board(self):

        board_display = [":one:", ":two:", ":three:",
                         ":four:", ":five:", ":six:",
                         ":seven:", ":eight:", ":nine:"
                         ]

        board_flat = self.board.flatten()

        for i in range(0, 9):
            if board_flat[i] == 0:
                board_display[i] = ":o:"

            elif board_flat[i] == -1:
                board_display[i] = ":x:"

        display = " {}  {}  {} \n{}  {}  {} \n{}  {}  {} ".format(*board_display)
        return display

    def return_open_spaces(self):
        open_spaces = []
        check = (self.board == 1)
        flat_board = check.flatten()

        for i, _ in enumerate(flat_board):
            if flat_board[i] == True:
                open_spaces.append(i + 1)

        return open_spaces

    def first_turn(self):
        if random.randint(0, 1) == 0:
            return self.player_two, self.player_one

        return self.player_one, self.player_two

    def boards_full(self):
        return self.return_open_spaces() == []

    def embed(self):

        display = self.display_board()
        embed = discord.Embed(title=f"Tic Tac Toe", description=display, color=self.ctx.bot.default_colors())
        embed.timestamp = self.ctx.message.created_at
        return embed

    async def set_players(self, author, member):
        letters = await self.player_letter_choice()
        self.player_one = TicTacToePlayer(author, letters[0], self.board, self.board_reaction_index)
        self.player_two = TicTacToePlayer(member, letters[1], self.board, self.board_reaction_index)

    async def player_letter_choice(self):
        msg = await self.ctx.send(f"{self.ctx.author.mention} Do you want to be X or O ?")

        choice = await self.ctx.bot.wait_for('message', check=lambda m: m.author == self.ctx.author and len(m.content)
                                             == 1, timeout=60)

        await msg.delete()

        if choice.content.lower() == "o":
            await self.ctx.send(":information_source: | your letter is O")
            return 0, -1

        await self.ctx.send(":information_source: | your letter is X")
        return -1, 0

    async def play_again(self):
        check_mark = "✅"

        await self.game_embed.add_reaction(check_mark)
        await self.game_embed.edit(content=f"{self.ctx.author.mention} Do you want to play again?")

        def check(reaction, user):
            return user == self.ctx.author and reaction.emoji == check_mark and reaction.message.id == self.game_embed.id

        reaction, user = await self.ctx.bot.wait_for('reaction_add', timeout=30, check=check)

        while reaction.emoji != check_mark:
            reaction, user = await self.ctx.bot.wait_for('reaction_add', timeout=30, check=check)

        if reaction.emoji == check_mark:
            new_game = TicTacToe(self.ctx)
            return await new_game.run(self.player_two.member_object)

        with contextlib.suppress(discord.Forbidden):
            await self.game_embed.clear_reactions()

    async def player_turn(self, check, player: TicTacToePlayer):

        if self.boards_full():
            await self.game_embed.edit(embed=self.embed(), content=":information_source: | The game was a draw")
            return await self.end_game()

        self.current_players_turn = player.member_object
        await self.game_embed.edit(embed=self.embed(), content=f"It's {player.name} turn")

        cancel_after = 0

        reaction, user = await self.ctx.bot.wait_for('reaction_add', timeout=60, check=check)

        with contextlib.suppress(discord.HTTPException):
            await self.game_embed.remove_reaction(reaction, user)

        while True:

            if self.reactions.index(reaction.emoji) + 1 in self.return_open_spaces():
                player.place_letter(self.reactions.index(reaction.emoji) + 1)
                break

            else:
                await self.game_embed.edit(embed=self.embed(),
                                           content=f":no_entry: | {player.name} invalid move react again")

                reaction, user = await self.ctx.bot.wait_for('reaction_add', timeout=30, check=check)
                cancel_after += 1

                if cancel_after == 5:
                    await self.game_embed.edit(embed=self.embed(),
                                               content=":no_entry: | too many invalid moves cancelling the game.")
                    await self.end_game()
                    # setting it to true so it skips the other player's turn
                    player.winner = True

        if player.winner:
            await self.game_embed.edit(embed=self.embed(), content=f":information_source: | {player.name} won")
            await self.end_game()

        await self.game_embed.edit(embed=self.embed())
        return player.winner

    async def end_game(self):
        with contextlib.suppress(discord.Forbidden):
            self.running = False
            await self.game_embed.clear_reactions()

    async def run(self, member):
        self.game_embed = await self.ctx.send(embed=self.embed())
        for emoji in self.reactions:
            await self.game_embed.add_reaction(emoji)

        def check(reaction, user):

            return user == self.current_players_turn and reaction.emoji in self.reactions \
                   and reaction.message.id == self.game_embed.id

        await self.set_players(self.ctx.author, member)
        first = self.first_turn()

        while self.running:

            first_player, second_player = first
            await self.player_turn(check, first_player)

            if not first_player.winner:
                await self.player_turn(check, second_player)

        await self.play_again()

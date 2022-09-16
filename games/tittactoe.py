import random

import discord
import numpy as np

from games.views import RequestToPlayView


class TicTacToePlayer:
    def __init__(self, member, letter):
        self.member = member
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


class TicTacToePlayersView(discord.ui.View):
    def __init__(self, ctx, member, message=None, timeout=15):
        super(TicTacToePlayersView, self).__init__(timeout=timeout)
        self.ctx = ctx
        self.member = member
        self.message = message
        self.players = None

    def set_players(self, player_one_letter, player_two_letter):
        player_one = TicTacToePlayer(self.ctx.author, player_one_letter)
        player_two = TicTacToePlayer(self.member, player_two_letter)
        self.clear_items()
        self.players = {self.ctx.author.id: player_one,
                        self.member.id: player_two}
        self.stop()

    @discord.ui.button(style=discord.ButtonStyle.green, label="O")
    async def set_o(self, button, interaction):
        self.set_players("O", "X")

    @discord.ui.button(style=discord.ButtonStyle.red, label="X")
    async def set_x(self, button, interaction):
        self.set_players("X", "O")

    async def start(self):
        message = f"{self.ctx.author.mention} do you want to be X or O?"

        if not self.message:
            self.message = await self.ctx.send(message, view=self)

        await self.message.edit(message, view=self)

    async def interaction_check(self, interaction):
        return interaction.user.id == self.ctx.author.id

    async def on_timeout(self) -> None:
        self.clear_items()
        await self.message.edit(":information_source: | haven't received an input for awhile stopping the game.",
                                delete_after=10)
        self.stop()


class TicTacToeButton(discord.ui.Button["TicTacToe"]):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None

        if interaction.user.id != self.view.current_player_id:
            return

        if self.label != "--":
            return await interaction.response.send_message("Someone already played there!", ephemeral=True)

        player = self.view.players[interaction.user.id]
        indexes = []

        for c in self.custom_id:
            if c.isdigit():
                indexes.append(int(c))

        self.label = player.letter
        self.view.board[indexes[0], indexes[1]] = player.letter

        if self.label == "X":
            self.style = discord.ButtonStyle.red
        else:
            self.style = discord.ButtonStyle.green

        self.view.check_winning_move(player)

        if player.winner:
            await self.view.message.edit(f":information_source: | {player.name} won", view=self.view)
            return self.view.stop()

        if self.view.boards_full():
            await self.view.message.edit("Game was a draw.", view=self.view)
            return self.view.stop()

        # honestly have no id of a better way to do this for now, this feels janky
        for player_id in self.view.players:
            if interaction.user.id != player_id:
                self.view.current_player_id = player_id
                await self.view.message.edit(f"It's {self.view.players[player_id].name} turn!", view=self.view)


class TicTacToe(discord.ui.View):

    def __init__(self, timeout=40):
        super().__init__(timeout=timeout)
        self.board = None
        self.message = None
        self.players = None
        self.current_player_id = None
        self.setup()

    async def play_again(self):
        pass

    async def run(self, ctx, member):

        view = RequestToPlayView(ctx, member, game="Tic-Tac-Toe")
        await view.start()
        await view.wait()

        if view.value:
            view = TicTacToePlayersView(ctx, member, message=view.message)
            await view.start()
            await view.wait()
            if view.players:
                self.players = view.players
                self.message = view.message
                # who goes first
                _, player = random.choice(list(self.players.items()))
                self.current_player_id = player.member.id
                await self.message.edit(f"It's {player.name} turn!", view=self)

    @property
    def current_player_id(self):
        return self._current_players_turn

    @current_player_id.setter
    def current_player_id(self, value):
        self._current_players_turn = value

    def setup(self):
        alist = []
        buttons = [[TicTacToeButton(style=discord.ButtonStyle.gray,
                                    label="--", row=row + 1, custom_id=f"ttt{row}{col}")
                    for col in range(3)] for row in range(3)]

        for row in buttons:
            sub_list = []
            for button in row:
                sub_list.append("")
                self.add_item(button)
            alist.append(sub_list)

        self.board = np.array(alist, dtype=np.str_)

    def check_winning_move(self, player):

        for i in range(3):
            rows = np.all(self.board[i, :] == player.letter)
            cols = np.all(self.board[:, i] == player.letter)

            if rows or cols:
                player.won()

        diags1 = np.all(np.diag(self.board) == player.letter)
        diags2 = np.all(np.diag(np.fliplr(self.board)) == player.letter)

        if diags1 or diags2:
            player.won()

    def boards_full(self):
        board = self.board.flatten()
        return np.all(board != "")

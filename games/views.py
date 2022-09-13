import discord


class RequestToPlayView(discord.ui.View):
    def __init__(self, ctx, member, game):
        super().__init__(timeout=15)
        self.member = member
        self.ctx = ctx
        self.message = None
        self.value = None
        self.game = game

    async def interaction_check(self, interaction):
        return interaction.user.id == self.member.id

    @discord.ui.button(label="Confirm", emoji="✅")
    async def confirm(self, _, interaction):
        self.clear_items()
        self.message.content = None
        self.value = True
        self.stop()

    @discord.ui.button(label="Deny", emoji="❌")
    async def deny(self, _, interaction):
        await interaction.response.edit_message(content=f"{self.ctx.author.input}, {self.member} cancelled the game.",
                                                view=None)
        self.value = False
        self.stop()

    async def start(self):
        self.message = await self.ctx.send(f"{self.member.input}, {self.ctx.author} is challenging you to {self.game}",
                                           view=self)

    async def on_timeout(self) -> None:
        self.clear_items()
        await self.message.edit(content=f"{self.ctx.author.mention}, did not respond in time.")
        self.stop()

import traceback

import random

import discord


class BaseModal(discord.ui.Modal):
    def __init__(self, title):
        super().__init__(title=title)  # Modal title

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """This is the function that gets called when the submit button is pressed"""
        await interaction.response.defer()

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.response.send_message("Oops! Something went wrong.", ephemeral=True)
        # Make sure we know what the error actually is
        traceback.print_tb(error.__traceback__)


class FishSellAllModal(BaseModal):
    def __init__(self, title):
        super().__init__(title=title)  # Modal title

        self.rarity_id = discord.ui.TextInput(
            label=f"Enter in the rarity id/name",
            required=True,
            custom_id="rarity_input",
            min_length=1,
        )

        self.add_item(self.rarity_id)

        self.fish_ids = discord.ui.TextInput(
            label=f"Enter in the fish ids/name",
            custom_id="fish_ids_input",
            required=False,
            min_length=1,
        )
        self.add_item(self.fish_ids)


class FishModal(BaseModal):
    def __init__(self, title, **kwargs):
        super().__init__(title=title)  # Modal title

        label = kwargs.get("label", "default")

        labels = {"bait": "Enter in the bait id/name.",
                  "fish": "Enter in the fish id/name.",
                  "rarity": "Enter in the rarity id/name.",
                  "default": "Enter in the id."}

        self.amount = discord.ui.TextInput(
            label=f"Enter in an amount",
            custom_id="amount_input",
            required=True,
            min_length=1,
        )
        self.add_item(self.amount)

        self.id = discord.ui.TextInput(
            label=labels[label],
            custom_id="id_input",
            required=True,
            min_length=1,
        )
        self.add_item(self.id)

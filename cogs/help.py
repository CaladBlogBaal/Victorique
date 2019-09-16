import random

from discord.ext import commands
import discord

import loadconfig


class MyHelpCommand(commands.MinimalHelpCommand):
    def __init__(self, **options):
        super().__init__(**options, command_attrs=dict(help=""))
        self.colours = [discord.Color.dark_magenta(), discord.Colour(15156347), discord.Color.dark_orange(),
                        discord.Color.red(), discord.Color.dark_red(), discord.Color(15121501)]
        self.col = int(random.random() * len(self.colours))
        # change this if you want
        self.url = "https://cdn.myanimelist.net/images/characters/5/108860.jpg"

    def get_command_signature(self, command):
        return '**{0.clean_prefix}{1.qualified_name} {1.signature}**'.format(self, command)

    def get_opening_note(self):
        return None

    def get_ending_note(self):
        command_name = self.invoked_with
        return """Use **{0}{1} [command name]** for more info on a command.
        To get a list of commands for a category use **{0}{1} [category name]** 
        *category names are case sensitive*. 
        
        :information_source: < > refers to a required argument [ ] is optional
        **do not actually type these**
        """.format(self.clean_prefix, command_name)

    def add_subcommand_formatting(self, command):
        fmt = "**{0} {1}** \N{EN DASH} `{2}`" if command.short_doc else '**{0} {1}** \N{EN DASH} `no description`'
        self.paginator.add_line(fmt.format(command.full_parent_name, command.name, command.short_doc, ""))

    def add_bot_commands_formatting(self, commands, heading):

        if commands and commands[0].cog_name:
            space = "\u2002"
            joined = f"{space.join(c.name for c in commands)}"

            self.paginator.add_line(f"**__{heading}__**")
            self.paginator.add_line(joined)

    def add_command_formatting(self, command):

        if command.description:
            self.paginator.add_line(command.description, empty=True)

        signature = self.get_command_signature(command)
        if command.aliases:
            self.paginator.add_line(signature)
            self.add_aliases_formatting(command.aliases)
        else:
            self.paginator.add_line(signature, empty=True)

        if command.help:
            try:
                self.paginator.add_line(f"```{command.help}\n```", empty=True)
            except RuntimeError:
                for line in command.help.splitlines():
                    self.paginator.add_line(line)
                self.paginator.add_line()

    async def send_pages(self):
        destination = self.get_destination()

        for page in self.paginator.pages:

            embed = discord.Embed(description=page, color=self.colours[self.col])
            embed.set_author(name=loadconfig.__username__, url="",
                             icon_url=self.url)
            await destination.send(embed=embed)


class MyCog(commands.Cog, name="Help"):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = MyHelpCommand()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command


def setup(bot):
    bot.add_cog(MyCog(bot))

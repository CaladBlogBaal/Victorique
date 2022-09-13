from discord.ext import commands
import discord


class MyHelpCommand(commands.MinimalHelpCommand):
    def __init__(self, **options):
        super().__init__(**options, command_attrs=dict(help=""))

    def get_command_signature(self, command):
        return '**{0.context.clean_prefix}{1.qualified_name} {1.signature}**'.format(self, command)

    def get_opening_note(self):
        return None

    def get_ending_note(self):
        command_name = self.invoked_with
        first_line = "Use **{0}{1} [command name/category name]** for more info on a command.\n"
        second_line = "*category names are case sensitive*.\n"
        third_line = ":information_source: < > refers to a required argument, [ ] is optional\n"
        last_line = "**do not actually type these**"
        return f"{first_line}{second_line}{third_line}{last_line}".format(self.context.clean_prefix, command_name)

    def add_subcommand_formatting(self, command):
        fmt = "→ **{0} {1}** \N{EN DASH} `{2}`" if command.short_doc else '→ **{0} {1}** \N{EN DASH} `no description`'
        self.paginator.add_line(fmt.format(command.full_parent_name, command.name, command.short_doc, ""))

    def add_bot_commands_formatting(self, commands, heading):

        if commands and commands[0].cog_name:
            self.paginator.add_line(f"➤ **{heading}**")

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
        avatar_url = self.context.me.avatar.replace(format="png")
        name = self.context.me.name
        for page in self.paginator.pages:

            embed = discord.Embed(description=page, color=self.context.bot.default_colors())
            embed.set_author(name=name, icon_url=str(avatar_url))
            await destination.send(embed=embed)


class MyCog(commands.Cog, name="Help"):
    def __init__(self, bot):
        self.bot = bot
        self._original_help_command = bot.help_command
        bot.help_command = MyHelpCommand()
        bot.help_command.cog = self

    def cog_unload(self):
        self.bot.help_command = self._original_help_command


async def setup(bot):
    await bot.add_cog(MyCog(bot))

import re

from contextlib import suppress

from discord.ext import commands


class TagNameConverter(commands.Converter):

    def add_command_alias(self, qualified_names, command: commands.Group):
        for cmd in command.commands:
            for alias in command.aliases:
                test = cmd.parent.name
                alias_qualified_name = cmd.qualified_name.replace(test, alias)
                qualified_names.append(alias_qualified_name)
            if isinstance(cmd, commands.Group):
                self.add_command_alias(qualified_names, cmd)

    async def convert(self, ctx, argument):

        new_name = await commands.clean_content().convert(ctx, argument.lower())

        if not new_name:
            raise commands.BadArgument("missing tag name.")

        if len(new_name) > 50:
            raise commands.BadArgument("tag names are a maximum of 50 characters.")

        qualified_names = []

        cmds = list(ctx.bot.walk_commands())
        group_cmds = [cmd for cmd in cmds if isinstance(cmd, commands.Group)]

        qualified_names.extend([cmd.qualified_name for cmd in cmds])
        # adding the aliases of a command group
        # otherwise tag create would fail but tags create would pass.
        for cmd in group_cmds:
            self.add_command_alias(qualified_names, cmd)

        if any(new_name == name for name in qualified_names):
            raise commands.BadArgument("tag name starts with a bot command or sub command.")

        return new_name


class FishRarityConventer(commands.Converter):
    async def convert(self, ctx, argument):
        rarity = argument.lower().strip()

        rarities = {"common": "1", "elite": "2", "super": "3", "legendary": "-1"}
        rarity = rarities.get(rarity, rarity)

        if rarity not in ("1", "2", "3", "-1"):
            raise commands.BadArgument(":no_entry: | an invalid rarity was passed.")

        return int(rarity)


class FishNameConventer(commands.Converter):
    async def convert(self, ctx, argument):
        argument = argument.lower().strip()
        fish = ""
        async with ctx.acquire():

            if not argument.isdigit():
                fish = await ctx.db.fetchval("SELECT fish_id from fish where (LOWER(fish_name) like '%' || $1 || '%')",
                                             argument)

            if fish:
                return fish

            if argument.isdigit():

                check = await ctx.db.fetchval("SELECT * from fish where fish_id = $1", int(argument))

                if check:
                    return int(argument)

            raise commands.BadArgument("an invalid fish was passed.")


class SeasonConverter(commands.Converter):
    async def convert(self, ctx, argument):
        argument = argument.lower().capitalize()

        seasons = ("Winter", "Summer", "Spring", "Autumn", "Fall")

        if argument in seasons:
            return argument

        months_seasons = {"March": "spring", "April": "spring", "May": "spring",
                          "June": "summer", "July": "summer", "August": "summer",
                          "September": "fall", "October": "fall", "November": "fall",
                          "December": "winter", "January": "winter", "February": "winter"}

        months = {'1': 'January', '2': 'February', '3': 'March',
                  '4': 'April', '5': 'May', '6': 'June',
                  '7': 'July', '8': 'August', '9': 'September',
                  '10': 'October', '11': 'November', '12': 'December'}

        months_short = {'Jan': 'January', 'Feb': 'February', 'Mar': 'March',
                        'Apr': 'April', 'May': 'May', 'Jun': 'June',
                        'Jul': 'July', 'Aug': 'August', 'Sep': 'September',
                        'Oct': 'October', 'Nov': 'November', 'Dec': 'December'}

        if argument.isdigit():
            if argument.startswith("0"):
                argument = argument[1::]
            season = months.get(argument, None)

        else:
            season = months_short.get(argument, None)

        if season in months_seasons:
            season = months_seasons[season]

        if season is None:
            raise commands.BadArgument("an invalid season was passed.")

        return season


class TriviaCategoryConverter(commands.Converter):
    async def convert(self, ctx, argument):
        async with ctx.acquire():

            argument = argument.lower()
            if argument.isdigit():
                argument = int(argument)
                result = await ctx.db.fetchval("SELECT category_id from category where category_id = $1", argument)

            else:

                result = await ctx.db.fetchval("SELECT category_id from category where LOWER(name) like $1", argument)

            if not result:
                raise commands.BadArgument("Invalid Category was passed.")

            return result


class TriviaDiffcultyConventer(commands.Converter):
    async def convert(self, ctx, argument):
        async with ctx.acquire():
            diffculties = [result["difficulty"] for result in
                           await ctx.db.fetch("SELECT DISTINCT difficulty from question")]
            if argument in diffculties:
                return argument

            raise commands.BadArgument("Invalid difficulty was entered")


class DieConventer(commands.Converter):
    async def convert(self, ctx, argument):
        rolls, d, expression = argument.partition("d")

        if any(x in expression for x in ("//", "**", "^")):
            raise commands.BadArgument("An invalid operator was passed.")

        if not d.startswith("d") or not rolls.isdigit():
            raise commands.BadArgument("dice must be in a NdN+m format.")

        if expression.count("(") != expression.count(")") or int(rolls) <= 0 or re.search(r"[a-zA-Z]", expression):
            raise commands.BadArgument("Invalid expression.")

        rolls = int(rolls)

        expression = expression.replace(" ", "")
        expression = re.findall(r"[/ *\-+()]|\d+\.?\d*", expression)

        limit = int(expression[0])

        if limit == 0:
            limit = 1

        del expression[0]

        with suppress(IndexError):
            while expression[-1] in ("+", "*", "/"):
                del expression[-1]

        return rolls, limit, expression

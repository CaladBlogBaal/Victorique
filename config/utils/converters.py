import re
from contextlib import suppress

from discord.ext import commands

from config.utils.context import Context


class QueryIdNameConverter:
    def __init__(self):
        pass

    async def check(self, ctx: Context, argument: str, id_query: str, name_query: str,
                    error_msg="An invalid id/name was passed.") -> int:
        argument = argument.lower().strip()

        async with ctx.acquire():

            if not argument.isdigit():
                check = await ctx.db.fetchval(name_query, argument)
            else:
                check = await ctx.db.fetchval(id_query, int(argument))

            if check:
                return check

            raise commands.BadArgument(error_msg)


class TagNameConverter(commands.Converter):

    def add_command_alias(self, qualified_names, command: commands.Group):
        for cmd in command.commands:
            for alias in command.aliases:
                test = cmd.parent.name
                alias_qualified_name = cmd.qualified_name.replace(test, alias)
                qualified_names.append(alias_qualified_name)
            if isinstance(cmd, commands.Group):
                self.add_command_alias(qualified_names, cmd)

    async def convert(self, ctx: Context, argument) -> str:

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


class BaitConverter(commands.Converter, QueryIdNameConverter):
    async def convert(self, ctx: Context, argument) -> int:
        name_statement = "SELECT bait_id from fish_bait WHERE (LOWER(bait_name) LIKE '%' || $1 || '%')"
        id_statement = "SELECT * FROM fish_bait WHERE bait_id = $1"
        return await self.check(ctx, argument, id_statement, name_statement, "an invalid rarity was passed.")


class FishRarityConventer(commands.Converter, QueryIdNameConverter):
    async def convert(self, ctx: Context, argument) -> int:
        name_statement = "SELECT rarity_id from fish_rarity WHERE (LOWER(rarity_name) LIKE '%' || $1 || '%')"
        id_statement = "SELECT * FROM fish_rarity WHERE rarity_id = $1"
        return await self.check(ctx, argument, id_statement, name_statement, "an invalid rarity was passed.")


class FishNameConventer(commands.Converter, QueryIdNameConverter):
    async def convert(self, ctx: Context, argument) -> int:

        name_statement = "SELECT fish_id FROM fish WHERE (LOWER(fish_name) LIKE '%' || $1 || '%')"
        id_statement = "SELECT * FROM fish WHERE fish_id = $1"
        return await self.check(ctx, argument, id_statement, name_statement, "an invalid fish was passed.")


class SeasonConverter(commands.Converter):
    async def convert(self, ctx: Context, argument) -> str:
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
    async def convert(self, ctx: Context, argument) -> int:
        async with ctx.acquire():

            argument = argument.lower()
            if argument.isdigit():
                argument = int(argument)
                result = await ctx.db.fetchval("SELECT category_id from category where category_id = $1", argument)

            else:

                result = await ctx.db.fetchval("SELECT category_id from category where LOWER(name) LIKE $1", argument)

            if not result:
                raise commands.BadArgument("Invalid Category was passed.")

            return result


class TriviaDiffcultyConventer(commands.Converter):
    async def convert(self, ctx: Context, argument) -> str:
        async with ctx.acquire():
            difficulties = [result["difficulty"] for result in
                           await ctx.db.fetch("SELECT DISTINCT difficulty from question")]
            if argument in difficulties:
                return argument

            raise commands.BadArgument("Invalid difficulty was entered")


class DieConventer(commands.Converter):
    async def convert(self, ctx: Context, argument) -> tuple[int, int, list]:
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

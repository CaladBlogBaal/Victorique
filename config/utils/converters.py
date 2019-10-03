from discord.ext import commands


class TagNameConvertor(commands.Converter):
    async def convert(self, ctx, argument):

        converted = await commands.clean_content().convert(ctx, argument.lower())

        new_name = converted.replace("\"", "").replace("'", "").rstrip()

        if not new_name:
            raise commands.BadArgument("missing tag name.")

        if len(new_name) > 50:
            raise commands.BadArgument("tag names are a maximum of 50 characters.")

        cmd_names = [c.name for c in ctx.bot.commands]
        aliases = [alias for c in ctx.bot.commands for alias in c.aliases]
        cmd_names.extend(aliases)

        if any(new_name in name for name in cmd_names):
            raise commands.BadArgument("tag name starts with a bot command or sub command.")

        return new_name


class FishRarityConventor(commands.Converter):
    async def convert(self, ctx, argument):
        rarity = argument.lower().strip()

        rarities = {"common": "1", "elite": "2", "super": "3", "legendary": "-1"}
        rarity = rarities.get(rarity, rarity)

        if rarity not in ("1", "2", "3", "-1"):
            raise commands.BadArgument(":no_entry: | an invalid rarity was passed.")

        return int(rarity)


class FishNameConventor(commands.Converter):
    async def convert(self, ctx, argument):
        argument = argument.lower().strip()
        fish = ""

        try:

            con = await ctx.con

        except TypeError:

            con = ctx.con

        if not argument.isdigit():
            fish = await con.fetchval("SELECT fish_id from fish where (LOWER(fish_name) like '%' || $1 || '%')", argument)

        if fish:
            return fish

        if argument.isdigit():

            check = await con.fetchval("SELECT * from fish where fish_id = $1", int(argument))

            if check:
                return int(argument)

        raise commands.BadArgument("an invalid fish was passed.")


class SeasonConverter(commands.Converter):
    async def convert(self, ctx, argument):
        argument = argument.lower().capitalize()

        seasons = ("Winter", "Summer", "Spring", "Autumn", "Fall")

        if argument in seasons:
            return argument

        spring = ("March", "April", "May")
        summer = ("June", "July", "August")
        autumn = ("September", "October", "November")

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
            month = months.get(argument, None)

        else:
            month = months_short.get(argument, None)

        if month in spring:
            month = "spring"

        elif month in summer:
            month = "summer"

        elif month in autumn:
            month = "fall"

        elif month:
            month = "winter"

        if month is None:
            raise commands.BadArgument("an invalid season was passed.")

        return month



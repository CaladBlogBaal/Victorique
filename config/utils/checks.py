from discord.ext import commands
from loadconfig import PRIVATE_GUILDS


def combined_permissions_check(**perms):
    # pretty combing
    # https://github.com/Rapptz/discord.py/blob/f513d831d137d29ee4638a5e6a218f70b56c5ac5/discord/ext/commands/core.py#L1460
    # and
    # https://github.com/Rapptz/discord.py/blob/f513d831d137d29ee4638a5e6a218f70b56c5ac5/discord/ext/commands/core.py#L1499

    async def predicate(ctx):
        channel = ctx.channel

        permissions = channel.permissions_for(ctx.author)
        permissions_bot = channel.permissions_for(ctx.me)

        missing = [perm for perm, value in perms.items() if getattr(permissions, perm, None) != value]
        missing_bot = [perm for perm, value in perms.items() if getattr(permissions_bot, perm, None) != value]

        if not missing and not missing_bot:
            return True

        if missing:
            raise commands.MissingPermissions(missing)

        if missing_bot:
            raise commands.BotMissingPermissions(missing_bot)

    return commands.check(predicate)


def checking_for_multiple_channel_instances():
    async def predicate(ctx):

        if ctx.guild:
            key = str(ctx.channel.id) + ctx.command.name
            if key in ctx.bot.channels_running_commands:
                return ctx.author.id not in ctx.bot.channels_running_commands[key]

        return True

    return commands.check(predicate)


def private_guilds_check():
    async def predicate(ctx):
        if ctx.guild:
            return ctx.guild.id in PRIVATE_GUILDS

        return True

    return commands.check(predicate)

import asyncio
import copy
import traceback
import sys

from discord.ext import commands
import discord

from config.utils.requests import RequestFailed


class CommandErrorHandler(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @staticmethod
    async def private_message_invoke(ctx):
        msg = copy.copy(ctx.message)
        msg.content += ctx.message.content
        new_ctx = await ctx.bot.get_context(msg)
        return await new_ctx.reinvoke()

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):

        author = ctx.bot.get_user(295325269558951936)

        if hasattr(ctx.command, 'on_error'):
            return

        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        ignored = commands.CommandNotFound

        accounted_for = (commands.BotMissingPermissions, commands.MissingRequiredArgument,
                         commands.MissingPermissions, commands.CommandOnCooldown, commands.NoPrivateMessage,
                         commands.NotOwner, commands.CommandNotFound, commands.TooManyArguments,
                         commands.DisabledCommand, commands.BadArgument, commands.BadUnionArgument,
                         RequestFailed, asyncio.TimeoutError)

        error = getattr(error, 'original', error)

        if isinstance(error, commands.errors.PrivateMessageOnly):
            await self.private_message_invoke(ctx)

        if isinstance(error, discord.errors.ClientException):
            return

        if isinstance(error, ignored):
            return

        if isinstance(error, accounted_for):
            return await ctx.send(f"> :no_entry: | {error}", delete_after=10)

        accounted_for += (commands.CheckFailure,)
        error_messsage = traceback.format_exception(type(error), error, error.__traceback__)
        error_messsage = "".join(c for c in error_messsage)

        try:
            if not isinstance(error, accounted_for):

                await author.send("```Python\n" + error_messsage + "```")

        except discord.errors.HTTPException:
            pass

        else:
            print("Ignoring exception in command {}:".format(ctx.command), file=sys.stderr)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)


def setup(bot):
    bot.add_cog(CommandErrorHandler(bot))

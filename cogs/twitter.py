import re

from collections import namedtuple

import discord
from discord.ext import commands

from config.utils import cache
from loadconfig import __prefix__


class Twitter(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    @cache.cache()
    async def check_replace(self, ctx):
        async with ctx.acquire():
            if ctx.guild:
                return await ctx.db.fetchval("SELECT replace_twitter_links FROM guilds WHERE guild_id = $1",
                                             ctx.guild.id)

        return True

    async def send_new_link(self, match: re.Match, regex: re.Pattern,
                            groups: namedtuple, message: discord.Message) -> [None, discord.Message]:
        """Send a new link to the channel the message was sent in."""
        embed_prefixes = ["fxtwitter.com", "vxtwitter.com", "twitter64.com"]

        if match:

            for prefix in embed_prefixes:
                revised = re.sub(regex, groups.first, prefix)
                user_name = match.group(groups.second)
                post_id = match.group(groups.third)
                new_link = f"https://{revised}/{user_name}/status/{post_id}"

                async with self.bot.session.get(new_link) as resp:
                    if resp.status == 200:

                        try:
                            await message.delete()
                        except discord.Forbidden:
                            pass

                        # can't send webhooks in DMs
                        if not message.guild:
                            return await message.channel.send(new_link)

                        webhooks = await message.channel.webhooks()  # We get all the webhooks

                        if not webhooks:
                            webhook = await message.channel.create_webhook(name="Twitter")
                        else:
                            webhook = webhooks[0]  # We get the first webhook

                        return await webhook.send(
                            content=message.content.replace(match.group(0), new_link),  # The message
                            username=message.author.display_name,  # The user name
                            avatar_url=message.author.display_avatar  # the user avatar
                        )

    @commands.command()
    async def twitter(self, ctx, *, user: str):
        """Get a link to a twitter user's profile."""
        user = user.strip("@")
        if not re.match(r"^[a-zA-Z0-9_]{1,15}$", user):
            return await ctx.send("Invalid username.")
        await ctx.send(f"https://twitter.com/{user}")

    @commands.command()
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_webhooks=True)
    async def allow_replace(self, ctx, *, allow: bool = True):
        """Toggle replacing twitter links to embed them using services like fxtwitter.
            True for yes False for no"""

        await ctx.db.execute("UPDATE guilds SET replace_twitter_links = $1 WHERE guild_id = $2", allow, ctx.guild.id)
        await ctx.send("Now replacing twitter links.", delete_after=5)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # lazily done
        ctx = await self.bot.get_context(message)

        if ctx.guild:
            allow = await self.check_replace(ctx)
        else:
            allow = True

        groups = namedtuple("group", "first second third")

        if message.author.bot:
            return

        if ctx.prefix:
            groups = groups(r"\g<3>", 4, 5)
            prefixes = r"((" + __prefix__ + ")"
            regex = prefixes + "https?:\/\/)?(?:www\.)?(twitter)\.com\/(?:#!\/)?(\w+)\/status(?:es)?\/(\d+)"

        elif allow:
            groups = groups(r"\g<1>", 2, 3)
            regex = r"(?:https?:\/\/)?(?:www\.)?(twitter)\.com\/(?:#!\/)?(\w+)\/status(?:es)?\/(\d+)"

        else:
            return

        check = re.match(regex, message.content)

        if check:
            await self.send_new_link(check, regex, groups, message)


async def setup(bot):
    await bot.add_cog(Twitter(bot))

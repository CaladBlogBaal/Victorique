import asyncio
import re

import discord
from discord.ext import commands

from config.utils.checks import combined_permissions_check


class Moderation(commands.Cog):
    """Moderation related commands"""
    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    @staticmethod
    async def hiearchy_check(ctx, member):

        if ctx.me.top_role <= member.top_role:
            await ctx.send(f"> I can't manage {member.name} due to hierarchy.", delete_after=8)
            await asyncio.sleep(1)
            return True

        return False

    @staticmethod
    async def set_perms(guild, role=None):
        muted_role = role

        if not role:
            muted_role = discord.utils.get(guild.roles, name="Muted")

        if not muted_role:
            return

        overwrite = discord.PermissionOverwrite()
        overwrite.update(send_messages=False)

        for channel in guild.channels:
            await channel.set_permissions(muted_role, overwrite=overwrite)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):

        guild = channel.guild
        await self.set_perms(guild)

    async def cog_check(self, ctx):

        if not ctx.guild:
            return False

        return True

    async def role_check(self, ctx, member, role):
        role_name = self.bot.safe_everyone(role.name)

        if member.top_role <= role:
            await ctx.send(f":no_entry: | member's top role is below the role `{role_name}` in the hierarchy")
            return False

        if ctx.me.top_role <= role:
            await ctx.send(f":no_entry: | the role `{role_name}` is above mine in the hierarchy")
            return False

        return role_name

    @commands.command()
    @combined_permissions_check(manage_messages=True)
    async def purge_bot(self, ctx, amount=1):
        """Delete x amount of bot messages"""

        if amount > 100:
            amount = 100

        if amount < 0:
            return

        def check(message):
            return message.author == self.bot.user

        await ctx.channel.purge(limit=amount, before=ctx.message, check=check)

    @commands.command(aliases=['boot', 'massboot', 'prune_members'])
    @combined_permissions_check(kick_members=True)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *, reason="No reason"):
        """
        Kick a guild member or members
        """
        member_display = []
        for member in members:
            if await self.hiearchy_check(ctx, member):
                continue

            await member.kick(reason=reason)
            member_display.append(str(member))

        member_display = ", ".join(member_display)

        if not member_display:
            member_display = "no one"

        await ctx.send(f"> {ctx.author.name} kicked {member_display}")

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @combined_permissions_check(manage_messages=True)
    async def purge(self, ctx, amount: int, member: discord.Member = None):
        """
        Purge any an amount of messages
        """
        if amount > 100:
            return await ctx.send(":no_entry: | The max amount of messages you can purge is 100")

        def check(message):
            return message.author == member

        if member is None:
            deleted = await ctx.channel.purge(limit=amount, before=ctx.message)

        else:
            deleted = await ctx.channel.purge(limit=amount, before=ctx.message, check=check)

        embed = discord.Embed(title="Purge",
                              description=f"Deleted __**{len(deleted)}**__ message(s)",
                              color=self.bot.default_colors())
        embed.set_footer(text=f"Requested by {ctx.message.author.name}", icon_url=ctx.message.author.avatar.url)
        embed.timestamp = ctx.message.created_at
        await ctx.send(embed=embed, delete_after=4)

    @commands.command()
    @combined_permissions_check(manage_roles=True)
    async def mute(self, ctx, members: commands.Greedy[discord.Member], reason="no reason"):
        """Mute a guild member or members"""

        role = discord.utils.get(ctx.guild.roles, name="Muted")
        member_display = []

        for i, member in enumerate(members):
            if role in member.roles:
                await ctx.send(f"guild member `{member.display_name}` is already muted", delete_after=8)
                del members[i]

        if role is None:
            permissions = discord.Permissions()
            permissions.change_nickname = True
            permissions.send_messages = False
            permissions.read_message_history = True
            role = await ctx.guild.create_role(name="Muted", permissions=permissions)

            await self.set_perms(ctx.guild, role)

        for member in members:

            if await self.hiearchy_check(ctx, member):
                continue

            member_display.append(str(member))
            await member.add_roles(role, reason=reason)

        member_display = ", ".join(member_display)

        if not member_display:
            member_display = "no one"

        await ctx.send(f"> {ctx.author.name} muted {member_display}")

    @commands.command()
    @combined_permissions_check(manage_roles=True)
    async def unmute(self, ctx, members: commands.Greedy[discord.Member], *, reason: str = None):
        """Unmute a guild member or members"""

        role = discord.utils.get(ctx.guild.roles, name="Muted")
        member_display = []

        for member in members:
            if role not in member.roles:
                await ctx.send(f"guild member `{member.display_name}` is already unmuted")

            else:

                if await self.hiearchy_check(ctx, member):
                    continue

                member_display.append(str(member))
                await member.remove_roles(role, reason=reason)

        member_display = ", ".join(member_display)

        if not member_display:
            member_display = "no one"

        await ctx.send(f"> {ctx.author.name} unmuted {member_display}")

    @commands.command()
    @combined_permissions_check(manage_emojis=True)
    async def emote(self, ctx, *, urls=None):
        """Create an emoji accepts file attachments"""
        if urls is None:
            urls = ""

        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                urls += attachment.url + " "

        custom_emojis = re.findall(r"<a?:(\w+):(\d+)>", urls)

        try:
            if re.findall('https?://(?:[-\\w.]|(?:%[\\da-fA-F]{2}))+', urls):
                # removing duplicate spaces
                urls = " ".join(urls.split())
                url_list = urls.split(" ")
                names = [link.split("/")[-1] for link in url_list]
                names = [name[:name.find(".") + 1].replace(".", "") for name in names]
                responses = []

                for url in url_list:
                    async with self.session.get(url) as response:
                        responses.append(await response.read())

                images = list(response for response in responses)

                for i, name in enumerate(names):
                    image = images[i]
                    emoji = await ctx.guild.create_custom_emoji(name=name, image=image, reason=None)
                    await ctx.send(f"{emoji.url} \nemoji {emoji.name} was created")

            if custom_emojis:
                for emote in custom_emojis:
                    url = f"https://cdn.discordapp.com/emojis/{emote[1]}.png?v=1"
                    name = emote[0]

                    async with self.session.get(url) as response:
                        image = await response.read()

                    emoji = await ctx.guild.create_custom_emoji(name=name, image=image, reason=None)
                    await ctx.send(f"{emoji.url} \nemoji {emoji.name} was created")

        except discord.errors.HTTPException as e:
            if e.status == 400:
                await ctx.send(f":no_entry: | an error occurred during the emote process ```{e.text}```.")

    @commands.command()
    @combined_permissions_check(manage_messages=True)
    async def pin(self, ctx, message_id: int = None):
        """Pin a message
        if no message id is passed will pin the command message."""

        if message_id is None:
            return await ctx.message.pin()

        try:

            msg = await ctx.channel.fetch_message(message_id)
            await msg.pin()

        except discord.errors.NotFound:

            await ctx.send(":no_entry: | couldn't find the message to pin.")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def set_prefix(self, ctx, prefix: commands.clean_content, allow_default=False):
        """Set a guilds prefix
           True for yes False for no to allow the bots default prefix"""

        if len(prefix) > 25:
            return await ctx.send(":no_entry: | prefixes can't be 25 characters or greater.")

        if re.findall(r"<a?:\w*:\d*>", prefix):
            return await ctx.send(":no_entry: | emoji's are not allowed as a guild's prefix")

        if re.findall(r'https?://(?:[-\\w.]|(?:%[\\da-fA-F]{2}))+', prefix):
            return await ctx.send(":no_entry: | urls are not allowed as a guild's prefix")

        async with ctx.acquire():
            await ctx.db.execute("""
                            INSERT INTO guilds (guild_id, prefix, allow_default) VALUES ($1, $2, $3)
                            ON CONFLICT (guild_id) DO UPDATE SET (prefix, allow_default) = ($2, $3)
                    
                            """, ctx.guild.id, prefix, allow_default)

        await ctx.send(f"The prefix for this guild is now {prefix}")

    @set_prefix.after_invoke
    async def set_prefix_after_invoke(self, ctx):
        # invalidating caches here
        self.bot.prefix_invalidate(ctx.guild.id)
        # invalidating the cache for every tag in this guild
        async with ctx.acquire():
            tags = await ctx.db.fetch("select tag_name from tags where guild_id = $1", ctx.guild.id)
            for tag in tags:
                self.bot.tags_invalidate(ctx.guild.id, tag["tag_name"])


def setup(bot):
    bot.add_cog(Moderation(bot))

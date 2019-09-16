import asyncio
import re
import typing

import discord
from discord.ext import commands

from config.utils.checks import combined_permissions_check


class Moderation(commands.Cog):
    """Moderation related commands"""
    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    async def cog_check(self, ctx):

        if not ctx.guild:
            return False

        return True

    async def role_check(self, ctx, member, role):
        role_name = self.bot.safe_everyone(role.name)

        if member.top_role <= role:
            await ctx.send(f":no_entry: | your top role is below the role {role_name} in the hierarchy")
            return False

        if ctx.me.top_role <= role:
            await ctx.send(f":no_entry: | the role {role_name} is above mine in the hierarchy")
            return False

        return role_name

    @commands.command()
    @combined_permissions_check(manage_messages=True)
    async def purge_bot(self, ctx, amount=1):
        """delete x amount of bot messages"""

        if amount > 100:
            amount = 100

        if amount < 0:
            return

        def check(message):
            return message.author == self.bot.user

        await ctx.channel.purge(limit=amount, before=ctx.message, check=check)

    @commands.command(aliases=['boot', 'massboot', 'prune_members'])
    @combined_permissions_check(kick_members=True)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *,
                   reason="No reason"):
        """
        kick a guild member or members
        """
        member_display = []
        for member in members:
            await member.kick(reason=reason)
            member_display.append(member.mention)

        member_display = ", ".join(repr(member) for member in member_display).replace("'", "")

        if len(member_display) == 0:
            member_display = "no one"

        await ctx.send(f"{ctx.author.name} kicked {member_display}")

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.user)
    @combined_permissions_check(manage_messages=True)
    async def purge(self, ctx, amount: int, member: discord.Member = None):
        """
        purge any an amount of messages
        """
        if amount > 100:
            return await ctx.send(":no_entry: | The max amount of messages you can purge is 100")

        def check(message):
            return message.author == member

        if member is None:
            deleted = await ctx.channel.purge(limit=amount, before=ctx.message)

        else:
            deleted = await ctx.channel.purge(limit=amount, before=ctx.message, check=check)

        embed = discord.Embed(title='Sufficient Perms! :white_check_mark:',
                              description=f'Deleted __**{len(deleted)}**__ message(s)!',
                              color=self.bot.default_colors())
        embed.set_footer(text=f'Requested by {ctx.message.author.name}', icon_url=ctx.message.author.avatar_url)
        embed.timestamp = ctx.message.created_at
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(10)
        await msg.delete()

    @commands.command()
    @combined_permissions_check(manage_roles=True)
    async def mute(self, ctx, members: commands.Greedy[discord.Member], reason="no reason"):
        """mute a guild member or members"""

        role = discord.utils.get(ctx.guild.roles, name="Muted")
        member_display = []

        for i, member in enumerate(members):
            if role in member.roles:
                await ctx.send(f"guild member [ {member.display_name} ] is already muted")
                del members[i]

        if role is None:
            permissions = discord.Permissions()
            permissions.change_nickname = True
            permissions.send_messages = False
            permissions.read_message_history = True
            role = await ctx.guild.create_role(name="Muted", permissions=permissions)

        overwrite = discord.PermissionOverwrite()
        overwrite.update(send_messages=False)
        for channel in ctx.guild.channels:
            await channel.set_permissions(role, overwrite=overwrite)

        for member in members:
            member_display.append(member.mention)
            await member.add_roles(role, reason=reason)

        member_display = ", ".join(repr(member) for member in member_display).replace("'", "")

        if len(member_display) == 0:
            member_display = "no one"

        await ctx.send(f"{ctx.author.name} muted {member_display}")

    @commands.command()
    @combined_permissions_check(manage_roles=True)
    async def unmute(self, ctx, members: commands.Greedy[discord.Member], length: int = 0, *, reason: str = None):
        """unmute a guild member or members"""

        role = discord.utils.get(ctx.guild.roles, name="Muted")
        member_display = []

        for member in members:
            if role not in member.roles:
                await ctx.send(f"guild member [ {member.display_name} ] is already unmuted")

            else:
                member_display.append(member.mention)
                await member.remove_roles(role, reason=reason)

        member_display = ", ".join(repr(member) for member in member_display).replace("'", "")

        if len(member_display) == 0:
            member_display = "no one"

        await ctx.send(f"{ctx.author.name} unmuted {member_display}")

    @commands.command()
    @combined_permissions_check(manage_roles=True)
    async def addrole(self, ctx, member: typing.Optional[discord.Member] = None, *, role: discord.Role):
        """add a role to a guild member"""
        member = member or ctx.author
        role_name = await self.role_check(ctx, member, role)

        if role_name is False:
            return

        await member.add_roles(role, reason=None, atomic=True)
        await ctx.send(f"> added the role {role.name} to {member.display_name} :white_check_mark:")

    @commands.command()
    @combined_permissions_check(manage_roles=True)
    async def removerole(self, ctx, member: typing.Optional[discord.Member] = None, *, role: discord.Role):
        """remove a role to a guild member"""

        member = member or ctx.author
        role_name = await self.role_check(ctx, member, role)

        if role_name is False:
            return

        await member.remove_roles(role)
        await ctx.send(f"> removed the role {role_name} from {member.display_name} :white_check_mark:")

    @commands.command()
    @combined_permissions_check(manage_emojis=True)
    async def emote(self, ctx, *, url=None):
        """create an emoji accepts file attachments"""
        if url is None:
            url = ""

        if ctx.message.attachments:
            for attachment in ctx.message.attachments:
                url += attachment.url + " "

        # checking if the message contains emote objects
        custom_emojis = re.findall(r"<a?:\w*:\d*>", url)
        custom_emojis_names = []
        custom_emojis_ids = []
        # extracting emote object details
        try:
            custom_emojis_names = [(await commands.PartialEmojiConverter().convert(ctx, emote)).name
                                   for emote in custom_emojis]
            custom_emojis_ids = [(await commands.PartialEmojiConverter().convert(ctx, emote)).id
                                 for emote in custom_emojis]

        except commands.BadArgument:
            pass

        # adding the emote to the guild
        try:
            if re.findall('https?://(?:[-\\w.]|(?:%[\\da-fA-F]{2}))+', url):
                # removing duplicate spaces
                url = " ".join(url.split())
                url_list = url.split(" ")
                names = [link.split("/")[-1] for link in url_list]
                names = [name[:name.find(".") + 1].replace(".", "") for name in names]
                responses = []

                for url_ in url_list:
                    async with self.session.get(url_) as response:
                        responses.append(await response.read())

                images = list(response for response in responses)

                for i, name in enumerate(names):
                    image = images[i]
                    emoji = await ctx.guild.create_custom_emoji(name=name, image=image, reason=None)
                    await ctx.send(f"{emoji.url} \nemoji {emoji.name} was created")
                    await asyncio.sleep(1)

            if len(custom_emojis_ids) != 0:
                for i, _id in enumerate(custom_emojis_ids):
                    url = f"https://cdn.discordapp.com/emojis/{_id}.png?v=1"
                    name = custom_emojis_names[i]

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
        """pin a message
        ir no message id is passed will pin the command message."""

        if message_id is None:
            return await ctx.message.pin()

        msg = await ctx.channel.fetch_message(message_id)

        if msg:
            await msg.pin()

        else:
            await ctx.send(":no_entry: | couldn't find the message to pin")

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def set_prefix(self, ctx, prefix: commands.clean_content, allow_default=False):
        """set a guilds prefix
           True for yes False for no to allow the bots default prefix"""

        if len(prefix) > 25:
            return await ctx.send(":no_entry: | prefixes can't be 25 characters or greater.")

        if re.findall(r"<a?:\w*:\d*>", prefix):
            return await ctx.send(":no_entry: | emoji's are not allowed as a guild's prefix")

        if re.findall(r'https?://(?:[-\\w.]|(?:%[\\da-fA-F]{2}))+', prefix):
            return await ctx.send(":no_entry: | urls are not allowed as a guild's prefix")

        async with ctx.con.transaction():
            await ctx.con.execute("""
                            INSERT INTO guilds (guild_id, prefix, allow_default) VALUES ($1, $2, $3)
                            ON CONFLICT (guild_id) DO UPDATE SET (prefix, allow_default) = ($2, $3)
                    
                            """, ctx.guild.id, prefix, allow_default)

        await ctx.send(f"The prefix for this guild is now {prefix}")

    @set_prefix.after_invoke
    async def set_prefix_after_invoke(self, ctx):
        self.bot.prefix_invalidate(ctx.guild.id)


def setup(bot):
    bot.add_cog(Moderation(bot))

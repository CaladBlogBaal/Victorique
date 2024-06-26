import typing

import discord
from discord.ext import commands
from config.utils.context import Context


class Members(commands.Cog):
    """Discord member related commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.guild_only()
    async def info(self, ctx: Context,  *, member: discord.Member = None):
        """
        Get info on a guild member
        only displays the first 40 roles.
        """

        member = member or ctx.author

        status = member.status
        id_ = member.id
        nickname = member.display_name
        shared_servers = len([guild for guild in self.bot.guilds if member in guild.members
                              and ctx.author in guild.members])
        joined_at = member.joined_at.strftime("%d/%m/%Y: %H:%M:%S")
        roles = ctx.chunk([role.mention if "everyone" not in role.name else role.name for role in member.roles[:40]], 4)
        roles_ = ""
        for chunk in roles:
            roles_ += " ".join(chunk)
            roles_ += "\n"

        roles = roles_

        prem_since = member.premium_since or "hasn't boosted this server"

        if not isinstance(prem_since, str):
            prem_since = prem_since.strftime("%d/%m/%Y: %H:%M:%S")

        embed = discord.Embed(title=f"{member.display_name}",
                              color=member.color)

        embed.add_field(name="**ID**", value=id_, inline=False)
        embed.add_field(name="**Shared servers**", value=str(shared_servers), inline=False)
        embed.add_field(name="**Nickname**", value=nickname)
        embed.add_field(name="**Status**", value=status)
        embed.add_field(name="**Joined at**", value=joined_at)
        embed.add_field(name="**Roles**", value=roles)
        embed.add_field(name="**Nitro boosting since**", value=prem_since)
        embed.set_author(icon_url=member.avatar.url, name=str(member))

        await ctx.send(embed=embed)

    @commands.command(name='perms', aliases=['perms_for', 'permissions'])
    @commands.guild_only()
    async def check_permissions(self, ctx: Context, *, member: discord.Member = None):
        """
        Check a members permissions
        """

        member = member or ctx.author

        perms = '\n'.join(perm for perm, value in member.guild_permissions if value)
        embed = discord.Embed(title='Permissions for:', description=ctx.guild.name, colour=member.colour)
        embed.set_author(icon_url=member.avatar.url, name=str(member))
        embed.add_field(name='\uFEFF', value=perms)

        await ctx.send(embed=embed)

    @commands.command()
    async def avatar(self, ctx: Context, *, member: typing.Union[discord.Member, discord.User] = None):
        """
         Check a guild member's or user's avatar
         """

        member = member or ctx.author

        embed = discord.Embed(color=self.bot.default_colors())
        embed.set_author(name=str(member), icon_url=member.display_avatar.replace(format="png", size=32))
        embed.set_image(url=member.display_avatar.replace(static_format="png", size=1024))
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Members(bot))

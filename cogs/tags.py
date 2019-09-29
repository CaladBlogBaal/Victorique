import functools
import operator
import re
import datetime
import typing

from io import BytesIO

import aiohttp
import asyncpg
import humanize as h

import discord
from discord.ext import commands

import loadconfig
from config.utils.paginator import Paginator
from config.utils.converters import TagNameConvertor


class Tags(commands.Cog):
    """tag related commands to call a created tag do [guild prefix][tag name}"""
    def __init__(self, bot):
        self.bot = bot
        self.cd = commands.CooldownMapping.from_cooldown(1, 4, commands.BucketType.member)

    async def cog_check(self, ctx):
        return ctx.guild is not None

    @staticmethod
    async def create_tag(ctx, name, content):
        async with ctx.con.transaction():
            try:
                await ctx.con.execute("""INSERT INTO tags (tag_name, guild_id, user_id, content, created_at) 
                                         VALUES ($1, $2, $3, $4, $5)""",
                                      name, ctx.guild.id, ctx.author.id, content, ctx.message.created_at)

            except asyncpg.UniqueViolationError:
                return await ctx.send(f":information_source: | tag name already exists")

            if len(name.split(" ")) >= 2:
                name = f"\"{name}\""

            await ctx.send(f":information_source: | created new tag `{name}` to add content to this tag do "
                           f"`{ctx.prefix}tag update {name} <content here>`.")

    @commands.Cog.listener()
    async def on_message(self, message):
        # this is crude as hell

        if message.guild and not message.author.bot:

            data = await self.bot.get_guild_prefix(message.guild.id)

            tag_prefix = loadconfig.__prefix__
            allow_default = False

            if data["prefix"]:
                tag_prefix = data["prefix"]
                allow_default = data["allow_default"]

            tags = await self.bot.get_tags(message.guild.id)

            if allow_default is False:
                tags = {f"{tag_prefix if tag_prefix else loadconfig.__prefix__}{tag['tag_name']}" for tag in tags}

            else:
                tags = {f"{tag_prefix}{tag['tag_name']}\u200b{loadconfig.__prefix__}{tag['tag_name']}" for tag in tags}
                tags = [t.split("\u200b") for t in tags]
                tags = functools.reduce(operator.iconcat, tags, [])

            content = message.content.lower()

            if content in tags:
                bucket = self.cd.get_bucket(message)
                retry_after = bucket.update_rate_limit()
                if retry_after:
                    return await message.channel.send(":no_entry: | woah slow down there you're being rated limited.",
                                                      delete_after=3)
                query = "SELECT content, nsfw from tags where LOWER(tag_name) = $1 and guild_id = $2"
                if message.content.startswith(loadconfig.__prefix__):
                    name = content.replace(loadconfig.__prefix__, "", 1)

                else:
                    name = content.replace(tag_prefix, "", 1)

                tag = await self.bot.db.fetchrow(query, name, message.guild.id)

                if tag["nsfw"] and not message.channel.nsfw:
                    return

                tag = tag["content"]

                if tag.count("||") >= 2:
                    return await message.channel.send(tag)

                reg = re.compile(r"""(?:http|https)?://(?:www.)?[-a-zA-Z0-9@:%.+~#=]{2,256}.[a-z]{2,6}\b
                                     (?:[-a-zA-Z0-9@:%_+.~#?&//=]*).
                                     (?:<format>|jpe?g|png|gif?)""", flags=re.VERBOSE | re.IGNORECASE)

                urls = reg.findall(tag)

                if urls:
                    url = urls[0]

                    if len(urls) > 2 or tag.replace(url, "") != "":
                        return await message.channel.send(tag)

                    if "SPOILER" in url:
                        return await message.channel.send(f"|| {url} ||")
                    try:
                        async with self.bot.session.get(url) as response:
                            header = response.headers.get("content-type", "null")
                            # if the url is dead don't load it into a file
                            if "image/" not in header or response.status in (404, 403, 400, 401):
                                return await message.channel.send(tag)

                            extension = header.split("/")[1]
                            size = response.headers.get("content-length")
                            size = int(size)

                            if size > 5242880:
                                embed = discord.Embed(color=0x36393f)
                                return await message.channel.send(embed=embed.set_image(url=url))

                            file_ = discord.File(filename=f"{name}_image.{extension}",
                                                 fp=BytesIO(await self.bot.fetch(url)))

                            return await message.channel.send(file=file_)

                    except (aiohttp.ClientConnectionError, aiohttp.InvalidURL):
                        return await message.channel.send(tag)

                await message.channel.send(tag)

    @commands.group(invoke_without_command=True, aliases=["tags"])
    async def tag(self, ctx, member: discord.Member = None):
        """The main command for tags returns your current tags by itself.."""

        p = Paginator(ctx)
        member = member or ctx.author
        data = await ctx.con.fetch("SELECT tag_name from tags where user_id = $1 and guild_id = $2", member.id,
                                   ctx.guild.id)

        if data == []:
            return await ctx.send(f"> {member.name} currently has no tags created for this guild.")

        names = [f'\n> **{tag["tag_name"]}**' for tag in data]

        name_chunks = ctx.chunk(names, 10)

        for name_chunk in name_chunks:
            names = "".join(name for name in name_chunk)
            await p.add_page(f"> {member.name} current tags for **{str(ctx.guild)}**...\n> {names}")

        await p.paginate()

    @tag.command()
    async def create(self, ctx, *, name: TagNameConvertor):
        """Create a customisable tag for this guild"""

        await self.create_tag(ctx, name, ".")

    @tag.command()
    async def claim(self, ctx, *, name: TagNameConvertor):
        """Claim a tag if the tag owner has left the server"""

        data = await ctx.con.fetchrow("SELECT tag_id, user_id FROM tags WHERE guild_id = $1 AND LOWER(tag_name) = $2",
                                      ctx.guild.id, name.lower())
        if data is None:
            return await ctx.send(f'A tag with the name of "{name}" does not exist.')

        try:
            member = ctx.guild.get_member(data["user_id"]) or await ctx.guild.fetch_member(data["user_id"])
        except discord.NotFound:
            member = None

        if member is not None:
            return await ctx.send(":no_entry: | tag owner is still in the server.")

        async with ctx.con.transaction():
            await ctx.con.execute("UPDATE tags set user_id = $1 WHERE guild_id = $2 and LOWER(tag_name) = $3",
                                  ctx.author.id, ctx.guild.id, name)

        await ctx.send(f"> successfully transferred ownership of `{name}` to you.")

    @tag.command()
    async def raw(self, ctx, *, name: TagNameConvertor):
        """display a tag without markdown eg spoilers."""

        content = await ctx.con.fetchval("SELECT content from tags where LOWER(tag_name) = $1 and guild_id = $2",
                                         name, ctx.guild.id)
        if content:
            return await ctx.send(discord.utils.escape_markdown(content))

        await ctx.send(f":no_entry: | could not find the tag {name}.")

    @tag.command()
    async def info(self, ctx, *, name: TagNameConvertor):
        """get info on a tag"""
        data = await ctx.con.fetchrow("SELECT * from tags where LOWER(tag_name) = $1 and guild_id = $2",
                                      name, ctx.guild.id)

        embed = discord.Embed(title=name,
                              color=self.bot.default_colors())
        if not data:
            return await ctx.send(f"> A tag with name `{name}` does not exist.")

        member = ctx.guild.get_member(data["user_id"]) or await self.bot.fetch_user(data["user_id"])
        date = h.naturaltime(datetime.datetime.utcnow() - data["created_at"])
        embed.add_field(name="Owner", value=member.name)
        embed.add_field(name="Created", value=date, inline=False)
        embed.set_author(name=member.name, icon_url=member.avatar_url_as(static_format="png"))

        await ctx.send(embed=embed)

    @tag.command(aliases=["content", "details", "update"])
    async def update_content(self, ctx, name: TagNameConvertor, *, content: commands.clean_content):
        """update a tag's content encase the tag's name in quotes if it has spaces"""

        check = await ctx.con.fetchval("SELECT tag_name FROM tags WHERE user_id = $1 and guild_id = $2",
                                       ctx.author.id, ctx.guild.id)

        if check is None:
            return await ctx.send(f":information_source: you do not have a tag for this guild create one with "
                                  f"{ctx.prefix}tag create name")

        async with ctx.con.transaction():
            check = await ctx.con.execute("""UPDATE tags SET content = $1 WHERE guild_id = $2 and user_id = $3 
                                             and tag_name = $4""",
                                          content, ctx.guild.id, ctx.author.id, name)

            if check[-1] == "0":
                return await ctx.send(f":no_entry: | could not edit the tag in question {name} do you own it "
                                      f"and it exists? `note you must encase a tag's name in quotes if it contains "
                                      f"spaces eg  {ctx.prefix}tag content \"hello world\" hi`")

            await ctx.send(f":information_source: | successfully updated tag with content `{content}`.")

    @tag.command()
    async def list(self, ctx):
        """get a list of tags for the current guild"""

        tags = await ctx.con.fetch("select tag_name, user_id from tags where guild_id =  $1",
                                   ctx.guild.id)

        tags = [f"Tag name: **{tag['tag_name']}** created by "
                f"**{str(ctx.guild.get_member(tag['user_id']))}**" for tag in tags if tag['tag_name']]

        tags_chunks = ctx.chunk(tags, 10)

        p = Paginator(ctx)

        if not tags_chunks:
            return await ctx.send("> Currently no tags for this guild exist.")

        for tags in tags_chunks:
            tags = "\n".join(tags)
            embed = discord.Embed(title="Tags for:", description=ctx.guild.name, colour=discord.Color.dark_magenta())
            embed.add_field(name='\uFEFF', value=tags)
            await p.add_page(embed)

        await p.paginate()

    @tag.group(invoke_without_command=True, aliases=["remove", "prune"])
    async def delete(self, ctx, *, name: TagNameConvertor):
        """delete a tag"""

        check = await self.bot.is_owner(ctx.author) or ctx.author.guild_permissions.manage_messages

        if check:
            deleted = await ctx.con.fetchrow("DELETE from tags where guild_id = $1 and LOWER(tag_name)"
                                             " = $2 RETURNING tag_id",
                                             ctx.guild.id, name)
        else:

            deleted = await ctx.con.fetchrow("DELETE from tags where guild_id = $1 "
                                             "and tag_name = $2 and user_id = $3 RETURNING tag_id",
                                             ctx.guild.id, name, ctx.author.id)

        if deleted is None:
            return await ctx.send(":no_entry: | tag deletion failed, does the tag exist,"
                                  " do you own this tag or have the manage server"
                                  " permissions to delete"
                                  " tags?")

        await ctx.send(f"> tag `{name}` successfully deleted.")

    @delete.command()
    async def all(self, ctx, member: discord.Member):
        """delete all of a member's tags"""

        check = await self.bot.is_owner(ctx.author) or ctx.author.guild_permissions.manage_messages

        if check:

            deleted = await ctx.con.fetch("DELETE from tags where guild_id = $1 and user_id = $2 RETURNING tag_id",
                                          ctx.guild.id, member.id)
            if deleted == []:
                return await ctx.send(f"> {member.name} has no tags to delete.")

            await ctx.send(f"> successfully deleted {len(deleted)} from {member.name}.")

        else:
            await ctx.send(":no_entry: | you need manage message permissions for this command.")

    @tag.command()
    async def nsfw(self, ctx, nsfw: typing.Optional[bool] = True, *, tag_name: TagNameConvertor):
        """set a tag to be only be usable in NSFW channels
        pass True for nsfw False to not make it NSFW"""

        check = await ctx.con.fetchval("SELECT tag_name FROM tags WHERE tag_name = $1 and guild_id = $2",
                                       tag_name, ctx.guild.id)

        if check is None:
            return await ctx.send(f"> The tag `{tag_name}` does not exist.")

        check = await self.bot.is_owner(ctx.author) or ctx.author.guild_permissions.manage_messages

        if check:
            async with ctx.con.transaction():
                await ctx.con.execute("UPDATE tags SET nsfw = $1 where tag_name = $2 and guild_id = $3",
                                      nsfw, tag_name, ctx.guild.id)

                if nsfw:
                    return await ctx.send(f"> The tag {tag_name} has been set to NSFW")

                await ctx.send(f"> The tag {tag_name} has been set to not NSFW")

        else:

            await ctx.send(":no_entry: | you need manage message permissions for this command.")

    @tag.command()
    async def transfer(self, ctx, member: discord.Member, *, tag_name: TagNameConvertor):
        """transfer a tag you own to another user"""

        check = await ctx.con.fetchval("""SELECT tag_name FROM tags 
                                          where guild_id = $1 and user_id = $2 and tag_name = $3
                                          """, ctx.guild.id, ctx.author.id, tag_name)

        if check is None:
            return await ctx.send(f":no_entry: | does the tag {tag_name} exist and do you own it?")

        async with ctx.con.transaction():
            await ctx.con.execute("UPDATE tags SET user_id = $1 where guild_id = $2 and tag_name = $3",
                                  member.id, ctx.guild.id, tag_name)

        await ctx.send(f"> Successfully transferred ownership of the tag `{tag_name}` to {member.name}.")

    @create.after_invoke
    @update_content.after_invoke
    async def after_tag_update(self, ctx):
        self.bot.tags_invalidate(ctx.guild.id)


def setup(bot):
    n = Tags(bot)
    bot.add_cog(n)

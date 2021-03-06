import re
import datetime
import typing

from io import BytesIO

import aiohttp
import asyncpg
import humanize as h

import discord
from discord.ext import commands

from config.utils.converters import TagNameConverter

import loadconfig


async def send_tag_content(tag, message, bot):
    # will try and refractor this later

    name = tag["tag_name"]
    if tag["nsfw"] and not message.channel.nsfw:
        return await message.channel.send(f"> This tag can only be used in NSFW channels.", delete_after=4)

    content = tag["content"]

    if content.count("||") >= 2:
        return await message.channel.send(content)

    reg = re.compile(r"""(?:http|https)?://(?:www.)?[-a-zA-Z0-9@:%.+~#=]{2,256}.[a-z]{2,6}\b
                         (?:[-a-zA-Z0-9@:%_+.~#?&//=]*).
                         (?:<format>|jpe?g|png|gif?)""", flags=re.VERBOSE | re.IGNORECASE)

    urls = reg.findall(content)

    if urls:
        url = urls[0]
        # if there's multiple urls send the tag content as is or if there's an url followed by text
        if len(urls) > 2 or content.replace(url, "") != "":
            return await message.channel.send(content)

        if "SPOILER" in url:
            return await message.channel.send(f"|| {url} ||")
        try:
            async with bot.session.get(url) as response:
                header = response.headers.get("content-type", "null")
                # if the url is dead don't load it into a file
                if "image/" not in header or response.status in (404, 403, 400, 401):
                    return await message.channel.send(content)

                extension = header.split("/")[1]
                size = response.headers.get("content-length")
                size = int(size)

                if size > 5242880:
                    embed = discord.Embed(color=0x36393f)
                    return await message.channel.send(embed=embed.set_image(url=url))

                file_ = discord.File(filename=f"{name}_image.{extension}",
                                     fp=BytesIO(await bot.fetch(url)))

                return await message.channel.send(file=file_)

        except (aiohttp.ClientConnectionError, aiohttp.InvalidURL):
            await message.channel.send(content)

    await message.channel.send(content)


class Tags(commands.Cog):
    """tag related commands to call a created tag do [guild prefix][tag name}"""

    def __init__(self, bot):
        self.bot = bot
        self.cd = commands.CooldownMapping.from_cooldown(1, 4, commands.BucketType.member)

    async def invalidate_user_tags(self, ctx, member):
        tag_names = await ctx.db.fetch("SELECT tag_name from tags where guild_id = $1 and user_id = $2",
                                       ctx.guild.id, member.id)
        for name in tag_names:
            self.bot.tags_invalidate(ctx.guild.id, name)

    async def cog_check(self, ctx):
        return ctx.guild is not None

    async def cog_before_invoke(self, ctx):
        # acquire a connection to the pool before every command
        await ctx.acquire()

    @staticmethod
    async def create_tag(ctx, name, content):

        try:
            await ctx.pool.execute("""INSERT INTO tags (tag_name, guild_id, user_id, content, created_at) 
                                    VALUES ($1, $2, $3, $4, $5)""",
                                   name, ctx.guild.id, ctx.author.id, content, ctx.message.created_at)
        except asyncpg.UniqueViolationError:
            return await ctx.send(f":information_source: | tag name already exists")

        if len(name.split(" ")) >= 2:
            name = f"\"{name}\""

        await ctx.send(f":information_source: | created new tag `{name}` to add content to this tag do "
                       f"`{ctx.prefix}tag update {name} <content here>`.")

    @staticmethod
    def prefixed_tag_names(allow_default, prefix, tag):
        if allow_default:
            check = (f"{prefix}{tag['tag_name']}", f"{loadconfig.__prefix__}{tag['tag_name']}")

        else:
            check = (f"{prefix}{tag['tag_name']}", )

        return check

    async def check_failure(self, tag, name, guild_id):
        if not tag:
            # if it failed to find a tag invalidate the cache for it
            self.bot.tags_invalidate(guild_id, name)
            return True
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        # still crude as hell
        # getting the context to check if the message contains a prefix
        ctx = await self.bot.get_context(message)

        if not message.guild or message.author.bot or not ctx.prefix:
            return

        data = await self.bot.get_guild_prefix(message.guild.id)

        prefix = loadconfig.__prefix__
        allow_default = False

        if data["prefix"]:
            prefix = data["prefix"]
            allow_default = data["allow_default"]

        content = message.content.lower()
        tag_name = content.replace(loadconfig.__prefix__, "", 1).replace(prefix, "", 1)

        tag = await self.bot.get_tag(message.guild.id, tag_name)
        check = await self.check_failure(tag, tag_name, message.guild.id)

        if check:
            return

        ptn = self.prefixed_tag_names(allow_default, prefix, tag)

        if tag and content in ptn:
            bucket = self.cd.get_bucket(message)
            retry_after = bucket.update_rate_limit()
            if retry_after:
                return await message.channel.send(":no_entry: | woah slow down there you're being rated limited.",
                                                  delete_after=3)

            return await send_tag_content(tag, message, self.bot)
        # invalidating the tag in the case the message was only the tag name with no prefix
        self.bot.tags_invalidate(message.guild.id, tag_name)

    @commands.group(invoke_without_command=True, aliases=["tags"])
    async def tag(self, ctx, member: discord.Member = None):
        """The main command for tags returns your current tags by itself or another member's."""

        member = member or ctx.author
        data = await ctx.db.fetch("SELECT tag_name from tags where user_id = $1 and guild_id = $2", member.id,
                                  ctx.guild.id)

        if data == []:
            return await ctx.send(f"> {member.name} currently has no tags created for this guild.")

        names = [f'\n> **{tag["tag_name"]}**' for tag in data]

        name_chunks = ctx.chunk(names, 10)

        for name_chunk in name_chunks:
            names = "".join(name for name in name_chunk)
            await ctx.paginator.add_page(f"> {member.name} current tags for **{str(ctx.guild)}**...\n> {names}")

        await ctx.paginator.paginate()

    @tag.command()
    async def create(self, ctx, *, name: TagNameConverter):
        """Create a customisable tag for this guild"""

        await self.create_tag(ctx, name, ".")

    @tag.command()
    async def claim(self, ctx, *, name):
        """Claim a tag if the tag owner has left the server"""

        data = await ctx.db.fetchrow(
            "SELECT tag_id, user_id FROM tags WHERE guild_id = $1 AND LOWER(tag_name) = $2",
            ctx.guild.id, name.lower())
        if data is None:
            return await ctx.send(f'A tag with the name of "{name}" does not exist.')

        try:
            member = ctx.guild.get_member(data["user_id"]) or await ctx.guild.fetch_member(data["user_id"])
        except discord.NotFound:
            member = None

        if member is not None:
            return await ctx.send(":no_entry: | tag owner is still in the server.")

        await ctx.pool.execute("UPDATE tags set user_id = $1 WHERE guild_id = $2 and LOWER(tag_name) = $3",
                               ctx.author.id, ctx.guild.id, name.lower())

        await ctx.send(f"> successfully transferred ownership of `{name}` to you.")

    @tag.command()
    async def raw(self, ctx, *, name):
        """Display a tag without markdown eg spoilers."""

        content = await ctx.db.fetchrow("SELECT content, nsfw from tags where LOWER(tag_name) = $1 and guild_id = $2",
                                        name.lower(), ctx.guild.id)

        if not content:
            return await ctx.send(f":no_entry: | could not find the tag {name}.")

        if content["nsfw"] and not ctx.channel.nsfw:
            return await ctx.send(":no_entry: | this tag can only be used in nsfw channels.", delete_after=4)

        await ctx.send(discord.utils.escape_markdown(content["content"]))

    @tag.command()
    async def info(self, ctx, *, name):
        """Get info on a tag"""
        name = name.lower()

        data = await ctx.db.fetchrow("SELECT * from tags where LOWER(tag_name) = $1 and guild_id = $2", name,
                                     ctx.guild.id)
        if not data:
            return await ctx.send(f"> A tag with name `{name}` does not exist.")

        nsfw = False if not data["nsfw"] else data["nsfw"]

        embed = discord.Embed(title=name,
                              color=self.bot.default_colors())

        member = ctx.guild.get_member(data["user_id"]) or await self.bot.fetch_user(data["user_id"])
        date = h.naturaltime(datetime.datetime.utcnow() - data["created_at"])
        embed.add_field(name="Owner", value=member.name, inline=False)
        embed.add_field(name="Nsfw", value=nsfw, inline=False)
        embed.add_field(name="Created", value=date, inline=False)
        embed.set_author(name=member.name, icon_url=member.avatar_url_as(static_format="png"))

        await ctx.send(embed=embed)

    @tag.command(aliases=["content", "details", "update"])
    async def update_content(self, ctx, name, *, content: commands.clean_content):
        """Update a tag's content encase the tag's name in quotes if it has spaces"""
        name = name.lower()

        check = await ctx.db.fetchval("SELECT tag_name FROM tags WHERE user_id = $1 and guild_id = $2",
                                      ctx.author.id, ctx.guild.id)

        if check is None:
            return await ctx.send(f":information_source: you do not have a tag for this guild create one with "
                                  f"{ctx.prefix}tag create name")

        check = await ctx.db.execute("""UPDATE tags SET content = $1 WHERE guild_id = $2 and user_id = $3 
                                        and LOWER(tag_name) = $4""",
                                     content, ctx.guild.id, ctx.author.id, name)

        if check[-1] == "0":
            return await ctx.send(f":no_entry: | could not edit the tag in question `{name}` do you own it "
                                  f"and it exists? `note you must encase a tag's name in quotes if it contains "
                                  f"spaces eg  {ctx.prefix}tag update \"hello world\" hi`")
        try:

            await ctx.send(f":information_source: | successfully updated tag with content `{content}`.")

        except discord.HTTPException:
            await ctx.send(f":information_source: | successfully updated tag but content too long to display.")

    @tag.command(ignore_extra=False)
    async def list(self, ctx):
        """Get a list of tags for the current guild"""

        tags = await ctx.db.fetch("select tag_name, user_id from tags where guild_id =  $1", ctx.guild.id)

        tags = [f"Tag name: **{tag['tag_name']}** created by "
                f"**{str(ctx.guild.get_member(tag['user_id']))}**" for tag in tags if tag['tag_name']]

        tags_chunks = ctx.chunk(tags, 10)

        if not tags_chunks:
            return await ctx.send("> Currently no tags for this guild exist.")

        for tags in tags_chunks:
            tags = "\n".join(tags)
            embed = discord.Embed(title="Tags for:", description=ctx.guild.name, colour=discord.Color.dark_magenta())
            embed.add_field(name='\uFEFF', value=tags)
            await ctx.paginator.add_page(embed)

        await ctx.paginator.paginate()

    @tag.group(invoke_without_command=True, aliases=["remove", "prune"])
    async def delete(self, ctx, *, name):
        """Delete a tag that you own
        Members with manage messages permissions can delete any tag."""
        name = name.lower()

        check = await self.bot.is_owner(ctx.author) or ctx.author.guild_permissions.manage_messages

        if check:
            deleted = await ctx.db.fetchrow("""DELETE from tags where guild_id = $1 and LOWER(tag_name)
                                            = $2 RETURNING tag_id""",
                                            ctx.guild.id, name)
        else:

            deleted = await ctx.db.fetchrow("""DELETE from tags where guild_id = $1 
                                             and LOWER(tag_name) = $2 and user_id = $3 RETURNING tag_id""",
                                            ctx.guild.id, name, ctx.author.id)

        if deleted is None:
            return await ctx.send(":no_entry: | tag deletion failed, either the tag doesn't exist or you lack "
                                  "the permissions to do so.")

        await ctx.send(f"> tag `{name}` successfully deleted.")

    @delete.command(name="all")
    async def delete_all(self, ctx, member: discord.Member):
        """Delete all of a member's tags"""

        check = await self.bot.is_owner(ctx.author) or ctx.author.guild_permissions.manage_messages

        if check:

            deleted = await ctx.db.fetch("DELETE from tags where guild_id = $1 and user_id = $2 RETURNING tag_id",
                                         ctx.guild.id, member.id)
            if deleted == []:
                return await ctx.send(f"> {member.name} has no tags to delete.")

            await self.invalidate_user_tags(ctx, member)
            await ctx.send(f"> successfully deleted {len(deleted)} from {member.name}.")

        await ctx.send(":no_entry: | you need manage message permissions for this command.")

    @tag.group(invoke_without_command=True)
    async def nsfw(self, ctx, nsfw: typing.Optional[bool] = True, *, name):
        """The main command for NSFW tags, by itself sets a tag to be only be usable in NSFW channels
        pass True for nsfw False to not make it NSFW **this command requires manage messages perms*"""
        name = name.lower()

        check = await ctx.db.fetchval("SELECT tag_name FROM tags WHERE LOWER(tag_name) = $1 and guild_id = $2",
                                      name, ctx.guild.id)

        if check is None:
            return await ctx.send(f"> The tag `{name}` does not exist.")

        check = await self.bot.is_owner(ctx.author) or ctx.author.guild_permissions.manage_messages

        if check:

            await ctx.db.execute("UPDATE tags SET nsfw = $1 where LOWER(tag_name) = $2 and guild_id = $3",
                                 nsfw, name.lower(), ctx.guild.id)

            if nsfw:
                return await ctx.send(f"> The tag {name} has been set to NSFW")

            await ctx.send(f"> The tag {name} has been set to not NSFW")

        else:

            await ctx.send(":no_entry: | you lack the permissions to make this tag NSFW.")

    @nsfw.command(name="all")
    async def nsfw_all(self, ctx, nsfw: typing.Optional[bool] = True, *, member: discord.Member):
        """Set all of a members tag to be NSFW or not NSFW."""

        check = await self.bot.is_owner(ctx.author) or ctx.author.guild_permissions.manage_messages

        if check:

            result = await ctx.db.execute("""UPDATE tags SET nsfw = $1 where user_id = $2 
                                             and guild_id = $3 RETURNING user_id""",
                                          nsfw, member.id, ctx.guild.id)

            if not result:
                return await ctx.send(f":no_entry: | {member.name} has no tags.")

            if nsfw:
                return await ctx.send(f"> set all of {member.name} tags to NSFW")

            await self.invalidate_user_tags(ctx, member)
            await ctx.send(f"> set all of {member.name} tags to not NSFW")

        else:
            await ctx.send(":no_entry: | you need manage message permissions for this command.")

    @tag.command()
    async def transfer(self, ctx, member: discord.Member, *, name):
        """Transfer a tag you own to another user"""
        name = name.lower()

        if member.bot:
            return await ctx.send(":no_entry: | can't give bots tags.")

        check = await ctx.db.fetchval("""SELECT tag_name FROM tags 
                                          where guild_id = $1 and user_id = $2 and LOWER(tag_name) = $3
                                          """, ctx.guild.id, ctx.author.id, name)

        if check is None:
            return await ctx.send(f":no_entry: | does the tag {name} exist and do you own it?")

        await ctx.db.execute("UPDATE tags SET user_id = $1 where guild_id = $2 and LOWER(tag_name) = $3",
                             member.id, ctx.guild.id, name)

        await ctx.send(f"> Successfully transferred ownership of the tag `{name}` to {member.name}.")

    @tag.command()
    async def search(self, ctx, *, name):
        """Search for tags that start with a name"""
        name = name.lower()

        result = await ctx.db.fetch("SELECT tag_name from tags where guild_id = $1 and LOWER(tag_name) like $2 || '%'",
                                    ctx.guild.id, name)

        if not result:
            return await ctx.send(f":no_entry: | could not find the tag {name}.")

        result = list(f"(**{name['tag_name']}**)" for name in result)
        results = ctx.chunk(result, 10)
        new_line = "\n"

        for result in results:
            await ctx.paginator.add_page(f"> Tags found that contained `{name}`:\n{new_line.join(result)}")

        await ctx.paginator.paginate()

    @update_content.after_invoke
    async def after_tag_update(self, ctx):
        self.bot.tags_invalidate(ctx.guild.id, ctx.args[-1])

    @delete.after_invoke
    @nsfw.after_invoke
    async def after_delete(self, ctx):
        self.bot.tags_invalidate(ctx.guild.id, ctx.kwargs["name"])


def setup(bot):
    n = Tags(bot)
    bot.add_cog(n)

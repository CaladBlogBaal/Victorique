import datetime
import typing

from collections import Counter

import asyncpg
import humanize as h

import discord
from discord.ext import commands

from config.utils.converters import TagNameConverter
from config.utils.menu import page_source
from config.utils.context import Context

import loadconfig


async def send_tag_content(tag: asyncpg.Record, message: discord.Message):
    if tag["nsfw"] and not message.channel.nsfw:
        return await message.channel.send(f"> This tag can only be used in NSFW channels.", delete_after=4)

    content = tag["content"]

    await message.channel.send(content)


class Tags(commands.Cog):
    """tag related commands to call a created tag do [guild prefix][tag name}"""

    def __init__(self, bot):
        self.bot = bot
        self.cd = commands.CooldownMapping.from_cooldown(1, 4, commands.BucketType.member)
        self.emotes = {1: "🥇", 2: "🥈", 3: "🥉"}

    async def invalidate_user_tags(self, ctx: Context, member: discord.Member):
        tag_names = await ctx.db.fetch("SELECT tag_name from tags where guild_id = $1 and user_id = $2",
                                       ctx.guild.id, member.id)
        for name in tag_names:
            self.bot.tags_invalidate(ctx.guild.id, name)

    @staticmethod
    @page_source()
    def tag_source(self, menu, entries: list):

        return "".join((f'\n> **{tag["tag_name"]}** (ID: {tag["tag_id"]})' for tag in entries))

    @staticmethod
    @page_source()
    def search_source(self, menu, entries: list):

        return f"> Tags found that contained `{self.input}`\n" + "\n".join((f"(**{tag['tag_name']}**)" for tag in entries))

    async def cog_check(self, ctx: Context):
        return ctx.guild is not None

    async def cog_before_invoke(self, ctx: Context):
        # acquire a connection to the pool before every command
        await ctx.acquire()

    async def get_member_stats(self, ctx: Context, member: discord.Member):
        query = """
                WITH stats AS (
                    SELECT tag_name, uses, tag_id,
                           RANK() OVER ( ORDER BY uses DESC) rank
                    FROM tags
                    WHERE guild_id = $1 and user_id = $2
                    )
                    SELECT tag_name, tag_id, uses, rank
                    FROM stats
                        """

        data = await ctx.db.fetch(query, ctx.guild.id, member.id)

        owned_tags = len(data)
        owned_tags_usage = sum(r["uses"] for r in data)

        total_tags_uses = await ctx.db.fetchval("""SELECT SUM(uses) FROM user_tag_usage WHERE guild_id = $1 and user_id 
                                                    = $2""",
                                                ctx.guild.id, member.id)

        embed = discord.Embed(title="Tag Stats",
                              color=self.bot.default_colors())

        embed.add_field(name="Owned Tags", value=h.intcomma(owned_tags), inline=True)
        embed.add_field(name="Owned Tags (used)", value=h.intcomma(owned_tags_usage), inline=True)
        embed.add_field(name="Total tags used", value=h.intcomma(total_tags_uses), inline=True)

        value = "\n".join(f"{self.emotes[r['rank']]}: {r['tag_name']} ({h.intcomma(r['uses'])} times)"
                          for r in data[:3]) or 0

        embed.add_field(name="Top Owned Tags", value=value)
        embed.set_author(name=member.name, icon_url=str(member.avatar.url))
        await ctx.send(embed=embed)

    async def get_guild_stats(self, ctx):
        query = """
            WITH stats AS (
                SELECT tag_name, nsfw, created_at, user_id, uses,
                       RANK() OVER ( ORDER BY uses DESC) rank
                FROM tags
                WHERE guild_id = $1
                )
                SELECT tag_name, nsfw, created_at, user_id, uses, rank
                FROM stats
                    """

        data = await ctx.db.fetch(query, ctx.guild.id)

        if not data:
            return await ctx.send("> Currently no tags for this guild exist.")

        top_creators = Counter(r["user_id"] for r in data).most_common(3)

        description = f"{len(data)} tags, {sum(r['uses'] for r in data)} tag uses"

        embed = discord.Embed(title="Tag Stats",
                              color=self.bot.default_colors())

        embed.description = description

        value = "\n".join(f"{self.emotes[i + 1]}: <@{t[0]}> ({h.intcomma(t[1])} tags)"
                          for i, t in enumerate(top_creators))
        embed.add_field(name="Top Tag Creators", value=value, inline=False)

        value = "\n".join(f"{self.emotes[r['rank']]}: {r['tag_name']} ({h.intcomma(r['uses'])} times)"
                          for r in data[:3])
        embed.add_field(name="Top Tags", value=value, inline=False)

        query = """
                    WITH stats AS (
                        SELECT user_id, uses,
                               RANK() OVER ( ORDER BY uses DESC) rank
                        FROM user_tag_usage
                        WHERE guild_id = $1
                        LIMIT 3
                        )
                        SELECT user_id, uses, rank
                        FROM stats
                            """

        data = await ctx.db.fetch(query, ctx.guild.id)

        value = "\n".join(f"{r['rank']}: <@{r['user_id']}> ({h.intcomma(r['uses'])} used)" for r in data)

        embed.add_field(name="Top Users", value=value, inline=False)

        await ctx.send(embed=embed)

    @staticmethod
    async def create_tag(ctx: Context, name: TagNameConverter, content: str):

        try:
            await ctx.pool.fetchval("""INSERT INTO tags (tag_name, guild_id, user_id, content, created_at) 
                                       VALUES ($1, $2, $3, $4, $5)""",
                                    name, ctx.guild.id, ctx.author.id, content,
                                    ctx.message.created_at.replace(tzinfo=None))

        except asyncpg.UniqueViolationError:
            return await ctx.send(f":information_source: | tag name already exists")

        if len(name.split(" ")) >= 2:
            name = f"\"{name}\""

        await ctx.send(f":information_source: | created new tag `{name}` to add content to this tag do "
                       f"`{ctx.prefix}tag update {name} <content here>`.")

    @staticmethod
    def prefixed_tag_names(allow_default: bool, prefix: str, tag: asyncpg.Record):
        if allow_default:
            check = (f"{prefix}{tag['tag_name']}", f"{loadconfig.__prefix__}{tag['tag_name']}")

        else:
            check = (f"{prefix}{tag['tag_name']}",)

        return check

    async def check_failure(self, tag: asyncpg.Record, name: str, guild_id: int):
        if not tag:
            # if it failed to find a tag invalidate the cache for it
            self.bot.tags_invalidate(guild_id, name)
            return True
        return False

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        async with self.bot.pool.acquire() as con:
            tups = [(m.id, guild.id) for m in guild.members if not m.bot]

            await con.executemany("""INSERT INTO user_tag_usage (user_id, guild_id) 
                                     VALUES ($1, $2) ON CONFLICT DO NOTHING;""", tups)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # still crude as hell
        # getting the context to check if the message contains a prefix
        ctx = await self.bot.get_context(message)

        if not message.guild or message.author.bot or not ctx.prefix:
            return

        data = await self.bot.get_guild_prefix(message.guild.id)

        allow_default = False

        if data["prefix"]:
            allow_default = data["allow_default"]

        content = ctx.message.content.lower()

        tag_name = content.replace(ctx.prefix, "", 1)

        tag = await self.bot.get_tag(message.guild.id, tag_name)
        check = await self.check_failure(tag, tag_name, message.guild.id)

        if check:
            return

        ptn = self.prefixed_tag_names(allow_default, ctx.prefix, tag)

        if content in ptn:
            bucket = self.cd.get_bucket(message)
            retry_after = bucket.update_rate_limit()
            if retry_after:
                return await message.channel.send(":no_entry: | woah slow down there you're being rated limited.",
                                                  delete_after=3)

            await send_tag_content(tag, message)
            await ctx.acquire()
            await ctx.db.execute("UPDATE tags SET uses = uses + 1 WHERE tag_name = $1 AND guild_id = $2",
                                 tag_name, message.guild.id)

            await ctx.db.execute("UPDATE user_tag_usage SET uses = uses + 1 WHERE user_id = $1 AND guild_id = $2",
                                 message.author.id, message.guild.id)

            await ctx.release()

    @commands.group(invoke_without_command=True, aliases=["tags"])
    async def tag(self, ctx: Context, member: discord.Member = None):
        """The main command for tags returns your current tags by itself or another member's."""

        member = member or ctx.author
        data = await ctx.db.fetch("SELECT tag_name, tag_id from tags where user_id = $1 and guild_id = $2", member.id,
                                  ctx.guild.id)

        if data == []:
            return await ctx.send(f"> {member.name} currently has no tags created for this guild.")
        pages = ctx.menu(self.tag_source(data))
        await pages.start(ctx)

    @tag.command()
    async def create(self, ctx: Context, *, name: TagNameConverter):
        """Create a customisable tag for this guild"""

        await self.create_tag(ctx, name, ".")

    @tag.command()
    async def claim(self, ctx: Context, *, name: str):
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
    async def raw(self, ctx: Context, *, name: str):
        """Display a tag without markdown eg spoilers."""

        content = await ctx.db.fetchrow("SELECT content, nsfw from tags where LOWER(tag_name) = $1 and guild_id = $2",
                                        name.lower(), ctx.guild.id)

        if not content:
            return await ctx.send(f":no_entry: | could not find the tag {name}.")

        if content["nsfw"] and not ctx.channel.nsfw:
            return await ctx.send(":no_entry: | this tag can only be used in nsfw channels.", delete_after=4)

        await ctx.send(discord.utils.escape_markdown(content["content"]))

    @tag.command()
    async def stats(self, ctx, member: typing.Union[discord.Member, discord.User] = None):
        """Get statistics for the current guild or a guild member"""
        if not member:
            return await self.get_guild_stats(ctx)

        await self.get_member_stats(ctx, member)

    @tag.command()
    async def info(self, ctx: Context, *, name: str):
        """Get info on a tag"""
        name = name.lower()

        query = """
        WITH stats AS (
            SELECT tag_name, nsfw, created_at, user_id, uses,
                   RANK() OVER ( ORDER BY uses DESC) rank
            FROM tags
            WHERE guild_id = $1
            )
            SELECT tag_name, nsfw, created_at, user_id, uses, rank
            FROM stats
            WHERE LOWER(tag_name) = $2
                """

        data = await ctx.db.fetchrow(query, ctx.guild.id, name)

        if not data:
            return await ctx.send(f"> A tag with name `{name}` does not exist.")

        embed = discord.Embed(title=name,
                              color=self.bot.default_colors())

        member = ctx.guild.get_member(data["user_id"]) or await self.bot.fetch_user(data["user_id"])
        date = h.naturaltime(datetime.datetime.utcnow() - data["created_at"])
        uses = h.intcomma(data["uses"])
        embed.add_field(name="Owner", value=member.name, inline=False)
        embed.add_field(name="Nsfw", value=data["nsfw"], inline=False)
        embed.add_field(name="Created", value=date, inline=False)
        embed.add_field(name="Uses: ", value=uses, inline=False)
        embed.set_author(name=member.name, icon_url=member.avatar.replace(static_format="png"))
        embed.add_field(name="Rank", value=data["rank"])

        await ctx.send(embed=embed)

    @tag.command(aliases=["content", "details", "update"])
    async def update_content(self, ctx: Context, name: str, *, content: commands.clean_content):
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

    @tag.command()
    async def random(self, ctx):
        """get a random tag"""
        tag = await ctx.db.fetchrow("SELECT tag_name, content FROM tags TABLESAMPLE SYSTEM(10) WHERE guild_id = $1",
                                    ctx.guild.id)

        if not tag:
            return await ctx.send("> Currently no tags for this guild exist.")

        await ctx.send(f"Tag Name: {tag['tag_name']}\n{tag['content']}")

    @tag.command(ignore_extra=False)
    async def list(self, ctx: Context):
        """Get a list of tags for the current guild"""
        query = """
            WITH stats AS (
                SELECT tag_name, user_id,
                       RANK() OVER ( ORDER BY uses DESC) rank
                FROM tags
                WHERE guild_id = $1
                )
                SELECT tag_name, user_id, rank
                FROM stats
                    """

        tags = await ctx.db.fetch(query, ctx.guild.id)

        if not tags:
            return await ctx.send("> Currently no tags for this guild exist.")

        tags = [f"Tag name: **{tag['tag_name']}** created by "
                f"**{str(ctx.guild.get_member(tag['user_id']))}**" for tag in tags if tag['tag_name']]

        entries = []
        tags_chunks = ctx.chunk(tags, 10)

        for tags in tags_chunks:
            tags = "\n".join(tags)
            embed = discord.Embed(title="Tags for:", description=ctx.guild.name, colour=discord.Color.dark_magenta())
            embed.add_field(name='\uFEFF', value=tags)
            entries.append(embed)

        pages = ctx.menu(ctx.list_source(entries))
        await pages.start(ctx)

    @tag.group(invoke_without_command=True, aliases=["remove", "prune"])
    async def delete(self, ctx: Context, *, name: str):
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
    async def delete_all(self, ctx: Context, member: discord.Member):
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
    async def nsfw(self, ctx, nsfw: typing.Optional[bool] = True, *, name: str):
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
    async def nsfw_all(self, ctx: Context, nsfw: typing.Optional[bool] = True, *, member: discord.Member):
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
    async def transfer(self, ctx: Context, member: discord.Member, *, name: str):
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
    async def search(self, ctx: Context, *, name: str):
        """Search for tags that start with a name"""
        name = name.lower()

        results = await ctx.db.fetch("SELECT tag_name from tags where guild_id = $1 and LOWER(tag_name) like $2 || '%'",
                                     ctx.guild.id, name)

        if not results:
            return await ctx.send(f":no_entry: | could not find the tag {name}.")

        self.search_source.name = name
        pages = ctx.menu(self.search_source(results))
        await pages.start(ctx)

    @update_content.after_invoke
    async def after_tag_update(self, ctx: Context):
        self.bot.tags_invalidate(ctx.guild.id, ctx.args[-1])

    @delete.after_invoke
    @nsfw.after_invoke
    async def after_delete(self, ctx: Context):
        self.bot.tags_invalidate(ctx.guild.id, ctx.kwargs["name"])


async def setup(bot):
    n = Tags(bot)
    await bot.add_cog(n)

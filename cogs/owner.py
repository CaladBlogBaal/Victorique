import asyncio
import sys
import platform
import os
import pathlib
import inspect

import psutil
import humanize as h

from collections import namedtuple

import discord
from discord.ext import commands, tasks

from cogs.utils.imageboards import default_source

from config.utils.menu import page_source
from config.utils.converters import TriviaCategoryConverter, TriviaDiffcultyConventer, FishRarityConventer
from config.utils.context import Context


@tasks.loop(hours=24)
async def random_images(ctx, tags="rating:safe score:>100"):
    post = namedtuple("post", "preview sources tags full_image")
    params = {"random": "true", "tags": tags}
    js = await ctx.bot.fetch("https://danbooru.donmai.us/posts.json", params=params)
    results = []
    for picture in js:
        result = post(picture.get("file_url"), picture.get("source", " "),
                      picture.get("tag_string"), picture.get("file_url"))

        results.append(result)

    pages = ctx.global_menu(default_source(results))
    await pages.start(ctx)


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    @page_source(per_page=24)
    def source_source(self, menu, entries):
        return f"```py\n{''.join(entries)}```"

    @commands.command()
    async def invite(self, ctx: Context):
        """Get the bot's invite url"""

        await ctx.send(discord.utils.oauth_url(ctx.me.id, permissions=discord.Permissions(1342515266)))

    @commands.command()
    async def source(self, ctx: Context, *, command_name=None):
        """Get the source for a command or the bot's source"""
        # idea pretty much taken from
        # https://github.com/Rapptz/RoboDanny/blob/99a8545b8aa86c75701f131a29d61bbc2f703eb6/cogs/meta.py#L329
        git_url = "https://github.com/CaladBlogBaal/Victorique"

        if not command_name:
            return await ctx.send(git_url)

        command = self.bot.get_command(command_name)
        if not command:
            return await ctx.send(f"> couldn't find {command_name}")

        src = command.callback.__code__

        rpath = src.co_filename

        try:
            source_lines, firstlineno = inspect.getsourcelines(src)
            location = os.path.relpath(rpath).replace('\\', '/')

            if r"discord/ext" not in location and "jishaku" not in location:
                final_url = f"<{git_url}/tree/master/{location}#L{firstlineno}-L{firstlineno + len(source_lines) - 1}>"
                await ctx.send(final_url)

            pages = ctx.menu(self.source_source(source_lines))
            await pages.start(ctx)
        except OSError:
            await ctx.send(f"> could not get source code for {command_name}")

    @commands.command()
    async def about(self, ctx: Context):
        """Get info about the bot."""

        member_online = len(list(m for m in self.bot.get_all_members() if m.status.value in ("online", "dnd")))
        member_offline = len(list(m for m in self.bot.get_all_members() if m.status.value == "offline"))

        ignore_these = (604816023291428874, 604688858591920148, 604688905190637598, 604688959640961038)
        guild_count = len(list(g for g in self.bot.guilds if g.id not in ignore_these))
        invite_url = f"[invite url]({discord.utils.oauth_url(ctx.me.id, permissions=discord.Permissions(1342515266))})"
        # pretty much a modified version of the jishaku, jsk/jishaku command
        proc = psutil.Process()
        mem = proc.memory_full_info()
        command_count = len({command for command in ctx.bot.walk_commands() if "jishaku" not in
                             command.name and "jishaku" not in command.qualified_name})
        py_version = ".".join(str(n) for n in sys.version_info[:3])
        embed = discord.Embed(color=self.bot.default_colors(), title="", description=f"")
        embed.add_field(name="Basic:", value=f"**OS**: {platform.platform()}\n**Hostname: **OVH\n**Python Version: **"
                                             f"{py_version}\n**Links**: {invite_url}")
        embed.add_field(name="Dev:", value="CaladWoDestroyer#9313")
        embed.add_field(name="Library:", value=f"Discord.py {discord.__version__}")
        embed.add_field(name="Commands:", value=str(command_count))
        embed.add_field(name="Guilds:", value=str(guild_count))
        embed.add_field(name="RAM:", value=f"Using {h.naturalsize(mem.rss)}")
        embed.add_field(name="VRAM:", value=str(h.naturalsize(mem.vms) + f" of which {str(h.naturalsize(mem.uss))}"
                                                                         f"\nis unique to this process"))
        embed.add_field(name="Ping", value=round(self.bot.latency * 1000, 2))
        # get these emotes by joining the discord.py server
        embed.add_field(name="Members", value=f"<:status_online:596576749790429200> Online: {member_online}\n"
                                              f"<:status_offline:596576752013279242> Offline: {member_offline}\n")
        embed.add_field(name="Unique Members", value=str(len(self.bot.users)))
        await ctx.send(embed=embed)


class OwnerCog(commands.Cog, name="Owner Commands"):
    """Owner only commands"""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    @page_source(per_page=5)
    def query_source(self, menu, entries):
        # temporary
        return f"```\n{entries}```"

    async def cog_unload(self):
        random_images.cancel()

    async def cog_check(self, ctx: Context):

        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner("begone thot.")

        return True

    @commands.command(name="close", hidden=True)
    async def __close(self, ctx: Context):
        """Closes the bot"""
        await ctx.send("*shutting down...*")
        await asyncio.sleep(1)
        await self.bot.logout()

    @commands.command(hidden=True, name="bot_avatar")
    async def __edit_bot_avatar(self, ctx: Context, url: str):
        """Edits the bots avatar"""

        async with self.bot.session.get(url) as response:
            image_bytes = await response.read()
            await ctx.bot.user.edit(avatar=image_bytes)
            await asyncio.sleep(2)
            await ctx.send(f"<:me:589614537775382552>"
                           f"<:and:589614537867657235>"
                           f"<:the:589614537309945878>"
                           f"<:boys:589614537490300940>"
                           f" | new bot avatar is \n{self.bot.user.avatar_url}")

    @commands.command()
    async def count(self, ctx: Context):
        """Count lines of code"""

        def get_total(file_dir, check_sql=False):
            line_total = 0
            with open(file_dir, "r", encoding="ISO-8859-1") as file:
                for line in file:

                    if not line.strip().startswith("#") and len(line.strip()) > 0:
                        # this feels hacky
                        if check_sql:

                            if "ctx.db" in line:
                                line_total += 1

                        elif "ctx.db" not in line:
                            line_total += 1

            return line_total

        py_line_count = 0
        sql_line_count = 0
        json_file_count = 0

        py_file_amount = 0
        json_file_amount = 0

        env = "venv"

        for path, _, files in os.walk("."):
            for name in files:
                file_dir = str(pathlib.PurePath(path, name))
                if not name.endswith((".py", ".json")) or env in file_dir:
                    continue

                if name.endswith(".py"):
                    py_file_amount += 1
                    py_line_count += get_total(file_dir)
                    sql_line_count += get_total(file_dir, True)

                elif name.endswith(".json"):
                    json_file_amount += 1
                    json_file_count += get_total(file_dir)

        await ctx.send(f"total lines of **Python** code **{py_line_count}** spread across **{py_file_amount} files**"
                       f" with **{sql_line_count}** lines of **SQL**, and **{json_file_count}** lines of **JSON** "
                       f"spread across **{json_file_amount} files** for this bot.")

    @commands.command()
    async def query(self, ctx: Context, *, query):
        """Return rows from the postgres database"""

        rows = await ctx.db.fetch(query)
        pages = ctx.menu(self.query_source(rows))
        await pages.start(ctx)

    @commands.command()
    async def update(self, ctx: Context, *, _query):
        """Update rows in the postgres database"""
        async with ctx.acquire():
            await ctx.db.execute(_query)

        await ctx.send("successfully updated.")

    @commands.command()
    async def add_fish(self, ctx:  Context, fish_emote: discord.Emoji, rarity_id: FishRarityConventer):
        """Add a fish to the fish table"""
        async with ctx.db.acquire():
            await ctx.db.execute("""INSERT INTO fish (fish_name, rarity_id) VALUES
                                ($1, $2) ON CONFLICT DO NOTHING""", str(fish_emote), rarity_id)

        await ctx.send("successfully updated.")

    @commands.command()
    async def add_default_fish(self, ctx):
        """Add the default fish"""
        async with ctx.db.acquire():
            await ctx.db.execute("""
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:MutsukiIcon:603142310686883860>', 1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:BeagleIcon:603139176417722368>', 2) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:SaratogaIcon:603137225663709204>', 3) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:LaffeyIcon:603137082373963797>', 3) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:JavelinIcon:603136994410889216>', 3) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:HiryuuIcon:603771548310175808>', 3) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:AkashiIcon:603140892823650307>', 4) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:IllustriousIcon:603141500737421313>', 4) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:AkagiIcon:603137320266498059>', 4) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:KagaIcon:603137459320127543>', 4) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:Saint_LouisIcon:605216882106040342>', 5) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:IbukiIcon:605216888326324225>', 5) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:KitakazeIcon:605216894030446593>', 5) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:GeorgiaIcon:605216899923443732>', 5) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:RoonIcon:605216905736880129>', 5) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:GascogneIcon:605216915597557771>', 5) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:IzumoIcon:605216921725566992>', 5) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:HMS_NeptuneIcon:605216928125943818>', 5) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:SeattleIcon:605216934203752448>', 5) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, rarity_id) VALUES ('<:MonarchIcon:606868127648710689>', 5) ON CONFLICT DO NOTHING;
            """)

        await ctx.send("Successfully added")

    @commands.group(invoke_without_command=True, aliases=["da"])
    async def daily_anime(self, ctx: Context, *, tags=None):
        """Get x amount of random images from danbooru and send them to the current channel periodically."""
        try:

            if tags:
                random_images.start(ctx, tags)

            else:

                random_images.start(ctx)

            await ctx.send("> task started.")

        except RuntimeError:
            await ctx.send(":no_entry: task is already launched.")

    @daily_anime.command()
    async def cancel(self, ctx: Context):
        """Cancel the random images task"""
        random_images.cancel()
        await ctx.send("> successfully cancelled.")

    @daily_anime.command(aliases=["ci"])
    async def change_interval(self, ctx: Context, hours: float):
        """Change the interval"""
        random_images.cancel()
        random_images.change_interval(hours=hours)
        await ctx.send(f"> successfully changed to `{hours}` hours restart the task with `{ctx.prefix}daily_anime`")

    @commands.group(invoke_without_command=True)
    async def question(self, ctx: Context):
        """The main command for updaing the trivia tables does nothing by itself"""

    @question.command()
    async def add(self, ctx: Context, category: TriviaCategoryConverter, difficulty: TriviaDiffcultyConventer,
                  type_, *, question):
        """Adds a question to the question table."""
        categories = (cat_id["category_id"] for cat_id in await ctx.db.fetch("SELECT category_id from category"))
        if category not in categories:
            return await ctx.send(":no_entry: | Invalid category was passed.")

        async with ctx.db.acquire():
            await ctx.db.execute("""INSERT INTO question (category_id, content, difficulty, type)
                                     VALUES ($1,$2,$3,$4)""", category, question, difficulty, type_)

        await ctx.send(f"> successfully updated with question `{question}`.")

    @question.command()
    async def delete(self, ctx: Context, *, question):
        """Delete a question and it's answers."""

        async with ctx.db.acquire():
            check = await ctx.db.execute("""DELETE FROM question 
                                          where LOWER(content) = $1 RETURNING question""", question.lower())

            if check == "DELETE 0":
                return await ctx.send(f":no_entry: | The question `{question}` does not exist.")

        await ctx.send("> successfully updated.")

    @question.command()
    async def add_answer(self, ctx: Context, content: str, is_correct: bool, *, question: str):
        """Add an answer to a existing question."""
        question_id = await ctx.db.fetchval("SELECT question_id from question where LOWER(content) = $1",
                                            question.lower())
        if not question_id:
            return await ctx.send(":no_entry: This question doesn't exist.")

        async with ctx.db.acquire():
            await ctx.db.execute("""INSERT INTO answer (question_id, content, is_correct) 
                                     VALUES ($1,$2,$3) ON CONFLICT DO NOTHING""", question_id, content, is_correct)

        await ctx.send("> successfully updated.")

    @question.command()
    async def delete_answer(self, ctx: Context, question: str, *, answer: str):
        """Delete an answer for a question."""
        question = await ctx.db.fetchval("SELECT question_id from question where content = $1", question)

        if not question:
            return await ctx.send(f":no_entry: | a question with id `{question}` does not exist.")

        async with ctx.db.acquire():
            check = await ctx.db.execute("""DELETE FROM answer where question_id = $1 and LOWER(content) = $2 
                                             RETURNING answer""", question, answer.lower())

            if check == "DELETE 0":
                return await ctx.send(f"The answer `{answer}` does not exist.")

        await ctx.send("> successfully updated.")


async def setup(bot):
    await bot.add_cog(OwnerCog(bot))
    await bot.add_cog(Info(bot))

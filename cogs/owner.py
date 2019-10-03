import asyncio
import sys
import platform
import os
import pathlib
import json
import inspect

import psutil
import humanize as h

import discord
from discord.ext import commands, tasks

from config.utils.paginator import Paginator, WarpedPaginator


@tasks.loop(seconds=86400)
async def random_images(ctx, amount):
    gb = "gb"
    db = "db"
    kc = "kc"
    ye = "ye"
    apn = "apn"
    image_boards = [gb, kc, ye, apn, db]

    for board in image_boards:
        for _ in range(amount):

            await ctx.invoke(ctx.bot.get_command(board))


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def invite(self, ctx):
        """Get the bot's invite url"""

        await ctx.send(discord.utils.oauth_url(ctx.me.id, discord.Permissions(1342515266)))

    @commands.command()
    async def source(self, ctx, *, command_name=None):
        """Get the source for a command or the bot's source"""
        # idea pretty much taken from
        # https://github.com/Rapptz/RoboDanny/blob/99a8545b8aa86c75701f131a29d61bbc2f703eb6/cogs/meta.py#L329
        git_url = "https://github.com/CaladBlogBaal/Victorique"

        if not command_name:
            return await ctx.send(git_url)

        p = Paginator(ctx)
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

            source_lines = ctx.chunk(source_lines, 24)

            for chunk in source_lines:
                source = "```py\n"
                source += "".join(chunk)
                source += "\n```"
                await p.add_page(source)

            await p.paginate()
        except OSError:
            await ctx.send(f"> could not get source code for {command_name}")

    @commands.command()
    async def about(self, ctx):
        """Get info about the bot."""

        member_online = len(list(m for m in self.bot.get_all_members() if m.status.value in ("online", "dnd")))
        member_offline = len(list(m for m in self.bot.get_all_members() if m.status.value == "offline"))

        ignore_these = (604816023291428874, 604688858591920148, 604688905190637598, 604688959640961038)
        guild_count = len(list(g for g in self.bot.guilds if g.id not in ignore_these))
        invite_url = "[invite url](https://discordapp.com" \
                     "/oauth2/authorize?client_id=558747464161820723&scope=bot&permissions=1342564418)"

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
        await ctx.send(embed=embed)


class OwnerCog(commands.Cog, name="Owner Commands"):
    """Owner only commands"""

    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):

        if not await self.bot.is_owner(ctx.author):
            raise commands.NotOwner("begone thot.")

        return True

    @commands.command(name="close", hidden=True)
    async def __close(self, ctx):
        """Closes the bot"""
        await ctx.send("*shutting down...*")
        await asyncio.sleep(1)
        await self.bot.logout()

    @commands.command(hidden=True, name="bot_avatar")
    async def __edit_bot_avatar(self, ctx, url: str):
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
    async def count(self, ctx):
        """Count lines of code"""

        def get_total(file_dir, check_sql=False):
            line_total = 0
            with open(file_dir, "r", encoding="ISO-8859-1") as file:
                for line in file:

                    if not line.strip().startswith("#") and len(line.strip()) > 0:
                        # this feels hacky
                        if check_sql:

                            if "ctx.con" in line:
                                line_total += 1

                        elif "ctx.con" not in line:
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

    @commands.command(aliases=["usj"])
    async def update_ship_json(self, ctx, *args):
        """Update the azur lane ship json"""
        keys = ['name', 'nation', 'rarity', 'type', 'hp', 'armor_type',
                'reload', 'fp', 'tp', 'evasion', 'aa', 'airp', 'oil',
                'asw', 'speed', 'luck', 'hit', 'eff', 'secff', 'trieff',
                'type1', 'type2', 'type3', 'plane1', 'plane2', 'plane3',
                'aaeff', 'aaeff2', 'oxy']

        ship_json = dict(zip(keys, args))
        ship_json["rarity"] = ship_json["rarity"].replace("_", " ")

        with open(r"settings\ship_list.json", "r") as f:
            ship_json_list = json.load(f)
            ship_json_list.append(ship_json)

        with open(r"settings\ship_list.json", "w") as f:
            json.dump(ship_json_list, f, indent=4)

        await ctx.send(f"Update completed new dict\n {ship_json} \n was added")

    @commands.command()
    async def query(self, ctx, *, _query):
        """Return rows from the postgres database"""
        wp = WarpedPaginator(ctx)
        _query = _query
        rows = await ctx.con.fetch(_query)

        await wp.add_page(str(rows))
        await wp.paginate()

    @commands.command()
    async def update(self, ctx, *, _query):
        """Update rows in the postgres database with a transaction"""
        async with ctx.con.transaction():
            await ctx.con.execute(_query)

        await ctx.send("successfully updated.")

    @commands.command()
    async def add_fish(self, ctx, fish_emote, rarity_id):
        """Add a fish to the fish table"""
        async with ctx.con.transaction():
            await ctx.con.execute("""INSERT INTO fish (fish_name, bait_id) VALUES
                                ($1, $2) ON CONFLICT DO NOTHING""", fish_emote, rarity_id)

        await ctx.send("successfully updated.")

    @commands.command()
    async def add_default_fish(self, ctx):
        """Add the default fish"""
        async with ctx.con.transaction():
            await ctx.con.execute("""
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:MutsukiIcon:603142310686883860>', 1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:BeagleIcon:603139176417722368>', 1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:SaratogaIcon:603137225663709204>', 2) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:LaffeyIcon:603137082373963797>', 2) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:JavelinIcon:603136994410889216>', 2) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:HiryuuIcon:603771548310175808>', 2) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:AkashiIcon:603140892823650307>', 3) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:IllustriousIcon:603141500737421313>', 3) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:AkagiIcon:603137320266498059>', 3) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:KagaIcon:603137459320127543>', 3) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:Saint_LouisIcon:605216882106040342>', -1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:IbukiIcon:605216888326324225>', -1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:KitakazeIcon:605216894030446593>', -1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:GeorgiaIcon:605216899923443732>', -1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:RoonIcon:605216905736880129>', -1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:GascogneIcon:605216915597557771>', -1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:IzumoIcon:605216921725566992>', -1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:HMS_NeptuneIcon:605216928125943818>', -1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:SeattleIcon:605216934203752448>', -1) ON CONFLICT DO NOTHING;
    INSERT INTO fish (fish_name, bait_id) VALUES ('<:MonarchIcon:606868127648710689>', -1) ON CONFLICT DO NOTHING;
            """)

    @commands.group(invoke_without_command=True, aliases=["da"])
    @commands.dm_only()
    async def daily_anime(self, ctx, amount: int = 2):
        """Get random images from danbooru, gelbooru, anime-pictures.net and yande.re"""

        if not random_images.current_loop != 1:
            return await ctx.send("> task is already running.")

        random_images.start(ctx, amount)
        await ctx.send("> task started.")

    @daily_anime.command()
    async def cancel(self, ctx):
        """Cancel the random images task"""
        random_images.cancel()
        await ctx.send("> successfully cancelled.")

    @daily_anime.command(aliases=["ci"])
    async def change_interval(self, ctx, seconds: int):
        """Change the interval"""
        random_images.cancel()
        random_images.change_interval(seconds=seconds)
        await ctx.send(f"> successfully changed to `{seconds}` seconds restart the task with `{ctx.prefix}daily_anime`")


def setup(bot):
    bot.add_cog(OwnerCog(bot))
    bot.add_cog(Info(bot))

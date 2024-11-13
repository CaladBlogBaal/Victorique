import asyncio
import typing
import contextlib
import random
import datetime
from asyncio import Lock
from typing import Union, Tuple

import asyncpg
import humanize as h

from collections import namedtuple

import discord
from discord.ext import commands, tasks

from cogs.utils.games import ShuntingYard
from config.utils.checks import private_guilds_check
from config.utils.converters import DieConventer
from config.utils.context import Context


class Curse(commands.Cog):
    """Curse related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.emotes = {1: "🥇", 2: "🥈", 3: "🥉"}
        self.bot = bot
        self.bot_initiated_changes_lock = Lock()
        self.bot_initiated_changes = set()  # A set to track bot-initiated nickname changes
        self.nickname_locks = {}

    async def cog_command_error(self, ctx, error):
        # reset cooldown if an error is raised during the command
        if ctx.command.qualified_name == "curse":
            await self.reset_cooldown(ctx, ctx.author.id, ctx.guild.id)

    async def execute_with_retries(self, con: asyncpg.pool.PoolConnectionProxy,
                                   query: str, *args, max_retries=5, max_delay=6):
        delay = 1
        for attempt in range(max_retries):
            try:
                async with con.transaction():
                    # Use an advisory lock to prevent race conditions
                    await con.execute("SELECT pg_advisory_xact_lock($1)", args[0])
                    return await con.fetch(query, *args[1:])
            except asyncpg.exceptions.DeadlockDetectedError:
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)  # Backoff delay before retrying
                    delay = min(max_delay, delay * 2) + random.uniform(0, 1)
                else:
                    raise  # Re-raise the exception if the maximum number of retries is reached

    async def reset_cooldown(self, ctx: Context, user_id: int, guild_id) -> str:
        query = "UPDATE cursed_user SET curse_cooldown = null WHERE user_id =  $1 and curse_at = $2"
        return await ctx.db.execute(query, user_id, guild_id)

    async def retry_with_backoff(self, func, retries=3, initial_delay=1, max_delay=10, *args, **kwargs):
        delay = initial_delay
        for attempt in range(retries):
            try:
                return await func(*args, **kwargs)

            except discord.errors.Forbidden:
                raise commands.BadArgument("An error occurred trying to edit a nickname, probably due role hierarchy")
            except (discord.HTTPException, Exception) as e:
                if attempt == retries - 1:
                    raise e
                await asyncio.sleep(delay)
                # multiplies the current delay by 2, doubling it each time the retry is attempted, with jitter
                # to spread out retries
                delay = min(max_delay, delay * 2) + random.uniform(0, 1)

    async def edit_nickname(self, target: discord.Member, name: str):
        lock = self.nickname_locks.setdefault(target.id, Lock())

        async def _edit_nick():
            async with lock:
                # Track the bot-initiated change
                async with self.bot_initiated_changes_lock:
                    self.bot_initiated_changes.add(target.id)

                try:
                    await target.edit(nick=name)
                finally:
                    # Make sure to remove the ID from tracking after the change
                    async with self.bot_initiated_changes_lock:
                        self.bot_initiated_changes.remove(target.id)
                    # Clean up the lock if no other task is waiting for it
                    if lock.locked():
                        self.nickname_locks.pop(target.id, None)

        await self.retry_with_backoff(_edit_nick)

    def calculate_critical_attack(self, attacker: int, defender: int) -> (str, int):
        if defender == 1 and attacker == 20:
            return ":dart: Nat 20 Critical attack against a critical failure! :dart:\n", 168
        elif attacker == 20:
            return ":dart: Nat 20 Critical hit! :dart:\n", 24
        elif defender == 1:
            return ":x: Critical defending failure! :x:\n", 24
        else:
            return "", 2

    def calculate_defense(self, attacker: int, defender: int, author_name: str) -> (str, int, int):
        if defender == 20:
            if attacker == 1:
                return f"...and it ended up being reflected back at {author_name}!", 168, 168
            else:
                return f"...and it ended up hitting someone else by mistake!", 2, 2
        elif attacker == 1:
            return ":x: Critical attacking failure! :x:\n", 24, 24
        else:
            return "", 2, 2

    async def resolve_equal_scenario(self, attacker: int, defender: int, member: discord.Member,
                                     nickname: str, author: discord.Member) -> (str, datetime.datetime):
        cooldown = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(hours=2)
        curse_time = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(hours=1)
        now = discord.utils.utcnow().replace(tzinfo=None)

        if attacker == defender:
            duration = h.naturaltime(now - curse_time)
            message = (
                ":crossed_swords: Both sides have gotten hurt due to an equal exchange.\n"
                f":white_check_mark: (Attacker: 1d20 ({attacker}) = {attacker}) vs. "
                f"(Defender: 1d20 ({defender}) = {defender})\n"
                f"Cursed {member.mention}'s to `{nickname}` until `{duration}`.\n"
                f"Cursed {author.mention}'s to `{nickname}` for {duration}.\n"
                f"Your ability to curse is on cooldown until {h.naturaltime(cooldown)}."
            )

            return message, curse_time

    def resolve_attack_scenario(self, attacker: int, defender: int, member: discord.Member,
                                nickname: str, cooldown: datetime.datetime) -> (str, datetime.datetime):

        critical_message, curse_hours = self.calculate_critical_attack(attacker, defender)
        curse_time = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(hours=curse_hours)
        message = self.format_message(member.mention, nickname, attacker,
                                      defender, cooldown, True, curse_time, starter_message=critical_message)
        return message, curse_time

    async def resolve_defense_scenario(self, ctx, attacker: int, defender: int, member: discord.Member,
                                       nickname: str) -> (str, datetime.datetime, datetime.datetime):

        message, curse_hours, cooldown_hours = self.calculate_defense(attacker, defender, ctx.author.mention)

        cooldown = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(hours=cooldown_hours)
        curse_time = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(hours=curse_hours)

        # Handle nickname editing and random member selection
        if "hitting someone else" in message:
            random_member = await self.get_random_active_member(ctx, member) or ctx.author
            message = message.replace("someone else", random_member.mention)
            # curse them
            async with ctx.acquire() as con:
                await self.curse_target(ctx, con, random_member, nickname, curse_time)

        message = self.format_message(
            member.mention, nickname, attacker, defender, cooldown, False, curse_time, msg=message
        )

        return message, curse_time, cooldown

    async def record_cursed_event(self, ctx: Context, con, target: discord.Member,
                                  curse_time: datetime.datetime, success: bool) -> None:
        """Record a cursed event in the database."""
        await con.execute("""INSERT INTO cursed_event 
                            (cursed_by_user_id, cursed_user_id, curse_at, curse_success, curse_length) VALUES 
                            ($1, $2, $3, $4, $5::interval)""", ctx.author.id, target.id, ctx.guild.id,
                          success, datetime.timedelta(hours=curse_time.hour))

    async def update_curse_attack(self, ctx: Context, con, cooldown: datetime.datetime) -> None:
        """Update curse records for a winning attacker."""
        await con.execute("""INSERT INTO cursed_user 
                                         (user_id, curse_at, curse_name, curse_cooldown, curse_ends_at) VALUES 
                                         ($1, $2, $3, $4, $5) ON CONFLICT (curse_at, user_id) DO UPDATE 
                                         SET curse_ends_at = $5, curse_at = $2, curse_cooldown = $4
                                         """, ctx.author.id, ctx.guild.id, None, cooldown, None)

    async def curse_target(self, ctx: Context, con, target: discord.Member, nickname: str,
                           curse_time: datetime.datetime):
        """Curse the target."""

        await con.execute("""INSERT INTO cursed_user 
                                    (user_id, curse_at, curse_name, curse_cooldown, curse_ends_at) VALUES 
                                    ($1, $2, $3, $4, $5) ON CONFLICT (curse_at, user_id) DO UPDATE 
                                    SET curse_ends_at = $5, curse_at = $2, curse_name = $3
                                    """, target.id, ctx.guild.id, nickname, None, curse_time)

        await self.edit_nickname(target, nickname)

    async def update_curse_crt_lost(self, ctx: Context, con, cooldown: datetime.datetime, nickname: str,
                                    curse_time: datetime.datetime):
        """Update curse records for a losing attacker."""

        await con.execute("""INSERT INTO cursed_user 
                                         (user_id, curse_at, curse_name, curse_cooldown, curse_ends_at) VALUES 
                                         ($1, $2, $3, $4, $5) ON CONFLICT (curse_at, user_id) DO UPDATE 
                                         SET curse_ends_at = $5, curse_at = $2, curse_name = $3, 
                                         curse_cooldown = $4
                                         """, ctx.author.id, ctx.guild.id, nickname, cooldown, curse_time)

        await self.edit_nickname(ctx.author, nickname)

    async def update_curse_tables(self, ctx, attacker: int, defender: int, nickname: str, message: str,
                                  member: discord.Member, cooldown: datetime.datetime,
                                  curse_time: datetime.datetime) -> None:

        async with ctx.bot.pool.acquire() as con:
            async with con.transaction():
                await self.update_curse_attack(ctx, con, cooldown)
                success = attacker > defender

                if success:
                    await self.curse_target(ctx, con, member, nickname, curse_time)

                elif attacker == 1 and defender == 20:
                    await self.update_curse_crt_lost(ctx, con, cooldown, nickname, curse_time)

                elif attacker == defender:
                    # attacks were equal, curse both
                    await self.curse_target(ctx, con, member, nickname, curse_time)
                    await self.curse_target(ctx, con, ctx.author, nickname, curse_time)

                await self.record_cursed_event(ctx, con, member, curse_time, success)

        await ctx.send(message)

    def calculate_attack_outcome(self, attacker: int, defender: int) -> namedtuple:
        attacker_won = attacker > defender
        cooldown = datetime.timedelta(hours=2)

        if attacker == defender:
            result_type = "equal"
        elif attacker_won:
            result_type = "attacker_won"
        else:
            result_type = "defender_won"

        return namedtuple("Outcome", ["result_type", "cooldown"])(result_type, cooldown)

    async def attempt_attack(self, ctx, attacker: int, defender: int, member: discord.Member,
                             nickname: str) -> namedtuple:

        outcome = self.calculate_attack_outcome(attacker, defender)
        cooldown = discord.utils.utcnow().replace(tzinfo=None) + outcome.cooldown

        if outcome.result_type == "equal":
            message, curse_time = await self.resolve_equal_scenario(attacker, defender, member, nickname, ctx.author)

        elif outcome.result_type == "attacker_won":
            message, curse_time = self.resolve_attack_scenario(attacker, defender, member, nickname, cooldown)
        else:  # defender > attacker
            message, curse_time, cooldown = await self.resolve_defense_scenario(
                ctx, attacker, defender, member, nickname)

        return namedtuple("curse", ["message", "curse_time", "cooldown"])(message, curse_time, cooldown)

    def format_message(self, member_name: str, nickname: str, attacker: int, defender: int, cooldown: datetime,
                       attack: bool, curse_time: datetime, starter_message: str = "", msg: str = "") -> str:

        if attack:
            return self.format_attack(member_name, nickname, attacker, defender, curse_time,
                                      cooldown, starter_message)

        return self.format_defence(member_name, msg, attacker, defender, cooldown, starter_message)

    def format_defence(self, member_name: str, msg: str, attacker: int, defender: int, cooldown: datetime,
                       starter_message: str = ""):

        message = (
            f"{starter_message}:shield: {member_name} shielded against the blow{msg}!\n"
            f":x: (Attacker: 1d20 ({attacker}) = {attacker}) vs. "
            f"(Defender: 1d20 ({defender}) = {defender})\n"
            f"Your ability to curse is on cooldown until {h.naturaltime(cooldown)}."
        )

        return message

    def format_attack(self, member_name: str, nickname: str, attacker: int, defender: int,
                      curse_time: datetime, cooldown: datetime, starter_message: str = ""):

        now = discord.utils.utcnow().replace(tzinfo=None)

        message = (
            f"{starter_message}:white_check_mark: "
            f"(Attacker: 1d20 ({attacker}) = {attacker}) vs. "
            f"(Defender: 1d20 ({defender}) = {defender})\n"
            f"Cursed {member_name}'s to `{nickname}` until `{h.naturaltime(now - curse_time)}`.\n"
            f"Your ability to curse is on cooldown until {h.naturaltime(cooldown)}. "
        )

        return message

    async def get_random_active_member(self, ctx: Context, member: discord.Member):
        """Gets a random active member from the guild"""
        members = [m.author async for m in ctx.channel.history(limit=200)
                   if not m.author.bot and m.author.status != discord.Status.offline and member != m.author]

        return random.choice(members)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        # Only proceed if the nickname changed
        if before.nick == after.nick:
            return

        async with self.bot_initiated_changes_lock:
            if after.id in self.bot_initiated_changes:
                # If the bot initiated this change, ignore it
                return

        # Mark this user ID to avoid processing further changes initiated by the bot
        self.bot_initiated_changes.add(after.id)
        new_name = after.nick
        lock_key = after.id  # Use the user ID as the lock key

        async with self.bot.pool.acquire() as con:
            data = await self.execute_with_retries(
                con,
                """SELECT curse_ends_at AS curse, curse_name AS name 
                   FROM cursed_user WHERE user_id = $1""",
                lock_key, after.id
            )

            if not data:
                return

            data = data[0]
            time = data["curse"]
            cursed_name = data["name"]

            if new_name != cursed_name:
                if time:
                    if time > discord.utils.utcnow().replace(tzinfo=None):
                        with contextlib.suppress(discord.errors.Forbidden):
                            await self.edit_nickname(after, cursed_name)

    @tasks.loop(hours=1)
    async def un_curse(self):
        # probably inefficient as hell but it's w/e
        async with self.bot.pool.acquire() as con:
            cursed_members = await con.fetch("""SELECT user_id, curse_ends_at AS curse, curse_at
                                                FROM cursed_user WHERE curse_ends_at IS NOT NULL""")
            for member in cursed_members:

                guild = self.bot.get_guild(member["curse_at"]) or await self.bot.fetch_guild(member["curse_at"])

                time = member["curse"]
                user_id = member["user_id"]

                try:

                    member = guild.get_member(user_id) or guild.fetch_member(user_id)

                    if time < discord.utils.utcnow().replace(tzinfo=None):
                        user_id = lock_key = member.id  # Use the user ID as the lock key

                        await self.execute_with_retries(
                            con,
                            "UPDATE cursed_user SET curse_ends_at = Null WHERE user_id = $1",
                            lock_key, user_id
                        )
                        await self.edit_nickname(member, "")

                except discord.HTTPException:
                    continue

    @commands.Cog.listener()
    async def on_ready(self):
        self.un_curse.start()

    async def roll_dice(self, ctx):

        rolls, limit, expression = await DieConventer().convert(ctx, "2d20")

        results = [random.randint(1, limit) for _ in range(rolls)]

        for i, res in enumerate(results):
            expression.insert(0, str(res))

            results[i] = ShuntingYard(expression).evaluate()

            del expression[0]

        return results[0], results[1]

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    @private_guilds_check()
    async def curse(self, ctx: Context, member: discord.Member, *, nickname):
        """The main command for curses by itself curses a member with a nickname"""

        # this command is still hacky and lazily as well as poorly done, but it's w/e

        if len(nickname) > 32:
            return await ctx.send("The curse name is too long.", delete_after=10)

        if ctx.me.guild_permissions.manage_nicknames is False:
            return await ctx.send(":no_entry: | I don't have the `manage nicknames` permission for this command.")

        if member.bot:
            return await ctx.send(":no_entry: | No cursing bots.")

        check = await ctx.db.fetchval("SELECT curse_cooldown FROM cursed_user WHERE user_id = $1 AND curse_at = $2",
                                      ctx.author.id, ctx.guild.id)

        if check:
            if check > discord.utils.utcnow().replace(tzinfo=None):
                return await ctx.send(f"Your ability to curse is on cooldown until {h.naturaltime(check)}.")

        attacker, defender = await self.roll_dice(ctx)

        curse = await self.attempt_attack(ctx, attacker, defender, member, nickname)

        await self.update_curse_tables(ctx, attacker, defender, nickname, curse.message,
                                       member, curse.cooldown, curse.curse_time)

    @commands.is_owner()
    @curse.command()
    async def reset(self, ctx, target: typing.Union[discord.Member, discord.User] = None):
        result = await self.reset_cooldown(ctx, target.id, ctx.guild.id)
        await ctx.send(result)

    # @curse.command()
    # async def test(self, ctx):
    #    await self.edit_nickname(ctx.author, "test")

    @curse.group(invoke_without_command=True)
    async def stats(self, ctx, member: typing.Union[discord.Member, discord.User] = None):
        """Get curse statistics for the current guild or a guild member"""
        if not member:
            return await self.get_guild_stats(ctx)

        await self.get_member_stats(ctx, member)

    @stats.command(aliases=["defense", "d", "defend"])
    async def defence(self, ctx, member: typing.Union[discord.Member, discord.User] = None):
        """Get defence statistics for the current guild or a guild member"""
        if not member:
            return await self.get_defense_stats(ctx)

        await self.get_member_defense_stats(ctx, member)

    def build_embed(self, title: str, description: str, fields: list, author: discord.Member = None) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=self.bot.default_colors())
        for name, value in fields:
            embed.add_field(name=name, value=value, inline=False)
        if author:
            embed.set_author(name=author.name, icon_url=str(author.avatar.url))
        return embed

    def calculate_success_rate(self, total_curses: int, successful_curses: int) -> float:
        return successful_curses / total_curses if total_curses > 0 else 0

    async def get_member_defense_stats(self, ctx, member: discord.Member):
        query = """
        WITH stats AS (
                    SELECT cursed_user_id, COUNT(*) as total_curses,
                        SUM(CASE WHEN not curse_success THEN 1 ELSE 0 END) as successful_defense,
                        RANK() OVER (ORDER BY COUNT(*) DESC ) rank
                    FROM cursed_event
                    WHERE curse_at = $1 AND cursed_user_id = $2 
                    GROUP BY cursed_user_id)
                    SELECT cursed_user_id, total_curses, successful_defense as sd, rank
                    FROM stats
                    LIMIT 1
        """

        data = await ctx.db.fetchrow(query, ctx.guild.id, member.id)

        if not data:
            return await ctx.send(f"> {member.name} hasn't cursed anyone yet for this guild.")

        success_rate = self.calculate_success_rate(data["total_curses"], data["sd"])

        fields = [
            ("Attacked count", h.intcomma(data["total_curses"])),
            ("Success defense rate", f"{success_rate:.1%}")
        ]

        embed = self.build_embed(title="Member Stats", description="", fields=fields, author=member)

        await ctx.send(embed=embed)

    async def get_defense_stats(self, ctx):
        query = """
        WITH stats AS (
                    SELECT cursed_user_id, COUNT(*) as total_curses,
                        SUM(CASE WHEN not curse_success THEN 1 ELSE 0 END) as successful_defense,
                        RANK() OVER (ORDER BY COUNT(*) DESC ) rank
                    FROM cursed_event
                    WHERE curse_at = $1
                    GROUP BY cursed_user_id)
                    SELECT cursed_user_id, total_curses as tc, successful_defense as sd, rank
                    FROM stats
        """
        data = await ctx.db.fetch(query, ctx.guild.id)

        if not data:
            return await ctx.send("> No curses have happened yet for this guild.")

        top_successful_defenders = sorted(data, key=lambda r: self.calculate_success_rate(r["tc"], r["sd"]),
                                          reverse=True)[:3]

        total_curses = sum(r["tc"] for r in data)
        total_sc = sum(r["sd"] for r in data)

        description = f"{total_curses} curses, of which {self.calculate_success_rate(total_curses, total_sc):.1%} " \
                      f"were defended"

        success_field = "\n".join(f"{self.emotes[i + 1]}: <@{r['cursed_user_id']}> "
                                  f"(defended {self.calculate_success_rate(r['tc'], r['sd']):.1%} of {r['tc']} curses)"
                                  for i, r in enumerate(top_successful_defenders))

        fields = [
            ("Most successful defenders(s)", success_field)
        ]

        embed = self.build_embed(title="Defence Stats", description=description, fields=fields)

        await ctx.send(embed=embed)

    async def get_guild_stats(self, ctx):
        query = """
            WITH stats AS (
                SELECT cursed_by_user_id, COUNT(*) AS total_curses, 
                        SUM(CASE WHEN curse_success THEN 1 ELSE 0 END) AS successful_curses,
                        RANK() OVER (ORDER BY COUNT(*) DESC) rank
                FROM cursed_event
                WHERE curse_at = $1
                GROUP BY cursed_by_user_id
                )
                SELECT cursed_by_user_id, total_curses, successful_curses as sc, rank
                FROM stats                      
        """

        data = await ctx.db.fetch(query, ctx.guild.id)

        if not data:
            return await ctx.send("> No curses have happened yet for this guild.")
        # data is already ranked by total curses
        top_cursers = data[:3]
        top_successful_cursers = sorted(data, key=lambda r: self.calculate_success_rate(r["total_curses"], r["sc"]),
                                        reverse=True)[:3]

        total_curses = sum(r["total_curses"] for r in data)
        total_sc = sum(r["sc"] for r in data)

        description = f"{total_curses} curses, of which {self.calculate_success_rate(total_curses, total_sc):.1%} " \
                      f"were successful"

        top_field = "\n".join(f"{self.emotes[i + 1]}: <@{t[0]}> ({h.intcomma(t[1])} curses)"
                              for i, t in enumerate(top_cursers))

        success_field = "\n".join(f"{self.emotes[i + 1]}: <@{r['cursed_by_user_id']}> "
                                  f"({self.calculate_success_rate(r['total_curses'], r['sc']):.1%} times)"
                                  for i, r in enumerate(top_successful_cursers))

        fields = [
            ("Top curser(s)", top_field),
            ("Most successful curser(s)", success_field)
        ]

        embed = self.build_embed(title="Curse Stats", description=description, fields=fields)

        await ctx.send(embed=embed)

    async def get_member_stats(self, ctx, member: discord.Member):
        query = """
            WITH stats AS (
                SELECT cursed_by_user_id, COUNT(*) AS total_curses, 
                        SUM(CASE WHEN curse_success THEN 1 ELSE 0 END) AS successful_curses,
                        RANK() OVER (ORDER BY COUNT(*) DESC) rank
                FROM cursed_event
                WHERE curse_at = $1 and cursed_by_user_id =  $2
                GROUP BY cursed_by_user_id
                )
                SELECT cursed_by_user_id, total_curses, successful_curses as sc, rank
                FROM stats
                LIMIT 1                 
        """

        data = await ctx.db.fetchrow(query, ctx.guild.id, member.id)

        if not data:
            return await ctx.send(f"> {member.name} hasn't cursed anyone yet for this guild.")

        success_rate = self.calculate_success_rate(data["total_curses"], data["sc"])

        fields = [
            ("Curse count", h.intcomma(data["total_curses"])),
            ("Success Rate", f"{success_rate:.1%}")
        ]

        embed = self.build_embed(title="Member Stats", description="", fields=fields, author=member)

        await ctx.send(embed=embed)


async def setup(bot):
    n = Curse(bot)
    await bot.add_cog(n)

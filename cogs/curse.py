import typing
import contextlib
import random
import datetime
import humanize as h

from collections import Counter, namedtuple

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
        self.curse = namedtuple("curse", "message curse_time cooldown")

    def get_critical_attack_message_and_hours(self, attacker: int, defender: int, member: discord.Member,
                                              nickname: str, cooldown: datetime.datetime) -> [str, datetime.datetime]:
        if defender == 1 and attacker == 20:
            message = ":dart: Nat 20 Critical attack against a critical failure! :dart:\n"
            curse_hours = 168
        elif attacker == 20:
            message = ":dart: Nat 20 Critical hit! :dart:\n"
            curse_hours = 24
        elif defender == 1:
            message = ":x: Critical defending failure! :x:\n"
            curse_hours = 24
        else:
            message = ""
            curse_hours = 2

        curse_time = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(hours=curse_hours)

        message = self.format_message(member.mention, nickname, attacker, defender, cooldown,
                                      starter_message=message, curse_hours=curse_hours)

        return message, curse_time

    async def do_defending_message_and_hours(self, ctx, attacker: int, defender: int, member: discord.Member,
                                             nickname: str, cooldown: datetime.datetime) -> [str, datetime.timedelta,
                                                                                             datetime.datetime]:
        if defender == 20:
            if attacker == 1:
                cooldown = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(days=7)
                message = f"{member.nick}...and it ended up being reflected back at {ctx.author.mention}!"
                curse_hours = 168
                member = ctx.author
            else:
                random_member = await self.get_random_active_member(ctx, member) or ctx.author
                message = f"{member.nick}...and it ended up hitting {random_member.mention} by mistake!"
                curse_hours = 2
                try:
                    await random_member.edit(nick=nickname)
                    member = random_member
                except discord.errors.Forbidden:
                    return await ctx.send(
                        "An error occurred trying to edit a nickname, probably due to role hierarchy.")
        elif attacker == 1:
            cooldown = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(days=1)
            message = ":x: Critical attacking failure! :x:\n"
            curse_hours = 24
        else:
            message = ""
            curse_hours = 2

        curse_time = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(hours=curse_hours)

        message = self.format_message(member.mention, nickname, attacker, defender, cooldown,
                                      starter_message=message, curse_hours=curse_hours)

        return message, curse_time, cooldown

    async def record_cursed_event(self, ctx: Context, con, target: discord.Member, nickname: str,
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

    async def update_curse_for_winner(self, ctx: Context, con, target: discord.Member, nickname: str,
                                      curse_time: datetime.datetime):
        """Update curse records for a winning attacker."""
        try:

            await target.edit(nick=nickname)

        except discord.errors.Forbidden:
            return await ctx.send("An error occurred trying to edit a nickname, probably due role hierarchy")

        await con.execute("""INSERT INTO cursed_user 
                                    (user_id, curse_at, curse_name, curse_cooldown, curse_ends_at) VALUES 
                                    ($1, $2, $3, $4, $5) ON CONFLICT (curse_at, user_id) DO UPDATE 
                                    SET curse_ends_at = $5, curse_at = $2, curse_name = $3
                                    """, target.id, ctx.guild.id, nickname, None, curse_time)

    async def update_curse_crt_lost(self, ctx: Context, con, cooldown: datetime.datetime, nickname: str,
                                    curse_time: datetime.datetime):
        """Update curse records for a losing attacker."""
        await con.execute("""INSERT INTO cursed_user 
                                         (user_id, curse_at, curse_name, curse_cooldown, curse_ends_at) VALUES 
                                         ($1, $2, $3, $4, $5) ON CONFLICT (curse_at, user_id) DO UPDATE 
                                         SET curse_ends_at = $5, curse_at = $2, curse_name = $3, 
                                         curse_cooldown = $4
                                         """, ctx.author.id, ctx.guild.id, nickname, cooldown, curse_time)

    async def update_curse_tables(self, ctx, attacker: int, defender: int, nickname: str, message: str,
                                  member: discord.Member, cooldown: datetime.datetime,
                                  curse_time: datetime.datetime) -> None:

        async with ctx.acquire() as con:
            await self.update_curse_attack(ctx, con, cooldown)
            success = attacker > defender

            if success:
                await self.update_curse_for_winner(ctx, con, member, nickname, curse_time)

            elif attacker == 1 and defender == 20:
                await self.update_curse_crt_lost(ctx, con, cooldown, nickname, curse_time)

            await self.record_cursed_event(ctx, con, member, nickname, curse_time, success)

        await ctx.send(message)

    async def attempt_attack(self, ctx, attacker: int, defender: int, member: discord.Member,
                             nickname: str) -> namedtuple:

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
                f"Cursed {ctx.author.mention}'s to `{nickname}` for {duration}.\n"
                f"Your ability to curse is on cooldown until {h.naturaltime(cooldown)}."
            )

            try:

                await ctx.author.edit(nick=nickname)

            except discord.errors.Forbidden:
                return await ctx.send("An error occurred trying to edit a nickname, probably due role hierarchy.")

        else:
            attacker_won = attacker > defender

            if attacker_won:

                message, curse_time = self.get_critical_attack_message_and_hours(attacker, defender,
                                                                                 member, nickname, cooldown)
            else:  # defender > attacker
                message, curse_time, cooldown = await self.do_defending_message_and_hours(ctx, attacker, defender,
                                                                                          member, nickname, cooldown)

        curse = self.curse(message, curse_time, cooldown)
        return curse

    def format_message(self, member_name: str, nickname: str, attacker: int, defender: int, cooldown: datetime,
                       starter_message: str = "", attack=True, curse_hours=2) -> str:

        curse_time = discord.utils.utcnow().replace(tzinfo=None) + datetime.timedelta(hours=curse_hours)

        if attack:
            return self.format_attack(member_name, nickname, attacker, defender, curse_time,
                                      cooldown, starter_message)

        return self.format_defence(member_name, nickname, attacker, defender, cooldown, starter_message)

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

        new_name = after.nick

        async with self.bot.pool.acquire() as con:
            data = await con.fetchrow("""SELECT curse_ends_at AS curse, curse_name AS name 
                                         FROM cursed_user WHERE user_id = $1""",
                                      after.id)

            time = data["curse"]
            cursed_name = data["name"]

            if new_name != cursed_name:
                if time:
                    if time > discord.utils.utcnow().replace(tzinfo=None):
                        with contextlib.suppress(discord.errors.Forbidden):
                            await after.edit(nick=cursed_name)

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
                        with contextlib.suppress(discord.errors.Forbidden):
                            await member.edit(nick="")

                        await con.execute("UPDATE cursed_user SET curse_ends_at = Null WHERE user_id = $1", user_id)

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
            return

        check = await ctx.db.fetchval("SELECT curse_cooldown FROM cursed_user WHERE user_id = $1", ctx.author.id)

        if check:
            if check > discord.utils.utcnow().replace(tzinfo=None):
                return await ctx.send(f"Your ability to curse is on cooldown until {h.naturaltime(check)}.")

        attacker, defender = await self.roll_dice(ctx)

        curse = await self.attempt_attack(ctx, attacker, defender, member, nickname)

        await self.update_curse_tables(ctx, attacker, defender, nickname, curse.message,
                                       member, curse.cooldown, curse.curse_time)

    @curse.command()
    async def stats(self, ctx, member: typing.Union[discord.Member, discord.User] = None):
        """Get statistics for the current guild or a guild member"""
        if not member:
            return await self.get_guild_stats(ctx)

        await self.get_member_stats(ctx, member)

    async def get_guild_stats(self, ctx):
        query = """
            WITH stats AS (
                SELECT cursed_by_user_id, curse_length, curse_success, COUNT(curse_success) AS successful_curses,
                        RANK() OVER (ORDER BY COUNT(*) DESC) rank
                FROM cursed_event
                WHERE curse_at = $1
                GROUP BY cursed_by_user_id, curse_length, curse_success
                )
                SELECT cursed_by_user_id, curse_length, successful_curses as sc, rank
                FROM stats                      
        """

        data = await ctx.db.fetch(query, ctx.guild.id)

        if not data:
            return await ctx.send("> No curses have happened yet for this guild.")

        top_cursers = Counter(r["cursed_by_user_id"] for r in data).most_common(3)

        description = f"{len(data)} curses, which {len(data) / sum(d['sc'] for d in data):.1%} were successful"

        embed = discord.Embed(title="Curse Stats",
                              color=self.bot.default_colors())

        embed.description = description

        value = "\n".join(f"{self.emotes[i + 1]}: <@{t[0]}> ({h.intcomma(t[1])} curses)"
                          for i, t in enumerate(top_cursers))
        embed.add_field(name="Top curser(s)", value=value, inline=False)

        value = "\n".join(f"{self.emotes[i + 1]}: <@{r['cursed_by_user_id']}> "
                          f"({len(data) / r['sc']:.1%} times)"
                          for i, r in enumerate(data[:3]))

        embed.add_field(name="Most successful curser(s)", value=value, inline=False)

        await ctx.send(embed=embed)

    async def get_member_stats(self, ctx, member: discord.Member):
        query = """
                  WITH stats AS (
                      SELECT cursed_by_user_id, curse_length, curse_success, COUNT(curse_success) AS successful_curses,
                              RANK() OVER (ORDER BY COUNT(*) DESC) rank
                      FROM cursed_event
                      WHERE curse_at = $1 and cursed_by_user_id = $2
                      GROUP BY cursed_by_user_id, curse_length, curse_success
                      )
                      SELECT cursed_by_user_id, curse_length, successful_curses, rank
                      FROM stats                      
              """

        data = await ctx.db.fetch(query, ctx.guild.id, member.id)

        if not data:
            return await ctx.send(f"> {member.name} hasn't cursed anyone yet for this guild.")

        curse_count = len(data)
        success_rate = data[0]["successful_curses"] / curse_count

        embed = discord.Embed(title="Member Stats",
                              color=self.bot.default_colors())

        embed.add_field(name="Curse count", value=h.intcomma(curse_count), inline=True)
        embed.add_field(name="Success Rate", value=f"{success_rate:.1%}", inline=True)

        embed.set_author(name=member.name, icon_url=str(member.avatar.url))
        await ctx.send(embed=embed)


async def setup(bot):
    n = Curse(bot)
    await bot.add_cog(n)

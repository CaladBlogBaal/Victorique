# Work with Python 3.6+
import asyncio
import re
import random
import aiohttp

import asyncpg

from discord.ext import commands, tasks
import discord


import loadconfig
from config.utils import cache, requests, checks


class Victorique(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channels_running_commands = {}
        self.loop.run_until_complete(self.__ainit__(self, *args, **kwargs))

    async def __ainit__(self, *args, **kwargs):
        self.session = aiohttp.ClientSession()
        self.request = requests.Request(self, self.session)
        db = await asyncpg.create_pool(loadconfig.credentials)
        self.db = db
        with open("schema.sql") as f:
            await self.db.execute(f.read())

    @staticmethod
    def default_colors():
        colours = [discord.Color.dark_magenta(), discord.Colour(15156347), discord.Color.dark_orange(),
                   discord.Color.red(), discord.Color.dark_red(), discord.Color(15121501)]
        col = int(random.random() * len(colours))
        return colours[col]

    @staticmethod
    def safe_everyone(msg):
        # modified version of the discord.utils.unescape_mentions
        return re.sub(r"@(everyone|here)", "@\u200b\\1", msg)

    async def update_databases(self, guild=None):
        if guild:
            async with self.db.aquire() as con:
                await con.execute("""INSERT INTO guilds (guild_id, allow_default) VALUES ($1,$2)
                                  ON CONFLICT DO NOTHING;""", guild.id, True)
            generator = ((m.id, m.name, 3000) for m in guild.members if not m.bot)
        else:
            generator = ((m.id, m.name, 3000) for m in self.get_all_members() if not m.bot)
        member_ids = list((data[0],) for data in generator)
        user_update = list(data for data in generator)
        async with self.db.acquire() as con:
            async with con.transaction():
                await con.executemany("""INSERT INTO users (user_id, name, credits) 
                                             VALUES ($1,$2,$3) ON CONFLICT DO NOTHING;""", user_update)
                await con.executemany("INSERT INTO fish_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING;",
                                      member_ids)

    async def is_owner(self, user):

        return user.id in loadconfig.__owner_ids__

    async def close(self):
        await self.session.close()
        await self.db.close()
        await super().close()

    async def fetch(self, url, **kwargs):
        return await self.request.fetch(url, **kwargs)

    async def post(self, url, data, **kwargs):
        return await self.request.post(url, data, **kwargs)

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=MyContext)

    @cache.cache()
    async def get_guild_prefix(self, guild_id):

        async with self.db.acquire() as con:
            data = await con.fetchrow("""

                SELECT * FROM guilds WHERE guild_id = $1

                """, guild_id)

            return data

    prefix_invalidate = get_guild_prefix.invalidate
    prefixes = get_guild_prefix.get_stats

    @staticmethod
    def emote_unescape(msg):
        p = re.compile(r"<a?:(\w*):\d*>")

        if not p.findall(msg):
            return msg

        msg = re.sub(p, r"\1", msg)

        return msg

    @cache.cache()
    async def get_tags(self, guild_id):
        async with bot.db.acquire() as con:
            tags = await con.fetch("select tag_name from tags where guild_id =  $1",
                                   guild_id)

            return tags

    tags_invalidate = get_tags.invalidate
    tags = get_tags.get_stats


async def get_prefix(bot_, msg):

    if msg.guild is None:
        return commands.when_mentioned_or(*[loadconfig.__prefix__, ""])(bot_, msg)

    data = await bot_.get_guild_prefix(msg.guild.id)

    if data is None:
        return commands.when_mentioned_or(loadconfig.__prefix__)(bot_, msg)

    prefix = [data["prefix"]]

    if data["allow_default"]:
        prefix.append(loadconfig.__prefix__)

    prefix.sort(reverse=True)
    return commands.when_mentioned_or(*prefix)(bot_, msg)


class MyContext(commands.Context):
    __slots__ = ("con", "emote_unescape", "safe_everyone", "chunk")

    @staticmethod
    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        for i in range(0, len(l), n):
            yield l[i:i + n]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.con = self.bot.db.acquire()
        self.emote_unescape = self.bot.emote_unescape
        self.safe_everyone = self.bot.safe_everyone
        self.chunk = self.chunks


bot = Victorique(command_prefix=get_prefix, description="Current commands for this bot", case_insensitive=True)


@bot.before_invoke
async def before_invoke(ctx):
    try:

        ctx.con = await ctx.con

    except TypeError:
        pass


@bot.after_invoke
async def after_invoke(ctx):
    await ctx.bot.db.release(ctx.con)


@bot.command()
@checks.private_guilds_check()
async def send_emote(ctx, name: str):
    emotes = [e for e in bot.emojis]
    emote = list()
    try:

        emote.append(random.sample([str(e) for e in emotes if name == e.name], 1))

    except ValueError:
        return

    if emote:
        await ctx.send(emote[0][0])
    else:
        pass


@bot.command(hidden=True)
async def prefix(ctx):
    result = await bot.get_guild_prefix(ctx.guild.id)
    if result is not None:
        return await ctx.send(f"The prefix for this guild is {result['prefix']}.")

    await ctx.send(f"The prefix for this guild is {loadconfig.__prefix__}")


@bot.command(hidden=True, name="icb")
async def i_cant_believe(ctx):
    await ctx.send("I can't believe you've done this")


@bot.event
async def on_message(message):

    user = message.author
    msg = message.content

    if message.author.id == bot.user.id:
        return

    if message.guild and message.guild.id in (520242432386793473, 432569553353048075):

        print(f"{user} said {msg} in guild {message.guild.name}")

        if msg.lower() == "floof":
            await message.channel.send(f"gloof {user.mention}")

        if msg.lower() == "point and laugh":
            await message.channel.send("https://i.imgur.com/uPHnUjQ.png")

    await bot.process_commands(message)


@tasks.loop(seconds=loadconfig.__presenceTimer__)
async def presence_change():
    random_presence = random.choice(loadconfig.__presences__)
    await bot.change_presence(activity=discord.Activity(type=random_presence[0], name=random_presence[1]))


@presence_change.before_loop
async def before_presence_change():
    await bot.wait_until_ready()

presence_change.start()


@bot.event
async def on_user_update(before, after):
    new_name = after.name
    user_id = after.id
    async with bot.db.acquire() as con:
        await con.execute("UPDATE users SET name = $1 where user_id = $2", new_name, user_id)


@bot.event
async def on_guild_join(guild):
    await bot.update_databases(guild)


@bot.event
async def on_member_join(member):
    if member.bot:
        return

    async with bot.db.acquire() as con:
        async with con.transaction():
            await con.execute("INSERT INTO users (user_id, name, credits) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING;",
                              (member.id, member.name, 3000))
            await con.execute("INSERT INTO fish_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING;", member.id)


@bot.event
async def on_disconnect():
    presence_change.cancel()
    await bot.wait_until_ready()
    await asyncio.sleep(loadconfig.__presenceTimer__)
    presence_change.start()


@bot.event
async def on_ready():
    await bot.update_databases()

    print(f"Successfully logged in and booted...!")
    print(f"\nLogged in as: {bot.user.name} - {bot.user.id}\nDiscord.py version: {discord.__version__}\n")
    print(f"Asyncpg version: {asyncpg.__version__}")

    print("Current servers:")
    for server in list(bot.guilds):
        print(f"{server.name}")


if __name__ == "__main__":

    for cog in loadconfig.__cogs__:

        try:

            bot.load_extension(cog)

        except Exception as e:
            print(f"{cog} could not be loaded.")
            raise e

    bot.run(loadconfig.__token__, bot=True, reconnect=True)


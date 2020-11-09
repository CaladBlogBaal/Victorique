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
from config.utils import context


class Victorique(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channels_running_commands = {}
        self.loop.run_until_complete(self.__ainit__(self, *args, **kwargs))

    async def __ainit__(self, *args, **kwargs):
        self.session = aiohttp.ClientSession()
        self.request = requests.Request(self, self.session)
        db = await asyncpg.create_pool(loadconfig.credentials)
        self.pool = db
        with open("schema.sql") as f:
            await self.pool.execute(f.read())

    @staticmethod
    def default_colors():
        colours = [discord.Color.dark_magenta(), discord.Colour(15156347), discord.Color.dark_orange(),
                   discord.Color.red(), discord.Color.dark_red(), discord.Color(15121501)]

        return random.choice(colours)

    @staticmethod
    def safe_everyone(msg):
        # modified version of the discord.utils.unescape_mentions
        return re.sub(r"@(everyone|here)", "@\u200b\\1", msg)

    async def update_databases(self, guild=None):
        async with self.pool.acquire() as con:
            if guild:
                await con.execute("""INSERT INTO guilds (guild_id, allow_default) VALUES ($1,$2)
                                     ON CONFLICT DO NOTHING;""", guild.id, True)
                user_tups = [(m.id, m.name, 3000) for m in guild.members if not m.bot]
            else:
                user_tups = [(m.id, m.name, 3000) for m in self.get_all_members() if not m.bot]
            member_ids = list((data[0],) for data in user_tups)

            await con.executemany("""INSERT INTO users (user_id, name, credits) 
                                     VALUES ($1,$2,$3) ON CONFLICT DO NOTHING;""", user_tups)

            await con.executemany("""INSERT INTO fish_users (user_id) 
                                     VALUES ($1) ON CONFLICT DO NOTHING;""", member_ids)

    async def is_owner(self, user):

        return user.id in loadconfig.__owner_ids__

    async def close(self):
        await self.session.close()
        await self.pool.close()
        await super().close()

    async def fetch(self, url, **kwargs):
        return await self.request.fetch(url, **kwargs)

    async def post(self, url, data, **kwargs):
        return await self.request.post(url, data, **kwargs)

    async def get_context(self, message, *, cls=None):
        return await super().get_context(message, cls=context.Context)

    @cache.cache()
    async def get_guild_prefix(self, guild_id):

        async with self.pool.acquire() as con:
            data = await con.fetchrow("""

                SELECT * FROM guilds WHERE guild_id = $1

                """, guild_id)

            return data

    async def api_get_image(self, content, url, key):

        js = await self.fetch(url)

        while js[key].endswith(".mp4"):
            js = await self.fetch(url)

        colours = [discord.Color.dark_magenta(), discord.Color.dark_teal(), discord.Color.dark_orange()]
        col = int(random.random() * len(colours))
        content = content
        embed = discord.Embed(color=colours[col],
                              description=random.choice(content), )
        embed.set_image(url=js[key])
        return embed

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
    async def get_tag(self, guild_id, tag_name):

        guild_id = guild_id
        tag_name = tag_name

        async with bot.pool.acquire() as con:
            tag = await con.fetchrow("""select guild_id, content, nsfw, tag_name from tags where guild_id =  $1 
                                     and lower(tag_name) LIKE $2""",
                                     guild_id, tag_name)

            return tag

    tags_invalidate = get_tag.invalidate
    tags = get_tag.get_stats


async def get_prefix(bot_, msg):
    if msg.guild is None:
        return commands.when_mentioned_or(*[loadconfig.__prefix__, ""])(bot_, msg)

    data = await bot_.get_guild_prefix(msg.guild.id)

    if data is None:
        return commands.when_mentioned_or(loadconfig.__prefix__)(bot_, msg)

    prefix = [data["prefix"]]

    if not prefix[0]:
        prefix = []

    if data["allow_default"]:
        prefix.append(loadconfig.__prefix__)

    prefix.sort(reverse=True)
    return commands.when_mentioned_or(*prefix)(bot_, msg)


bot = Victorique(command_prefix=get_prefix, case_insensitive=True)


@bot.after_invoke
async def after_invoke(ctx):
    # release any lingering connections
    await ctx.release()


@bot.command(aliases=["se"])
@checks.private_guilds_check()
async def send_emote(ctx, name: str):
    try:
        emote = (random.sample([str(e) for e in bot.emojis if name.lower() == e.name.lower()], 1))
    except ValueError:
        return

    await ctx.send(*emote)


@bot.command(hidden=True)
async def prefix(ctx):
    if ctx.guild:
        result = await bot.get_guild_prefix(ctx.guild.id)
        if result["prefix"] is not None:
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
    async with bot.pool.acquire() as con:
        await con.execute("UPDATE users SET name = $1 where user_id = $2", new_name, user_id)


@bot.event
async def on_guild_join(guild):
    await bot.update_databases(guild)


@bot.event
async def on_member_join(member):
    if member.bot:
        return

    async with bot.pool.acquire() as con:
        await con.execute("INSERT INTO users (user_id, name, credits) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING;",
                          member.id, member.name, 3000)
        await con.execute("INSERT INTO fish_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING;", member.id)


@bot.event
async def on_disconnect():
    presence_change.cancel()
    await bot.wait_until_ready()
    await asyncio.sleep(loadconfig.__presenceTimer__)
    presence_change.start()

# As of 2020-10-28, discord requires users declare what sort of information their bot requires which is done in the form
# of intents
intents = discord.Intents.default()

# these intents are known as privileged which requires you to go to the developer portal
# and manually enable it.

# need this to track members
intents.members = True
# need this for discord.Member.status
intents.presences = True


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

    bot.run(loadconfig.__token__, bot=True, reconnect=True, intents=intents)

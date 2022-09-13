from discord.ext import commands


class Database(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

    async def batch_insert(self, guild):
        async with self.bot.pool.acquire() as con:

            user_tups = [(m.id, m.name, 3000) for m in guild.members if not m.bot]

            member_ids = list((data[0],) for data in user_tups)

            await con.execute("""INSERT INTO guilds (guild_id, allow_default) VALUES ($1,$2)
                                 ON CONFLICT DO NOTHING;""", guild.id, True)

            await con.executemany("""INSERT INTO users (user_id, name, credits) 
                                     VALUES ($1,$2,$3) ON CONFLICT DO NOTHING;""", user_tups)

            await con.executemany("""INSERT INTO fish_users (user_id)         
                                     VALUES ($1) ON CONFLICT DO NOTHING;""", member_ids)

            await con.executemany("""INSERT INTO user_tag_usage (user_id, guild_id)
                                     VALUES ($1, $2) ON CONFLICT DO NOTHING;""", ((m[0], guild.id) for m in member_ids))

    @commands.Cog.listener()
    async def on_ready(self):
        for g in self.bot.guilds:
            await self.batch_insert(g)

    @commands.Cog.listener()
    async def on_user_update(self, _, after):
        new_name = after.name
        user_id = after.id
        async with self.bot.pool.acquire() as con:
            await con.execute("UPDATE users SET name = $1 where user_id = $2", new_name, user_id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.batch_insert(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.bot:
            return

        async with self.bot.pool.acquire() as con:
            await con.execute("INSERT INTO users (user_id, name, credits) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING;",
                              member.id, member.name, 3000)
            await con.execute("INSERT INTO fish_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING;", member.id)
            await con.execute("INSERT INTO user_tag_usage (user_id, guild_id) VALUES ($1, $2) ON CONFLICT DO NOTHING;",
                              member.id, member.guild.id)


async def setup(bot):
    await bot.add_cog(Database(bot))

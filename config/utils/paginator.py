# taken from https://gist.github.com/OneEyedKnight/0f188251247c58345a1a97e94d05dd15
import random
import asyncio
from asyncpg import InterfaceError

from contextlib import suppress

import discord

from config.utils.emojis import RIGHT_POINT, DRIGHT_POINT, LEFT_POINT, DLEFT_POINT, STOP


class Paginator:
    __slots__ = ("bot", "ctx", "_pages", "max_pages", "msg", "index", "running", "user", "channel", "reactions",
                 "execute")

    def __init__(self, ctx):
        self.bot = ctx.bot
        self.ctx = ctx
        self._pages = []
        self.max_pages = 0
        self.msg = ctx.message
        self.index = 0
        self.user = ctx.author
        self.channel = ctx.channel
        self.reactions = [(str(DLEFT_POINT), self.first_page),
                          (str(LEFT_POINT), self.backward),
                          (str(RIGHT_POINT), self.forward),
                          (str(DRIGHT_POINT), self.last_page),
                          (str(STOP), self.stop)
                          ]
        self.running = True

    async def init_max_pages(self):
        self.max_pages = len(self._pages) - 1

    async def add_page(self, msg):
        self._pages.append(msg)

    async def close_page(self, page):
        del self._pages[self._pages.index(page)]

    async def setup(self):
        await self.init_max_pages()

        if isinstance(self._pages[0], discord.Embed):
            self.msg = await self.channel.send(embed=self._pages[0])

        else:
            self.msg = await self.channel.send(self._pages[0])

        if len(self._pages) == 1:
            return

        for (r, _) in self.reactions:

            await self.msg.add_reaction(r)

    async def alter(self, index: int):
        page_number = str(index + 1)
        page_display = f"page {page_number}/{str(self.max_pages + 1)}"

        if isinstance(self._pages[index], discord.Embed):
            self._pages[index].set_footer(text=page_display)
            await self.msg.edit(content="", embed=self._pages[index])

        else:
            await self.msg.edit(content=self._pages[index] + f"\n`{page_display}`", embed=None)

    async def first_page(self):

        self.index = 0

        await self.alter(self.index)

    async def last_page(self):

        self.index = self.max_pages

        await self.alter(self.index)

    async def backward(self):

        if self.index == 0:

            self.index = self.max_pages

            await self.alter(self.index)

        else:

            self.index -= 1

            await self.alter(self.index)

    async def forward(self):

        if self.index == self.max_pages:

            self.index = 0

            await self.alter(self.index)

        else:

            self.index += 1

            await self.alter(self.index)

    async def stop(self):
        await self.msg.delete()
        self.running = False

    async def shuffle_pages(self):
        random.shuffle(self._pages)

    async def terminate(self):
        self.running = False

        try:

            await self.msg.clear_reactions()

        except discord.Forbidden:
            pass

    def _check(self, reaction, user):

        if user.id != self.user.id or reaction.message.id != self.msg.id:
            return False

        for (emote, func) in self.reactions:
            if str(reaction.emoji) == emote:
                self.execute = func
                return True

        return False

    async def paginate(self):
        # get rid of any lingering postgres pool connections

        with suppress(InterfaceError):
            await self.ctx.bot.db.release(self.ctx.con)

        perms = True
        if self.ctx.guild is not None:
            perms = self.ctx.me.guild_permissions.manage_messages

        await self.setup()

        while self.running:

            if perms:
                try:

                    reaction, user = await self.bot.wait_for('reaction_add', check=self._check, timeout=200)

                except asyncio.TimeoutError:
                    return await self.terminate()

                try:

                    await self.msg.remove_reaction(reaction, user)

                except discord.HTTPException:

                    pass

                await self.execute()

            else:

                done, pending = await asyncio.wait(

                    [self.bot.wait_for('reaction_add', check=self._check),

                     self.bot.wait_for('reaction_remove', check=self._check)],

                    return_when=asyncio.FIRST_COMPLETED)

                done.pop().result()

                for future in pending:
                    future.cancel()

                await self.execute()


class PaginatorGlobal(Paginator):

    def __init__(self, ctx):
        super().__init__(ctx)

        self.reactions = [(str(DLEFT_POINT), self.first_page),
                          (str(LEFT_POINT), self.backward),
                          (str(RIGHT_POINT), self.forward),
                          (str(DRIGHT_POINT), self.last_page)
                          ]

    def _check(self, reaction, user):
        if reaction.message.id != self.msg.id or user.bot:
            return False

        for (emote, func) in self.reactions:
            if str(reaction.emoji) == emote:
                self.execute = func
                return True


class WarpedPaginator(Paginator):
    __slots__ = ("max_size",)

    def __init__(self, ctx, max_size=1800):
        self.max_size = max_size
        super().__init__(ctx)

    async def add_page(self, msg):

        if isinstance(msg, discord.Embed):
            description = msg.description
            truncated = list(self.ctx.chunk(description, self.max_size))
            title = msg.title
            title += " continued..."

            if len(truncated) > 1:
                continuation_msg = "... **the rest of this description continues onto the next page/pages**"
                msg.description = truncated[0] + continuation_msg
                self._pages.append(msg)
                for chunk in truncated[1::]:
                    embed = discord.Embed(title=title, colour=self.ctx.bot.default_colors())
                    embed.description = chunk
                    self._pages.append(embed)

            else:

                self._pages.append(msg)

        else:

            truncated = list(self.ctx.chunk(msg, self.max_size))

            for chunk in truncated:
                self._pages.append(chunk)

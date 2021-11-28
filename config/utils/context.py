import discord
from discord.ext import commands
from config.utils.menu import BaseMenu, ReplyMenu, GlobalMenu, page_source


@page_source(per_page=1)
async def list_source(self, menu, entry):
    if isinstance(entry, discord.Embed):
        footer_text = ""
        # check if it's not empty
        if entry.footer:
            footer_text = entry.footer.text
        entry.set_footer(text=footer_text + f"page {menu.current_page + 1} /{self.get_max_pages()}")
    elif isinstance(entry, str):
        entry += f"\npage {menu.current_page + 1} /{self.get_max_pages()}"
    return entry


class _ContextDBAcquire:
    # pretty much taken from
    # https://github.com/Rapptz/RoboDanny/blob/ac3a0ed64381050c37761d358d4af90b89ec1ca3/cogs/utils/context.py

    __slots__ = 'ctx'

    def __init__(self, ctx):
        self.ctx = ctx

    def __await__(self):
        return self.ctx._acquire().__await__()

    async def __aenter__(self):
        await self.ctx._acquire()

        return self.ctx.pool

    async def __aexit__(self, *args):
        await self.ctx.release()


class Context(commands.Context):
    __slots__ = ("emote_unescape", "safe_everyone", "chunk", "paginator", "paginator_global", "paginator_warped")

    def __init__(self, **kwargs):

        super().__init__(**kwargs)
        self.menu = BaseMenu
        self.reply_menu = ReplyMenu
        self.global_menu = GlobalMenu
        self.list_source = list_source
        self.pool = self.bot.pool
        self._db = None
        self.emote_unescape = self.bot.emote_unescape
        self.safe_everyone = self.bot.safe_everyone
        self.chunk = self.chunks

    @staticmethod
    def chunks(l, n):
        """Yield successive n-sized chunks from l."""
        for i in range(0, len(l), n):
            yield l[i:i + n]

    async def wait_for_input(self, transaction_id, cancel_message):

        message = await self.bot.wait_for('message', check=lambda message: message.author == self.author,
                                          timeout=120)

        while transaction_id not in message.content and "cancel" not in message.content.lower():
            message = await self.bot.wait_for('message', check=lambda message: message.author == self.author,
                                              timeout=120)

        if message.content.lower() == "cancel":
            await self.send(cancel_message.format(self.author.name))
            return False

        return True

    # pretty much taken from
    # https://github.com/Rapptz/RoboDanny/blob/ac3a0ed64381050c37761d358d4af90b89ec1ca3/cogs/utils/context.py
    @property
    def db(self):

        return self._db if self._db else self.pool

    async def _acquire(self):

        if self._db is None:
            self._db = await self.pool.acquire()

        return self._db

    def acquire(self):

        return _ContextDBAcquire(self)

    async def release(self):

        if self._db is not None:
            await self.bot.pool.release(self._db)

            self._db = None

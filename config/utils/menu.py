import typing
import asyncio

from discord.ext.menus.views import menus
from discord.ext.menus import First, Last, button

from config.utils.emojis import RIGHT_POINT, DRIGHT_POINT, LEFT_POINT, DLEFT_POINT, STOP

from main import Victorique


def page_source(per_page=10, parent: typing.Union[menus.PageSource,
                                                  menus.ListPageSource,
                                                  menus.GroupByPageSource,
                                                  menus.AsyncIteratorPageSource] = menus.ListPageSource):
    """Compact Page sources"""

    def pages(f):
        def __init__(self, *args, **kwargs):
            kwargs["per_page"] = per_page
            super(self.__class__, self).__init__(*args, **kwargs)
            self.__class__.default_colors = staticmethod(Victorique.default_colors)

        return type(f.__name__, (parent,), {"__init__": __init__, "format_page": f})

    return pages


class BaseMenu(menus.views.ViewMenuPages):

    def __init__(self, source, **kwargs):
        # to not allow spamming of certain buttons
        self.lock = asyncio.Lock()
        super().__init__(source, **kwargs)
        self.default_emojis = (
            "\N{BLACK LEFT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
            "\N{BLACK LEFT-POINTING TRIANGLE}\ufe0f",
            "\N{BLACK RIGHT-POINTING TRIANGLE}\ufe0f",
            "\N{BLACK RIGHT-POINTING DOUBLE TRIANGLE WITH VERTICAL BAR}\ufe0f",
            "\N{BLACK SQUARE FOR STOP}\ufe0f")

        for emoji in self.buttons:
            if emoji.name not in self.default_emojis:
                continue
            self.remove_button(emoji)

    # buttons for pagination

    @button(DRIGHT_POINT,
            position=First(0), skip_if=menus.MenuPages._skip_double_triangle_buttons)
    async def go_to_first_page(self, payload):
        """go to the first page"""
        await self.show_page(0)

    @button(LEFT_POINT, position=First(1))
    async def go_to_previous_page(self, payload):
        """go to the previous page"""
        await self.show_checked_page(self.current_page - 1)

    @button(RIGHT_POINT, position=Last(0))
    async def go_to_next_page(self, payload):
        """go to the next page"""
        await self.show_checked_page(self.current_page + 1)

    @button(DLEFT_POINT,
            position=Last(1), skip_if=menus.MenuPages._skip_double_triangle_buttons)
    async def go_to_last_page(self, payload):
        """go to the last page"""
        # The call here is safe because it's guarded by skip_if
        await self.show_page(self._source.get_max_pages() - 1)

    @button(STOP, position=Last(2))
    async def stop_pages(self, payload):
        """stops the pagination session."""
        self.stop()


class ReplyMenu(BaseMenu):
    def __init__(self, source, **kwargs):
        super().__init__(source, **kwargs)

    async def send_initial_message(self, ctx, channel):
        page = await self._source.get_page(0)
        kwargs = await self._get_kwargs_from_page(page)
        return await ctx.reply(**kwargs)


class GlobalMenu(BaseMenu):
    def __init__(self, source, **kwargs):

        super().__init__(source, **kwargs)

    def reaction_check(self, payload):

        if payload.message_id != self.message.id:
            return False

        if payload.user_id == self.bot.user.id:
            return False

        return payload.emoji in self.buttons


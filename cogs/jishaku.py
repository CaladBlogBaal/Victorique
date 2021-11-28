from jishaku.exception_handling import *
from jishaku.cog import Jishaku
from config.utils.emojis import *

# emojis
# Taken from the discord.py sever
task = NEGEVCHARGE
done = ALBASPARKLE
done_two = AWORRY
syntax_error = MIKASASNAPPED
timeout_error = "\N{ALARM CLOCK}"
error = MIKASASHOCK


class ReactorSub(ReplResponseReactor):

    async def __aenter__(self):
        self.handle = self.loop.create_task(do_after_sleep(1, attempt_add_reaction, self.message, task))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.handle:
            self.handle.cancel()
        if not exc_val:
            await attempt_add_reaction(self.message, done)
            await attempt_add_reaction(self.message, done_two)
            return
        self.raised = True
        if isinstance(exc_val, (asyncio.TimeoutError, subprocess.TimeoutExpired)):
            await attempt_add_reaction(self.message, timeout_error)
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)
        elif isinstance(exc_val, SyntaxError):
            await attempt_add_reaction(self.message, syntax_error)
            await send_traceback(self.message.channel, 0, exc_type, exc_val, exc_tb)
        else:
            await attempt_add_reaction(self.message, error)
            await send_traceback(self.message.author, 8, exc_type, exc_val, exc_tb)


Jishaku.ReplResponseReactor = ReactorSub
Jishaku.JISHAKU_RETAIN = True
Jishaku.JISHAKU_HIDE = True


def setup(bot):
    bot.add_cog(Jishaku(bot=bot))

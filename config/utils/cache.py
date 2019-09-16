import asyncio
import enum
from functools import wraps

from lru import LRU

# pretty much taken from https://gist.github.com/dlebech/c16a34f735c0c4e9b604


class Strategy(enum.Enum):

    lru = 1

    raw = 2


def _wrap_coroutine_storage(cache_dict, key, future):

    async def wrapper():

        val = await future

        cache_dict[key] = val

        return val

    return wrapper()


def _wrap_value_in_coroutine(val):

    async def wrapper():

        return val

    return wrapper()


def cache(maxsize=256, strategy=Strategy.lru):
    def memoize(f):
        if strategy is Strategy.lru:
            __cache = LRU(maxsize)
            __stats = __cache.items

        elif strategy is Strategy.raw:
            __cache = {}
            __stats = __cache.items

        def make_key(*args, **kwargs):
            key = f"{f.__module__}#{f.__name__}#{repr((args, kwargs))}"
            return key

        @wraps(f)
        def wrapper(*args, **kwargs):

            key = make_key(*args, **kwargs)

            try:

                val = __cache[make_key(*args, **kwargs)]

                if asyncio.iscoroutinefunction(f):

                    return _wrap_value_in_coroutine(val)

                return val

            except KeyError:

                val = f(*args, **kwargs)

                if asyncio.iscoroutine(val):

                    return _wrap_coroutine_storage(__cache, key, val)

                __cache[key] = val

                return val

        def __invalidate(*args, **kwargs):
            key = make_key(*args, **kwargs)

            try:

                del __cache[key]

            except KeyError:

                return False

            else:

                return True

        wrapper.get_stats = __stats
        wrapper.invalidate = __invalidate
        return wrapper

    return memoize

import re
import random

from collections import namedtuple
from html import unescape

import aiohttp
import discord

from bs4 import BeautifulSoup

from config.utils import requests
from config.utils.menu import page_source


@page_source(per_page=1)
async def default_source(self, menu, entry):

    urls = re.findall(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                      entry.sources)

    cleaned_sources = " "

    if urls:
        cleaned_sources = "\n".join("[Image source(%s)](%s)" % (urls.index(url) + 1, url) for url in urls[:4])

    cleaned_tags = unescape(entry.tags)
    length = 1200
    preview_url = entry.preview or entry.full_image
    full_size = entry.full_image
    # loli booru does not encode urls for some reason
    preview_url = preview_url.replace(" ", "%20")
    full_size = full_size.replace(" ", "%20")

    if len(cleaned_tags) <= length:
        pass
    else:
        cleaned_tags = " ".join(cleaned_tags[:length + 1].split(' ')[0:-1]) + " ..."

    embed = discord.Embed(colour=discord.Colour.dark_magenta(),
                          description=f"{cleaned_sources}\n```{cleaned_tags}```\n[Full size img url]({full_size})")

    footer_text = f"page {menu.current_page + 1} /{self.get_max_pages()}"

    embed.set_image(url=preview_url)

    if entry.preview:
        footer_text += "\npreview image for discord."

    embed.set_footer(text=footer_text)

    return embed


class AnimePicturesNet:

    def __init__(self, ctx, **kwargs):
        self.session = ctx.bot.session
        self.fetch = ctx.bot.fetch
        self.url = "https://anime-pictures.net/pictures/view_posts/0?"
        self.ctx = ctx
        self._image_url = None
        self._tags = None
        self._posts = None
        self._pages = None
        self._sources = None
        self._preview_url = None
        self._soup = None

        if "html" in kwargs:
            self.soup = kwargs["html"]

    @property
    def soup(self):
        return self._soup

    @soup.setter
    def soup(self, content):
        self._soup = BeautifulSoup(content, "html.parser")

    @property
    def tags(self):
        tags = self.soup.find("div", {"id": "tags_descriptions"}).find_all("strong")
        return " ".join(tag.text for tag in tags)

    @property
    def preview_url(self):
        return "https:" + self.soup.find("img", {"id": "big_preview"})["src"]

    @property
    def image_url(self):
        return "https://anime-pictures.net" + self.soup.find("div", {"id": "big_preview_cont"}).find("a")["href"]

    @property
    def sources(self):
        links = []

        for a in self.soup.find_all("div", "post_content"):

            a_s = a.find_all("a")[1:]

            for link in a_s:

                if link is None:
                    links.append("null")
                    continue

                link = link.get("href")

                if "anime-pictures.net" not in link and "view_" not in link:
                    links.append(f"{link}")

        return links

    @property
    def pages(self):
        divs = self.soup.find_all('div', attrs={'style': 'text-align: center;line-height: 16px;'})
        text = [a.text for a in divs]
        return int(text[0].split(" ")[2]) // 80

    @property
    def posts(self):
        return ["https://anime-pictures.net" + a.find("a").get("href")
                for a in self.soup.find_all("span", attrs={"img_block_big"})]

    async def post_response(self, tags=None):

        params = {"lang": "en", "order_by": "date"}

        if tags:
            params["search_tag"] = tags

        else:
            self.url = self.url.replace("0", str(random.randint(0, 4)))

        self.soup = await self.fetch(self.url, params=params)
        pages = self.pages

        if pages >= 1 and tags:
            random_page = random.randint(0, pages)
            self.url = self.url.replace("0", str(random_page))
            self.soup = await self.fetch(self.url, params=params)

        return self.posts

    async def post_request(self, limit, tags=None):
        if tags:
            posts = await self.post_response(tags)

        else:
            posts = await self.post_response()

        if not posts:
            return []

        posts = random.sample(posts, k=limit)
        posts = [await self.fetch(url) for url in posts]
        post = namedtuple("post", "preview sources tags full_image")
        results = set()

        for content in posts:
            self.soup = content
            sources = " ".join(self.sources)
            preview_url = self.preview_url
            if preview_url:
                results.add(post(preview_url, sources, self.tags.replace(":", ""), self.image_url))

        return list(results)

    async def get_posts(self, tags="", limit=1):

        try:

            results = await self.post_request(limit, tags)

        except TypeError as e:
            # one of properties are returning None if a type error is raised
            await self.ctx.reply("> A breaking change has occurred on anime-pictures.net bot owner has been notified.")
            raise e

        if not results:
            return await self.ctx.send(f":no_entry: | search failed with tags `{tags}`")

        pages = self.ctx.global_menu(default_source(results))
        await pages.start(self.ctx)


class BoardError(Exception):
    """Class to catch Pybooru error message."""


class _Moebooru:

    def __init__(self, site_name="", session=None, bot=None):

        self.site_list = {
            "konachan": {
                "url": "https://konachan.com",
                "api_version": "1.13.0+update.3"},
            "yandere": {
                "url": "https://yande.re",
                "api_version": "1.13.0+update.3"},
            "danbooru": {
                "url": "https://danbooru.donmai.us"},
            "safebooru": {
                "url": "https://safebooru.org/index.php?page=dapi"},
            "lolibooru": {
                "url": "https://lolibooru.moe"},
            "gelbooru": {
                "url": "https://gelbooru.com//index.php?page=dapi"
            },
        }

        if not bot:
            raise BoardError("Missing required argument (bot)")

        if not site_name:
            raise BoardError("Missing required argument (site_name)")

        headers = {"user-agent": "Victorique",
                   "content-type": "application/json; charset=utf-8"}

        self.__site_name = ""
        self.__site_url = ""
        self.request = requests.Request(bot, session)
        self.site_name = site_name
        if not session:
            self.client = aiohttp.ClientSession(headers=headers)
        self.client = session

    async def fetch(self, url, **kwargs):
        return await self.request.fetch(url, **kwargs)

    async def post(self, url, data, **kwargs):
        return await self.request.post(url, data, **kwargs)

    @property
    def site_name(self):
        return self.__site_name

    @property
    def site_url(self):
        return self.__site_url

    @site_name.setter
    def site_name(self, site_name):
        if site_name in self.site_list:

            self.__site_name = site_name
            self.__site_url = self.site_list[site_name]["url"]

        else:

            raise BoardError("The 'site_name' is not valid, specify a valid 'site_name'.")

    async def _request(self, url, request_args, method="GET"):

        if method != "GET":
            self.client.headers.update({"content-type": None})

            response = await self.post(url, **request_args)

        else:
            response = await self.fetch(url, **request_args)

        return response


class MoebooruApiMixin:
    def sanitize_params(self, allowed_params, params, method_name):
        for key in params:
            if key not in allowed_params:
                raise BoardError("Invalid parameter '{0}' for method {1}".format(key, method_name))

    async def post_list(self, **params):
        self.sanitize_params(["tags", "limit", "page"], params, "post_list")
        return await self._get("post", params)

    async def tag_list(self, **params):
        self.sanitize_params(["name", "id", "limit", "page", "order", "after_id"], params, "tag_list")
        return await self._get("tag", params)

    async def tag_related(self, **params):
        self.sanitize_params(["tags", "tupe"], params, "tag_related")
        return await self._get("tag/related", params)

    async def artist_list(self, **params):
        self.sanitize_params(["name", "order", "page"], params, "artist_list")
        return await self._get("artist", params)

    async def pool_list(self, **params):
        self.sanitize_params(["query", "page"], params, "pool_list")
        return await self._get("pool", params)

    async def pool_posts(self, **params):
        self.sanitize_params(["id", "page"], params, "pool_posts")
        return await self._get("pool/show", params)


class Moebooru(_Moebooru, MoebooruApiMixin):

    def __init__(self, ctx, site_name="", api_version='1.13.0+update.3'):

        super().__init__(site_name, ctx.bot.session, ctx.bot)
        self.ctx = ctx
        self.api_version = api_version.lower()

    async def get_nsfw_channel(self):
        async with self.ctx.acquire():
            if self.ctx.guild:
                return await self.ctx.db.fetchval("SELECT nsfw_channel from guilds where guild_id = $1",
                                                  self.ctx.guild.id)
            return True

    @_Moebooru.site_name.setter
    def site_name(self, site_name):

        _Moebooru.site_name.fset(self, site_name)

        if 'api_version' in self.site_list[site_name]:
            self.api_version = self.site_list[site_name]['api_version']

    def _build_url(self, api_call):

        if self.site_name == "gelbooru":

            api_call = api_call.replace("/", "&s")

            return "{0}&s={1}&q=index&json=1".format(self.site_url, api_call)

        if self.api_version in ("1.13.0", "1.13.0+update.1", "1.13.0+update.2"):
            if "/" not in api_call:
                return "{0}/{1}/index.json".format(self.site_url, api_call)
        return "{0}/{1}.json".format(self.site_url, api_call)

    async def _get(self, api_call, params, method='GET'):

        url = self._build_url(api_call)

        request_args = {'params': params}

        # Do call
        return await self._request(url, request_args, method)

    def process_tags(self, tags, safe):
        # re.split(r"(\)(?=\s+))"
        # for later
        tags = tags.replace("||", "\u200B").replace("|", "\u200B").replace("&&", "\u200B")
        tags = list(tag.rstrip().lstrip().replace(" ", "_") for tag in tags.split("\u200B"))

        if safe:
            tags.append("rating:safe")
            tags = re.sub(r"rating:[^\s\\]*.", "rating:safe", " ".join(tags))
        else:

            tags = " ".join(tags)

        return tags

    async def get_posts(self, tags="", limit=1):
        post = namedtuple("post", "preview sources tags full_image")
        nsfw_channel_id = await self.get_nsfw_channel()
        # flag for safe is the nsfw channel is not set as well
        safe = self.ctx.channel.id != nsfw_channel_id and nsfw_channel_id is not True
        tags = self.process_tags(tags, safe)
        results = await self.post_list(tags=tags)

        if isinstance(results, dict):
            results = results["post"]

        if not results:
            return await self.ctx.send(f":no_entry: | search failed with tags `{tags}`")

        pictures = set()
        limit = limit if len(results) >= limit else limit - len(results)
        results = random.sample(results, limit)

        for js in results:
            pictures.add(post(js.get("sample_url") or js.get("file_url"),
                              js.get("source", " "), js.get("tags"),
                              js.get("file_url")))

        pages = self.ctx.global_menu(default_source(list(pictures)))
        await pages.start(self.ctx)


class Safebooru(Moebooru):
    def __init__(self, ctx):

        super().__init__(ctx, "safebooru")

    def _build_url(self, api_call):
        api_call = api_call.replace("/", "&s")
        return "{0}&s={1}&q=index".format(self.site_url, api_call)

    async def _request(self, url, request_args, method="GET"):
        api_calls = re.findall(r"&s=(\w+)", url)
        if method != "GET":
            self.client.headers.update({"content-type": None})

            response = await self.post(url, **request_args)

        else:
            response = await self.fetch(url, **request_args)

        return BeautifulSoup(response, "lxml").find_all(api_calls[0])

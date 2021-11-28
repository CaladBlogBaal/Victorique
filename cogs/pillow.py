import random
import textwrap

from functools import partial
from io import BytesIO

import discord
from discord.ext import commands

from PIL import Image, ImageDraw, ImageFont

from config.utils.checks import private_guilds_check


class ImageDrawText:
    def __init__(self, bot, file_or_path):
        self.buffer = BytesIO()
        self.bot = bot
        self.image = Image.open(file_or_path)
        self.size = self.image.size
        self.draw = ImageDraw.Draw(self.image)
        self.font = None

    def save(self):
        self.image.save(self.buffer, "PNG")
        self.buffer.seek(0)
        self.image.close()
        return self.buffer

    @staticmethod
    def text_wrap(text, width):
        wrapper = textwrap.TextWrapper(width=width)
        text = wrapper.wrap(text)
        return text

    def font_setter(self, font, font_size=16, font_colour=(0, 0, 0)):
        font = ImageFont.truetype(font, font_size)
        self.font = (font, font_colour)

    @staticmethod
    def _boundary_box_set(img_x, img_y, top_boundary, lower_boundary):
        return img_x - top_boundary, img_y - lower_boundary, img_x + top_boundary, img_y + lower_boundary

    def _draw_text_on_image(self, text, coordinates: list, down=False):

        font, font_colour = self.font[0], self.font[1]
        for c in text:
            width, height = font.getsize(c)
            self.draw.text(coordinates, c, font=font, fill=font_colour)

            if down:
                coordinates[1] += height

            else:
                coordinates[0] += width

    def _draw_text_image_rotated(self, text, coordinates: list, rotate, down=False):
        buf = BytesIO()
        font, font_colour = self.font[0], self.font[1]
        cords = [0, 0]

        width, height = font.getsize(" ".join(text))
        if down:
            img = Image.new("RGBA", (width, height * len(text)), (0, 0, 0, 0))
        else:
            img = Image.new("RGBA", (width, height), (255, 0, 0, 0))

        draw = ImageDraw.Draw(img)
        for c in text:
            width, height = font.getsize(c)
            draw.text(cords, c, font=font, fill=font_colour)
            if down:
                cords[1] += height

            else:
                cords[0] += width

        img = img.rotate(rotate, expand=1)
        img.save(buf, "png")
        buf.seek(0)
        self._paste_image_on_image(coordinates, buf)

    def _draw_circle_on_image(self, size, cords, fill):
        # crude circle pasting since eclipse.draw by itself is too rough
        # make a new rectangular image filled with a colour
        buf = BytesIO()
        image = Image.new("RGB", size, fill)
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 0, 0), fill=fill)
        image.save(buf, "png")
        buf.seek(0)
        # crop it to a circle
        circle = self._circle_crop(buf)
        # paste it on the image
        self._paste_image_on_image(cords, circle)

    def _paste_image_on_image(self, offset, img, alpha=True):

        with Image.open(img) as img_:
            if alpha:
                self.image.paste(img_, offset, img_)

            else:
                self.image.paste(img_, offset)

    @staticmethod
    def _circle_crop(img):
        buf = BytesIO()

        with Image.open(img) as im:
            with Image.new("L", im.size, 0) as mask:
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0) + im.size, fill=255)

            bigsize = (im.size[0] * 4, im.size[1] * 4)

            with Image.new("L", bigsize, 0) as mask:
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0) + bigsize, fill=255)
                mask = mask.resize(im.size, Image.ANTIALIAS)
                im.putalpha(mask)

        im.save(buf, "png")
        buf.seek(0)
        return buf

    async def draw_text_on_image_rotated(self, *args, **kwargs):
        thing = partial(self._draw_text_image_rotated, *args, **kwargs)
        return await self.bot.loop.run_in_executor(None, thing)

    async def draw_text_on_image(self, *args, **kwargs):
        partial_func = partial(self._draw_text_on_image, *args, **kwargs)
        return await self.bot.loop.run_in_executor(None, partial_func)

    async def draw_circle_on_image(self, *args, **kwargs):
        partial_func = partial(self._draw_circle_on_image, *args, **kwargs)
        return await self.bot.loop.run_in_executor(None, partial_func)

    async def paste_image_on_image(self, *args, **kwargs):
        partial_func = partial(self._paste_image_on_image, *args, **kwargs)
        return await self.bot.loop.run_in_executor(None, partial_func)

    async def circle_crop(self, *args, **kwargs):
        partial_func = partial(self._circle_crop, *args, **kwargs)
        return await self.bot.loop.run_in_executor(None, partial_func)


class Images(commands.Cog):
    """Image generation related commands"""
    def __init__(self, bot):
        self.bot = bot
        self.default_avatars = ["https://cdn.discordapp.com/embed/avatars/0.png",
                                "https://cdn.discordapp.com/embed/avatars/1.png",
                                "https://cdn.discordapp.com/embed/avatars/2.png",
                                "https://cdn.discordapp.com/embed/avatars/3.png",
                                "https://cdn.discordapp.com/embed/avatars/4.png"]

        self.whitney = "images/resources/fonts/Whitney-Medium.ttf"
        self.arial_unicode = "images/resources/fonts/Arial-Unicode-Regular.ttf"
        self.droid_serif = "images/resources/fonts/DroidSerif-Bold.ttf"

    @staticmethod
    def string_splice(comment, index):
        if len(comment) > index:
            return " ".join([comment[0:index]])
        return comment

    def string_splice_append(self, text, index, length, characters_to_append):
        text = self.string_splice(text, index)
        if len(text) > length:
            text += characters_to_append
            return text

        return text

    @staticmethod
    def image_resize(image_path, size):
        buf = BytesIO()
        im = Image.open(image_path)
        im = im.resize(size, Image.ANTIALIAS)
        im.save(buf, "png")
        buf.seek(0)
        return buf

    @commands.command()
    async def rate(self, ctx, *, message):
        """Have momiji rate something"""
        image = ImageDrawText(self.bot, "images/rate.png")
        number = random.randint(0, 10)
        rating = f"{number}/10"

        cords = [147.5, 430]

        if number < 10:
            cords = [185.5, 430]

        image.font_setter(self.whitney, 80)

        await image.draw_text_on_image(rating, cords)

        file = discord.File(filename="rate.png", fp=image.save())
        await ctx.send(file=file)

    @commands.command()
    async def clyde(self, ctx, *, message: commands.clean_content):
        """Have clyde say a echo a message"""
        image = ImageDrawText(self.bot, "images/clyde.png")
        message = ctx.emote_unescape(message)
        cords = [123, 86]
        font_colour = (255, 255, 255)
        message = self.string_splice(message, 108)
        image.font_setter(self.whitney, font_colour=font_colour)
        await image.draw_text_on_image(message, cords, False)
        file = discord.File(filename="clyde.png", fp=image.save())
        await ctx.send(file=file)

    @commands.command(aliases=["fc"])
    @commands.guild_only()
    async def fake_kick(self, ctx, *, member: discord.Member):
        """Get a false kick image of a guild/user member"""
        await ctx.trigger_typing()
        image = ImageDrawText(self.bot, "images/kick.png")
        avatar_icon_bytes_list = [member]

        guild_members = [member for member in ctx.guild.members if member.status.value in ("online", "dnd", "idle")]

        if member in guild_members:
            guild_members.remove(member)

        try:
            randoms = random.sample(guild_members, 5)
        except ValueError:
            randoms = random.choices(guild_members, k=5)

        avatar_icon_bytes_list.extend(randoms)
        # convert the avatars to icon's
        for i, member_ in enumerate(avatar_icon_bytes_list):

            # if it's a default avatar resize, since (format="png", size=32) does not work on default avatars
            if str(member_.avatar.replace(format="png")) in self.default_avatars:
                avatar_icon_bytes = BytesIO(await member_.avatar_url_as(format="png").read())
                partial_func = partial(self.image_resize, avatar_icon_bytes, (32, 32))
                avatar_bytes = await self.bot.loop.run_in_executor(None, partial_func)
                avatar_bytes = await image.circle_crop(avatar_bytes)

            else:
                avatar_icon_bytes = BytesIO(await member_.avatar.replace(format="png", size=32).read())
                avatar_bytes = await image.circle_crop(avatar_icon_bytes)

            avatar_icon_bytes_list[i] = avatar_bytes

        avatar_font_colour = member.colour.to_rgb()

        if avatar_font_colour == (0, 0, 0):
            avatar_font_colour = (188, 189, 189)

        kick_text = self.string_splice_append(f"Kick {member.name}", 24, 23, "...")
        ban_text = self.string_splice_append(f"Ban {member.name}", 25, 24, "...")
        avatar_name_text = self.string_splice_append(member.display_name, 17, 16, "...")
        online_text = str(len(guild_members)) if len(guild_members) >= 6 else "6"

        image.font_setter(self.whitney, 14, (215, 66, 66))
        await image.draw_text_on_image(kick_text, [60, 382.5])
        await image.draw_text_on_image(ban_text, [60, 412.5])

        image.font_setter(self.whitney, 16, avatar_font_colour)
        await image.draw_text_on_image(avatar_name_text, [50, 36.5])

        image.font_setter(self.whitney, 12, (114, 130, 132))
        await image.draw_text_on_image(online_text, [68, 5])

        # avatar url, coordinates
        avatar_x, avatar_y = 9, 30
        # dark circle, coordinates
        dark_circle_x, dark_circle_y = 28, 49
        # online circle, coordinates
        status_circle_x, status_circle_y = 31, 52
        for avatar_bytes in avatar_icon_bytes_list:
            await image.paste_image_on_image((avatar_x, avatar_y), avatar_bytes)
            await image.paste_image_on_image((195, 385), "images/mouseicon.png")
            await image.draw_circle_on_image((15, 15), (dark_circle_x, dark_circle_y), (47, 49, 54))
            await image.draw_circle_on_image((10, 10), (status_circle_x, status_circle_y), (67, 181, 129))
            # the next set of images will be drawn down
            avatar_y += 44
            dark_circle_y += 44
            status_circle_y += 44

        file = discord.File(filename="kick.png", fp=image.save())
        await ctx.send(file=file)

    @commands.command()
    async def sign(self, ctx, *, text: commands.clean_content):
        """write some text on a dead meme"""
        # this is gonna be improved later tbh
        image = ImageDrawText(self.bot, "images/sign.png")
        text = ctx.emote_unescape(text)
        text = self.string_splice(text, 36)
        text = image.text_wrap(text, 9)
        image.font_setter(self.arial_unicode, 60, (0, 0, 0))
        rotate = 356
        await image.draw_text_on_image_rotated(text, [473, 190], rotate, True)

        file = discord.File(filename="sign.png", fp=image.save())
        await ctx.send(file=file)

    @commands.command()
    async def two_cats(self, ctx, *, text: commands.clean_content):
        """Write some text on two signs
        to write on both signs split the text with || or | if no separator is passed the text will be halved
        and written on both signs."""
        image = ImageDrawText(self.bot, "images/two_cats.jpg")
        text = ctx.emote_unescape(text)
        try:

            text, text_two = text.split("|", 1) or text.split("||", 1)

        except ValueError:
            index = len(text) // 2
            text_two = " ".join([text[index:]])
            text = " ".join([text[:index]])

            if not text:
                text = text_two
                # this is an invisible character
                text_two = "\u200b"

        text = self.string_splice(text, 41)
        text_two = self.string_splice(text_two, 41)

        image.font_setter(self.arial_unicode, 18, (6, 0, 15))
        text = image.text_wrap(text, 14)
        text_two = image.text_wrap(text_two, 14)
        rotate = 358
        await image.draw_text_on_image_rotated(text, [67, 217], rotate, True)
        await image.draw_text_on_image_rotated(text_two, [268, 232], rotate, True)

        file = discord.File(filename="sign.png", fp=image.save())
        await ctx.send(file=file)

    @private_guilds_check()
    @commands.command()
    async def nimi(self, ctx, *, message: commands.clean_content):
        """Have nimi say something"""
        image = ImageDrawText(self.bot, "images/warnimage.PNG")
        date = ctx.message.created_at
        date = date.strftime("%d/%m/20%y")

        message = ctx.emote_unescape(message)
        message = image.text_wrap(message, 70)
        cords = [81, 74]
        font_colour = (193, 195, 197)
        font_date_colour = (108, 112, 119)

        image.font_setter(self.whitney, font_colour=font_colour)
        await image.draw_text_on_image(message, cords, True)

        image.font_setter(self.whitney, 12, font_date_colour)

        await image.draw_text_on_image(date, [191, 6])
        file = discord.File(filename="nimi.png", fp=image.save())
        await ctx.send(file=file)


def setup(bot):
    bot.add_cog(Images(bot))

import re
import asyncio
import csv
import shutil
import json
import typing

from io import BytesIO
from tempfile import NamedTemporaryFile

import discord
from discord.ext import commands

import matplotlib.pyplot as plt

from bs4 import BeautifulSoup

from config.utils.paginator import PaginatorGlobal, Paginator


class AzurLane(commands.Cog, name="Azur Lane"):
    """Azur lane related commands"""
    def __init__(self, bot):

        # thanks to @cyberFluff#9161
        with open(r"config/Gear Guide Hub.csv", "r") as file:
            ship_gear_hub = list(row for row in csv.reader(file) if row)

        self.ship_gear_hub = ship_gear_hub
        self.bot = bot

    @staticmethod
    def auxiliary_slots(auxiliary_list, option=0):
        auxiliary_slot_hp = 0
        auxiliary_slot_evasion = 0

        if option == 9:
            auxiliary_slot_hp = 0
            auxiliary_slot_evasion = 0

        if option in (1, 2, 5):
            auxiliary_slot_hp = auxiliary_list[option - 1][1]

        elif option == 6:
            auxiliary_slot_evasion = auxiliary_list[option - 1][1]

        elif option in (3, 4, 7, 8):
            auxiliary_slot_hp = auxiliary_list[option - 1][1]
            auxiliary_slot_evasion = auxiliary_list[option - 1][2]

        return auxiliary_slot_hp, auxiliary_slot_evasion

    @staticmethod
    def get_ship_stat_evasion_rate(list_in, ship_name):
        for row in list_in:
            if row[1] == ship_name:
                evasion_rate = float(row[7] + row[8] + row[9])
                return evasion_rate

    @staticmethod
    async def azur_lane_wiki_search(ctx, item, allow_none_png=False, paginate=True):

        if allow_none_png is False:
            with open(r"config/ship_list.json", "r") as f:
                ship_json_list = json.load(f)

            item = item.replace(" ", "_")

            if not item.endswith(".png"):
                item = item + ".png"

            for json_ in ship_json_list:

                if json_.get("name").lower() == item.lower():

                    item = json_.get("name").capitalize() + ".png"

                elif json_.get("name").lower() in item.lower() and paginate:

                    item = re.sub(r"\s+", "", item, flags=re.UNICODE).replace("_", "")

        p = PaginatorGlobal(ctx)
        kwargs = {
            "aisort": "name",
            "action": "query",
            "format": "json",
            "list": "allimages",
            "aiprefix": item
        }

        js = await ctx.bot.fetch("https://azurlane.koumakan.jp/w/api.php?action=query", params=kwargs)

        for js in js["query"]["allimages"]:
            if paginate:

                if item in js["url"]:
                    embed = discord.Embed(color=ctx.bot.default_colors(), description=f"[{js['title']}]({js['url']})")

                    if allow_none_png is False:
                        embed.set_image(url=js["url"])

                    await p.add_page(embed)

            else:
                return js["url"]

        try:

            await p.paginate()

        except IndexError:
            if not paginate:
                return "https://www.sweetsquared.ie/sca-dev-kilimanjaro/img/no_image_available.jpeg" \
                       "?resizeid=19&resizeh=1200&resizew=1200"
            return await ctx.send(f":no_entry: | search failed for {item}")

    async def make_gear_guide_embed(self, ctx, ship_name, url):
        # since im lazy this only temp
        if "kai" in ship_name:
            ship_name = ship_name.replace("kai", "Kai")

        img_url = await self.azur_lane_wiki_search(ctx, ship_name, paginate=False)
        embed = discord.Embed(title=f"Gear guide for {ship_name}", url=url, color=self.bot.default_colors())
        embed.set_image(url=img_url)
        return embed

    async def get_hull_or_rarity(self, ctx, index, item):
        p = Paginator(ctx)
        col_name = self.ship_gear_hub[0][index]

        for row in self.ship_gear_hub:
            if row[index].lower() == item.lower():
                ship_name = row[0]
                url = row[3]
                embed = await self.make_gear_guide_embed(ctx, ship_name, url)
                await p.add_page(embed)

        try:

            await p.paginate()

        except IndexError:
            await ctx.send(f"> invalid {col_name} was entered.")

    @commands.command()
    async def ehp(self, ctx, enemy_level: typing.Optional[int] = 0, default: typing.Optional[bool] = False,
                  *, ship_name):
        """
        Get a ships basic ehp value
        pass True to default to use default auxiliary slots
        """
        # will probably improve this later
        async def category_choice_set(auxiliary_list_):

            category_choice_ = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author,
                                                       timeout=60)

            category_choice_ = category_choice_.content

            try:
                category_choice_ = int(category_choice_)
            except ValueError:
                pass

            if category_choice_ not in (1, 2, 3, 4, 5, 6, 7, 8, 9):

                await ctx.send(":no_entry: | invalid category choice was received will default to the best"
                               " average auxiliary slot for this hull ")

                if hull in ("DD", "CL"):
                    display_aux_ = auxiliary_list_[0][0]
                    category_choice_ = 1

                else:
                    display_aux_ = auxiliary_list_[7][0]
                    category_choice_ = 8

                if category_choice_ == 0:
                    await ctx.send("exiting the calc... 0 was entered")
                    return False

            else:
                if not category_choice_ == 9:
                    display_aux_ = auxiliary_list[category_choice_ - 1][0]
                else:
                    display_aux_ = "nothing"

            msg_ = await ctx.send(f"auxiliary slot has been set to {display_aux_}")
            messages_to_delete.append(msg_.id)
            await asyncio.sleep(0.25)
            return category_choice_, display_aux_

        messages_to_delete = []
        ship_name = ship_name.lower()

        with open(r"config/ship_list.json", "r") as f:
            ship_json_list = json.load(f)

        ship_json = None

        for json_ in ship_json_list:
            if json_.get("name").lower() == ship_name:
                ship_json = json_

        if ship_json is None:
            return await ctx.send(f"the ship {ship_name} was not found try correctly spelling the ship's name")

        csv_file = r"config/ShipStats120.csv"
        level_display = 120

        msg = await ctx.send(":ship: :ship: :ship:  | Type in the formation, Single, Diamond or Double.")
        messages_to_delete.append(msg.id)

        formation_choice = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author,
                                                   timeout=60)

        formation_choice = formation_choice.content

        if formation_choice.lower() == "exit":
            return await ctx.send("exiting the calc...")

        if formation_choice.lower() not in ("single", "diamond", "double"):
            await ctx.send(f":no_entry: |  invalid formation {formation_choice} was passed defaulting to diamond.")

        if formation_choice.lower == "single":
            formation_bonus = -0.1

        elif formation_choice.lower == "double":
            formation_bonus = 0.3

        else:
            formation_bonus = 0

        level_difference = enemy_level - level_display

        if level_difference < 0:
            level_difference = 0

        elif level_difference > 20:
            level_difference = 20

        with open(csv_file, "r") as file:
            ship_stat_list = list(csv.reader(file))

        ehp_list = []
        hit_list = []

        auxiliary_list = [["Repair Tool", 500],
                          ["Fire Suppressor", 226],
                          ["Navy Camouflage", 44, 17],
                          ["Fuel Filter", 350, 5],
                          ["Anti Torpedo Bulge", 350],
                          ["SG Radar", 15],
                          ["Beaver Badge", 75, 35],
                          ["Improved Hydraulic Rudder", 60, 40]]

        await asyncio.sleep(0.25)
        hull = ship_json["type"]

        if hull in ("DD", "CL"):
            display_aux = auxiliary_list[0][0]
            display_aux2 = display_aux
            category_choice = 1
            category_choice2 = category_choice

        else:
            display_aux = auxiliary_list[7][0]
            display_aux2 = display_aux
            category_choice = 1
            category_choice2 = category_choice

        embed = discord.Embed(title=f"EHP Calculator",
                              description=f"Select an option for aux slot by typing it's number"
                              "\n1) Repair Tool "
                              "\n2) Fire Suppressor"
                              "\n3) Navy Camouflage "
                              "\n4) Fuel Filter "
                              "\n5) Anti Torpedo Bulge  "
                              "\n6) SG Radar "
                              "\n7) Beaver Badge "
                              "\n8) IHR "
                              "\n9) Nothing "
                              "\n ( say 0 to exit )",
                              color=discord.Color.dark_magenta())

        embed.set_footer(text=f'Requested by {ctx.message.author.name}', icon_url=ctx.message.author.avatar_url)
        embed.timestamp = ctx.message.created_at

        if not default:

            msg = await ctx.send(embed=embed)
            category_choice, display_aux = await category_choice_set(auxiliary_list)
            messages_to_delete.append(msg.id)

            await msg.delete()
            await asyncio.sleep(0.25)

            msg = await ctx.send(embed=embed)
            messages_to_delete.append(msg.id)
            category_choice2, display_aux2 = await category_choice_set(auxiliary_list)

        await msg.delete()
        await asyncio.sleep(0.25)

        auxiliary_slot_hp, auxiliary_slot_evasion = self.auxiliary_slots(auxiliary_list, category_choice)
        auxiliary_slot_hp2, auxiliary_slot_evasion2 = self.auxiliary_slots(auxiliary_list, category_choice2)

        ship_evasion = ship_json["evasion"]
        ship_hp = ship_json["hp"]
        ship_luck = ship_json["luck"]

        ship_evasion_rate = self.get_ship_stat_evasion_rate(ship_stat_list, ship_name)
        if not ship_evasion_rate:
            ship_evasion_rate = 0

        enemy_hit = 0
        enemy_luck = 0

        ship_evasion += + auxiliary_slot_evasion + auxiliary_slot_evasion2
        ship_evasion = ship_evasion * (1 + formation_bonus)
        ship_hp += auxiliary_slot_hp + auxiliary_slot_hp2
        for _ in range(11):
            accuracy = 0.1 + enemy_hit / (enemy_hit + ship_evasion + 2) + (
                (enemy_luck - ship_luck + level_difference) * 0.001
            ) - ship_evasion_rate

            if accuracy < 0.1:
                accuracy = 0.1

            elif accuracy > 1:
                accuracy = 1

            ehp = ship_hp / accuracy
            ehp = round(ehp, 2)
            ehp_list.append(ehp)
            hit_list.append(enemy_hit)
            enemy_hit += 10

        ship_details = "Enemy luck is set to 0 as a constant \nin auxiliary slot one is {}, in auxiliary slot two is {}"
        ship_details = ship_details.format(display_aux, display_aux2)

        for i, _ in enumerate(hit_list):
            ship_details += f"\n{ship_name}\'s EHP at enemy hit {str(hit_list[i])} is {str(ehp_list[i])}"

        ship_name = ship_name.capitalize()
        embed = discord.Embed(title=f"{ship_name}\'s EHP values",
                              description=ship_details,
                              color=discord.Color.dark_magenta())
        embed.set_footer(text=f'Requested by {ctx.message.author.name}', icon_url=ctx.message.author.avatar_url)
        embed.timestamp = ctx.message.created_at

        hit_list = [hit for hit in hit_list if hit >= 40]
        ehp_list = [ehp_list[i] for i, value in enumerate(ehp_list) if i >= 4]
        plt.plot(hit_list, ehp_list, "mo")
        plt.ylabel("EHP")
        plt.xlabel("Enemy hit")
        plt.title(f"EHP values for {ship_name}\n (with enemy luck 0)")

        buf = BytesIO()
        plt.savefig(buf, format="png")
        buf.seek(0)
        file = discord.File(filename="EHP Graph.png", fp=buf)
        embed.set_image(url="attachment://EHP Graph.png")

        await ctx.send(file=file, embed=embed)

        buf.close()
        plt.close()

        try:
            await ctx.channel.purge(check=lambda message: message.id in messages_to_delete)

        except AttributeError:
            pass

    @commands.command(aliases=["ss"])
    async def ship_stats(self, ctx, *, ship_name):
        """get the stats of a ship"""
        ship_name = ship_name.lower()

        with open(r"config/ship_list.json", "r") as f:
            ship_json_list = json.load(f)

        ship_json = None

        for json_ in ship_json_list:
            if json_.get("name").lower() == ship_name:
                ship_json = json_

        if ship_json is None:
            return await ctx.send(f":no_entry: | could not find {ship_name}.")

        content = ""

        rep_dict = {"eff": "primary efficiency", "secff": "secondary efficiency", "aaeff": "anti air efficiency",
                    "trieff": "tertiary efficiency"}

        for key, value in ship_json.items():

            if value != 0:

                if rep_dict.get(key):
                    key = rep_dict[key]

                if isinstance(value, (float, int)):
                    if key == "oil":
                        pass

                    elif value < 10 or value < 0:
                        value *= 100
                        value = str(int(value)) + " %"
                    value = str(value)

                name = key.capitalize()
                result = f"[{name.ljust(22)}: {value.ljust(5)}"
                content += f"\n{result}"

        await ctx.send(f"```ini\n{content}```")

    @commands.command()
    async def al(self, ctx, *, search):
        """
        Search for something on the AL wiki
        """
        p = PaginatorGlobal(ctx)
        count = 1

        kwargs = {"search": search}
        results = await self.bot.fetch("https://azurlane.koumakan.jp/w/api.php?action=opensearch", params=kwargs)
        length = len(results)

        link = f"https://azurlane.koumakan.jp/w/index.php?" \
            f"search={search}&title=Special%3ASearch&profile=default&fulltext=1"

        for result in results:

            for url in result:

                if re.findall('https?://(?:[-\\w.]|(?:%[\\da-fA-F]{2}))+', url):
                    embed = discord.Embed(title=f"Search results for {search}", color=self.bot.default_colors())
                    embed.add_field(name=f"Search result: {count}", value=url, inline=False)
                    count += 1
                    await p.add_page(embed)

        if length == 0:
            content = await self.bot.fetch(link)

            soup = BeautifulSoup(content, "html.parser")

            a = soup.find("ul", {"class": "mw-search-results"})

            if a is None:
                return await ctx.send(f":no_entry: | no search results for {search}")

            for link in a.find_all("a", href=True):
                embed = discord.Embed(title=f"Main search failed searched for any page that contained "
                                            f"{search}", color=self.bot.default_colors())
                embed.add_field(name=f"Search result: {count}", value=f"https://azurlane.koumakan.jp{link.get('href')}"
                                , inline=False)
                await p.add_page(embed)
        try:

            await p.paginate()

        except IndexError:
            return await ctx.send(f":no_entry: | search failed for {search}")

    @commands.command(aliases=["afs"])
    async def al_file_search(self, ctx, *, item):
        """Search for any file type on the al aiki"""
        await self.azur_lane_wiki_search(ctx, item, True)

    @commands.command(aliases=["ais"])
    async def al_img_search(self, ctx, *, item):
        """search for a image on the al wiki"""
        await self.azur_lane_wiki_search(ctx, item)

    @commands.group(aliases=["gg"], invoke_without_command=True)
    async def gear_guide(self, ctx, *, ship_name):
        """the main command for gear guides by itself gets the gear guide of a ship"""

        if "kai" in ship_name.lower():
            ship_name = ship_name[::-1].replace(" ", "", 1)[::-1]

        for row in self.ship_gear_hub:
            if row[0].lower() == ship_name.lower():
                ship_name = row[0]
                url = row[3]
                embed = await self.make_gear_guide_embed(ctx, ship_name, url)
                return await ctx.send(embed=embed)

        return await ctx.send(f"> couldn't find a guide for {ship_name}")

    @gear_guide.command()
    async def hull(self, ctx, *, hull):
        """get a list of gear guides based on hull type."""
        await ctx.trigger_typing()
        await self.get_hull_or_rarity(ctx, 2, hull)

    @gear_guide.command()
    async def rarity(self, ctx, *, rarity):
        """get a list of gear guides based on rarity
           rarities are as follow common, rare, elite, super rare or ssr."""
        await ctx.trigger_typing()

        if rarity.lower() == "super rare":
            rarity = "ssr"

        await self.get_hull_or_rarity(ctx, 1, rarity)

    @gear_guide.command()
    @commands.is_owner()
    async def add(self, ctx, url, hull, rarity, *, ship_name):
        """add a new ship to the csv"""
        new_row = [ship_name, rarity, hull, url]
        temp = NamedTemporaryFile(mode="w", delete=False)
        filename = "config/Gear Guide Hub.csv"

        with open(r"config/Gear Guide Hub.csv", "r") as file, temp:
            csv_writer = csv.writer(temp, delimiter=',')

            for row in self.ship_gear_hub:
                if row[0].lower() == ship_name.lower():
                    return await ctx.send("> ship already exists.")

            self.ship_gear_hub.append(new_row)

            csv_writer.writerows(self.ship_gear_hub)

        shutil.move(temp.name, filename)
        await ctx.send("> successfully updated.")
        self.bot.reload_extension("cogs.azur_lane")


def setup(bot):
    bot.add_cog(AzurLane(bot))



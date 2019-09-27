import re
import asyncio
import csv
import shutil
import json
import typing

from tempfile import NamedTemporaryFile

import discord
from discord.ext import commands

from bs4 import BeautifulSoup

from config.utils.paginator import PaginatorGlobal, Paginator


class AzurLane(commands.Cog, name="Azur Lane"):
    """Azur lane related commands"""
    def __init__(self, bot):

        # thanks to @cyberFluff#9161
        with open(r"config/Gear Guide Hub.csv", "r") as file:
            ship_gear_hub = list(csv.reader(file))

        with open(r"config/ShipStats120.csv", "r") as file:
            reader = csv.DictReader(file, fieldnames=("# Lvl 120", "Name", "Hull", "HP", "EVA", "LUK", "Armor",
                                                      "EVA Rate", "EVAS", "DMGR"))
            reader = list(reader)

        self.ship_stats_reader = reader
        self.ship_gear_hub = ship_gear_hub
        self.bot = bot

    @staticmethod
    def delete_from_reader(ship_name, list_of_rows, update_function):
        for i, row in enumerate(list_of_rows):
            if isinstance(row, dict):

                if row["Name"].lower() == ship_name.lower():
                    del list_of_rows[i]
                    update_function()
                    return True

            else:

                if row[0].lower() == ship_name.lower():
                    del list_of_rows[i]
                    update_function()
                    return True

        return False

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

    def update_ship_gear_hub(self):
        temp = NamedTemporaryFile(mode="w", delete=False)
        filename = "config/Gear Guide Hub.csv"

        with open(r"config/Gear Guide Hub.csv", "r") as file, temp:
            csv_writer = csv.writer(temp, delimiter=",", lineterminator="\n")
            csv_writer.writerows(self.ship_gear_hub)

        shutil.move(temp.name, filename)

    def update_ship_stats_csv(self):
        temp = NamedTemporaryFile(mode="w", delete=False)
        filename = "config/ShipStats120.csv"
        fields = ["# Lvl 120", "Name", "Hull", "HP", "EVA", "LUK", "Armor", "EVA Rate", "EVAS", "DMGR"]

        with open(r"config/ShipStats120.csv", "r") as file, temp:
            writer = csv.DictWriter(temp, fieldnames=fields, lineterminator="\n")

            for row in self.ship_stats_reader:
                writer.writerow(row)

        shutil.move(temp.name, filename)

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
    async def ehp(self, ctx, enemy_hit: typing.Optional[int] = 45, default: typing.Optional[bool] = False,
                  enemy_level: typing.Optional[int] = 0, *, ship_name):
        """
        Get a ships basic ehp value
        pass True to default to use default auxiliary slots, if you want to change
        the enemy level you must pass the enemy hit followed by the enemy level eg
        vic ehp 45 130 Javelin / vic ehp 45 True 130 Javelin
        """

        async def category_choice_set(aux_list):

            index_ = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)

            index_ = index_.content

            try:
                index_ = int(index_)
            except ValueError:
                pass

            if index_ not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 0):

                await ctx.send(":no_entry: | invalid category choice was received will default to the best"
                               " average auxiliary slot for this hull ")

                if hull in ("DD", "CL"):
                    display_aux_ = aux_list[0][0]
                    index_ = 1

                else:
                    display_aux_ = aux_list[7][0]
                    index_ = 8

            else:

                if index_ == 0:
                    await ctx.send("exiting the calc... 0 was entered")
                    return False

                display_aux_ = "nothing"

            msg_ = await ctx.send(f"auxiliary slot has been set to {display_aux_}")
            messages_to_delete.append(msg_.id)
            await asyncio.sleep(0.25)
            return index_, display_aux_

        messages_to_delete = []
        ship_name = ship_name.lower()
        ship_dict = None

        for row in self.ship_stats_reader:
            if row.get("Name", "null").lower() == ship_name:
                ship_dict = row

        if ship_dict is None:
            return await ctx.send(f"> the ship {ship_name} was not found.")

        for key, value in ship_dict.items():
            if value.isdigit():
                ship_dict[key] = int(value)

            try:
                ship_dict[key] = float(value)
            except ValueError:
                pass

        msg = await ctx.send(":ship: :ship: :ship:  | Type in the formation, Single, Diamond or Double.")
        messages_to_delete.append(msg.id)

        msg = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)

        msg = msg.content.lower()

        if msg == "exit":
            return await ctx.send("exiting the calc...")

        if msg not in ("single", "diamond", "double"):
            await ctx.send(f":no_entry: |  invalid formation {msg} was passed defaulting to diamond.")

        formation_bonus = {"single": -0.1, "double": 0.3}.get(msg, 0)
        form_display = msg

        level_difference = enemy_level - 120

        if level_difference < 0:
            level_difference = 0

        elif level_difference > 20:
            level_difference = 20

        auxiliary_list = [["Repair Tool", 500],
                          ["Fire Suppressor", 226],
                          ["Navy Camouflage", 44, 17],
                          ["Fuel Filter", 350, 5],
                          ["Anti Torpedo Bulge", 350],
                          ["SG Radar", 15],
                          ["Beaver Badge", 75, 35],
                          ["Improved Hydraulic Rudder", 60, 40]]

        hull = ship_dict["Hull"]

        if hull in ("DD", "CL"):
            display_aux = auxiliary_list[0][0]
            display_aux_two = display_aux
            index = 1
            index_two = index

        else:
            display_aux = auxiliary_list[7][0]
            display_aux_two = display_aux
            index = 8
            index_two = index

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
            try:

                msg = await ctx.send(embed=embed)
                index, display_aux = await category_choice_set(auxiliary_list)
                await msg.delete()

                msg = await ctx.send(embed=embed)
                index_two, display_aux_two = await category_choice_set(auxiliary_list)

                await msg.delete()

            except TypeError:
                return

        aux_slot_hp, aux_slot_eva = self.auxiliary_slots(auxiliary_list, index)
        aux_slot_hp_two, aux_slot_eva_two = self.auxiliary_slots(auxiliary_list, index_two)

        ship_evasion = ship_dict["EVA"] * (1 + ship_dict["EVAS"] + formation_bonus) + aux_slot_eva + aux_slot_eva_two
        ship_hp = ship_dict["HP"] + aux_slot_hp + aux_slot_hp_two
        ship_luck = ship_dict["LUK"]

        ship_evasion_rate = ship_dict["EVA Rate"]

        ship_details = "Enemy luck set to 0 as a constant \nIn auxiliary slot one is {}, in auxiliary slot two is {}"
        ship_details = ship_details.format(display_aux, display_aux_two)

        enemy_luck = 0

        ship_name = ship_name.capitalize()
        accuracy = 0.1 + enemy_hit / (enemy_hit + ship_evasion + 2) + (
            (enemy_luck - ship_luck + level_difference) * 0.001
            ) - ship_evasion_rate

        if accuracy < 0.1:
            accuracy = 0.1

        elif accuracy > 1:
            accuracy = 1

        ehp = ship_hp / (accuracy * (1 - ship_dict["DMGR"]))
        ehp = round(ehp, 2)
        ship_details += f"\n{ship_name}\'s EHP at enemy hit **{enemy_hit}** is **{ehp}**"
        embed.timestamp = ctx.message.created_at

        await ctx.send(f"> {ship_name}\'s EHP with {ship_details} with formation {form_display}")

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

    @commands.command(name="al")
    async def azur_lane_wiki_opensearch(self, ctx, *, search):
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

    @commands.is_owner()
    @gear_guide.command(name="add")
    async def add_ship_to_ggh(self, ctx, url, hull, rarity, *, ship_name):
        """add a new ship to the gear guide hub"""
        new_row = [ship_name, rarity, hull, url]

        for row in self.ship_gear_hub:
            if row[0].lower() == ship_name.lower():
                return await ctx.send("> ship already exists.")

        self.ship_gear_hub.append(new_row)
        self.update_ship_gear_hub()
        await ctx.send("> successfully updated.")
        self.bot.reload_extension("cogs.azur_lane")

    @commands.is_owner()
    @gear_guide.command(name="delete")
    async def delete_ship_from_ggh(self, ctx, *, ship_name):
        """remove a ship from the gear guide hub."""
        if not self.delete_from_reader(ship_name, self.ship_gear_hub, self.update_ship_gear_hub):
            return await ctx.send(f":no_entry: | {ship_name} doesn't exist")

        await ctx.send("> successfully updated.")
        self.bot.reload_extension("cogs.azur_lane")

    @commands.is_owner()
    @commands.group(name="uss", invoke_without_command=True)
    async def update_ship_stats(self, ctx):
        """main command for updating the ship stats csv does nothing by itself"""

    @commands.is_owner()
    @update_ship_stats.command(name="add")
    async def add_ship_to_ss_csv(self, ctx, *fields):
        """add a ship to the ship stats csv"""

        keys = ["# Lvl 120", "Name", "Hull", "HP", "EVA", "LUK", "Armor", "EVA Rate", "EVAS", "DMGR"]

        if len(fields) != len(keys):
            return await ctx.send(":no_entry: | not enough keys entered")

        for row in self.ship_stats_reader:
            if row["Name"].lower() == fields[1].lower():
                return await ctx.send("> Ship already exists.")

        row = dict(zip(keys, fields))

        self.ship_stats_reader.append(row)
        self.update_ship_stats_csv()
        await ctx.send("> successfully updated.")
        self.bot.reload_extension("cogs.azur_lane")

    @commands.is_owner()
    @update_ship_stats.command(name="delete")
    async def delete_ship_from_ss_csv(self, ctx, *, ship_name):
        """remove a ship from the ship stats csv"""
        if not self.delete_from_reader(ship_name, self.ship_stats_reader, self.update_ship_stats_csv):
            return await ctx.send(f":no_entry: | {ship_name} doesn't exist")

        await ctx.send("> successfully updated.")
        self.bot.reload_extension("cogs.azur_lane")


def setup(bot):
    bot.add_cog(AzurLane(bot))



import re
import copy
import csv
import shutil
import typing

from itertools import combinations_with_replacement
from operator import itemgetter
from contextlib import suppress
from tempfile import NamedTemporaryFile
from io import BytesIO

import discord
from discord.ext import commands

from config.utils.menu import page_source
from config.utils.context import Context


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

        #    self.auxiliary_list = [["Repair Tool", 500],
        #                                ["Fire Suppressor", 226],
        #                                ["Navy Camouflage", 44, 17],
        #                                ["Fuel Filter", 350, 5],
        #                                ["Anti Torpedo Bulge", 350],
        #                                ["SG Radar", 15],
        #                                ["Beaver Badge", 75, 35],
        #                                ["Improved Hydraulic Rudder", 60, 40]]

        self.auxiliary_list = [["Repair Tool", 500],
                               ["Fire Suppressor", 226],
                               ["Navy Camouflage", 44, 17],
                               ["Fuel Filter", 350, 5],
                               ["SG Radar", 0, 15],
                               ["Beaver Badge", 75, 35],
                               ["Improved Hydraulic Rudder", 60, 40]]

    @staticmethod
    @page_source(per_page=11)
    async def find_source(self, menu, entries):
        return f'```fix\n{"".join(entries)}```'

    @staticmethod
    @page_source(per_page=10)
    async def default_source(self, menu, entries):
        entries = "\n".join(f"> **{name.replace('_', ' ')}**" for name in entries)
        return entries

    @staticmethod
    def __return_based_on_length(aux_slot):
        if len(aux_slot) == 3:
            return aux_slot[1], aux_slot[2]

        return aux_slot[1]

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

    def check_ship_name(self, ship_name):

        for row in self.ship_gear_hub:
            if row[0].lower() == ship_name.lower():
                ship_name = row[0].replace("kai", "Kai")

        return ship_name

    async def find_image_names(self, ctx: Context, word, ship=True):

        params = {
            "aisort": "name",
            "action": "query",
            "format": "json",
            "aiprop": "size",
            "list": "allimages",
            "aimime": "image/png",
            "aifrom": word,
            "ailimit": 60
        }

        results = await self.bot.fetch("https://azurlane.koumakan.jp/w/api.php", params=params)

        names = [result["name"] for result in results["query"]["allimages"]
                 if word.lower() in result["name"].lower() or
                 (result["height"] >= 800 and ship)]

        if not names:
            if ship:
                return await ctx.send(f":no_entry: | no images for the ship {word} were found.")

            return await ctx.send(f":no_entry: | nothing was found for file {word}.")

        await ctx.send(f"> Image File names for `{word}`")

        pages = ctx.menu(self.default_source(names))

        await pages.start(ctx)

    async def azur_lane_wiki_search(self, ctx, item, allow_none_png=False, paginate=True):

        params = {
            "aisort": "name",
            "action": "query",
            "format": "json",
            "list": "allimages"
        }

        if "kai" in item.lower():
            item = item[::-1].replace(" ", "", 1)[::-1]

        if allow_none_png is False:
            params["aimime"] = "image/png"

            item = self.check_ship_name(item)

            if not item.endswith(".png"):
                item = f"{item}.png"

        params["aiprefix"] = item.replace("_", " ")
        js = await ctx.bot.fetch("https://azurlane.koumakan.jp/w/api.php", params=params)
        entries = []
        for js in js["query"]["allimages"]:

            if paginate:

                if item in js["title"]:
                    embed = discord.Embed(color=ctx.bot.default_colors(), description=f"[{js['title']}]({js['url']})")

                    if allow_none_png is False:
                        embed.set_image(url=js["url"])

                    entries.append(embed)
            else:
                return js["url"]

        if entries == [] and paginate:
            return await ctx.send(f":no_entry: | search failed for {item}")

        if not paginate:
            return "https://i.imgur.com/la4e2G4.jpg"

        pages = ctx.global_menu(ctx.list_source(entries))
        await pages.start(ctx)

    def auxiliary_slots(self, option=0):
        auxiliary_slot_hp = 0
        auxiliary_slot_evasion = 0

        if option in (1, 2):
            auxiliary_slot_hp = self.auxiliary_list[option - 1][1]

        elif option in (3, 4, 7, 5):
            auxiliary_slot_hp = self.auxiliary_list[option - 1][1]
            auxiliary_slot_evasion = self.auxiliary_list[option - 1][2]

        return auxiliary_slot_hp, auxiliary_slot_evasion

    def return_ship_dict(self, ship_name):
        for row in self.ship_stats_reader:
            if row.get("Name", "null").lower() == ship_name:
                ship_dict = row

                for key, value in ship_dict.items():
                    with suppress(AttributeError, ValueError):
                        ship_dict[key] = float(value)

                return ship_dict

        return None

    def find_best_ehp(self, enemy_hit, ship_dict, aux_list_combinations):

        aux_slot_eva = 0
        aux_slot_eva_two = 0
        results = []

        for tup_list in aux_list_combinations:
            aux_slot, aux_slot_two = tup_list
            display_aux, display_aux_two = aux_slot[0], aux_slot_two[0]
            result = self.__return_based_on_length(aux_slot)
            result_two = self.__return_based_on_length(aux_slot_two)
            if not isinstance(result, int):
                aux_slot_hp, aux_slot_eva = result
            else:
                aux_slot_hp = result

            if not isinstance(result_two, int):
                aux_slot_hp_two, aux_slot_eva_two = result_two

            else:
                aux_slot_hp_two = result_two
            # to not allow two IHR result shouldn't change if it's slotted with a beaver badge
            if (aux_slot_hp, aux_slot_eva) == (aux_slot_hp_two, aux_slot_eva_two) == (60, 40):
                display_aux = "Beaver Badge"
                aux_slot_hp, aux_slot_eva = self.auxiliary_list[6][1], self.auxiliary_list[6][2]

            ship_evasion = ship_dict["EVA"] * (1 + ship_dict["EVAS"]) + aux_slot_eva + aux_slot_eva_two
            ship_hp = ship_dict["HP"] + aux_slot_hp + aux_slot_hp_two
            ship_luck = ship_dict["LUK"]

            ship_evasion_rate = ship_dict["EVA Rate"]

            accuracy = 0.1 + enemy_hit / (enemy_hit + ship_evasion + 2) + (
                    (0 - ship_luck) * 0.001
            ) - ship_evasion_rate

            if accuracy < 0.1:
                accuracy = 0.1

            elif accuracy > 1:
                accuracy = 1

            ehp = ship_hp / (accuracy * (1 - ship_dict["DMGR"]))
            ehp = round(ehp, 2)
            results.append([ehp, (display_aux, display_aux_two)])
        # getting the index and max value
        result = max(enumerate(map(itemgetter(0), results)), key=itemgetter(1))
        return results[result[0]][1], result[1]

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

    async def make_gear_guide_embed(self, ctx: Context, ship_name, url):
        # since im lazy this only temp
        if "kai" in ship_name:
            ship_name = ship_name.replace("kai", "Kai")

        img_url = await self.azur_lane_wiki_search(ctx, ship_name, paginate=False)
        embed = discord.Embed(title=f"Gear guide for {ship_name}", url=url, color=self.bot.default_colors())
        embed.set_image(url=img_url)
        return embed

    async def get_hull_or_rarity(self, ctx: Context, index, item):
        entries = []
        col_name = self.ship_gear_hub[0][index]

        for row in self.ship_gear_hub:
            if row[index].lower() == item.lower():
                ship_name = row[0]
                url = row[3]
                embed = await self.make_gear_guide_embed(ctx, ship_name, url)
                entries.append(embed)

        if not entries:
            return await ctx.send(f"> invalid {col_name} was entered.")

        pages = ctx.menu(ctx.list_source(entries))
        await pages.start(ctx)

    @commands.group(invoke_without_command=True)
    async def ehp(self, ctx: Context, enemy_hit: typing.Optional[int] = 45, enemy_level: typing.Optional[int] = 0, *,
                  ship_name):
        """
        The main command for ehp by itself it gets a ships basic ehp value
        """

        # it just works.tm function
        # this will probably be rewritten again in the future to be honest
        async def category_choice_set():

            message = await self.bot.wait_for('message', check=lambda message: message.author == ctx.author, timeout=60)

            content = message.content

            try:
                content = int(content)
            except ValueError:
                pass

            if content not in (1, 2, 3, 4, 5, 6, 7, 8, 0):

                await ctx.send(":no_entry: | invalid category choice was received will default to the best"
                               " average auxiliary slot for this hull ")

                if hull in ("DD", "CL"):
                    display_aux_ = self.auxiliary_list[0][0]
                    content = 0

                else:
                    display_aux_ = self.auxiliary_list[6][0]
                    content = 7

            else:

                if content == 0:
                    await ctx.send("exiting the calc... 0 was entered")
                    return False
                try:
                    display_aux_ = self.auxiliary_list[content - 1][0]

                except IndexError:
                    display_aux_ = "Nothing"

            msg_ = await ctx.send(f"auxiliary slot has been set to {display_aux_}")
            messages_to_delete.append(msg_.id)
            return content, display_aux_

        messages_to_delete = []
        ship_name = ship_name.lower()
        ship_dict = self.return_ship_dict(ship_name)

        if ship_dict is None:
            return await ctx.send(f"> the ship {ship_name} was not found.")

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

        hull = ship_dict["Hull"]

        embed = discord.Embed(title=f"EHP Calculator",
                              description=f"Select an option for aux slot by typing it's number"
                                          "\n1) Repair Tool "
                                          "\n2) Fire Suppressor"
                                          "\n3) Navy Camouflage "
                                          "\n4) Fuel Filter "
                                          "\n5) SG Radar "
                                          "\n6) Beaver Badge "
                                          "\n7) IHR "
                                          "\n8) Nothing "
                                          "\n ( say 0 to exit )",
                              color=discord.Color.dark_magenta())

        embed.set_footer(text=f'Requested by {ctx.message.author.input}', icon_url=ctx.message.author.avatar.url)
        embed.timestamp = ctx.message.created_at

        try:

            msg = await ctx.send(embed=embed)
            index, display_aux = await category_choice_set()
            await msg.delete()

            msg = await ctx.send(embed=embed)
            index_two, display_aux_two = await category_choice_set()

            await msg.delete()

        except TypeError:
            return

        aux_slot_hp, aux_slot_eva = self.auxiliary_slots(index)
        aux_slot_hp_two, aux_slot_eva_two = self.auxiliary_slots(index_two)

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

    @ehp.command()
    async def default(self, ctx: Context, enemy_hit: typing.Optional[int] = 45, *, ship_name):
        """Attempts to find the best ehp with default aux slots set and formation set to diamond"""
        # it just works.tm function and goes beyond

        aux_list = copy.deepcopy(self.auxiliary_list)
        ship_name = ship_name.lower()
        ship_dict = self.return_ship_dict(ship_name)

        if ship_dict is None:
            return await ctx.send(f"> the ship {ship_name} was not found.")

        combinations = combinations_with_replacement(aux_list, 2)
        result = self.find_best_ehp(enemy_hit, ship_dict, combinations)
        aux_string, aux_string_two = result[0]
        aux_slots = "aux slot one being **{}** and aux slot two **{}**".format(aux_string, aux_string_two)
        await ctx.send(f"> {ship_name}\'s EHP with {aux_slots} and enemy hit {enemy_hit} is **{result[1]}**")

    @commands.command(aliases=["sd"])
    async def ship_details(self, ctx, filtered: typing.Optional[bool] = False, *, ship_name):
        """Grabs all the details of a ship pass True to filtered to return only stats and skills."""

        ship_name = self.check_ship_name(ship_name)

        params = {'action': 'query',
                  'titles': ship_name,
                  'prop': 'revisions|categories',
                  'rvprop': 'content',
                  'format': 'json',
                  'formatversion': '2',
                  'rvslots': 'main'}

        results = await self.bot.fetch("https://azurlane.koumakan.jp/w/api.php", params=params)

        if all("Category:Ships" not in x["title"] for x in results["query"]["pages"][0]["categories"]):
            return await ctx.send(f"The ship `{ship_name}` could not be found.")

        result = results["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
        ship_dets = ""

        replace_dict = {"Skin": f"{ship_name}\'s skin ",
                        "Initial": " Level 1",
                        "Max": " Level 100",
                        "{{": " | ",
                        "}}": "",
                        "|": "",
                        "Consumption": "Oil ",
                        "=": ":",
                        "[": "(",
                        "]": ")",
                        "Fire": "Fp",
                        "120": " Level 120",
                        "Air": "Avi"}

        regex = re.compile("(%s)" % "|".join(map(re.escape, replace_dict.keys())))

        for line in result.split("\n"):
            line = line.strip()

            if line.startswith("|"):

                if re.findall(r"Skill[0-9]Icon", line):
                    continue

                if line in ("| DLimited = 1", "| DLight = 1"):
                    break

                if filtered:

                    if all(x not in line
                           for x in ("Skill", "Acc",
                                     "Luck", "Fire",
                                     "ASW", "Air",
                                     "Evade", "Health",
                                     "Reload", "Armour")):
                        continue

                ship_dets += f"\n{line}"

        ship_dets = re.sub(r"Kai[^\w-]", " Level 100 Kai", ship_dets)
        ship_dets = re.sub(r"<.*?>", "", ship_dets)
        ship_dets = re.sub(r"Skill[1-4]Desc", "Desc", ship_dets)
        ship_dets = regex.sub(lambda mo: replace_dict[mo.string[mo.start():mo.end()]], ship_dets)
        bytes_ = BytesIO(ship_dets.encode())
        await ctx.send(file=discord.File(bytes_, filename=f"{ship_name}_details.txt"))

        pages = ctx.menu(self.find_source(ship_dets.split("\n")))
        await pages.start(ctx)

    @ship_details.error
    async def ship_details_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            error = error.original

        if isinstance(error, KeyError):
            return await ctx.send(f"> The ship `{ctx.kwargs['ship_name']}` could not be found.")

    @commands.command(name="al")
    async def azur_lane_wiki_opensearch(self, ctx: Context, *, search):
        """
        Search for something on the AL wiki
        """
        count = 1

        params = {"search": search}
        results = await self.bot.fetch("https://azurlane.koumakan.jp/w/api.php?action=opensearch", params=params)
        entries = []
        for result in results:

            for url in result:

                if re.findall('https?://(?:[-\\w.]|(?:%[\\da-fA-F]{2}))+', url):
                    embed = discord.Embed(title=f"Search results for {search}", color=self.bot.default_colors())
                    embed.add_field(name=f"Search result: {count}", value=url, inline=False)
                    count += 1
                    entries.append(embed)

        if not entries:
            return await ctx.send(f":no_entry: | search failed for {search}")

        pages = ctx.menu(ctx.list_source(entries))
        await pages.start(ctx)

    @commands.command(aliases=["afs"])
    async def al_file_search(self, ctx: Context, *, item):
        """Search for any file type on the al wiki by filename, **file names are case sensitive**"""
        await self.azur_lane_wiki_search(ctx, item, True)

    @commands.command(aliases=["ais"])
    async def al_img_search(self, ctx: Context, *, item):
        """Search for a image on the al wiki by filename, **file names are case sensitive**"""
        await self.azur_lane_wiki_search(ctx, item)

    @commands.group(aliases=["gg"], invoke_without_command=True)
    async def gear_guide(self, ctx: Context, *, ship_name):
        """The main command for gear guides by itself gets the gear guide of a ship"""

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
    async def hull(self, ctx: Context, *, hull):
        """Get a list of gear guides based on hull type."""
        await ctx.typing()
        await self.get_hull_or_rarity(ctx, 2, hull)

    @gear_guide.command()
    async def rarity(self, ctx: Context, *, rarity):
        """Get a list of gear guides based on rarity
           rarities are as follow common, rare, elite, super rare or ssr."""
        await ctx.typing()

        if rarity.lower() == "super rare":
            rarity = "ssr"

        await self.get_hull_or_rarity(ctx, 1, rarity)

    @commands.is_owner()
    @gear_guide.command(name="add")
    async def add_ship_to_ggh(self, ctx: Context, url, hull, rarity, *, ship_name):
        """Add a new ship to the gear guide hub"""
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
    async def delete_ship_from_ggh(self, ctx: Context, *, ship_name):
        """Remove a ship from the gear guide hub."""
        if not self.delete_from_reader(ship_name, self.ship_gear_hub, self.update_ship_gear_hub):
            return await ctx.send(f":no_entry: | {ship_name} doesn't exist")

        await ctx.send("> successfully updated.")
        self.bot.reload_extension("cogs.azur_lane")

    @commands.is_owner()
    @commands.group(name="uss", invoke_without_command=True)
    async def update_ship_stats(self, ctx: Context):
        """Main command for updating the ship stats csv does nothing by itself"""

    @commands.is_owner()
    @update_ship_stats.command(name="add")
    async def add_ship_to_ss_csv(self, ctx: Context, *fields):
        """Add a ship to the ship stats csv"""

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
    async def delete_ship_from_ss_csv(self, ctx: Context, *, ship_name):
        """Remove a ship from the ship stats csv"""
        if not self.delete_from_reader(ship_name, self.ship_stats_reader, self.update_ship_stats_csv):
            return await ctx.send(f":no_entry: | {ship_name} doesn't exist")

        await ctx.send("> successfully updated.")
        self.bot.reload_extension("cogs.azur_lane")

    @commands.command(aliases=["fsi"])
    async def find_ship_image(self, ctx: Context, *, word):
        """Attempts to find image file names for a ship or any image that starts with the word."""
        await ctx.typing()
        word = self.check_ship_name(word)
        await self.find_image_names(ctx, word)

    @commands.command(aliases=["fai"])
    async def find_any_image(self, ctx: Context, *, word):
        """Attempts to find image file names that starts with the word."""
        await ctx.typing()
        await self.find_image_names(ctx, word, False)


async def setup(bot):
    await bot.add_cog(AzurLane(bot))

import os
from config.cogs import __cogs__
from config.presence import __presences__, __presenceTimer__

__token__ = os.environ.get("BOT_TOKEN")
__prefix__ = os.environ.get("BOT_PREFIX")
__owner_ids__ = os.environ.get("BOT_OWNER_IDS")
__owner_ids__ = [int(owner_id) for owner_id in __owner_ids__.split(" ")]

credentials = "postgres://postgres:InsertPassWord@LocalHost:5432/InsertDatabase"

__img_flip_username__ = "InsertName"
__img_flip_password__ = "InsertPassword"

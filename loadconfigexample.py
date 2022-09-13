import os
from config.cogs import __cogs__
from config.presence import __presences__, __presenceTimer__

__tracemoe_api__key__ = ""
__saucenao_api_key__ = "3cead9686cf24d48d6e1f232e17fd1b63e59276c"


PRIVATE_GUILDS = (520242432386793473, 432569553353048075)

__token__ = os.environ.get("BOT_TOKEN")
__prefix__ = os.environ.get("BOT_PREFIX")
__owner_ids__ = os.environ.get("BOT_OWNER_IDS")
__owner_ids__ = [int(owner_id) for owner_id in __owner_ids__.split(" ")]

credentials = "postgres://postgres:InsertPassWord@LocalHost:5432/InsertDatabase"

__img_flip_username__ = "InsertName"
__img_flip_password__ = "InsertPassword"

legendary = [604816023291428874, 623296055378837535, 1018394851508752415]
FISH_GUILDS = {"Normal": [604688858591920148, 1018354568440062042, 1018394922501550080],
               "Rare": [1018230348049559642, 1018230396212744253, 623236616219000852, 1018394711783919696],
               "Elite": [604688905190637598, 1018229848050761738, 1018229892506189865, 1018230027264983040,
                         1018230100669517956, 1018394666988740708],
               "Super": [604688959640961038, 1018232525002387576, 1018232566739910707, 875174118650175550,
                         1018394766557327390],
               "Decisive": legendary,
               "Ultra": legendary,
               "Priority": legendary}

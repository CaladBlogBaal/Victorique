A personal Discord Bot written in discord.py<br>The actual code is only semi decent.
## Running<br>
You can self host this bot though I'd prefer it if you use [this](https://discordapp.com/oauth2/authorize?client_id=558747464161820723&scope=bot&permissions=1342515266
)
to have it in your server.

1. Requires python 3 or higher

2. Install dependencies 
<br><br>pip install -r requirements

3. Create the database
<br><br>You will need to create a postgres database owned by postgres and require PostgreSQL 9.5 or higher
<br>the bot will add the tables on startup.
2. Setting up configuration 

You will have to setup your token, bot prefix and owner ids as environment variables.

 
edit the loadconfig.py with your database credentials, img flip password and username.


## Requirements<br>
* Python 3.6+
* v1.2.3+ of discord.py
* Img flip account
* Jikan py
* lxml
* Pillow
* lru-dict
* Asyncpg
* Beautifulsoup4
* Jishaku
* Typing
* Psutil
* Numpy
* python-dateutil
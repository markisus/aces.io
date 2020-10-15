Running Locally
===============
`python3 -m venv env`

*Linux*  
`source env/bin/activate `

*Windows*  
`env\Scripts\activate.bat`

`python -m pip install -r requirements.txt`
`python main.py`

Navigate to http://localhost:8888


Creating a Game
=============
A game will be created with the name `my_game_name` on the fly whenever you visit a url of the scheme
- http://localhost:8888/game/my_game_name
- http://localhost:8888/game/my_game_name/my_skin_name

The template used for the game will be either `templates/client.html` for the first scheme or `templates/skins/my_skin_name.html` for the second

Available skins are
- `modern`

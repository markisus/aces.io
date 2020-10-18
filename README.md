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
- http://localhost:8888/my_game_name
- http://localhost:8888/my_game_name/my_skin_name

The template used for the game will `templates/skins/my_skin_name.html` or the default skin

Available skins are
- `modern`

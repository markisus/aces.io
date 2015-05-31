import os
import json
import uuid
from urllib import quote, unquote
import tornado.ioloop
import tornado.web
import tornado.websocket
from gamelobby import GameLobby
import pokerengine

max_games = 100
room_size = 10
lobby = GameLobby(max_games)

sockets_to_userids = dict()

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        name = self.get_cookie('name', '?')
        name = unquote(name)

        self.render("index.html", name=name, games=lobby.get_games(), room_size=room_size)

    def post(self):
        name = self.get_argument('name', '')
        self.set_cookie('name', quote(name))
        self.redirect('/')

class GameHandler(tornado.web.RequestHandler):
    def get(self, gameid):
        self.render("client.html", gameid=gameid)


class GameSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        self.userid = str(uuid.uuid4())

    def on_message(self, message):
        data = json.loads(message)
        print(data)
        action = data['action']

        if action == 'connect':
            #todo: fetch actual game
            self.game = pokerengine.make_new_game()
            self.write_message({'action': 'synchronize_game', 'game': self.game})

        if action == 'buy_in':
            result = pokerengine.join(self.game, self.userid, self.get_cookie('name'), data['seat_number'], data['buy_in'])
            self.write_message(result)

    def on_close(self):
        pass

application = tornado.web.Application(
    [
        (r"/", MainHandler),
        (r"/game/([0-9]+)", GameHandler),
        (r"/gamesocket", GameSocketHandler),
    ],
    cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
    template_path=os.path.join(os.path.dirname(__file__), "templates"),
    static_path=os.path.join(os.path.dirname(__file__), "static"),
    xsrf_cookies=True,
    debug=True,
)

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.current().start()

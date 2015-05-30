import os
from urllib import quote, unquote
import tornado.ioloop
import tornado.web
import tornado.websocket
from gamelobby import GameLobby

max_games = 100
room_size = 10
lobby = GameLobby(max_games)

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
        self.write_message("Okay guy!")

    def on_message(self, message):
        print(message)

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

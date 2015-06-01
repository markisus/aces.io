import os
import json
import uuid
from collections import defaultdict
from urllib import quote, unquote
import tornado.ioloop
import tornado.web
import tornado.websocket
import pokerengine

room_size = 10
lobby = pokerengine.GameLobby(room_size)
listeners = defaultdict(set)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        userid = self.get_cookie('userid', None)
        if not userid:
            self.set_cookie('userid', str(uuid.uuid4()))
        name = self.get_cookie('name', '?')
        name = unquote(name)

        self.render("index.html", name=name, games=lobby.get_summary(), room_size=room_size)

    def post(self):
        name = self.get_argument('name', '')
        self.set_cookie('name', quote(name))
        self.redirect('/')

class GameHandler(tornado.web.RequestHandler):
    def get(self, gameid):
        self.render("client.html", gameid=gameid)


class GameSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        self.userid = self.get_cookie('userid')
        if not self.userid:
            self.write_message({'error': 'no userid'})
            self.close()
        print("Opening with " + self.userid)

    def on_message(self, message):
        data = json.loads(message)
        action = data['action']

        if action == 'connect':
            gameid = data['gameid']
            listeners[gameid].add(self)
            self.gameid = gameid
            self.game = lobby.get_game(gameid)
            if not self.game:
                self.write_message({'error': 'Game does not exist'});
            else:
                self.write_message({'action': 'set_userid', 'userid': self.userid})
                self.force_client_synchronize()
        
        if action == 'buy_in':
            result = self.game.join(self.userid, self.get_cookie('name'), data['seat_number'], data['buy_in'])
            self.force_all_clients_synchronize(result)

    def make_synchronize_message(self):
        return {'action': 'synchronize_game', 'game': self.game.make_facade_for_user(self.userid)}

    def force_client_synchronize(self):
        self.write_message(self.make_synchronize_message())

    def force_all_clients_synchronize(self, result = {}):
        if not result.get('error'):
            for listener in listeners[self.gameid]:
                if result:
                    listener.write_message(result)
                listener.force_client_synchronize()
        else:
            self.write_message(result)

    def on_close(self):
        result = self.game.kick_user(self.userid)
        listeners[self.gameid].remove(self)
        self.force_all_clients_synchronize()

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

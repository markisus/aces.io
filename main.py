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
listener_userids = defaultdict(set)

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
            return

    def on_message(self, message):
        data = json.loads(message)
        action = data['action']

        if action == 'connect':
            gameid = data['gameid']
            if self.userid in listener_userids[gameid]:
                self.write_message({'error': 'user already connected from another location'})
                self.close()
                return
            listeners[gameid].add(self)
            listener_userids[gameid].add(self.userid)
            self.gameid = gameid
            self.game = lobby.get_game(gameid)
            if not self.game:
                self.write_message({'error': 'Game does not exist'});
            else:
                self.write_message({'action': 'set_userid', 'userid': self.userid})
                self.force_client_synchronize()
        
        success = False
        if action == 'buy_in':
            success = self.game.try_join(self.userid, self.get_cookie('name'), data['seat_number'], data['buy_in'])

        if action == 'fold':
            success = self.game.try_fold(self.userid)

        if action == 'call':
            success = self.game.try_call(self.userid)

        if action == 'raise':
            raise_amount = data['raise_amount']
            success = self.game.try_raise(self.userid, raise_amount)

        if action == 'all_in':
            success = self.game.try_all_in(self.userid)

        if success:
            self.force_all_clients_synchronize()

        #Try transition
        self.try_start_next_phase()

    def try_start_next_phase(self):
        if self.game.can_start_next_phase():
            delay = .3
            if self.game.is_game_over():
                delay = 2
            self.send_all_listeners({'action': 'phase_transition_timer', 'delay': delay})
            ioloop = tornado.ioloop.IOLoop.instance()
            def callback():
                previous = self.game._game['game_state']
                transitioned = self.game.try_start_next_phase()
                if transitioned:
                    current = self.game._game['game_state']
                    self.force_all_clients_synchronize()
                    # The game might still be stuck
                    # Like last action of showdown will auto advance to waiting for players
                    self.try_start_next_phase()
            ioloop.call_later(delay, callback)

    def make_synchronize_message(self):
        return {'action': 'synchronize_game', 'game': self.game.make_facade_for_user(self.userid)}

    def force_client_synchronize(self):
        self.write_message(self.make_synchronize_message())

    def force_all_clients_synchronize(self, result = {}):
        if result.get('error'):
            self.write_message(result)
        else:
            if result:
                self.send_all_listeners(result)
            msg_factory = lambda listener: listener.make_synchronize_message()
            self.send_all_listeners(msg_factory)

    def send_all_listeners(self, msg_factory):
        # A message (dictionary) will be lifted to a factory producing the message
        if type(msg_factory) == type(dict()):
            data = msg_factory
            msg_factory = lambda listener: data
        
        for listener in listeners[self.gameid]:
            listener.write_message(msg_factory(listener))

    def on_close(self):
        result = self.game.kick_user(self.userid)
        listeners[self.gameid].remove(self)
        listener_userids[self.gameid].remove(self.userid)
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

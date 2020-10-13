import os
import json
import uuid
from collections import defaultdict
import urllib.parse
import tornado.ioloop
import tornado.web
import tornado.websocket
import pokerengine

room_size = 10
games = {}
listeners = defaultdict(set)
listener_userids = defaultdict(set)

def get_name(handler):
    name = handler.get_cookie('name', '')
    name = urllib.parse.unquote(name).strip()
    name = name or "no-name"
    return name

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        userid = self.get_cookie('userid', None)
        if not userid:
            self.set_cookie('userid', str(uuid.uuid4()))
        
        name = get_name(self)

        self.render("index.html", name=name)

    def post(self):
        name = self.get_argument('name', '')
        self.set_cookie('name', urllib.parse.quote(name))
        self.redirect('/')

class StatsHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(str(games))
        
class ChangeNameHandler(tornado.web.RequestHandler):
    def post(self):
        name = self.get_argument('name', '')
        self.set_cookie('name', urllib.parse.quote(name))
        self.redirect('/')

class NewGameHandler(tornado.web.RequestHandler):
    def post(self):
        game_id = str(uuid.uuid4())
        games[game_id] = pokerengine.Game(game_id, room_size)
        self.redirect("game/%s" % game_id)

class GameHandler(tornado.web.RequestHandler):
    def get(self, gameid):
        userid = self.get_cookie('userid', None)
        if not userid:
            self.set_cookie('userid', str(uuid.uuid4()))

        self.render("client.html", gameid=gameid)

class GameSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self, gameid):
        self.gameid = gameid
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
            game = games.get(gameid, None)
            if not game:
                game = pokerengine.Game(gameid, room_size)
                games[gameid] = game
            self.game = game
            self.gameid = gameid            

            if self.userid in listener_userids[gameid]:
                self.write_message({'warning': 'user already connected from another location'})

            listeners[gameid].add(self)
            listener_userids[gameid].add(self.userid)

            reconnected = self.game.try_reconnect(self.userid)
            if reconnected:
                self.force_all_clients_synchronize()
            else:
                self.force_client_synchronize()

        if action == 'ping':
            self.write_message({'info': 'pong'})
        
        success = False
        if action == 'buy_in':
            name = get_name(self)
            success = self.game.try_join(self.userid, name, data['seat_number'], data['buy_in'])

        if action == 'fold':
            success = self.game.try_fold(self.userid)

        if action == 'call':
            success = self.game.try_call(self.userid)

        if action == 'raise':
            raise_amount = data['raise_amount']
            success = self.game.try_raise(self.userid, raise_amount)

        if action == 'all_in':
            success = self.game.try_all_in(self.userid)

        if action == 'reconnect':
            success = self.game.try_reconnect(self.userid)

        if success:
            self.force_all_clients_synchronize()

        #Try transition
        self.try_start_next_phase()

    def try_start_next_phase(self):
        if self.game.can_auto_advance() and not self.game.data['transitioning']:
            self.game.data['transitioning'] = True
            
            delay = 0.5
            game_state = self.game.data['game_state']
            if game_state == 'last_man_standing':
                delay = 1.0
            if game_state == 'reveal':
                delay = 2.0

            self.send_all_listeners({'action': 'phase_transition_timer', 'delay': delay})

            ioloop = tornado.ioloop.IOLoop.instance()
            def callback():
                transitioned = self.game.auto_advance()
                if transitioned:
                    self.game.data['transitioning'] = False
                    self.force_all_clients_synchronize()
                    # The game might still be stuck
                    # Like last action of showdown will auto advance to waiting for players
                    self.try_start_next_phase()

            ioloop.call_later(delay, callback)

    def make_synchronize_message(self):
        return {
            'action': 'synchronize_game', 
            'game': self.game.make_facade_for_user(self.userid), 
            'userid': self.userid 
        }

    def force_client_synchronize(self):
        self.write_message(json.dumps(self.make_synchronize_message(), default=list))

    def force_all_clients_synchronize(self):
        for listener in listeners[self.gameid]:
            listener.force_client_synchronize()

    def send_all_listeners(self, msg):
        for listener in listeners[self.gameid]:
            listener.write_message(msg)

    def on_close(self):
        result = False
        if self.game:
            result = self.game.try_disconnect(self.userid)
        listeners[self.gameid].remove(self)
        listener_userids[self.gameid].remove(self.userid)
        if result:
            self.force_all_clients_synchronize()
            self.try_start_next_phase()

application = tornado.web.Application(
    [
        (r"/", MainHandler),
        (r"/stats", StatsHandler),
        (r"/change_name", ChangeNameHandler),
        (r"/new_game", NewGameHandler),
        (r"/game/([a-zA-Z0-9\-]+)", GameHandler),
        (r"/gamesocket/([a-zA-Z0-9\-]+)", GameSocketHandler),
    ],
    cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
    template_path=os.path.join(os.path.dirname(__file__), "templates"),
    static_path=os.path.join(os.path.dirname(__file__), "static"),
    xsrf_cookies=True,
    debug=True,
)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="aces.io")
    parser.add_argument('--port', dest='P', type=int, help='port number to listen on', default=8888)
    args = parser.parse_args()
    application.listen(args.P)
    tornado.ioloop.IOLoop.current().start()

from collections import defaultdict
import json
import os
import pokerengine
import time
import tornado.ioloop
import tornado.web
import tornado.websocket
import urllib.parse
import uuid
import human_id
import random
import string

room_size = 10
games = {}
listeners = defaultdict(set)

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")

class StatsHandler(tornado.web.RequestHandler):
    def get(self):
        for gameid, l in listeners.items():
            self.write("{}: {}".format(gameid, len(l)))
        
class GameHandler(tornado.web.RequestHandler):
    def get(self, gameid, skin_id = None):
        preferred_name = self.get_cookie('name', '')
        
        if skin_id is not None:
            template_path = "skins/{}.html".format(skin_id)
        else:
            template_path = "skins/modern.html"

        self.render(template_path,
                    gameid = gameid,
                    preferred_name = preferred_name)

def make_name():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def activate_transition(game):
    game.data['transitioning'] = False

    if not game.can_auto_advance():
        # https://en.wikipedia.org/wiki/Time-of-check_to_time-of-use
        # prevent toctou conditions if users disconnect
        return False

    game.auto_advance()
    for l in listeners[game.data['gameid']]:
        l.force_client_synchronize()

    # since transitions may be stacked
    # e.g. if everyone is all in
    # attemp the schedule another transition
    try_enter_transition(game)

# returns true if transition was scheduled or if already transitoning
def try_enter_transition(game):
    if game.can_auto_advance() and not game.data['transitioning']:
        game.data['transitioning'] = True

        delay = 0.5 # don't wait too long by default

        if game.data['game_state'] == pokerengine.wait_for_players:
            delay = 2.0

        if game.data['phase_prologue']:
            delay = 1.0

        if game.data['win_screen'] and game.data['win_screen'].get('winner', None):
            # currently awarding winner, keep this screen for longer
            if game.data['game_state'] == pokerengine.reveal:
                delay = 6.0
            else:
                # last man standing
                delay = 4.0

        ioloop = tornado.ioloop.IOLoop.instance()
        def callback():
            activate_transition(game)
        ioloop.call_later(delay, callback)
    return game.data['transitioning']

class GameSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self, gameid):
        self.gameid = gameid
        self.userid = str(uuid.uuid4())
        self.name = None # name is set on connect

        listeners[gameid].add(self)
        if not games.get(self.gameid, None):
            games[self.gameid] = pokerengine.Game(self.gameid, room_size)
        self.game = games[self.gameid]
        
    def on_message(self, message):
        data = json.loads(message)
        action = data['action']

        if action == 'connect':
            preferred_name = urllib.parse.unquote(data.get('preferred_name', ''))
            if preferred_name:
                self.name = preferred_name
            else:
                self.name = make_name()
            self.force_client_synchronize()

        if action == 'ping':
            self.write_message({'info': 'pong'})
        
        success = False
        if action == 'buy_in':
            success = self.game.try_join(self.userid, self.name, data['seat_number'], data['buy_in'])

        if action == 'replace':
            success = self.game.try_replace(self.userid, self.name, data['seat_number'])

        if action == 'fold':
            success = self.game.try_fold(self.userid)

        if action == 'call':
            success = self.game.try_call(self.userid)

        if action == 'raise':
            raise_amount = data['raise_amount']
            success = self.game.try_raise(self.userid, raise_amount)

        if action == 'all_in':
            success = self.game.try_all_in(self.userid)

        if action == 'reveal':
            success = self.game.try_reveal(self.userid)

        if action == 'change_name':
            self.name = data['name']
            success = self.game.try_change_name(self.userid, self.name)
            if not success:
                self.force_client_synchronize()

        if action == 'disconnect':
            success = self.game.try_disconnect(self.userid)

        if success:
            self.force_all_clients_synchronize()

    def make_synchronize_message(self):
        return {
            'action': 'synchronize_game', 
            'game': self.game.make_facade_for_user(self.userid), 
            'userid': self.userid,
            'name': self.name,
            'timestamp': time.time()
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

        if len(listeners[self.gameid]) == 0:
            # no more connections to this game
            del games[self.gameid]
            del listeners[self.gameid]
        elif result:
            self.force_all_clients_synchronize()

def try_handle_move_timeout(curr_time, game):
    active_user_position = game.data['active_user_position']
    if active_user_position is not None:
        if curr_time > game.data['next_move_due']:
            active_userid = game.data['seats'][active_user_position]['userid']
            return game.try_fold(active_userid)
    return False

def tick_games():
    curr_time = time.time()

    for gameid, game in games.items():
        if try_enter_transition(game):
            continue
        
        if try_handle_move_timeout(curr_time, game):
            for l in listeners[gameid]:
                l.force_client_synchronize()

application = tornado.web.Application(
    [
        (r"/", MainHandler),
        (r"/_stats", StatsHandler),
        (r"/_gamesocket/([a-zA-Z0-9\-]+)", GameSocketHandler),        
        (r"/([a-zA-Z0-9\-]+)", GameHandler),
        (r"/([a-zA-Z0-9\-]+)/([a-zA-Z0-9\-]+)", GameHandler), # with skin parameter

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
    tornado.ioloop.PeriodicCallback(tick_games, 500).start()
    tornado.ioloop.IOLoop.current().start()

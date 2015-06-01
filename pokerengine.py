import copy

just_joined = 'just_joined'
dead = 'dead'
empty = 'empty'

wait_for_players = 'wait_for_players'


class Game:
    def __init__(self, gameid, room_size):
        self._game = {
            'gameid': gameid,
            'seats': [],
            'room_size': room_size,
            'min_raise': 2,
            'min_buy_in': 20,
            'dealer_position': 0,
            'active_user_position': 0,
            'small_blind_position': 0,
            'big_blind_position': 0,
            'pot': 0,
            'current_bet': 0,
            'deck': [],
            'community_cards': [],
            'game_state': wait_for_players
        }

        for seat_number in range(room_size):
            self._game['seats'].append(self._make_empty_seat())

    @staticmethod
    def _make_error(msg):
        return {'error': msg}    

    @staticmethod
    def _make_empty_seat():
        return {'state': 'empty'}

    def get_seated_userids(self):
        userids = set()
        for seat in self._game['seats']:
            userid = seat.get('userid', None)
            if userid:
                userids.add(userid)
        return userids

    def join(self, userid, name, seat_number, buy_in):
        game = self._game
        if not game:
            return self._make_error('Game does not exist')

        if seat_number < 0 or seat_number >= len(game['seats']):
            return self._make_error('Seat not found')
        seat = game['seats'][seat_number]
        
        if userid in self.get_seated_userids():
            return self._make_error('User already seated')

        if buy_in < game['min_buy_in']:
            return self._make_error('Buy in too low, got %s needed %s' % (buy_in, game['min_buy_in']))

        self._seat_user(seat_number, userid, name, buy_in)
    
        return {"action": "player_joined", "seat_number": seat_number, "seat": seat}

    def get_id(self):
        return self._game['gameid']

    def _seat_user(self, seat_number, userid, name, money):
        game = self._game
        seat = game['seats'][seat_number]
        seat['userid'] = userid
        seat['name'] = name
        seat['money'] = money
        seat['round_bet'] = 0
        seat['total_bet'] = 0
        seat['state'] = just_joined
        seat['hole_cards'] = []
        seat['had_turn'] = False

    def make_facade_for_user(self, userid):
        facade = copy.deepcopy(self._game)
        for seat in facade['seats']:
            seat_userid = seat.get('userid', None)
            if seat_userid != userid:
               num_hole_cards = len(seat.get('hole_cards', []))
               seat['hole_cards'] = num_hole_cards*['unknown']
        return facade

    def _find_seat_by_userid(self, userid):
        seats = self._game['seats']
        for seat in seats:
            if seat.get('userid', None) == userid:
                return seat
        else:
            return None

    def _do_if_user_exists(self, userid, action):
        user_seat = self._find_seat_by_userid(userid)
        if user_seat:
            return action(user_seat)
        else:
            return self._make_error("user not found")

    def kick_user(self, userid):
        def action(user_seat):
            del user_seat['userid']
            del user_seat['name']
            del user_seat['money']
            user_seat['state'] = empty
        self._do_if_user_exists(userid, action)

        
class GameLobby:
    def __init__(self, room_size):
        self._games = dict()
        for gameid in range(100):
            self._games[gameid] = Game(gameid, room_size)

    def get_summary(self):
        lobby = []
        for game in self._games.values():
            summary = {
                'gameid': game.get_id(),
                'num_users': len(game.get_seated_userids())
            }
            lobby.append(summary)
        return lobby

    def get_game(self, gameid):
        return self._games[gameid]



import copy
import random
import handranker
from handranker import cards, suits, ranks

just_joined = 'just_joined'
ready = 'ready'
forcing_big_blind = 'forcing_big_blind'
all_in = 'all_in'
folded = 'folded'
busted = 'busted'
empty = 'empty'

wait_for_players = 'wait_for_players'
pre_flop = 'pre_flop'
flop = 'flop'
turn = 'turn'
river = 'river'
reveal = 'reveal'
last_man_standing = 'last_man_standing'

#todo move to util
def next_greatest(current, candidates):
    greater = [c for c in candidates if c > current]
    less = [c for c in candidates if c < current]
    if not greater and not less:
        return None
    else:
        return min(greater or less)

class Game:
    def __init__(self, gameid, room_size):
        self._game = {
            'gameid': gameid,
            'seats': [],
            'room_size': room_size,
            'min_raise': 0,
            'min_buy_in': 20,
            'small_blind': 1,
            'big_blind': 2,
            'dealer_position': 0,
            'active_user_position': None,
            'small_blind_position': 0,
            'big_blind_position': 0,
            'pot': 0,
            'deck': [],
            'community_cards': [],
            'game_state': wait_for_players,
            'win_screen': None,
            'transitioning': False,
        }

        for seat_number in range(room_size):
            self._game['seats'].append(self._make_empty_seat(seat_number))

    @staticmethod
    def _make_error(msg):
        return {'error': msg}    

    @staticmethod
    def _make_empty_seat(seat_number):
        seat = {}
        seat['userid'] = None
        seat['name'] = ''
        seat['money'] = 0
        seat['round_bet'] = 0
        seat['total_bet'] = 0
        seat['state'] = empty
        seat['hole_cards'] = []
        seat['had_turn'] = False
        seat['seat_number'] = seat_number
        seat['last_move'] = None
        return seat

    def get_seated_userids(self):
        userids = set()
        for seat in self._game['seats']:
            userid = seat.get('userid', None)
            if userid:
                userids.add(userid)
        return userids

    def try_join(self, userid, name, seat_number, buy_in):
        game = self._game
        if not game:
            return False
        if seat_number < 0 or seat_number >= len(game['seats']):
            return False
        seat = game['seats'][seat_number]
        if userid in self.get_seated_userids():
            return False
        if buy_in < game['min_buy_in']:
            return False
        self._seat_user(seat_number, userid, name, buy_in)
        return True
    
    def is_game_over(self):
        return self._game['game_state'] in [last_man_standing, reveal]

    def get_id(self):
        return self._game['gameid']

    def _seat_user(self, seat_number, userid, name, money):
        game = self._game
        seat = game['seats'][seat_number]
        seat['userid'] = userid
        seat['name'] = name
        seat['money'] = money
        seat['state'] = just_joined

    def make_facade_for_user(self, userid):
        facade = copy.deepcopy(self._game)

        still_standing_userids = self._extract_userids(
            self._get_still_standing_seats()
        )

        for seat in facade['seats']:
            seat_userid = seat.get('userid', None)
            if seat_userid != userid:
                should_reveal = self._game['game_state'] == reveal \
                                and seat_userid in still_standing_userids
                if not should_reveal:
                    num_hole_cards = len(seat.get('hole_cards', []))
                    seat['hole_cards'] = num_hole_cards*['unknown']
        del facade['deck']
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

    def kick_user(self, userid):
        def action(user_seat):
            seat_number = user_seat['seat_number']
            folded = self.try_fold(user_seat['userid'])
            self._game['seats'][seat_number] = self._make_empty_seat(seat_number)
            if not folded:
                self._try_award_last_man_standing()
            return True
        return self._do_if_user_exists(userid, action)

    def _get_prepared_seats(self):
        prepared_user_states = set((just_joined, ready, forcing_big_blind))
        return self._filter_seats(lambda seat: seat['state'] in prepared_user_states)

    def _get_ready_seats(self):
        return self._filter_seats(lambda seat: seat['state'] == ready)

    def _get_still_standing_seats(self):
        return self._filter_seats(lambda seat: seat['state'] in [ready, all_in])

    def _get_forcing_big_blind_seats(self):
        return self._filter_seats(lambda seat: seat['state'] == forcing_big_blind)

    def _filter_seats(self, pred):
        return [seat for seat in self._game['seats'] if pred(seat)]

    def _can_start(self):
        game = self._game
        if game['game_state'] != wait_for_players:
            return False
        if len(self._get_prepared_seats()) < 2:
            return False
        return True

    @staticmethod
    def _extract_seat_numbers(seats):
        return map(lambda seat: seat['seat_number'], seats)

    @staticmethod
    def _extract_userids(seats):
        return map(lambda seat: seat['userid'], seats)

    @staticmethod
    def _make_shuffled_deck():
        _cards = copy.deepcopy(cards)
        random.shuffle(_cards)

        #Test deck
        return [
            '7.spades', '8.diamonds', 
            '9.diamonds', '3.diamonds', 
            '4.spades', '10.clubs', '5.diamonds', '5.clubs', 'jack.clubs'
            ][::-1]

        return _cards

    def _try_start(self):
        if self._can_start():
            self._game['win_screen'] = None
            # Set Deck
            self._game['deck'] = self._make_shuffled_deck()

            # Ready more players
            ready_seats = self._get_ready_seats()
            if len(ready_seats) <= 1:
                prepared_seats = self._get_prepared_seats()
                for seat in prepared_seats:
                    seat['state'] = ready

            # Set Dealer
            dealer_position = self._game['dealer_position']
            ready_seats = self._get_ready_seats()
            ready_positions = self._extract_seat_numbers(ready_seats)
            dealer_position = next_greatest(dealer_position, ready_positions)
            self._game['dealer_position'] = dealer_position

            # Set Blind Positions
            small_blind_potentials = self._extract_seat_numbers(self._get_ready_seats())
            big_blind_potentials = self._extract_seat_numbers(self._get_prepared_seats())
            small_blind_position = next_greatest(dealer_position, small_blind_potentials)
            big_blind_position = next_greatest(small_blind_position, big_blind_potentials)
            if big_blind_position == dealer_position:
                #Heads up position
                small_blind_position, big_blind_position = \
                    big_blind_position, small_blind_position
            self._game['small_blind_position'] = small_blind_position
            self._game['big_blind_position'] = big_blind_position

            # Collect Blinds
            small_blind = self._game['small_blind']
            big_blind = self._game['big_blind']
            forcing_big_blind_seats = self._get_forcing_big_blind_seats()
            small_blind_seat = self._game['seats'][small_blind_position]
            big_blind_seat = self._game['seats'][big_blind_position]
            for seat in [big_blind_seat] + forcing_big_blind_seats:
                self._bet_or_all_in(seat, big_blind)
            self._bet_or_all_in(small_blind_seat, small_blind)

            # Deal hole cards
            for seat in self._get_still_standing_seats():
                for i in range(2):
                    card = self._deal_card()
                    seat['hole_cards'].append(card)

            return True

    def _deal_card(self):
        deck = self._game['deck']
        card = deck[-1]
        deck.pop()
        return card
        
    def _get_can_bet_seats(self):
        return self._filter_seats(
            lambda seat:
            seat['state'] == ready and \
            (seat['round_bet'] < self._get_current_bet() or not seat['had_turn'])
        )

    def can_start_next_phase(self):
        if self._game['active_user_position'] is None \
           and self._game['game_state'] != wait_for_players:
            return True
        if self._can_start():
            return True
        return False
        
    def try_start_next_phase(self):
        if not self.can_start_next_phase():
            return False

        just_started = self._try_start()
        if not just_started:
            self._reset_round()

        if self.is_game_over():
            self._reset_game()
            return True

        current_state = self._game['game_state']

        next_states = {
            wait_for_players: pre_flop,
            pre_flop: flop,
            flop: turn,
            turn: river,
            river: reveal,
        }

        current_state = next_states[current_state]
        self._game['game_state'] = current_state

        if current_state == reveal:
            self._showdown()
            return True
        
        # Deal Community Cards
        num_community_cards = {
            pre_flop: 0,
            flop: 3,
            turn: 1,
            river: 1,
        }[current_state]
        
        for i in range(num_community_cards):
            card = self._deal_card()
            self._game['community_cards'].append(card)

        # Set UTG
        utg_potentials = self._extract_seat_numbers(self._get_can_bet_seats())

        big_blind_position = self._game['big_blind_position']

        self._game['active_user_position'] = next_greatest(
            big_blind_position, utg_potentials
        )

        return True

    def _showdown(self):
        self._game['active_user_position'] = None
        # Deep copy so that when we attach best hands we don't leak to the client
        standing_seats = copy.deepcopy(self._get_still_standing_seats())
        num_standing_seats = len(standing_seats)
        for seat in standing_seats:
            hand7 = seat['hole_cards'] + self._game['community_cards']
            seat['best_hand'] = handranker.search(hand7)
        standing_seats.sort(
            cmp = lambda s1, s2: handranker.compare_hand_dicts(s1['best_hand'], s2['best_hand'])
        )
        max_total_bet = max((seat['total_bet'] for seat in standing_seats))
        level = 0
        winner_infos = []
        while level < max_total_bet:
            print "level is now ", level
            winner = standing_seats[-1]
            winners = []
            while standing_seats and handranker.compare_hand_dicts(
                    standing_seats[-1]['best_hand'], winner['best_hand']) == 0:
                winners.append(standing_seats.pop())
            winners.sort(key=lambda seat: seat['total_bet'])
            num_winners = len(winners)
            for winner in winners:
                winnings = 0
                for seat in self._game['seats']:
                    winnings += min(seat['total_bet'], winner['total_bet']) - level
                winnings /= num_winners
                self._game['seats'][winner['seat_number']]['money'] += winnings
                winner_infos.append({'winner': winner, 'winnings': winnings})
                num_winners -= 1
            level = max((winner['total_bet'] for winner in winners))
        self._game['win_screen'] = {'win_condition': 'showdown', 'winners': winner_infos}

    def _get_current_bet(self):
        bet = 0
        for seat in self._game['seats']:
            bet = max(seat['round_bet'], bet)
        return bet

    def _bet_or_all_in(self, seat, amount):
        user_money = seat['money']
        amount_to_bet = min(user_money, amount)
        going_all_in = amount >= user_money
        bet_before = self._get_current_bet()
        seat['round_bet'] += amount_to_bet
        seat['total_bet'] += amount_to_bet
        bet_after = self._get_current_bet()
        seat['money'] -= amount_to_bet
        if going_all_in:
            seat['state'] = all_in
            seat['last_move'] = 'all in'
        else:
            seat['state'] = ready
        amount_raised = bet_after - bet_before
        self._game['min_raise'] = max(self._game['min_raise'], amount_raised)

    def _is_user_active(self, userid):
        active_user_position = self._game['active_user_position']
        if active_user_position is None:
            return False
        active_user_id = self._game['seats'][active_user_position].get('userid', None)
        return active_user_id == userid

    def try_fold(self, userid):
        if self._is_user_active(userid):
            seat = self._find_seat_by_userid(userid)
            seat['state'] = folded
            seat['had_turn'] = True
            seat['last_move'] = 'fold'
            self._end_turn()
            return True

    def _try_award_last_man_standing(self):
        still_standing_seats = self._get_still_standing_seats()
        if len(still_standing_seats) == 1:
            self._game['active_user_position'] = None
            last_man = still_standing_seats[0]
            self._make_pot()
            pot_amount = self._game['pot']
            last_man['money'] += pot_amount
            self._game['pot'] = 0
            self._game['win_screen'] = {'win_condition': 'last_man_standing', 'winner': last_man, 'winnings': pot_amount}
            self._game['game_state'] = last_man_standing
            return True

    def _make_pot(self):
        for seat in self._game['seats']:
            self._game['pot'] += seat['round_bet']
            seat['round_bet'] = 0


    def _end_turn(self):
        if not self._try_award_last_man_standing():
            # Advance user
            active_user_position = self._game['active_user_position']
            next_active_positions = self._extract_seat_numbers(self._get_can_bet_seats())
            next_active_position = next_greatest(
                active_user_position, next_active_positions
            )
            self._game['active_user_position'] = next_active_position
        
    def _reset_round(self):
        self._make_pot()
        for seat in self._game['seats']:
            if seat['state'] == empty:
                continue
            seat['had_turn'] = False
            seat['round_bet'] = 0
            if seat['last_move'] not in ['fold', 'all in']:
                seat['last_move'] = None
        self._game['min_raise'] = self._game['big_blind']

    def _reset_game(self):
        for seat in self._game['seats']:
            if seat['state'] == empty:
                continue
            seat['hole_cards'] = []
            seat['total_bet'] = 0
            seat['round_bet'] = 0
            seat['had_turn'] = False
            seat['last_move'] = None
            if seat['state'] in [folded, all_in]:
                seat['state'] = ready
            if seat['money'] == 0:
                seat['state'] = busted
        self._game['community_cards'] = []
        self._game['min_raise'] = 0
        self._game['pot'] = 0
        self._game['game_state'] = wait_for_players

    def try_call(self, userid):
        if self._is_user_active(userid):
            seat = self._find_seat_by_userid(userid)
            needed_to_call = self._get_current_bet() - seat['round_bet']
            if needed_to_call == 0:
                seat['last_move'] = 'check'
            else:
                seat['last_move'] = 'call'
            self._bet_or_all_in(seat, needed_to_call)
            seat['had_turn'] = True
            self._end_turn()
            return True

    def try_raise(self, userid, raise_amount):
        if self._is_user_active(userid):
            seat = self._find_seat_by_userid(userid)
            current_bet = self._get_current_bet()
            round_bet = seat['round_bet']
            if raise_amount < self._game['min_raise']:
                # Raise does not meet min raise
                return False
            needed_to_call = current_bet - round_bet
            seat['last_move'] = 'raise'
            self._bet_or_all_in(seat, raise_amount + needed_to_call)
            seat['had_turn'] = True

            self._end_turn()
            return True

    def try_all_in(self, userid):
        if self._is_user_active(userid):
            seat = self._find_seat_by_userid(userid)
            seat['last_move'] = 'all in'
            self._bet_or_all_in(seat, seat['money'])
            seat['had_turn'] = True
            self._end_turn()
            return True
            
                
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


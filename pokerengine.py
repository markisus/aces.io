from collections import deque, defaultdict
from handranker import cards, suits, ranks
import copy
import handranker
import random
import time

ready = 'ready'
forcing_big_blind = 'forcing_big_blind'
all_in = 'all_in'
folded = 'folded'
busted = 'busted'
empty = 'empty'

# main game phases
wait_for_players = 'wait_for_players'
pre_flop = 'pre_flop'
flop = 'flop'
turn = 'turn'
river = 'river'
reveal = 'reveal'
last_man_standing = 'last_man_standing'

def is_state_still_standing(state):
    return state in [ready, all_in]

# python2 -> python3
def cmp_to_key(mycmp):
    'Convert a cmp= function into a key= function'
    class K:
        def __init__(self, obj, *args):
            self.obj = obj
        def __lt__(self, other):
            return mycmp(self.obj, other.obj) < 0
        def __gt__(self, other):
            return mycmp(self.obj, other.obj) > 0
        def __eq__(self, other):
            return mycmp(self.obj, other.obj) == 0
        def __le__(self, other):
            return mycmp(self.obj, other.obj) <= 0
        def __ge__(self, other):
            return mycmp(self.obj, other.obj) >= 0
        def __ne__(self, other):
            return mycmp(self.obj, other.obj) != 0
    return K

#todo move to util
def next_greatest(current, candidates):
    greater = [c for c in candidates if c > current]
    less = [c for c in candidates if c < current]
    if not greater and not less:
        return None
    else:
        return min(greater or less)


def make_shuffled_deck():
    _cards = copy.deepcopy(cards)
    random.shuffle(_cards)
    return _cards

# package together winner data for the win screen
def make_winner(winner_seat, winnings, hole_cards = None, best_hand = None):
    return {
        'userid': winner_seat['userid'],
        'name': winner_seat['name'],
        'hole_cards': hole_cards,
        'best_hand': best_hand,
        'winnings': winnings,
    }

class Game:
    def __init__(self, gameid, room_size, make_deck=make_shuffled_deck):
        self._make_shuffled_deck = make_deck
        self._deck = make_deck()
        self.data = {
            'gameid': gameid,
            'denomination': 'cents',
            'seats': [],
            'room_size': room_size,
            'min_raise': 0,
            'min_buy_in': 1000,
            'max_buy_in': 5000,
            'small_blind': 5,
            'big_blind': 10,
            'dealer_position': 0,
            'active_user_position': None,
            'small_blind_position': 0,
            'big_blind_position': 0,
            'pot': 0,
            'community_cards': [],
            'game_state': wait_for_players,
            'win_screen': None,
            'win_queue': [],
            'aggressor': None, # in a showdown, the aggressor must show            
            'revealers': [], # userids who reveal cards at showdown
            'transitioning': False,
            'next_move_due': 0,
            'move_time': 18,
            'history': deque(),
            'ledger': defaultdict(dict),
            'phase_prologue': False, # just dealt hole cards, or just deal community cards, no active user yet
        }

        for seat_number in range(room_size):
            self.data['seats'].append(self._make_empty_seat(seat_number))

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
        seat['best_hand'] = None
        seat['had_turn'] = False
        seat['seat_number'] = seat_number
        seat['last_move'] = None
        seat['disconnected'] = False
        return seat

    def get_seated_userids(self):
        userids = set()
        for seat in self.data['seats']:
            userid = seat.get('userid', None)
            if userid:
                userids.add(userid)
        return userids

    def _update_ledger(self, userid, name, delta_payout):
        ledger_entry = self.data['ledger'][userid]
        ledger_entry['name'] = name
        current_payout = ledger_entry.get('payout', 0) + delta_payout
        if current_payout:
            ledger_entry['payout'] = current_payout
        else:
            del self.data['ledger'][userid]

    def try_join(self, userid, name, seat_number, buy_in):
        game = self.data
        if seat_number < 0 or seat_number >= len(game['seats']):
            return False
        if userid in self.get_seated_userids():
            return False
        if buy_in < game['min_buy_in']:
            return False
        if buy_in > game['max_buy_in']:
            return False
        self._seat_user(seat_number, userid, name, buy_in)
        return True
    
    def is_game_over(self):
        return self.data['game_state'] in [last_man_standing, reveal]

    def _seat_user(self, seat_number, userid, name, money):
        game = self.data
        seat = game['seats'][seat_number]
        seat['userid'] = userid
        seat['name'] = name
        seat['money'] = money
        seat['state'] = forcing_big_blind

    # masks out global information that this particular user is not supposed to know
    def make_facade_for_user(self, userid):
        facade = copy.deepcopy(self.data)

        still_standing_userids = self._extract_userids(
            self._get_still_standing_seats()
        )

        for seat in facade['seats']:
            seat_userid = seat.get('userid', None)
            if seat_userid != userid:
                should_reveal = seat_userid in self.data['revealers']
                if not should_reveal:
                    num_hole_cards = len(seat.get('hole_cards', []))
                    seat['hole_cards'] = num_hole_cards*['unknown']
                    seat['best_hand'] = None
        return facade

    def _find_seat_by_userid(self, userid):
        seats = self.data['seats']
        for seat in seats:
            if seat.get('userid', None) == userid:
                return seat
        else:
            return None

    # if the game has started, set the user as disconnected
    # otherwise, just clear the seat
    def try_disconnect(self, userid):
        user_seat = self._find_seat_by_userid(userid)
        if user_seat:
            seat_number = user_seat['seat_number']
            if self.data['game_state'] == wait_for_players:
                user_seat.update(self._make_empty_seat(user_seat['seat_number']))
            else:
                folded = self.try_fold(user_seat['userid'])
                self.data['seats'][seat_number]['disconnected'] = True
            return True
        return False

    def try_replace(self, userid, name, seat_number):
        if seat_number < 0 or seat_number >= len(self.data['seats']):
            return False

        if userid in self.get_seated_userids():
            # user already seated
            return False
        
        seat = self.data['seats'][seat_number]
        if seat['disconnected']:
            #can only replace a disconnected user
            seat['userid'] = userid
            seat['name'] = name
            seat['disconnected'] = False
            return True
        return False

    def try_change_name(self, userid, name):
        seat = self._find_seat_by_userid(userid)
        if seat:
            seat['name'] = name
            self._update_ledger(userid, name, delta_payout = 0)
            return True
        return False

    def _get_prepared_seats(self):
        prepared_user_states = set((ready, forcing_big_blind))
        return self._filter_seats(lambda seat: seat['state'] in prepared_user_states)

    def _get_ready_seats(self):
        return self._filter_seats(lambda seat: seat['state'] == ready)

    def _get_still_standing_seats(self):
        return self._filter_seats(lambda seat: is_state_still_standing(seat['state']))

    def _get_forcing_big_blind_seats(self):
        return self._filter_seats(lambda seat: seat['state'] == forcing_big_blind)

    def _filter_seats(self, pred):
        return [seat for seat in self.data['seats'] if pred(seat)]

    @staticmethod
    def _extract_seat_numbers(seats):
        return list(map(lambda seat: seat['seat_number'], seats))

    @staticmethod
    def _extract_userids(seats):
        return list(map(lambda seat: seat['userid'], seats))

    def _deal_card(self):
        deck = self._deck
        card = deck[-1]
        deck.pop()
        return card
        
    def _get_can_bet_seats(self):
        return self._filter_seats(
            lambda seat:
            seat['state'] == ready and \
            (seat['round_bet'] < self._get_current_bet() or not seat['had_turn'])
        )

    def can_auto_advance(self):
        if self.data['active_user_position'] is None \
           and self.data['game_state'] != wait_for_players:
            return True
        if self._can_enter_pre_flop():
            return True
        if self.data['phase_prologue']:
            return True
        return False

    def _append_phase_transition_to_history(self):
        phase_names = {
            pre_flop: "pre-flop",
            flop: "flop",
            turn: "turn",
            river: "river",
            reveal: "showdown",
            last_man_standing: "last man standing"
        }
        self._append_data_to_history(
            category = "phase_transition",
            data = {
                "phase": phase_names.get(self.data['game_state'], self.data['game_state']),
                "community_cards": list(self.data['community_cards'])
            })


    def _can_enter_last_man_standing(self):
        return len(self._get_still_standing_seats()) == 1

    def _enter_last_man_standing(self):
        self._make_pot()
        last_man = self._get_still_standing_seats()[0]
        self.data['win_screen'] = {'win_condition': 'last_man_standing'}
        self.data['win_queue'].append(make_winner(last_man, winnings = self.data['pot']))
        self.data['game_state'] = last_man_standing
        self.data['active_user_position'] = None

    def _set_utg(self):
        # Set under the gun (UTG)
        utg_potentials = self._extract_seat_numbers(self._get_can_bet_seats())
        if len(utg_potentials) == 1:
            # This can happen when, in the last round,
            # everyone went all-in except one caller
            # Then in this round the caller would play himself only
            # So do a check to avoid this and then auto advance to showdown
            self._update_active_user_position(None)
        else:
            dealer_position = self.data['dealer_position']
            self._update_active_user_position(
                next_greatest(dealer_position, utg_potentials))

    def _update_best_hands(self):
        for seat in self.data['seats']:
            if not seat['hole_cards']:
                continue
            hand7 = seat['hole_cards'] + self.data['community_cards']
            seat['best_hand'] = handranker.search(hand7)

    def _can_enter_pre_flop(self):
        return self.data['game_state'] == wait_for_players \
            and len(self._get_prepared_seats()) >= 2

    def _enter_pre_flop(self):
        if not self._can_enter_pre_flop():
            raise RuntimeError("cannot enter pre-flop")

        self.data['game_state'] = pre_flop

        self.data['win_screen'] = None
        self._deck = self._make_shuffled_deck()

        # Ready more players
        ready_seats = self._get_ready_seats()
        if len(ready_seats) <= 1:
            prepared_seats = self._get_prepared_seats()
            for seat in prepared_seats:
                seat['state'] = ready

        # Set Dealer
        dealer_position = self.data['dealer_position']
        ready_seats = self._get_ready_seats()
        ready_positions = self._extract_seat_numbers(ready_seats)

        dealer_position = next_greatest(dealer_position, ready_positions)
        self.data['dealer_position'] = dealer_position

        # Set Blind Positions
        small_blind_potentials = self._extract_seat_numbers(self._get_ready_seats())
        big_blind_potentials = self._extract_seat_numbers(self._get_prepared_seats())
        small_blind_position = next_greatest(dealer_position, small_blind_potentials)
        big_blind_position = next_greatest(small_blind_position, big_blind_potentials)
        if big_blind_position == dealer_position:
            #Heads up position
            small_blind_position, big_blind_position = \
                big_blind_position, small_blind_position

        self.data['small_blind_position'] = small_blind_position
        self.data['big_blind_position'] = big_blind_position

        # Collect Blinds
        small_blind = self.data['small_blind']
        big_blind = self.data['big_blind']
        forcing_big_blind_seats = self._get_forcing_big_blind_seats()
        small_blind_seat = self.data['seats'][small_blind_position]
        big_blind_seat = self.data['seats'][big_blind_position]

        paid_big_blind = set()
        for seat in [big_blind_seat] + forcing_big_blind_seats:
            if seat['userid'] in paid_big_blind:
                continue
            self._bet_or_all_in(seat, big_blind)
            paid_big_blind.add(seat['userid'])

        if small_blind_seat['userid'] not in paid_big_blind:
            self._bet_or_all_in(small_blind_seat, small_blind)

        # Deal hole cards
        for seat in self._get_still_standing_seats():
            for i in range(2):
                card = self._deal_card()
                seat['hole_cards'].append(card)

        self.data['phase_prologue'] = True

    def _continue_pre_flop(self):
        # set utg to next after the big blind
        # do not use _continue_phase since pre-flop has different utg logic
        utg_potentials = self._extract_seat_numbers(self._get_can_bet_seats())
        big_blind_position = self.data['big_blind_position']
        self._update_active_user_position(
            next_greatest(big_blind_position, utg_potentials))
        self._update_best_hands()
        self.data['phase_prologue'] = False

    def _enter_flop(self):
        self.data['game_state'] = flop
        self._prepare_next_round()
        for i in range(3):
            card = self._deal_card()
            self.data['community_cards'].append(card)
        self.data['phase_prologue'] = True

    def _enter_turn(self):
        self.data['game_state'] = turn
        self._prepare_next_round()
        card = self._deal_card()
        self.data['community_cards'].append(card)
        self.data['phase_prologue'] = True

    def _enter_river(self):
        self.data['game_state'] = river
        self._prepare_next_round()
        card = self._deal_card()
        self.data['community_cards'].append(card)
        self.data['phase_prologue'] = True

    def _continue_phase(self):
        # do not use for pre-flop - instead call _continue_preflop
        self._set_utg()
        self._update_best_hands()
        self.data['phase_prologue'] = False

    def auto_advance(self):
        if self.data['phase_prologue']:
            game_state = self.data['game_state']
            if game_state == pre_flop:
                self._continue_pre_flop()
            else:
                self._continue_phase()
            return True
        
        # cannot advance if currently waiting for user move
        if not self.data['active_user_position'] is None:
            return False

        if self.is_game_over():
            if self.data['win_queue']:
                self._award_next_winner()
            else:
                self._reset_data()
            return True

        current_state = self.data['game_state']

        if self._can_enter_pre_flop():
            self._enter_pre_flop()
        elif self._can_enter_last_man_standing():
            self._enter_last_man_standing()
        elif current_state == pre_flop:
            self._enter_flop()
        elif current_state == flop:
            self._enter_turn()
        elif current_state == turn:
            self._enter_river()
        elif current_state == river:
            self._enter_showdown()

        self._append_phase_transition_to_history()
        return True
    
    def _enter_showdown(self):
        self.data['game_state'] = reveal

        standing_seats = self._get_still_standing_seats()

        # stable sort / lexical sort (hand score, reverse total bet)
        # the last entry is the best hand
        # if there are ties, then the one who bet least is last
        standing_seats.sort(
            key = lambda s: -s['total_bet']
        )
        standing_seats.sort(
            key = cmp_to_key(
                lambda s1, s2: handranker.compare_hand_dicts(
                    s1['best_hand'], s2['best_hand']))
        )
        winner_infos = []

        while standing_seats:
            winner = standing_seats[-1]
            winners = [] # those who tied this winner, but put more in the pot
            while standing_seats and handranker.compare_hand_dicts(
                    standing_seats[-1]['best_hand'], 
                    winner['best_hand']) == 0:
                winners.append(standing_seats.pop())

            num_winners = len(winners)
            for winner in winners:
                winnings = 0
                winner_bet = winner['total_bet']
                for seat in self.data['seats']:
                    # collect winnings contributed by this seat
                    # taking into account if there were ties
                    gains = min(seat['total_bet'], winner_bet)/num_winners
                    seat['total_bet'] -= gains
                    winnings += gains
                winner_infos.append(make_winner(winner,
                                                winnings,
                                                winner['hole_cards'],
                                                winner['best_hand']))
                num_winners -= 1
            standing_seats = [seat for seat in standing_seats if seat['total_bet'] > 0]

        self.data['win_screen'] = {'win_condition': 'showdown'}
        self.data['win_queue'] = winner_infos

        for winner_info in winner_infos:
            self.data['revealers'].append(winner_info['userid'])

        # aggressor must reveal
        if self.data['aggressor'] is not None:
            self.data['revealers'].append(self.data['aggressor'])

    def _award_next_winner(self):
        win_info = self.data['win_queue'].pop(0)
        winnings = win_info['winnings']
        self.data['win_screen']['winner'] = win_info
        self.data['pot'] -= winnings
        winner_seat = self._find_seat_by_userid(win_info['userid'])
        if winner_seat:
            winner_seat['money'] += winnings
            self._update_ledger(win_info['userid'], winner_seat['name'], delta_payout = winnings)

        # simplified version for history
        self._append_data_to_history(category = 'win_info', data = win_info)

    def _get_current_bet(self):
        bet = 0
        for seat in self.data['seats']:
            bet = max(seat['round_bet'], bet)
        return bet

    # return amount raised
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
        self.data['min_raise'] = max(self.data['min_raise'], amount_raised)
        self._update_ledger(seat['userid'], seat['name'], delta_payout = -amount_to_bet)
        return amount_raised

    def _is_user_active(self, userid):
        active_user_position = self.data['active_user_position']
        if active_user_position is None:
            return False
        active_user_id = self.data['seats'][active_user_position].get('userid', None)
        return active_user_id == userid

    def _make_pot(self):
        for seat in self.data['seats']:
            self.data['pot'] += seat['round_bet']
            seat['round_bet'] = 0

    def _update_active_user_position(self, new_position):
        self.data['active_user_position'] = new_position
        if new_position is not None:
            self.data['next_move_due'] = time.time() + self.data['move_time']

    def _end_turn(self, seat):
        seat['had_turn'] = True
        self._append_last_move_to_history(seat)

        # set next user if we are not in last man standing state
        if not self._can_enter_last_man_standing():
            active_user_position = self.data['active_user_position']
            next_active_positions = self._extract_seat_numbers(self._get_can_bet_seats())
            next_active_position = next_greatest(
                active_user_position, next_active_positions
            )
            self._update_active_user_position(next_active_position)
        else:
            self._update_active_user_position(None)

    def _prepare_next_round(self):
        self._make_pot()
        for seat in self.data['seats']:
            if seat['state'] == empty:
                continue
            seat['had_turn'] = False
            seat['round_bet'] = 0
            if seat['last_move'] not in ['fold', 'all in']:
                seat['last_move'] = None
        self.data['min_raise'] = self.data['big_blind']

    def _reset_data(self):
        for seat in self.data['seats']:
            if seat['state'] == empty:
                continue            
            empty_seat = self._make_empty_seat(seat['seat_number'])
            if seat['disconnected']:
                seat.update(empty_seat)
            seat['hole_cards'] = []
            seat['best_hand'] = None
            seat['total_bet'] = 0
            seat['round_bet'] = 0
            seat['had_turn'] = False
            seat['last_move'] = None
            if seat['state'] in [folded, all_in]:
                seat['state'] = ready
            if seat['money'] == 0 and seat['userid']:
                self._append_msg_to_history("{} busted".format(seat['name']))
                # For now when someone busts, they just get kicked
                seat.update(empty_seat)
        self.data['community_cards'] = []
        self.data['min_raise'] = 0
        self.data['pot'] = 0
        self.data['game_state'] = wait_for_players
        self.data['win_queue'] = []
        self.data['win_screen'] = None
        self.data['active_user_position'] = None
        self.data['game_state'] = wait_for_players
        self.data['aggressor'] = None
        self.data['revealers'] = []
        self.data['phase_prologue'] = False

    def _append_data_to_history(self, category, data):
        tagged_data = {'category': category}
        tagged_data.update(data)
        self.data['history'].append(tagged_data)
        while len(self.data['history']) > 10:
            self.data['history'].popleft()

    def _append_msg_to_history(self, msg):
        self.data['history'].append({'category': 'text', 'message':msg})
        while len(self.data['history']) > 10:
            self.data['history'].popleft()

    def _append_last_move_to_history(self, seat):
        msg = "{name} {move}ed".format(name = seat['name'], move= seat['last_move'])
        amt = seat['round_bet']
        name = seat['name']
        move = seat['last_move']
        if move == 'all in':
            msg = "{name} shoved all in ({amt})".format(name = name, amt = amt)
        if move == 'check' or move == 'call':
            msg = "{name} {move}ed ({amt})".format(name = name, amt = amt, move = move)
        if move == 'raise':
            msg = "{name} raised ({amt})".format(name = name, amt = amt)
        if move == 'fold':
            msg = "{name} folded".format(name = name)
        self._append_msg_to_history(msg)

    def try_call(self, userid):
        if self._is_user_active(userid):
            seat = self._find_seat_by_userid(userid)
            needed_to_call = self._get_current_bet() - seat['round_bet']
            if needed_to_call == 0:
                seat['last_move'] = 'check'
            else:
                seat['last_move'] = 'call' 
            self._bet_or_all_in(seat, needed_to_call)
            self._end_turn(seat)
            return True

    def try_raise(self, userid, raise_amount):
        if self._is_user_active(userid):
            seat = self._find_seat_by_userid(userid)
            current_bet = self._get_current_bet()
            round_bet = seat['round_bet']
            if raise_amount < self.data['min_raise']:
                # Raise does not meet min raise
                return False
            needed_to_call = current_bet - round_bet
            seat['last_move'] = 'raise'
            self.data['aggressor'] = userid
            self._bet_or_all_in(seat, raise_amount + needed_to_call)
            self._end_turn(seat)
            return True

    def try_all_in(self, userid):
        if self._is_user_active(userid):
            seat = self._find_seat_by_userid(userid)
            seat['last_move'] = 'all in'
            amount_raised = self._bet_or_all_in(seat, seat['money'])
            if amount_raised > 0:
                # note its possible to go all in without raising
                # when your stack does not meet the current bet
                self.data['aggressor'] = userid
            self._end_turn(seat)
            return True

    def try_fold(self, userid):
        if self._is_user_active(userid):
            seat = self._find_seat_by_userid(userid)
            seat['state'] = folded
            seat['had_turn'] = True
            seat['last_move'] = 'fold'
            if self.data['aggressor'] == userid:
                self.data['aggressor'] = None
            self._end_turn(seat)
            return True

    def try_reveal(self, userid):
        seat = self._find_seat_by_userid(userid)
        if seat is None:
            return False

        if not seat['hole_cards']:
            return False
        
        if userid not in self.data['revealers'] and \
           self.is_game_over():
            self.data['revealers'].append(userid)
            self._append_data_to_history(
                category = 'reveal',
                data = {
                    'userid': userid,
                    'name': seat['name'],
                    'hole_cards': seat['hole_cards'],
                    'best_hand': seat['best_hand']
                })
            return True
        return False
    


            

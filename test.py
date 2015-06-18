import copy
from handranker import cards
from pokerengine import Game
from pprint import PrettyPrinter as PP

p = PP()

two_person_tie_deck =  [
    '7.spades', '8.diamonds', 
    '7.diamonds', '8.spades', 
    '4.spades', '10.clubs', '5.diamonds', '5.clubs', 'jack.clubs'
][::-1]

def make_deck():
    return cards

def find_bug():
    game = Game(0, 10)

    game.try_join(0, 'mark', 0, 20)
    game.try_join(1, 'terry', 1, 30)
    game.try_join(2, 'joe', 2, 40)
    game.try_start_next_phase()

    game.try_all_in(1)
    game.try_all_in(2)
    game.try_all_in(0)

    assert game._game['active_user_position'] == None, "everyone is all in"

    game.try_start_next_phase() #preflop -> flop
    game.try_start_next_phase() #flop -> turn
    game.try_start_next_phase() #turn -> river

    river = copy.deepcopy(game)

    game.try_start_next_phase()
    game.try_start_next_phase()
    game.try_start_next_phase()
    game.try_start_next_phase()

    seats = game._game['seats']
    for seat in seats:
        if seat['money'] < 0:
            return river

def find_bug2():
    game = Game(0, 10, lambda: two_person_tie_deck)
    game.try_join(0, 'mark', 0, 20)
    game.try_join(1, 'terry', 1, 20)
    game.try_all_in(1)
    game.try_all_in(0)

    while game._game['game_state'] != 'wait_for_players':
        game.try_start_next_phase()

    if not (game._game['seats'][0]['money'] == game._game['seats'][1]['money'] == 20):
        return game

bug = None
for _ in range(1000):
    bug = find_bug2()
    if bug:
        print "found bug"
        break
else:
    print "no bug found"

def display():
    for seat in bug._game['seats']:
        if seat['state'] != 'empty':
            p.pprint(seat)
        



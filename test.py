import copy
from handranker import cards
import handranker
from pokerengine import Game
from copy import deepcopy
from pprint import PrettyPrinter as PP

p = PP()

two_person_tie_deck =  [
    '7.spades', '8.diamonds', 
    '7.diamonds', '8.spades', 
    '4.spades', '10.clubs', '5.diamonds', '5.clubs', 'jack.clubs'
][::-1]

two_person_tie_deck2 = [
    '5.clubs', '8.diamonds',
    '8.hearts', '2.clubs',
    '8.clubs', '9.diamonds', '6.diamonds', 'king.hearts', 'jack.diamonds'
][::-1]

def make_deck():
    return cards

def find_bug():
    game = Game(0, 10)

    game.try_join(0, 'mark', 0, 20)
    game.try_join(1, 'terry', 1, 30)
    game.try_join(2, 'joe', 2, 40)
    game.auto_advance()

    game.try_all_in(1)
    game.try_all_in(2)
    game.try_all_in(0)

    assert game.data['active_user_position'] == None, "everyone is all in"

    game.auto_advance() #preflop -> flop
    game.auto_advance() #flop -> turn
    game.auto_advance() #turn -> river

    river = copy.deepcopy(game)

    for i in range(4):
        if game.can_auto_advance():
            game.auto_advance()

    seats = game.data['seats']
    for seat in seats:
        if seat['money'] < 0:
            return game

    return None

def find_bug2():
    game = Game(0, 10, lambda: deepcopy(two_person_tie_deck))
    game.try_join(0, 'mark', 0, 20)
    game.try_join(1, 'terry', 1, 20)
    game.auto_advance()

    game.try_all_in(1)
    game.try_all_in(0)

    while game.data['game_state'] != 'wait_for_players':
        game.auto_advance()

    if not (game.data['seats'][0]['money'] == game.data['seats'][1]['money'] == 20):
        return game

    return None

def find_bug3():
    game = Game(0, 10, lambda: deepcopy(two_person_tie_deck2))
    game.try_join(0, 'mark', 0, 90)
    game.try_join(1, 'jeff', 1, 20)
    game.auto_advance()
    game.try_all_in(1)
    game.try_all_in(0)

    while game.data['game_state'] != 'wait_for_players':
        game.auto_advance()

    if not (game.data['seats'][0]['money'] == 90 and  game.data['seats'][1]['money'] == 20):
        return game

    return None


def display(game):
    for seat in game.data['seats']:
        if seat['state'] != 'empty':
            p.pprint(seat)
    for card in game.data['community_cards']:
        p.pprint(card)
        

if __name__ == "__main__":
    bugs = [find_bug(), find_bug2(), find_bug3()]

    for i, bug in enumerate(bugs):
        if bug:
            print("Found bug", i)
            display(bug)

    if not any(bugs):
        print("No bugs")

    straight = handranker.find_straight([
        '8.hearts', '7.diamonds', '6.hearts', '5.hearts', '5.diamonds', '4.hearts', '4.hearts'])
    if len(straight['hand']) != 5:
        print("handranker bug", straight)

    



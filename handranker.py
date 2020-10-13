from itertools import islice

suits = "diamonds clubs hearts spades".split(" ")
ranks = "2 3 4 5 6 7 8 9 10 jack queen king ace".split(" ")
cards = [rank + "." + suit for rank in ranks for suit in suits]

def _index_dict(l):
    d = dict()
    for index, item in enumerate(l):
        d[item] = index
    return d

_ranks_to_indices = _index_dict(ranks)
_suits_to_indices = _index_dict(suits)

for i, rank in enumerate(ranks):
    _ranks_to_indices[rank] = i

def add_rank(rank, delta):
    i = _ranks_to_indices[rank]
    next_i = (i+delta) % len(ranks)
    return ranks[next_i]

def next_rank(rank):
    return add_rank(rank, 1)

def get_rank(card):
    return card.split('.')[0]

def get_suit(card):
    return card.split('.')[1]

def get_ranks(cards):
    return map(get_rank, cards)

def high_rank(some_ranks):
    max_index = max(map(
        lambda rank: _ranks_to_indices[rank], 
        some_ranks))
    return ranks[max_index]

def _make_straight_ranks(high_rank):
    straight_ranks = set()
    current_rank = high_rank
    for i in range(5):
        straight_ranks.add(current_rank)
        current_rank = add_rank(current_rank, -1)
    return straight_ranks

def find_straight(hand):
    ranks = set(get_ranks(hand))
    upper_discontinuities = filter(
        lambda rank: next_rank(rank) not in ranks,
        ranks
    )
    possible_straight_highs = filter(
        lambda rank: _ranks_to_indices[rank] >= _ranks_to_indices['5'],
        upper_discontinuities
    )
    possible_straights = map(
        lambda high: _make_straight_ranks(high),
        possible_straight_highs
    )
    straights = filter(
        lambda straight: straight <= ranks,
        possible_straights
    )
    for straight in straights:
        # There is at most one straight in a hand of size 7
        # after separating by discontinuities
        if 'ace' in straight and '5' in straight:
            high = '5'
        else:
            high = high_rank(straight)
        final = [card for card in hand if get_rank(card) in straight]
        return {'hand':final, 'type':'straight','high_rank': high}

def find_super_flush(hand):
    for suit in suits:
        super_flush = [card for card in hand if get_suit(card) == suit]
        if len(super_flush) >= 5:
            return super_flush

def find_flush(hand):
    super_flush = find_super_flush(hand)
    if super_flush:
        arrange_hand_descending(super_flush)
        flush = super_flush[:5]
        return {'hand': flush, 'type': 'flush'}

def most_valuable_multiples(hand, times):
    arrange_hand_descending(hand)
    last_rank = None
    for card in hand:
        current_rank = get_rank(card)
        if current_rank != last_rank:
            last_rank = current_rank
            multiples = []
        multiples.append(card)
        if len(multiples) == times:
            return multiples

def arrange_hand_descending(hand):
    hand.sort(key=lambda card:-_ranks_to_indices[get_rank(card)])
    return hand

def find_quads(hand):
    quads = most_valuable_multiples(hand, 4)
    if quads:
        # Find the kicker
        rank = get_rank(quads[0])
        arrange_hand_descending(hand)
        for card in hand:
            if card in quads:
                continue
            else:
                quads.append(card)
                return {'hand': quads, 'type': 'quads', 'kicker': card, 'rank': rank}

def find_three_of_a_kind(hand):
    trips = most_valuable_multiples(hand, 3)
    if trips:
        rank = get_rank(trips[0])
        rest = islice((card for card in hand if card not in trips), 2)
        trips += list(rest)
        return {'hand': trips, 'type': 'three of a kind', 'rank': rank}

def find_pair(hand):
    pair = most_valuable_multiples(hand, 2)
    if pair:
        arrange_hand_descending(hand)
        rank = get_rank(pair[0])
        rest = islice((card for card in hand if card not in pair), 3)
        pair += list(rest)
        return {'hand': pair, 'type': 'pair', 'rank': rank}

def find_two_pair(hand):
    pair = most_valuable_multiples(hand, 2)
    if pair:
        rest = [card for card in hand if card not in pair]
        pair_2 = most_valuable_multiples(rest, 2)
        if pair_2:
            pairs = pair + pair_2
            rest = islice((card for card in hand if card not in pairs), 1)
            pairs += list(rest)
            return {
                'hand': pairs, 
                'first_rank': get_rank(pair[0]), 
                'second_rank': get_rank(pair_2[0]), 
                'type': 'two pair'
            }

def find_full_house(hand):
    trips = most_valuable_multiples(hand, 3)
    if trips:
        trip_rank = get_rank(trips[0])
        rest = list(card for card in hand if card not in trips)
        dubs = most_valuable_multiples(rest, 2)
        if dubs:
            dub_rank = get_rank(dubs[0])
            return {'hand': trips + dubs, 'triple_rank': trip_rank, 'double_rank': dub_rank, 'type': 'full house'} 
        
        
def find_default(hand):
    arrange_hand_descending(hand)
    return {'hand': hand[:5], 'high_rank': get_rank(hand[0]), 'type': 'high card'}

def search(hand):
    super_flush = find_super_flush(hand)
    if super_flush:
        straight_flush = find_straight(super_flush)
        if straight_flush and high_rank == 'ace':
            return {'hand': straight_flush['hand'],
                    'type': 'royal flush',
                    'high_rank':straight_flush['high_rank']}
        if straight_flush:
            return {'hand': straight_flush['hand'],
                    'type': 'straight flush',
                    'high_rank':straight_flush['high_rank']}
        if not straight_flush:
            return find_flush(hand) #garaunteed to find a flush from superflush
    else:
        searches = (
            find_quads,
            find_full_house,
            find_straight,
            find_three_of_a_kind,
            find_two_pair,
            find_pair,
            find_default,
        )
        for search in searches:
            result = search(hand)
            if result:
                return result

def get_hand_score(hand_dict):
    type_to_score = {
        'royal flush': 10,
        'straight flush': 9,
        'quads': 8,
        'full house': 7,
        'flush': 6,
        'straight': 5,
        'three of a kind': 4,
        'two pair': 3,
        'pair': 2,
        'high card': 1
    }
    hand_type = hand_dict['type']
    return type_to_score[hand_type]

def get_numerical_rank(card):
    return _ranks_to_indices[get_rank(card)]

def compare_hand_dicts(hand_a, hand_b):
    score_diff = get_hand_score(hand_a) - get_hand_score(hand_b)
    if score_diff == 0:
        a_cards = hand_a['hand']
        b_cards = hand_b['hand']
        cards = zip(a_cards, b_cards)
        for a_card, b_card in cards:
            card_diff = get_numerical_rank(a_card) - get_numerical_rank(b_card)
            if card_diff != 0:
                return card_diff
    return score_diff

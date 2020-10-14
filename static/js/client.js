function url(s) {
  var l = window.location;
  return ((l.protocol === "https:") ? "wss://" : "ws://") + l.hostname +
         (((l.port != 80) && (l.port != 443)) ? ":" + l.port : "") + '/' + s;
}

function game_connect(gameid, preferred_name, callback) {
  var socketUrl = url('gamesocket/' + gameid)
  var ws = new WebSocket(socketUrl);
  var send = function(data) {
    data = JSON.stringify(data);
    ws.send(data);
  };
  ws.onopen = function() { send({'action' : 'connect', 'preferred_name': preferred_name}); };
  ws.onmessage = function(evt) { callback(evt.data); };
  return send
}

var initialize_ractive = function(template, images_dir) {
  ractive = new Ractive({
    el : '#content',
    template : template,

    data : {
      get_card_url : function(card) {
        if (!card)
          card = 'unknown';
        if (card == 'unknown')
          return images_dir + "cards/blue-back.png";
        var card_array = card.split('.');
        var rank = card_array[0];
        var suit = card_array[1];
        return images_dir + "cards/compact/" + suit + "/" + rank + ".svg";
      },

      get_card_rank : function(card) {
        if (!card)
          card = 'unknown';
        var card_array = card.split('.');
        return card_array[0];
      },

      is_win_card : function(card) {
        if (ractive.get('game.win_screen.win_condition') != 'showdown') return false;
        if (!ractive.get('game.win_screen.winner')) return false;
        var win_cards = ractive.get('game.win_screen.winner.best_hand.hand');
        win_cards = win_cards || [];
        return win_cards.indexOf(card) >= 0
      },

      is_lose_card : function(card) {
        if (ractive.get('game.win_screen.win_condition') != 'showdown') return false;
        if (!ractive.get('game.win_screen.winner')) return false;
        return !ractive.get('is_win_card')(card);
      },
    },

    computed : {
      is_any_user_active : function() {
        var active_user_position = this.get('game.active_user_position');
        return (active_user_position != undefined);
      },

      can_i_bet_later : function() {
        return this.get('is_any_user_active') &&
          (this.get('game_state') != 'wait_for_players') &&
          !this.get('is_my_turn') &&
          (this.get('my_seat.state') == 'ready');
      },

      seated_userids : function() {
        var seats = this.get('game.seats');
        if (!seats) return null;
        return seats.map(function(seat) { return seat.userid });
      },

      my_seat : function() {
        var userid = this.get('userid');
        var seated_userids = this.get('seated_userids');
        if (!seated_userids) return null;
        index = seated_userids.indexOf(userid);
        var seats = this.get('game.seats');
        return seats[index];
      },

      is_my_turn : function() {
        var my_seat = this.get('my_seat');
        if (!my_seat)
          return false;
        var active_user_position = this.get('game.active_user_position');
        var game_state = this.get('game.game_state');
        return this.get('my_seat.seat_number') == this.get('game.active_user_position') &&
          this.get('game.game_state') != 'wait_for_players';
      },

      current_bet : function() {
        var seats = this.get('game.seats');
        if (!seats) return 0;
        var round_bets = seats.map(function(seat) { return seat.round_bet });
        return Math.max.apply(null, round_bets);
      },

      call_check : function() {
        amount_needed_to_call = this.get('amount_needed_to_call');
        if (amount_needed_to_call == 0)
          return 'check'
          return 'call'
      },

      amount_needed_to_call : function() {
        var my_seat = this.get('my_seat');
        if (!my_seat) return 0;

        var current_bet = this.get('current_bet');
        var my_round_bet = my_seat.round_bet;
        return current_bet - my_round_bet;
      },

      maybe_my_seat_number : function() {
        var my_seat = this.get('my_seat');
        if (my_seat) {
          return my_seat.seat_number;
        }
        return -1;
      },

      raise_increment : function() {
        var min_raise = this.get('game.min_raise');
        var big_blind = this.get('game.big_blind');
        return Math.max(min_raise, big_blind);
      },

      can_raise : function() {
        var amount_needed_to_call = this.get('amount_needed_to_call');
        var min_raise = this.get('game.min_raise');
        var my_seat = this.get('my_seat');
        if (!my_seat) {
          return false;
        }
        return my_seat.money >= amount_needed_to_call + min_raise;
      },

      can_call : function() {
        var amount_needed_to_call = this.get('amount_needed_to_call');
        var my_seat = this.get('my_seat');
        if (!my_seat) return false;
        return my_seat.money > amount_needed_to_call;
      },

      buy_in_increment : function() {
        if (!this.get('game'))
          return 0;
        return this.get('game.min_buy_in') / 2;
      }
    }
  });

  ractive.on('show_buyin_menu', event => {
    ractive.set('show_buyin_menu', event.context.seat_number);
    ractive.set('buy_in', ractive.get('game.min_buy_in'))
  });

  ractive.on('buy_in_increase', event => {
    var current = ractive.get('buy_in');
    var cap = ractive.get('game.max_buy_in');
    var next = current + ractive.get('buy_in_increment');
    var result = Math.min(next, cap);
    ractive.set('buy_in', result);
  });

  ractive.on('buy_in_decrease', event => {
    var current = ractive.get('buy_in');
    var next = current - ractive.get('buy_in_increment');
    var result = Math.max(next, ractive.get('game.min_buy_in'));
    ractive.set('buy_in', result);
  });

  ractive.on('show_raise_menu', event => {
    ractive.set('raise_menu', true);
    ractive.set('raise_amount', ractive.get('game.min_raise'));
  });

  ractive.on('hide_raise_menu',
             function(event) { ractive.set('raise_menu', false); });

  ractive.on('raise_increase', event => {
    var my_seat = ractive.get('my_seat')
    var amount_needed_to_call = ractive.get('amount_needed_to_call');
    var next = ractive.get('raise_amount') + ractive.get('raise_increment');
    ractive.set('raise_amount',
                Math.min(my_seat.money - amount_needed_to_call, next));
  });

  ractive.on('raise_decrease', event => {
    var current = ractive.get('raise_amount');
    var next = current - ractive.get('raise_increment');
    var result = Math.max(next, ractive.get('game.min_raise'));
    ractive.set('raise_amount', result);
  });

  ractive.on('hide_raise_menu',
             event => ractive.set('raise_menu', false));

  ractive.observe('is_my_turn', function(current, old, path) {
    if (!current)
      ractive.set('raise_menu', false);
    if (current) {
      var auto_action = ractive.get('auto_action');
      var amount_needed = ractive.get('amount_needed_to_call');
      if (auto_action == 'call_any') {
        send({'action' : 'call'});
      }
      if (auto_action == 'call') {
        console.log("Sending call or check due to auto action.");
        var auto_call_amount = ractive.get('auto_call_amount');
        if (auto_call_amount >= amount_needed)
          send({'action' : 'call'});
      }
      if (auto_action == 'check_fold') {
        console.log("Sending check_fold due to auto action.");
        if (amount_needed == 0) {
          send({'action' : 'call'})
        } else {
          send({'action' : 'fold'})
        }
      }

      ractive.set('auto_action', ''); // reset auto action
    }
  });

  // Reset auto action
  ractive.observe('amount_needed_to_call', function(current, old) {
    var auto_action = ractive.get('auto_action');
    if (current > old && auto_action == 'call')
      ractive.set('auto_action', '');
  });

  ractive.observe('game.game_state',
                  function(current, old) { ractive.set('auto_action', ''); });

  ractive.on('buy_in', event =>
    send({
      'action' : 'buy_in',
      'buy_in' : ractive.get('buy_in'),
      'seat_number' : event.context.seat_number
    }));

  ractive.on('replace', event => 
    send({'action' : 'replace',
          'seat_number' : event.context.seat_number}));

  ractive.on('fold', event => send({'action' : 'fold'}));

  ractive.on('call_check', event => send({'action' : 'call'}));

  ractive.on('raise', event => {
    var raise_amount = ractive.get('raise_amount');
    send({'action' : 'raise', 'raise_amount' : raise_amount});
  });

  ractive.on('all_in', event => send({'action' : 'all_in'}));

  ractive.on('auto_action', event => {
    var new_action = event.node.value;
    var current_action = ractive.get('auto_action');
    if (current_action == new_action) {
      ractive.set('auto_action', '')
    } else {
      ractive.set('auto_action', new_action);
    }
    if (new_action == 'call') {
      var amount_needed = ractive.get('amount_needed_to_call');
      ractive.set('auto_call_amount', amount_needed);
    }
  });

  ractive.on('change_name', event =>
             {
               new_name = ractive.get('new_name');
               document.cookie = "name=" + encodeURIComponent(new_name);
               send({'action' : 'change_name', 'name': new_name});
             });

  window.addEventListener("keydown", event => {
    if (event.key == '0') {
      ractive.fire('all_in');
    }
    if (event.key == '1') {
      ractive.fire('fold');
    }
    if (event.key == '2') {
      ractive.fire('call_check');
    }
    if (event.key == '3') {
      ractive.fire('show_raise_menu');
    }
    if (event.key == '+' || event.key == '=') {
      ractive.fire('raise_increase');
    }
    if (event.key == '-' || event.key == '_') {
      ractive.fire('raise_decrease');
    }
    if (event.key == 'Escape') {
      ractive.fire('hide_raise_menu');
      ractive.set('auto_action', null);
    }
    if (event.key == 'Enter') {
      ractive.fire('raise');
    }
    if (event.key == '4') {
      if (ractive.get('auto_action') == 'check_fold') {
        ractive.set('auto_action', '');
      } else {
        ractive.set('auto_action', 'check_fold');
      }
    }
    if (event.key == '5') {
      if (ractive.get('auto_action') == 'call') {
        ractive.set('auto_action', '');
      } else {
        ractive.set('auto_action', 'call');
      }
    }
    if (event.key == '6') {
      if (ractive.get('auto_action') == 'call_any') {
        ractive.set('auto_action', '');
      } else {
        ractive.set('auto_action', 'call_any');
      }
    }
    
  });

  return ractive;
}

var init = function(gameid, preferred_name, template, images_dir) {
  var ractive = undefined;
  var socket = undefined

  var send = data => socket.send(JSON.stringify(data));
  var receive = msg => {
    var msg = JSON.parse(msg);
    console.log(msg);

    if (msg['warning']) {
      ractive.set('warning', msg['warning']);
    }
    if (msg['error']) {
      ractive.set('error', msg['error']);
    }

    var action = msg['action'];
    if (action == "synchronize_game" && ractive) {
      ractive.set({
        game : msg.game,
        userid : msg.userid,
        name : msg.name,
        timestamp : msg.timestamp
      });
      if (!ractive.get('new_name') && msg.name) {
        // init new name functionality:
        // the new name field needs a placeholder
        // the placeholder should be the current name
        ractive.set('new_name', msg.name);
      }
    }
  };

  function parse_ledger_csv(csv) {
    var lines = csv.split('\n');
    var data = {};
    for (var i = 0; i < lines.length; ++i) {
      var line = lines[i];
      var name_comma_payout = line.split(',');
      if (name_comma_payout.length != 2) {
        continue;
      }
      var name = name_comma_payout[0].trim();
      var payout = parseFloat(name_comma_payout[1].trim());
      if (isNaN(payout)) {
        continue;
      }
      if (name in data) {
        data[name] += payout;
      }
      else {
        data[name] = payout;
      }
    }
    return data;
  }

  function url(s) {
    var l = window.location;
    return ((l.protocol === "https:") ? "wss://" : "ws://") + l.hostname +
           (((l.port != 80) && (l.port != 443)) ? ":" + l.port : "") + '/' + s;
  }

  function game_connect(gameid, preferred_name) {
    var socketUrl = url('gamesocket/' + gameid)
    socket = new WebSocket(socketUrl);
    socket.onopen = function() {
      send({'action' : 'connect', 'preferred_name' : preferred_name});
    };
    socket.onmessage = event => receive(event.data);
  }

  var initialize_ractive =
      function(template, images_dir) {
    ractive = new Ractive({
      el : '#content',
      template : template,

      data : {
        is_unknown_card : function(card) {
          return (card == 'unknown');
        },
        
        get_card_color : function(card) {
          if (!card) {
            card = 'unknown';
          }
          if (card == "unknown") {
            return "purple";
          }
          var card_array = card.split('.');          
          var suit = card_array[1];
          if (suit == "daimonds" || suit == "hearts") {
            return "red";
          }
          return "black";
        },

        short_rank : function(rank) {
          if (rank == "king") return "K";
          if (rank == "ace") return "A";
          if (rank == "queen") return "Q";
          if (rank == "jack") return "J";
          return rank;
        },
        
        get_card_unicode : function(card) {
          if (!card)
            card = 'unknown';
          if (card == 'unknown')
            return "🂠"; //

          var card_array = card.split('.');
          var rank = card_array[0];
          var suit = card_array[1];

          var suit_code;
          if (suit == 'spades') suit_code = "♠";
          if (suit == 'hearts') suit_code = "♥";
          if (suit == 'diamonds') suit_code = "♦";
          if (suit == 'clubs') suit_code = "♣";

          return suit_code + this.get('short_rank').apply(this, [rank]);
        },
        
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


        is_current_winner : function(userid) {
          console.log("Calling is current winner");
          return (userid && (userid == this.get('game.win_screen.winner.userid')));
        },        

        is_win_card : function(card) {
          if (this.get('game.win_screen.win_condition') != 'showdown')
            return false;
          if (!this.get('game.win_screen.winner'))
            return false;
          var win_cards = this.get('game.win_screen.winner.best_hand.hand');
          win_cards = win_cards || [];
          return win_cards.indexOf(card) >= 0
        },

        is_lose_card : function(card) {
          if (this.get('game.win_screen.win_condition') != 'showdown')
            return false;
          if (!this.get('game.win_screen.winner'))
            return false;

          // `this` must be piped
          return !this.get('is_win_card').apply(this, [ card ]);
        },

        is_me : function(userid) {
          return this.get('userid') == userid;
        },

        new_name : '',

        previous_ledger_csv : '',
      },

      computed : {
        seat_idxs : function() {
          var seats = this.get('game.seats');
          return Array.from(seats, (x, i) => i);
        },
        reverse_seat_idxs : function() {
          var seats = this.get('game.seats');
          return Array.from(seats, (x, i) => seats.length - i - 1);
        },
        pretty_game_state : function() {
          var game_state = this.get('game.game_state');
          if (game_state == 'wait_for_players') return 'waiting for players';
          if (game_state == 'pre_flop') return 'pre-flop';
          if (game_state == 'flop') return 'flop';
          if (game_state == 'turn') return 'turn';
          if (game_state == 'river') return 'river';
          if (game_state == 'last_man_standing') return 'last man standing';
          if (game_state == 'reveal') return 'showdown';
          return game_state;
        },
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
          if (!seats)
            return null;
          return seats.map(function(seat) { return seat.userid });
        },

        my_seat : function() {
          var userid = this.get('userid');
          var seated_userids = this.get('seated_userids');
          if (!seated_userids)
            return null;
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
          return this.get('my_seat.seat_number') ==
                     this.get('game.active_user_position') &&
                 this.get('game.game_state') != 'wait_for_players';
        },

        current_bet : function() {
          var seats = this.get('game.seats');
          if (!seats)
            return 0;
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
          if (!my_seat)
            return 0;

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
          if (!my_seat)
            return false;
          return my_seat.money > amount_needed_to_call;
        },

        buy_in_increment : function() {
          if (!this.get('game'))
            return 0;
          return this.get('game.min_buy_in') / 2;
        },

        can_reveal : function() {
          var revealers = this.get('game.revealers');
          if (!revealers) return false;

          var game_state = this.get('game.game_state');
          if (!(game_state == 'reveal' ||
                game_state == 'last_man_standing')) {
            return false;
          }

          var my_seat = this.get('my_seat');
          if (!my_seat) return false;
          if (!my_seat.hole_cards.length) return false;


          var userid = this.get('userid');
          return !revealers.includes(userid);
        },

        previous_ledger : function() {
          // unlike the current ledger which is keyed by userid,
          // the previous ledger is keyed by name
          // userids are not meaningful across sessions
          
          var previous_ledger_csv = this.get('previous_ledger_csv');
          return parse_ledger_csv(previous_ledger_csv);
        },

        previous_ledger_sum : function() {
          var sum = 0;
          var previous_ledger = this.get('previous_ledger');
          for (var name in previous_ledger) {
            sum += previous_ledger[name];
          }
          return sum;
        },

        previous_ledger_size : function() {
          var sz = 0;
          var previous_ledger = this.get('previous_ledger');
          for (var name in previous_ledger) {
            ++sz;
          }
          return sz;
        },        

        ledger_csv : function() {
          var ledger = this.get('game.ledger');
          // copy prev ledger so we can mutate it
          var prev_ledger = Object.assign({}, this.get('previous_ledger'));;
          // fuse current ledger into prev ledger
          for (key in ledger) {
            var name = ledger[key].name;
            var payout = ledger[key].payout;
            if (name in prev_ledger) {
              prev_ledger[name] += payout;
            }
            else {
              prev_ledger[name] = payout;
            }
          }

          var csv = '';
          for (name in prev_ledger) {
            var payout = prev_ledger[name];
            csv += (name + ',' + payout + '\n');
          }

          return csv;
        }
      }
    });

    ractive.on('show_buyin_menu', function(event) {
      this.set('show_buyin_menu', event.context.seat_number);
      this.set('buy_in', this.get('game.min_buy_in'))
    });

    ractive.on('buy_in_increase', function(event) {
      var current = this.get('buy_in');
      var cap = this.get('game.max_buy_in');
      var next = current + this.get('buy_in_increment');
      var result = Math.min(next, cap);
      this.set('buy_in', result);
    });

    ractive.on('buy_in_decrease', function(event) {
      var current = this.get('buy_in');
      var next = current - this.get('buy_in_increment');
      var result = Math.max(next, this.get('game.min_buy_in'));
      this.set('buy_in', result);
    });

    ractive.on('show_raise_menu', function(event) {
      this.set('raise_menu', true);
      this.set('raise_amount', this.get('game.min_raise'));
    });

    ractive.on('hide_raise_menu',
               function(event) { this.set('raise_menu', false); });

    ractive.on('raise_increase', function(event) {
      var my_seat = this.get('my_seat')
      var amount_needed_to_call = this.get('amount_needed_to_call');
      var next = this.get('raise_amount') + this.get('raise_increment');
      this.set('raise_amount',
               Math.min(my_seat.money - amount_needed_to_call, next));
    });

    ractive.on('raise_decrease', function(event) {
      var current = this.get('raise_amount');
      var next = current - this.get('raise_increment');
      var result = Math.max(next, this.get('game.min_raise'));
      this.set('raise_amount', result);
    });

    ractive.on('hide_raise_menu',
               function(event) { this.set('raise_menu', false) });

    ractive.observe('is_my_turn', function(current, old, path) {
      if (!current)
        this.set('raise_menu', false);
      if (current) {
        var auto_action = this.get('auto_action');
        var amount_needed = this.get('amount_needed_to_call');
        if (auto_action == 'call_any') {
          send({'action' : 'call'});
        }
        if (auto_action == 'call') {
          console.log("Sending call or check due to auto action.");
          var auto_call_amount = this.get('auto_call_amount');
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

        this.set('auto_action', ''); // reset auto action
      }
    });

    ractive.observe('game.next_move_due', function(current, old, path) {
      if (!this.get('is_any_user_active')) {
        return;
      }
      var move_due = this.get('game.next_move_due');
      var curr_time = this.get('timestamp');
      var move_time_left =
          move_due - curr_time

                     this.set('move_time_left', move_time_left);
      this.animate('move_time_left', 0, {duration : move_time_left * 1000});
      console.log("Move timer updated to", move_time_left);
    });

    // Reset auto action
    ractive.observe('amount_needed_to_call', function(current, old) {
      var auto_action = this.get('auto_action');
      if (current > old && auto_action == 'call')
        this.set('auto_action', '');
    });

    ractive.observe('game.game_state',
                    function(current, old) { this.set('auto_action', ''); });

    ractive.on('copy_ledger_csv', function(event) {
      navigator.clipboard.writeText(this.get('ledger_csv'));
     });
                 
        
    ractive.on('buy_in', function(event) {
      send({
        'action' : 'buy_in',
        'buy_in' : this.get('buy_in'),
        'seat_number' : event.context.seat_number
      });
    });

    ractive.on(
        'replace',
        event => send(
            {'action' : 'replace', 'seat_number' : event.context.seat_number}));

    ractive.on('fold', event => send({'action' : 'fold'}));

    ractive.on('call_check', event => send({'action' : 'call'}));

    ractive.on('raise', function(event) {
      var raise_amount = this.get('raise_amount');
      send({'action' : 'raise', 'raise_amount' : raise_amount});
    });

    ractive.on('all_in', event => send({'action' : 'all_in'}));

    ractive.on('auto_action', function(event) {
      var new_action = event.node.value;
      var current_action = this.get('auto_action');
      if (current_action == new_action) {
        this.set('auto_action', '')
      } else {
        this.set('auto_action', new_action);
      }
      if (new_action == 'call') {
        var amount_needed = this.get('amount_needed_to_call');
        this.set('auto_call_amount', amount_needed);
      }
    });

    ractive.on('change_name', function(event) {
      new_name = this.get('new_name');
      document.cookie = "name=" + encodeURIComponent(new_name);
      send({'action' : 'change_name', 'name' : new_name});
    });

    ractive.on('leave_seat', event => send({'action' : 'disconnect'}));

    ractive.on('reveal', event => send({'action' : 'reveal'}));

    window.addEventListener("keydown", function(event) {
      if (event.key == '0') {
        this.fire('all_in');
      }
      if (event.key == '1') {
        this.fire('fold');
      }
      if (event.key == '2') {
        this.fire('call_check');
      }
      if (event.key == '3') {
        this.fire('show_raise_menu');
      }
      if (event.key == '+' || event.key == '=') {
        this.fire('raise_increase');
      }
      if (event.key == '-' || event.key == '_') {
        this.fire('raise_decrease');
      }
      if (event.key == 'Escape') {
        this.fire('hide_raise_menu');
        this.set('auto_action', null);
      }
      if (event.key == 'Enter') {
        this.fire('raise');
      }
      if (event.key == '4') {
        if (this.get('auto_action') == 'check_fold') {
          this.set('auto_action', '');
        } else {
          this.set('auto_action', 'check_fold');
        }
      }
      if (event.key == '5') {
        if (this.get('auto_action') == 'call') {
          this.set('auto_action', '');
        } else {
          this.set('auto_action', 'call');
        }
      }
      if (event.key == '6') {
        if (this.get('auto_action') == 'call_any') {
          this.set('auto_action', '');
        } else {
          this.set('auto_action', 'call_any');
        }
      }
    });

    return ractive;
  }


  // init logic
  fetch(template)
    .then(response => response.text())
    .then(function(text) {
      ractive = initialize_ractive(text, images_dir);
      game_connect(gameid, preferred_name);
    });
};

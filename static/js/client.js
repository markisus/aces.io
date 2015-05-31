function url(s) {
    var l = window.location;
    return ((l.protocol === "https:") ? "wss://" : "ws://") + l.hostname + (((l.port != 80) && (l.port != 443)) ? ":" + l.port : "") + '/' + s;
}


function connect(gameid, callback) {
    var socketUrl = url('gamesocket')

    var ws = new WebSocket(socketUrl);
    var send = function(data) {
	data = JSON.stringify(data);
	ws.send(data);
    };

    ws.onopen = function() {
	send({'action': 'connect', 'gameid': gameid});
    };

    ws.onmessage = function (evt) {
	callback(evt.data);
    };

    return send
}

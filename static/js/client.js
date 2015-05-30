function url(s) {
    var l = window.location;
    return ((l.protocol === "https:") ? "wss://" : "ws://") + l.hostname + (((l.port != 80) && (l.port != 443)) ? ":" + l.port : "") + '/' + s;
}


function connect(gameid) {
    var socketUrl = url('gamesocket')

    var ws = new WebSocket(socketUrl);

    ws.onopen = function() {
	ws.send(gameid);
    };

    ws.onmessage = function (evt) {
	alert(evt.data);
    };
}

(function(window) {

    var conn = new WebSocket('ws://' + location.host + '/ws');
    var handlers = {};
    conn.onopen = function() {
    }
    conn.onmessage = function(ev) {
        var json = JSON.parse(ev.data)
        var cmd = handlers[json.shift()];
        if(cmd) {
            cmd.apply(this, json);
        }
    }
    function send_message() {
        var data = Array.prototype.slice.call(arguments)
        conn.send(JSON.stringify(data));
    }


    handlers['vote'] = function(vote) {
        var el = document.getElementById('votes_' + vote.issue);
        if(el) {
            el.textContent = vote.votes;
        }
    }

})(this);

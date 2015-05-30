import os
import tornado.ioloop
import tornado.web
import tornado.websocket

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("index.html")

class GameHandler(tornado.web.RequestHandler):
    def get(self, gameid):
        self.render("client.html", gameid=gameid)

class GameSocketHandler(tornado.websocket.WebSocketHandler):
    def open(self):
        self.write_message("Okay guy!")

    def on_message(self, message):
        print(message)

    def on_close(self):
        pass

application = tornado.web.Application(
    [
        (r"/", MainHandler),
        (r"/game/([0-9]+)", GameHandler),
        (r"/gamesocket", GameSocketHandler),
    ],
    cookie_secret="__TODO:_GENERATE_YOUR_OWN_RANDOM_VALUE_HERE__",
    template_path=os.path.join(os.path.dirname(__file__), "templates"),
    static_path=os.path.join(os.path.dirname(__file__), "static"),
    xsrf_cookies=True,
    debug=True,
)

if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.current().start()

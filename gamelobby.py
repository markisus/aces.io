import sqlite3

class GameLobby:
    def __init__(self, max_games):
        self.max_games = max_games
        conn = sqlite3.connect(':memory:')
        self.conn = conn

        c = conn.cursor()
        c.execute('''create table games (gameid integer, primary key (gameid))''')
        c.execute('''create table users_games(gameid integer, user varchar, foreign key (gameid) references games(gameid))''')
        c.execute('''create index user_games_user_idx on users_games (user)''')
        for gameid in range(max_games):
            c.execute('''insert into games values (?)''', (gameid,))
        conn.commit()

    def get_games(self):
        c = self.conn.cursor()
        result = c.execute(
            '''select games.gameid, count(users_games.user) from games \
            left join users_games on games.gameid = users_games.gameid \
            group by games.gameid \
            order by games.gameid asc''')
        for row in result:
            print row

if __name__ == "__main__":
    g = GameLobby(4)
    g.get_games()

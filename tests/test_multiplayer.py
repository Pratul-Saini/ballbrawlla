from conftest import make_game, run

from ballbrawlla.input import Intent

IDLE = Intent()
GRAB = Intent(z_pressed=True)


def test_closest_player_wins_simultaneous_pickup():
    # Ball at x=640; P1 is 30px away, P2 is 15px away. Both in reach.
    g = make_game(players=[(610, 650), (655, 650)], ball=(640, 670))
    run(g, ticks=60)
    run(g, [GRAB, GRAB])
    assert g.ball.held_by is g.players[1]
    assert g.players[0].held_ball is None


def test_cannot_pick_up_ball_held_by_other_player():
    g = make_game(players=[(620, 650), (660, 650)], ball=(640, 670))
    run(g, ticks=60)
    run(g, [GRAB, IDLE])
    assert g.ball.held_by is g.players[0]
    run(g, [IDLE, GRAB])
    assert g.ball.held_by is g.players[0]


def test_players_pass_through_each_other():
    g = make_game(players=[(400, 650), (440, 650)])
    run(g, ticks=60)
    run(g, [Intent(move_x=1), Intent(move_x=-1)], ticks=30)
    assert g.players[0].center.x > g.players[1].center.x


def test_disconnected_player_is_not_simulated_and_drops_ball():
    g = make_game(players=[(200, 650), (620, 650)], ball=(640, 670))
    run(g, ticks=60)
    run(g, [IDLE, GRAB])
    assert g.ball.held_by is g.players[1]
    g.reset_player(1, connected=False)
    assert g.ball.held_by is None
    y0 = g.players[1].body.pos.y
    run(g, ticks=30)
    assert g.players[1].body.pos.y == y0  # frozen: not updated

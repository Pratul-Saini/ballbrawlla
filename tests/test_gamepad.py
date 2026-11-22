"""Controller support, driven by a fake DualSense (no hardware needed)."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest
from conftest import make_game, run

from ballbrawlla.gamepad import AXIS_MAX, BUTTON_TOUCHPAD, Gamepads
from ballbrawlla.input import Intent, KeyboardInput
from ballbrawlla.net.host import RemoteInput
from ballbrawlla.net.protocol import intent_to_msg

A, B, X = (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_B,
            pygame.CONTROLLER_BUTTON_X)
LX, LY, RX, RY = (pygame.CONTROLLER_AXIS_LEFTX, pygame.CONTROLLER_AXIS_LEFTY,
                  pygame.CONTROLLER_AXIS_RIGHTX, pygame.CONTROLLER_AXIS_RIGHTY)


class FakePad:
    name = "DualSense Wireless Controller"

    def __init__(self):
        self.axes = {}
        self.buttons = set()

    def tilt(self, axis, frac):
        self.axes[axis] = int(frac * AXIS_MAX)

    def get_axis(self, axis):
        return self.axes.get(axis, 0)

    def get_button(self, b):
        return int(b in self.buttons)


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((64, 64))
    yield
    pygame.quit()


@pytest.fixture
def pads():
    g = Gamepads()
    g.pads.clear()
    pad = FakePad()
    g.pads[7] = pad
    return g, pad


def ev(kind, **kw):
    return pygame.event.Event(kind, **kw)


# ---------------------------------------------------------------- held state

def test_left_stick_and_dpad_move(pads):
    g, pad = pads
    assert g.held().move_x == 0
    pad.tilt(LX, 0.2)  # inside the deadzone
    assert g.held().move_x == 0
    pad.tilt(LX, 0.8)
    assert g.held().move_x == 1
    pad.tilt(LX, 0)
    pad.buttons.add(pygame.CONTROLLER_BUTTON_DPAD_LEFT)
    assert g.held().move_x == -1


def test_stick_down_crouches_but_a_slight_diagonal_does_not(pads):
    g, pad = pads
    pad.tilt(LX, 0.9)
    pad.tilt(LY, 0.4)   # SDL: positive Y is down
    assert g.held().vertical == 0
    pad.tilt(LY, 0.8)
    assert g.held().vertical == -1
    pad.tilt(LY, -0.8)
    assert g.held().vertical == 1


def test_cross_held_and_right_stick_aim(pads):
    g, pad = pads
    pad.buttons.add(A)
    pad.tilt(RX, 0.0)
    pad.tilt(RY, -0.9)  # pushed up
    h = g.held()
    assert h.jump_held
    assert h.aim_stick == pytest.approx((0.0, 0.9), abs=1e-3)
    pad.tilt(RY, -0.3)  # not pushed far enough
    assert g.held().aim_stick is None


# ---------------------------------------------------------------- button events

def test_face_buttons_map_to_jump_grab_throw(pads):
    g, _ = pads
    g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=A, instance_id=7))
    g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=X, instance_id=7))
    g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=B, instance_id=7))
    e = g.consume_edges()
    assert e.jump and e.grab and e.throw
    e = g.consume_edges()
    assert not (e.jump or e.grab or e.throw)  # edges are one-shot


def test_r1_and_r2_also_throw_and_r2_fires_once_per_pull(pads):
    g, _ = pads
    g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_RIGHTSHOULDER, instance_id=7))
    assert g.consume_edges().throw
    trig = pygame.CONTROLLER_AXIS_TRIGGERRIGHT
    for v in (0.2, 0.7, 0.9, 1.0):
        g.handle_event(ev(pygame.CONTROLLERAXISMOTION, axis=trig, value=int(v * AXIS_MAX), instance_id=7))
    assert g.consume_edges().throw
    g.handle_event(ev(pygame.CONTROLLERAXISMOTION, axis=trig, value=int(0.95 * AXIS_MAX), instance_id=7))
    assert not g.consume_edges().throw  # still held: no second throw
    g.handle_event(ev(pygame.CONTROLLERAXISMOTION, axis=trig, value=0, instance_id=7))
    g.handle_event(ev(pygame.CONTROLLERAXISMOTION, axis=trig, value=AXIS_MAX, instance_id=7))
    assert g.consume_edges().throw


def test_menu_buttons(pads):
    g, _ = pads
    assert g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_START, instance_id=7)) == "restart"
    assert g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_BACK, instance_id=7)) == "debug"
    assert g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=BUTTON_TOUCHPAD, instance_id=7)) == "debug"


def test_unplugging_removes_the_pad(pads):
    g, _ = pads
    assert g.names == ["DualSense Wireless Controller"]
    g.handle_event(ev(pygame.CONTROLLERDEVICEREMOVED, instance_id=7))
    assert g.pads == {} and g.held() == type(g.held())()


# ---------------------------------------------------------------- merged into Intent

def test_keyboard_input_merges_the_controller(pads):
    g, pad = pads
    k = KeyboardInput(shared_pads=g)              # events go to the shared pads, as in local play
    pad.tilt(LX, -1.0)
    pad.buttons.add(A)
    g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=A, instance_id=7))
    g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=X, instance_id=7))
    i = k.consume()
    assert i.move_x == -1 and i.jump_pressed and i.jump_held and i.up_held and i.z_pressed
    i = k.consume()
    assert not i.jump_pressed and not i.z_pressed and i.jump_held
    assert g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_START, instance_id=7)) == "restart"


def test_an_input_that_owns_the_pads_forwards_their_events():
    k = KeyboardInput()
    k.gamepads.pads.clear()
    k.gamepads.pads[7] = FakePad()
    assert k.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=pygame.CONTROLLER_BUTTON_START, instance_id=7)) == "restart"
    k.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=X, instance_id=7))
    assert k.consume().z_pressed


def test_local_play_gives_each_player_their_own_controller(pads):
    g, blue_pad = pads
    red_pad = FakePad()
    g.pads[9] = red_pad                            # connected second
    blue = KeyboardInput(shared_pads=g, pad_slot=0)
    red = KeyboardInput(shared_pads=g, pad_slot=1)
    blue_pad.tilt(LX, 1.0)
    red_pad.tilt(LX, -1.0)
    g.handle_event(ev(pygame.CONTROLLERBUTTONDOWN, button=X, instance_id=9))   # Red presses Square
    b, r = blue.consume(), red.consume()
    assert b.move_x == 1 and r.move_x == -1
    assert r.z_pressed and not b.z_pressed


def test_controller_fields_cross_the_network():
    r = RemoteInput()
    r.feed(intent_to_msg(Intent(jump_held=True, aim_stick=(0.5, -0.7))))
    i = r.consume()
    assert i.jump_held and i.aim_stick == pytest.approx((0.5, -0.7))


# ---------------------------------------------------------------- gameplay

def _jump_peak(intent_held: Intent) -> float:
    g = make_game()
    run(g, ticks=60)
    y0 = g.player.box.bottom
    run(g, Intent(jump_pressed=True, jump_held=intent_held.jump_held))
    top = y0
    for _ in range(120):
        run(g, intent_held)
        top = min(top, g.player.box.bottom)
    return y0 - top


def test_holding_cross_gives_a_full_jump_releasing_it_cuts_it_short():
    full = _jump_peak(Intent(jump_held=True))
    short = _jump_peak(Intent())
    assert full > short * 1.5
    keyboard = _jump_peak(Intent(vertical=1))  # same as holding Up
    assert full == pytest.approx(keyboard)


def test_right_stick_points_the_aim_in_sandbox():
    g = make_game(player=(200, 650), ball=(220, 650))
    run(g, ticks=60)
    run(g, Intent(z_pressed=True))
    run(g, Intent(z_pressed=True))
    assert g.player.state.name == "aiming"
    run(g, Intent(aim_stick=(-0.7, 0.7)))  # up-left
    assert g.player.aim_angle == pytest.approx(135)


def test_right_stick_points_the_aim_in_the_play_call():
    from test_session import make_session, step

    s = make_session()
    step(s, off=Intent(z_pressed=True))  # Square: confirm QB spot
    step(s, off=Intent(aim_stick=(0.0, 1.0)))
    assert s.call.aim_angle == pytest.approx(90)
    step(s, off=Intent(x_pressed=True))  # Circle: lock in
    assert s.call.offense_locked

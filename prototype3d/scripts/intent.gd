extends RefCounted
## One actor's input for one simulation tick (mirrors the 2-D game's Intent: the sim only ever sees
## this, never a device, so the AI defender and a human produce the same thing).

var move := Vector2.ZERO        # desired move on the ground, camera-relative: x = right, y = forward, len <= 1
var move_world := Vector3.ZERO  # horizontal world-space move dir * magnitude (filled by main from the camera)
var jump_pressed := false       # edge
var jump_held := false
var catch_pressed := false      # edge: catch / tag / confirm a placement
var slide_pressed := false      # edge: start a slide, or cancel one
var throw_pressed := false      # edge: lock in the throw

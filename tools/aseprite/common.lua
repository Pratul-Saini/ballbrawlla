-- Shared constants and helpers for the fball rig scripts.
-- Run through the Aseprite CLI, see tools/make_run_cycle.sh.
local C = {}

C.SIZE = 96
C.LAYER_ORDER = { "leg_far", "leg_near", "head_torso", "arm_far", "arm_near" } -- bottom to top
C.LAYERS = C.LAYER_ORDER

-- Region rules, right-facing art space. Left-facing sources use x -> 95 - x.
C.LEG_TOP = 65          -- rows >= this are legs, the pelvis block above stays in head_torso
C.LEG_SPLIT_X = 51      -- x <= this is leg_far (the back leg), above it leg_near
C.ARM_NEAR = { x0 = 62, y0 = 28, y1 = 46 }
C.ARM_FAR = { x1 = 37, y0 = 26, y1 = 50 }

-- Fist of the near arm (the old HAND_RIGHT anchor in player_sprites.gd), right-facing.
C.HAND = { x = 76.2, y = 39.4 }

function C.region(x, y, mirror)
  local xx = mirror and (C.SIZE - 1 - x) or x
  if y >= C.LEG_TOP then
    if xx <= C.LEG_SPLIT_X then return "leg_far" end
    return "leg_near"
  end
  if xx >= C.ARM_NEAR.x0 and y >= C.ARM_NEAR.y0 and y <= C.ARM_NEAR.y1 then return "arm_near" end
  if xx <= C.ARM_FAR.x1 and y >= C.ARM_FAR.y0 and y <= C.ARM_FAR.y1 then return "arm_far" end
  return "head_torso"
end

-- Reads a cel into a plain table t[y][x] = packed rgba (0 when transparent).
function C.read_cel(cel, w, h)
  local t = {}
  for y = 0, h - 1 do t[y] = {} end
  if not cel then
    for y = 0, h - 1 do for x = 0, w - 1 do t[y][x] = 0 end end
    return t
  end
  local img, p = cel.image, cel.position
  for y = 0, h - 1 do
    for x = 0, w - 1 do
      local ix, iy = x - p.x, y - p.y
      local v = 0
      if ix >= 0 and iy >= 0 and ix < img.width and iy < img.height then
        v = img:getPixel(ix, iy)
        if app.pixelColor.rgbaA(v) == 0 then v = 0 end
      end
      t[y][x] = v
    end
  end
  return t
end

-- pure black (outline) and pure white (number, stripes) are never copied by the hole fill
function C.is_outline(v)
  local pc = app.pixelColor
  return (pc.rgbaR(v) == 0 and pc.rgbaG(v) == 0 and pc.rgbaB(v) == 0)
    or (pc.rgbaR(v) == 255 and pc.rgbaG(v) == 255 and pc.rgbaB(v) == 255)
end

function C.param(name, default)
  local v = app.params[name]
  if v == nil or v == "" then return default end
  return v
end

return C

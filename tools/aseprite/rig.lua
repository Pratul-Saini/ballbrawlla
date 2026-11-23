-- Builds the tagged animation by moving whole layer cels per frame (integer offsets only, no rotation),
-- closes small holes with colours that already exist in the sprite, and keeps every layer editable.
-- params: root, split (layered .aseprite from split_layers.lua), out (rigged .aseprite),
--         hands (hands.json to write), mirror (true for *_left art)
local C = dofile(app.params["root"] .. "/tools/aseprite/common.lua")
local mirror = app.params["mirror"] == "true"
local S = C.SIZE
local GROUND_ROW = 85       -- lowest opaque row of every grounded frame
local CLOSE_R = 2           -- hole closing radius (px) for the disocclusion fill
local SEARCH_R = 4          -- how far the fill looks for a neighbour colour

-- Offsets are right-facing {dx, dy} (y down). Left-facing art negates dx.
-- Part keys: lf leg_far (the back leg), ln leg_near, ht head_torso, af arm_far, an arm_near.
local Z = { 0, 0 }
local FRAMES = {
  -- idle: legs gathered under the body, a 1 px breathing dip
  { tag = "idle", ms = 500, ground = true, o = { lf = { 14, 0 }, ln = { -9, 0 }, af = { 4, 0 }, an = { 0, 0 } } },
  { tag = "idle", ms = 500, ground = true, o = { lf = { 14, 0 }, ln = { -9, 0 }, ht = { 0, 1 }, af = { 4, 1 }, an = { 0, 1 } } },
  -- run: frames 1-4 start from the drawn contact pose, frames 5-8 are the same legs mirrored
  -- (flip = both leg layers mirrored about the hips, offsets negated), so the legs trade places.
  -- The arms never flip: the ball hand stays on the right side and the number stays uncovered.
  { tag = "run", ms = 80, ground = true, o = { af = { 0, 0 }, an = { 0, 0 } } },
  { tag = "run", ms = 80, ground = true, o = { lf = { 6, 0 }, ln = { -5, 0 }, ht = { 0, 1 }, af = { 3, 1 }, an = { 0, 1 } } },
  { tag = "run", ms = 80, ground = true, o = { lf = { 13, -3 }, ln = { -10, 0 }, af = { 6, 0 }, an = { 1, 0 } } },
  { tag = "run", ms = 80, ground = true, o = { lf = { 16, -2 }, ln = { -14, 0 }, ht = { 0, -1 }, af = { 3, -1 }, an = { 0, -1 } } },
  { tag = "run", ms = 80, ground = true, flip = true, o = { af = { 0, 0 }, an = { 0, 0 } } },
  { tag = "run", ms = 80, ground = true, flip = true, o = { lf = { -6, 0 }, ln = { 5, 0 }, ht = { 0, 1 }, af = { 3, 1 }, an = { 0, 1 } } },
  { tag = "run", ms = 80, ground = true, flip = true, o = { lf = { -9, -3 }, ln = { 12, 0 }, af = { 6, 0 }, an = { 1, 0 } } },
  { tag = "run", ms = 80, ground = true, flip = true, o = { lf = { -11, -2 }, ln = { 14, 0 }, ht = { 0, -1 }, af = { 3, -1 }, an = { 0, -1 } } },
  -- jump: take-off squash, then stretch with the feet tucked up
  { tag = "jump", ms = 60, ground = true, o = { ht = { 0, 2 }, af = { 0, 2 }, an = { 0, 2 } } },
  { tag = "jump", ms = 90, ground = false, o = { lf = { 10, -4 }, ln = { -6, -4 }, ht = { 0, 1 }, af = { 2, -4 }, an = { 0, -4 } } },
  -- apex
  { tag = "apex", ms = 100, ground = false, o = { lf = { 16, -6 }, ln = { -10, -6 }, af = { 4, -3 }, an = { 0, -3 } } },
  -- fall: arms up, feet reaching down
  { tag = "fall", ms = 100, ground = false, o = { lf = { 4, -2 }, ln = { -3, -2 }, af = { 2, -5 }, an = { 0, -5 } } },
  { tag = "fall", ms = 100, ground = false, o = { lf = { 3, -3 }, ln = { -2, -2 }, ht = { 0, -1 }, af = { 3, -6 }, an = { 0, -6 } } },
  -- land: squash then recover
  { tag = "land", ms = 60, ground = true, o = { ht = { 0, 3 }, af = { 0, 3 }, an = { 0, 3 } } },
  { tag = "land", ms = 60, ground = true, o = { ht = { 0, 1 }, af = { 0, 1 }, an = { 0, 1 } } },
}
-- ground frames that are not run get the gathered stance of idle as base
local FLIP_AXIS = mirror and 90 or 100 -- x -> axis - x mirrors a leg about the hips
local KEYS = { lf = "leg_far", ln = "leg_near", ht = "head_torso", af = "arm_far", an = "arm_near" }
local KEY_ORDER = { "lf", "ln", "ht", "af", "an" }

local spr = Sprite{ fromFile = app.params["split"] }
local layers = {}
for _, l in ipairs(spr.layers) do layers[l.name] = l end

-- base silhouette and base colour regions (frame 1 of the split file, before any move)
local base = {}
for _, name in ipairs(C.LAYER_ORDER) do base[name] = C.read_cel(layers[name].cels[1], S, S) end
local baseAlpha = {}
for y = 0, S - 1 do
  baseAlpha[y] = {}
  for x = 0, S - 1 do
    local o = 0
    for _, name in ipairs(C.LAYER_ORDER) do if base[name][y][x] ~= 0 then o = 1 end end
    baseAlpha[y][x] = o
  end
end

local function offset(frame, key)
  local o = frame.o[key] or Z
  local dx = mirror and -o[1] or o[1]
  return dx, o[2]
end

-- composite of the layers at the given offsets (+ global dy), returns t[y][x]
local function is_leg(key) return key == "lf" or key == "ln" end

local function composite(frame, shift)
  local comp = {}
  for y = 0, S - 1 do comp[y] = {}; for x = 0, S - 1 do comp[y][x] = 0 end end
  for _, name in ipairs(C.LAYER_ORDER) do
    local key
    for k, v in pairs(KEYS) do if v == name then key = k end end
    local dx, dy = offset(frame, key)
    dy = dy + shift
    local flipped = frame.flip and is_leg(key)
    local src = base[name]
    for y = 0, S - 1 do
      local ty = y + dy
      if ty >= 0 and ty < S then
        for x = 0, S - 1 do
          local v = src[y][x]
          if v ~= 0 then
            local tx = x + dx
            if flipped then tx = FLIP_AXIS - x + dx end
            if tx >= 0 and tx < S then comp[ty][tx] = v end
          end
        end
      end
    end
  end
  return comp
end

local function lowest_row(comp)
  for y = S - 1, 0, -1 do
    for x = 0, S - 1 do if comp[y][x] ~= 0 then return y end end
  end
  return -1
end

-- Fill holes: pixels that were opaque in the base pose, are empty now, and sit inside the
-- radius-CLOSE_R morphological closing of the current silhouette. The colour is copied from the
-- nearest opaque non-outline pixel of the same frame, so no new colours appear.
local function fill_holes(comp, shift)
  local function inb(x, y) return x >= 0 and y >= 0 and x < S and y < S end
  local dil = {}
  for y = 0, S - 1 do
    dil[y] = {}
    for x = 0, S - 1 do
      local hit = 0
      for dy = -CLOSE_R, CLOSE_R do
        for dx = -CLOSE_R, CLOSE_R do
          local nx, ny = x + dx, y + dy
          if inb(nx, ny) and comp[ny][nx] ~= 0 then hit = 1 end
        end
      end
      dil[y][x] = hit
    end
  end
  local filled = {}
  local count = 0
  for y = 0, S - 1 do
    filled[y] = {}
    for x = 0, S - 1 do filled[y][x] = 0 end
  end
  for y = 0, S - 1 do
    for x = 0, S - 1 do
      local by = y - shift
      if comp[y][x] == 0 and dil[y][x] == 1 and inb(x, by) and baseAlpha[by][x] == 1 then
        -- closing = erosion of the dilation: every pixel of the (2r+1) box must be in the dilation
        local inside = true
        for dy = -CLOSE_R, CLOSE_R do
          for dx = -CLOSE_R, CLOSE_R do
            local nx, ny = x + dx, y + dy
            if inb(nx, ny) and dil[ny][nx] == 0 then inside = false end
          end
        end
        if inside then
          local found = 0
          for k = 1, SEARCH_R do
            for dy = -k, k do
              for dx = -k, k do
                if found == 0 and math.max(math.abs(dx), math.abs(dy)) == k then
                  local nx, ny = x + dx, y + dy
                  if inb(nx, ny) and comp[ny][nx] ~= 0 and not C.is_outline(comp[ny][nx]) then
                    found = comp[ny][nx]
                  end
                end
              end
            end
            if found ~= 0 then break end
          end
          if found ~= 0 then filled[y][x] = found; count = count + 1 end
        end
      end
    end
  end
  return filled, count
end

local hands = {}
local fillCounts = {}

app.transaction(function()
  while #spr.frames < #FRAMES do spr:newFrame(#spr.frames) end
  local fillLayer = spr:newLayer()
  fillLayer.name = "fill"
  -- place the fill layer directly under head_torso
  fillLayer.stackIndex = layers["head_torso"].stackIndex
  layers["fill"] = fillLayer

  for fi, frame in ipairs(FRAMES) do
    spr.frames[fi].duration = frame.ms / 1000
    -- feet on the same ground line in every grounded frame: shift the whole frame by an integer
    local shift = 0
    if frame.ground then shift = GROUND_ROW - lowest_row(composite(frame, 0)) end
    for _, key in ipairs(KEY_ORDER) do
      local dx, dy = offset(frame, key)
      local cel = layers[KEYS[key]]:cel(fi)
      if frame.flip and is_leg(key) then
        local img = Image(S, S, spr.colorMode)
        local src = base[KEYS[key]]
        for y = 0, S - 1 do for x = 0, S - 1 do
          local v = src[y][x]
          local fx = FLIP_AXIS - x
          if v ~= 0 and fx >= 0 and fx < S then img:drawPixel(fx, y, v) end
        end end
        cel.image = img
      end
      cel.position = Point(dx, dy + shift)
    end
    local comp = composite(frame, shift)
    local filled, n = fill_holes(comp, shift)
    fillCounts[fi] = n
    local img = Image(S, S, spr.colorMode)
    for y = 0, S - 1 do for x = 0, S - 1 do
      if filled[y][x] ~= 0 then img:drawPixel(x, y, filled[y][x]) end
    end end
    spr:newCel(fillLayer, fi, img, Point(0, 0))
    local hx = mirror and (S - 1 - C.HAND.x) or C.HAND.x
    local adx, ady = offset(frame, "an")
    hands[fi] = { hx + adx, C.HAND.y + ady + shift }
  end

  -- tags
  local first = {}
  local last = {}
  local order = {}
  for fi, frame in ipairs(FRAMES) do
    if not first[frame.tag] then first[frame.tag] = fi; order[#order + 1] = frame.tag end
    last[frame.tag] = fi
  end
  for _, t in ipairs(order) do
    local tag = spr:newTag(first[t], last[t])
    tag.name = t
    tag.aniDir = AniDir.FORWARD
  end
end)

spr:saveAs(app.params["out"])

local f = assert(io.open(app.params["hands"], "w"))
f:write("[\n")
for i, h in ipairs(hands) do
  f:write(string.format("  [%.1f, %.1f]%s\n", h[1], h[2], i < #hands and "," or ""))
end
f:write("]\n")
f:close()
local fc = {}
for i, n in ipairs(fillCounts) do fc[#fc + 1] = tostring(n) end
print("rigged " .. app.params["out"] .. " frames=" .. #FRAMES .. " fill px per frame: " .. table.concat(fc, ","))

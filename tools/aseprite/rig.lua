-- Builds the tagged animation from the split layers. No rotation and no flips: every leg is
-- re-assembled per frame from sub-parts of the hand-drawn legs (integer offsets, column shear,
-- row duplication), the torso leans by shearing rows, and holes are closed with colours that
-- already exist in the sprite. Every layer stays editable in the saved .aseprite.
-- params: root, split (layered .aseprite from split_layers.lua), out (rigged .aseprite),
--         hands (hands.json to write), legs (legs.json to write), mirror (true for *_left art)
--
-- All art decisions are made in right-facing ("canonical") coordinates. Left-facing sources are read
-- mirrored (x -> 95 - x) and every cel is written mirrored back, so the torso and the "23" are
-- exactly the source pixels in every frame.
local C = dofile(app.params["root"] .. "/tools/aseprite/common.lua")
local mirror = app.params["mirror"] == "true"
local S = C.SIZE
local GROUND_ROW = 85       -- lowest opaque row of every grounded frame
local CLOSE_R = 2           -- hole closing radius (px) for the disocclusion fill
local SEARCH_R = 4          -- how far the fill looks for a neighbour colour

----------------------------------------------------------------------------------------------
-- Leg parts of the drawn pose (canonical coordinates)
--   N = the drawn front leg: shin (rows 65..73) and a flat shoe (rows 74..83, sole row 83).
--   F = the drawn back leg: a horizontal leg (rows 65..75) and a toe-down shoe (rows 73..85).
-- A leg spec is { art = "N", dx, dy, st }  st = rows added to the shin so the sole drops by st
--              { art = "F", dx, dy, r, lift } r = how far the far end of the leg is sheared up,
--                                              lift = extra lift of the shoe only
----------------------------------------------------------------------------------------------
local F_PIVOT, F_END = 40, 22      -- shear pivot column and the far end column of the back leg

local function N(dx, dy, st) return { art = "N", dx = dx, dy = dy or 0, st = st or 0 } end
local function F(dx, r, dy) return { art = "F", dx = dx, r = r or 0, dy = dy or 0 } end

-- Run cycle, 4 steps per half. Leg X is planted in front at step 1 of half 1 (leg layer "far"),
-- leg Y trails. X: planted at 1 (loaded), 2 (down, body moves over it), 3 (passing, under the body),
-- lifts to trail at 4. Y: trails at 1, 2, swings through at 3 (knee up), touches down in front at 4.
-- Frames 5-8 swap the layers, so each leg is planted for 4 frames and in the air for 4.
-- The arms swing against the legs: far arm forward (in toward the body) in half 2, near arm forward in half 1.
local RUN_X = { N(0, 0, 2), N(-6, 0, 2), N(-12, 0, 2), F(8, 1, -4) }
local RUN_Y = { F(-2, 2, -6), F(2, 2, -7), N(-3, -9, 0), N(5, 0, 2) }
local RUN_TORSO = { { 0, 2 }, { 1, 1 }, { -1, 0 }, { -1, 1 } }             -- { dy, lean }
local RUN_AF = { { 0, 0 }, { 1, 0 }, { 4, -1 }, { 7, -1 }, { 8, 0 }, { 7, 0 }, { 4, 1 }, { 1, 1 } }
local RUN_AN = { { 2, -2 }, { 2, -1 }, { 1, 0 }, { 0, 1 }, { 0, 2 }, { 0, 1 }, { 1, 0 }, { 2, -1 } }

local FRAMES = {}
local function add(f) FRAMES[#FRAMES + 1] = f end

-- idle: relaxed stance, both flat shoes planted side by side, 1 px breathing dip
add { tag = "idle", ms = 500, ground = true, torso = { 0, 0 }, af = { 5, 2 }, an = { 0, 2 },
      far = N(-9, 0, 2), near = N(1, 0, 2) }
add { tag = "idle", ms = 500, ground = true, torso = { 1, 0 }, af = { 5, 3 }, an = { 0, 3 },
      far = N(-9, 0, 2), near = N(1, 0, 2) }

local RUN_MS = 80
for half = 1, 2 do
  for k = 1, 4 do
    local i = (half - 1) * 4 + k
    local f = { tag = "run", ms = RUN_MS, ground = true, torso = RUN_TORSO[k], af = RUN_AF[i], an = RUN_AN[i] }
    if half == 1 then f.far, f.near = RUN_X[k], RUN_Y[k] else f.far, f.near = RUN_Y[k], RUN_X[k] end
    add(f)
  end
end

-- jump: take-off squash (legs compressed), then rise with the front knee up and the back leg trailing
add { tag = "jump", ms = 60, ground = true, torso = { 1, 0 }, af = { 3, 3 }, an = { 0, 3 },
      far = N(-13, 0, -3), near = N(3, 0, -3) }
add { tag = "jump", ms = 90, ground = false, torso = { -1, 0 }, af = { 3, -5 }, an = { 0, -5 },
      far = F(-1, 0, -4), near = N(4, -9, 0) }
-- apex: knees tucked, split legs, arms up
add { tag = "apex", ms = 100, ground = false, torso = { 0, 0 }, af = { 5, -4 }, an = { 0, -4 },
      far = F(9, 1, -10), near = N(7, -14, 0) }
-- fall: legs extended down and apart, feet reaching, arms up
add { tag = "fall", ms = 100, ground = false, torso = { 0, 0 }, af = { 1, -5 }, an = { 0, -5 },
      far = N(-11, -3, 3), near = N(3, -3, 3) }
add { tag = "fall", ms = 100, ground = false, torso = { -1, 0 }, af = { 0, -6 }, an = { 0, -6 },
      far = N(-12, -2, 4), near = N(4, -2, 4) }
-- land: deep crouch (legs compressed, torso lowered 3 to 4 px), then recover
add { tag = "land", ms = 60, ground = true, torso = { 1, 0 }, af = { 3, 4 }, an = { 0, 4 },
      far = N(-14, 0, -4), near = N(5, 0, -4) }
add { tag = "land", ms = 60, ground = true, torso = { 0, 0 }, af = { 4, 2 }, an = { 0, 2 },
      far = N(-11, 0, -2), near = N(2, 0, -2) }

----------------------------------------------------------------------------------------------
-- Grid helpers. A grid is g[y][x] = packed rgba, 0 when transparent.
----------------------------------------------------------------------------------------------
local function newgrid()
  local g = {}
  for y = 0, S - 1 do
    g[y] = {}
    for x = 0, S - 1 do g[y][x] = 0 end
  end
  return g
end

local function flipx(g)
  if not mirror then return g end
  local o = newgrid()
  for y = 0, S - 1 do for x = 0, S - 1 do o[y][x] = g[y][S - 1 - x] end end
  return o
end

local function blit(dst, src, dx, dy)
  for y = 0, S - 1 do
    local ty = y + dy
    if ty >= 0 and ty < S then
      for x = 0, S - 1 do
        local v = src[y][x]
        if v ~= 0 then
          local tx = x + dx
          if tx >= 0 and tx < S then dst[ty][tx] = v end
        end
      end
    end
  end
end

local function sub(g, pred)
  local o = newgrid()
  for y = 0, S - 1 do for x = 0, S - 1 do
    if g[y][x] ~= 0 and pred(x, y) then o[y][x] = g[y][x] end
  end end
  return o
end

-- n > 0: copies row `row` n more times, everything below moves down by n.
-- n < 0: removes -n rows after `row`, everything below moves up.
local function stretch(g, row, n)
  if n == 0 then return g end
  local o = newgrid()
  for y = 0, S - 1 do
    if y <= row then
      for x = 0, S - 1 do o[y][x] = g[y][x] end
    elseif n > 0 then
      if y + n < S then for x = 0, S - 1 do o[y + n][x] = g[y][x] end end
    elseif y > row - n then
      for x = 0, S - 1 do o[y + n][x] = g[y][x] end
    end
  end
  if n > 0 then
    for k = 1, n do if row + k < S then for x = 0, S - 1 do o[row + k][x] = g[row][x] end end end
  end
  return o
end

-- columns left of `pivot` move up by r * (pivot - x) / (pivot - x0), a shear that raises the far end
local function shear_up(g, pivot, x0, r)
  local o = newgrid()
  for x = 0, S - 1 do
    local d = 0
    if x < pivot then d = math.floor(r * (pivot - x) / (pivot - x0) + 0.5) end
    for y = 0, S - 1 do
      local v = g[y][x]
      if v ~= 0 and y - d >= 0 then o[y - d][x] = v end
    end
  end
  return o
end

local function lowest_row(g)
  for y = S - 1, 0, -1 do
    for x = 0, S - 1 do if g[y][x] ~= 0 then return y end end
  end
  return -1
end

local function extent_x(g)
  local lo, hi = S, -1
  for y = 0, S - 1 do for x = 0, S - 1 do
    if g[y][x] ~= 0 then if x < lo then lo = x end; if x > hi then hi = x end end
  end end
  return lo, hi
end

----------------------------------------------------------------------------------------------
-- Load the split layers in canonical coordinates
----------------------------------------------------------------------------------------------
local spr = Sprite{ fromFile = app.params["split"] }
local layers = {}
for _, l in ipairs(spr.layers) do layers[l.name] = l end

local base = {}
for _, name in ipairs(C.LAYER_ORDER) do base[name] = flipx(C.read_cel(layers[name].cels[1], S, S)) end

local baseAlpha = newgrid()
for y = 0, S - 1 do for x = 0, S - 1 do
  for _, name in ipairs(C.LAYER_ORDER) do if base[name][y][x] ~= 0 then baseAlpha[y][x] = 1 end end
end end

local N_SHIN = sub(base.leg_near, function(x, y) return y < 74 end)
local N_SHOE = sub(base.leg_near, function(x, y) return y >= 74 end)
local N_STRETCH_ROW = 70

local function build_leg(spec, shift)
  local g = newgrid()
  if spec.art == "N" then
    blit(g, stretch(N_SHIN, N_STRETCH_ROW, spec.st), spec.dx, spec.dy + shift)
    blit(g, N_SHOE, spec.dx, spec.dy + spec.st + shift)
  else
    -- the drawn back leg (tube + toe-down shoe) sheared as one piece, the far end raised by r px
    blit(g, shear_up(base.leg_far, F_PIVOT, F_END, spec.r), spec.dx, spec.dy + shift)
  end
  return g
end

-- head and torso with a forward lean: rows above the shoulders shift by L, the chest by L // 2,
-- the pelvis stays so the legs keep their attachment. Rows 29..40 (the number) always move together.
local HEAD_ROW, CHEST_ROW = 21, 48
local function build_torso(dy, lean, shift)
  local g = newgrid()
  local src = base.head_torso
  for y = 0, S - 1 do
    local dx = 0
    if y <= HEAD_ROW then dx = lean elseif y <= CHEST_ROW then dx = math.floor(lean / 2) end
    local ty = y + dy + shift
    if ty >= 0 and ty < S then
      for x = 0, S - 1 do
        local v = src[y][x]
        if v ~= 0 and x + dx >= 0 and x + dx < S then g[ty][x + dx] = v end
      end
    end
  end
  return g
end

local function build_arm(name, dx, dy, shift)
  local g = newgrid()
  blit(g, base[name], dx, dy + shift)
  return g
end

----------------------------------------------------------------------------------------------
-- Frame assembly
----------------------------------------------------------------------------------------------
local ORDER = { "arm_far", "leg_far", "leg_near", "head_torso", "arm_near" }  -- bottom to top (fill sits under head_torso)

local function parts_for(frame, shift)
  local dyT, lean = frame.torso[1], frame.torso[2]
  local armShift = math.floor(lean / 2)
  return {
    arm_far = build_arm("arm_far", frame.af[1] + armShift, frame.af[2], shift),
    leg_far = build_leg(frame.far, shift),
    leg_near = build_leg(frame.near, shift),
    head_torso = build_torso(dyT, lean, shift),
    arm_near = build_arm("arm_near", frame.an[1] + armShift, frame.an[2], shift),
  }
end

local function composite(parts)
  local comp = newgrid()
  for _, name in ipairs(ORDER) do blit(comp, parts[name], 0, 0) end
  return comp
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
  local filled = newgrid()
  local count = 0
  for y = 0, S - 1 do
    for x = 0, S - 1 do
      local by = y - shift
      if comp[y][x] == 0 and dil[y][x] == 1 and inb(x, by) and baseAlpha[by][x] == 1 then
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

local function to_image(g)
  local g2 = flipx(g)
  local img = Image(S, S, spr.colorMode)
  for y = 0, S - 1 do for x = 0, S - 1 do
    if g2[y][x] ~= 0 then img:drawPixel(x, y, g2[y][x]) end
  end end
  return img
end

local hands = {}
local legsInfo = {}
local fillCounts = {}
local shifts = {}

app.transaction(function()
  while #spr.frames < #FRAMES do spr:newFrame(#spr.frames) end
  layers["arm_far"].stackIndex = 1
  local fillLayer = spr:newLayer()
  fillLayer.name = "fill"
  fillLayer.stackIndex = layers["head_torso"].stackIndex
  layers["fill"] = fillLayer

  for fi, frame in ipairs(FRAMES) do
    spr.frames[fi].duration = frame.ms / 1000
    -- feet on the same ground line in every grounded frame: shift the whole frame by an integer
    local shift = 0
    if frame.ground then shift = GROUND_ROW - lowest_row(composite(parts_for(frame, 0))) end
    shifts[fi] = shift
    local parts = parts_for(frame, shift)
    for _, name in ipairs(ORDER) do
      local cel = layers[name]:cel(fi)
      cel.image = to_image(parts[name])
      cel.position = Point(0, 0)
    end
    local comp = composite(parts)
    local filled, n = fill_holes(comp, shift)
    fillCounts[fi] = n
    spr:newCel(fillLayer, fi, to_image(filled), Point(0, 0))

    local lean = frame.torso[2]
    local hx = C.HAND.x + frame.an[1] + math.floor(lean / 2)
    if mirror then hx = S - 1 - hx end
    hands[fi] = { hx, C.HAND.y + frame.an[2] + shift }

    local info = { tag = frame.tag }
    for _, nm in ipairs({ "far", "near" }) do
      local g = parts["leg_" .. nm]
      local lo, hi = extent_x(g)
      if mirror then lo, hi = S - 1 - hi, S - 1 - lo end
      info[nm] = { lowest_row(g), lo, hi }
    end
    legsInfo[fi] = info
  end

  -- tags
  local first, last, order = {}, {}, {}
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

-- per frame foot info for the gait check: lowest row and x extent of each leg layer
local lf = assert(io.open(app.params["legs"], "w"))
lf:write("[\n")
for i, l in ipairs(legsInfo) do
  lf:write(string.format('  {"tag": "%s", "far": [%d, %d, %d], "near": [%d, %d, %d]}%s\n', l.tag,
    l.far[1], l.far[2], l.far[3], l.near[1], l.near[2], l.near[3], i < #legsInfo and "," or ""))
end
lf:write("]\n")
lf:close()

local fc, sh = {}, {}
for i, n in ipairs(fillCounts) do fc[#fc + 1] = tostring(n); sh[#sh + 1] = tostring(shifts[i]) end
print("rigged " .. app.params["out"] .. " frames=" .. #FRAMES .. " fill px per frame: " .. table.concat(fc, ",")
  .. " ground shift per frame: " .. table.concat(sh, ","))

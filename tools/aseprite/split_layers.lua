-- Splits the flat hand-drawn sprite into named layers by pixel region.
-- Never edits the source: the result is saved under a new name.
-- params: root (repo root), src (.aseprite), out (.aseprite to write), mirror (true for *_left art)
local C = dofile(app.params["root"] .. "/tools/aseprite/common.lua")
local src, out = app.params["src"], app.params["out"]
local mirror = app.params["mirror"] == "true"

local spr = Sprite{ fromFile = src }
assert(spr.width == C.SIZE and spr.height == C.SIZE, "source must be 96x96")
assert(#spr.layers == 1 and #spr.frames == 1, "source must be one flat layer, one frame")
local flat = C.read_cel(spr.layers[1].cels[1], C.SIZE, C.SIZE)

app.transaction(function()
  local imgs = {}
  for _, name in ipairs(C.LAYER_ORDER) do
    imgs[name] = Image(C.SIZE, C.SIZE, spr.colorMode)
  end
  for y = 0, C.SIZE - 1 do
    for x = 0, C.SIZE - 1 do
      local v = flat[y][x]
      if v ~= 0 then imgs[C.region(x, y, mirror)]:drawPixel(x, y, v) end
    end
  end
  spr:deleteLayer(spr.layers[1])
  for _, name in ipairs(C.LAYER_ORDER) do
    local layer = spr:newLayer()
    layer.name = name
    spr:newCel(layer, 1, imgs[name], Point(0, 0))
  end
end)

spr:saveAs(out)
print("split " .. src .. " -> " .. out)

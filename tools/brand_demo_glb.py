#!/usr/bin/env python3
"""Build the branding demo model: a black "YOUR LOGO" sticker on the chest and a "YOUR AD" board on the back.

    python3 tools/brand_demo_glb.py

Reads src/models/montari.glb and writes src/models/montari-branding.glb. It shows a client where their
artwork goes, so both surfaces are deliberately blank placeholders rather than our own mark.

The torso is a plain node in the hierarchy, not a skinned mesh, so geometry added to its mesh follows
every animation on its own. The chest already carries a "decal" material whose single image is the
printed wordmark, so that surface is a texture swap; the back board is four new vertices.
"""
import json
import pathlib
import struct

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "models" / "montari.glb"
OUT = ROOT / "src" / "models" / "montari-branding.glb"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# A real A3 sheet, 297 by 420 mm, mounted just behind the torso shell, which ends at x = -0.067 in the
# link's own frame. The torso is only 208 mm across, so an A3 board overhangs it, exactly as it would in life.
A3_W, A3_H = 0.297, 0.420
BOARD = {"x": -0.075, "half_width": A3_W / 2, "z_top": 0.29, "z_bottom": 0.29 - A3_H}


# ---------------------------------------------------------------- textures
def placeholder(size, text, pad, radius, tracking):
    """A black plate with centred white text, the artwork a client replaces."""
    w, h = size
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pad, pad, w - pad, h - pad), radius=radius, fill=(12, 12, 14, 255))
    # Letter spacing has to be drawn by hand, so measure the tracked string, then shrink it to fit the plate.
    inner = w - 2 * pad - h * 0.2
    size_px = int(h * 0.42)
    for _ in range(40):
        font = ImageFont.truetype(FONT, size_px)
        widths = [d.textlength(c, font=font) for c in text]
        total = sum(widths) + tracking * (len(text) - 1)
        if total <= inner or size_px <= 8:
            break
        size_px = int(size_px * 0.94)
    box = d.textbbox((0, 0), text, font=font)
    x, y = (w - total) / 2, (h - (box[3] - box[1])) / 2 - box[1]
    for c, cw in zip(text, widths):
        d.text((x, y), c, font=font, fill=(255, 255, 255, 235))
        x += cw + tracking
    return im


def png_bytes(im):
    from io import BytesIO
    buf = BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------- glb
def read_glb(path):
    d = path.read_bytes()
    magic, _, length = struct.unpack("<III", d[:12])
    if magic != 0x46546C67:
        raise SystemExit(f"{path} is not a .glb")
    off, chunks = 12, {}
    while off < length:
        clen, ctype = struct.unpack("<II", d[off:off + 8])
        chunks[ctype] = d[off + 8:off + 8 + clen]
        off += 8 + clen
    return json.loads(chunks[0x4E4F534A]), bytearray(chunks[0x004E4942])


def write_glb(path, gltf, binary):
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary += b"\x00" * (-len(binary) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    out = struct.pack("<III", 0x46546C67, 2, total)
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(binary), 0x004E4942) + bytes(binary)
    path.write_bytes(out)


gltf, binary = read_glb(SRC)

decal_mat = next(i for i, m in enumerate(gltf["materials"]) if m.get("name") == "decal")
mesh_i, prim = next((mi, p) for mi, mesh in enumerate(gltf["meshes"])
                    for p in mesh["primitives"] if p.get("material") == decal_mat)
chest_view = gltf["bufferViews"][gltf["images"][0]["bufferView"]]
chest_view_i = gltf["images"][0]["bufferView"]

chest_png = png_bytes(placeholder((2048, 422), "YOUR LOGO", pad=6, radius=40, tracking=26))
board_png = png_bytes(placeholder((1754, 2480), "YOUR AD", pad=10, radius=34, tracking=26))   # A3 at 150 dpi

# Repack every existing bufferView in place, substituting the chest texture, then append the new data.
order = sorted(range(len(gltf["bufferViews"])), key=lambda i: gltf["bufferViews"][i].get("byteOffset", 0))
packed, offsets = bytearray(), {}
for i in order:
    bv = gltf["bufferViews"][i]
    start = bv.get("byteOffset", 0)
    data = chest_png if i == chest_view_i else bytes(binary[start:start + bv["byteLength"]])
    packed += b"\x00" * (-len(packed) % 4)
    offsets[i] = (len(packed), len(data))
    packed += data
for i, (off, ln) in offsets.items():
    gltf["bufferViews"][i]["byteOffset"] = off
    gltf["bufferViews"][i]["byteLength"] = ln


def add_view(data, target=None):
    global packed
    packed += b"\x00" * (-len(packed) % 4)
    bv = {"buffer": 0, "byteOffset": len(packed), "byteLength": len(data)}
    if target:
        bv["target"] = target
    gltf["bufferViews"].append(bv)
    packed += data
    return len(gltf["bufferViews"]) - 1


def add_accessor(view, component, count, type_, **extra):
    gltf["accessors"].append({"bufferView": view, "componentType": component, "count": count, "type": type_, **extra})
    return len(gltf["accessors"]) - 1


b = BOARD
# Seen from behind the robot the viewer's right is -Y, so u grows towards -Y and v downwards.
positions = [(b["x"], b["half_width"], b["z_top"]), (b["x"], -b["half_width"], b["z_top"]),
             (b["x"], -b["half_width"], b["z_bottom"]), (b["x"], b["half_width"], b["z_bottom"])]
normals = [(-1.0, 0.0, 0.0)] * 4
uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
indices = [0, 2, 1, 0, 3, 2]          # counter-clockwise seen from -X, so the front face points outwards

pos_a = add_accessor(add_view(struct.pack(f"<{len(positions) * 3}f", *[v for p in positions for v in p]), 34962),
                     5126, 4, "VEC3",
                     min=[min(p[i] for p in positions) for i in range(3)],
                     max=[max(p[i] for p in positions) for i in range(3)])
nrm_a = add_accessor(add_view(struct.pack(f"<{len(normals) * 3}f", *[v for n in normals for v in n]), 34962), 5126, 4, "VEC3")
uv_a = add_accessor(add_view(struct.pack(f"<{len(uvs) * 2}f", *[v for u in uvs for v in u]), 34962), 5126, 4, "VEC2")
idx_a = add_accessor(add_view(struct.pack(f"<{len(indices)}H", *indices), 34963), 5123, len(indices), "SCALAR")

gltf["images"].append({"name": "adboard", "mimeType": "image/png", "bufferView": add_view(board_png)})
gltf["textures"].append({"sampler": 0, "source": len(gltf["images"]) - 1})
gltf["materials"].append({
    "name": "board",
    "pbrMetallicRoughness": {"baseColorTexture": {"index": len(gltf["textures"]) - 1},
                             "metallicFactor": 0.0, "roughnessFactor": 0.75},
    "doubleSided": True,
})
gltf["meshes"][mesh_i]["primitives"].append({
    "attributes": {"POSITION": pos_a, "NORMAL": nrm_a, "TEXCOORD_0": uv_a},
    "indices": idx_a,
    "material": len(gltf["materials"]) - 1,
})

gltf["buffers"][0]["byteLength"] = len(packed)
gltf.setdefault("asset", {})["generator"] = "robotmonaco brand_demo_glb"
write_glb(OUT, gltf, packed)
print(f"{OUT.name}: chest sticker + back board on mesh {mesh_i} ({OUT.stat().st_size} bytes)")

#!/usr/bin/env python3
"""Build the branding demo: two robots side by side, one showing its chest plate, one its back board.

    python3 tools/brand_demo_glb.py

Reads src/models/montari.glb and writes src/models/montari-branding.glb.

What changes against the source model:

* The chest. The source carries its wordmark on a strip 13 by 2.7 cm, too small to read from across a
  room. That strip is removed and replaced by a plate 17 cm wide that follows the curve of the chest
  shell, sampled from the shell itself, so it sits on the robot like a printed patch instead of
  floating off it as a flat card would. 17 cm is as wide as the chest faces forward: past about 8.5 cm
  either side of centre the shell turns away into the shoulders.
* The back. A real A3 board, 297 by 420 mm, mounted behind the torso.
* A second robot. It is a copy of the node tree turned half a turn, so the camera sees the chest of one
  and the board of the other at once. The copy shares every mesh with the first, so it costs a few
  hundred bytes of JSON, not another four megabytes.
* No animation. This is a still for reading artwork, and a walking robot's board is unreadable; the
  clips are dropped, which also makes the file smaller.

The torso is a plain node in the hierarchy, not a skinned mesh, so geometry added to its mesh moves
with it and both copies of the robot carry both plates.
"""
import io
import json
import math
import pathlib
import struct

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "models" / "montari.glb"
OUT = ROOT / "src" / "models" / "montari-branding.glb"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Coordinates below are in the torso link's own frame: x forward, y to the robot's left, z up.
CHEST = {"half_width": 0.085, "z_bottom": 0.130, "z_top": 0.228, "lift": 0.0018, "grid": (32, 18)}
A3_W, A3_H = 0.297, 0.420
BOARD = {"x": -0.075, "half_width": A3_W / 2, "z_top": 0.29, "z_bottom": 0.29 - A3_H}
SPACING = 0.42          # metres from the centre of the pair to each robot


# ---------------------------------------------------------------- artwork
def _fit_font(draw, text, max_w, max_h, tracking):
    size = int(max_h)
    while size > 8:
        font = ImageFont.truetype(FONT, size)
        widths = [draw.textlength(c, font=font) for c in text]
        total = sum(widths) + tracking * (len(text) - 1)
        box = draw.textbbox((0, 0), text, font=font)
        if total <= max_w and box[3] - box[1] <= max_h:
            return font, widths, total
        size = int(size * 0.95)
    return font, widths, total


def plate(size, lines, pad, radius, tracking, fill=(12, 12, 14, 255)):
    """A black plate with one or more lines of white text, set as large as the plate allows."""
    w, h = size
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pad, pad, w - pad, h - pad), radius=radius, fill=fill)
    inner_w, inner_h = w - 2 * pad - h * 0.16, h - 2 * pad - h * 0.2
    line_h = inner_h / len(lines) * 0.82
    fitted = [_fit_font(d, t, inner_w, line_h, tracking) for t in lines]
    size_px = min(f.size for f, _, _ in fitted)          # one type size for every line
    font = ImageFont.truetype(FONT, size_px)
    gap = size_px * 0.28
    heights = [d.textbbox((0, 0), t, font=font) for t in lines]
    block = sum(b[3] - b[1] for b in heights) + gap * (len(lines) - 1)
    y = (h - block) / 2
    for t, b in zip(lines, heights):
        widths = [d.textlength(c, font=font) for c in t]
        x = (w - (sum(widths) + tracking * (len(t) - 1))) / 2
        for c, cw in zip(t, widths):
            d.text((x, y - b[1]), c, font=font, fill=(255, 255, 255, 240))
            x += cw + tracking
        y += (b[3] - b[1]) + gap
    return im


def logo_plate(size, logo_path, pad, radius, width_share, caption=None, fill=(12, 12, 14, 255)):
    """A black plate carrying a real logo, scaled to the plate, optionally with a line of text below."""
    w, h = size
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((pad, pad, w - pad, h - pad), radius=radius, fill=fill)
    logo = Image.open(logo_path).convert("RGBA")
    logo = logo.crop(logo.getbbox())
    lw = int((w - 2 * pad) * width_share)
    logo = logo.resize((lw, round(logo.height * lw / logo.width)), Image.LANCZOS)
    cap_h = 0
    if caption:
        font, widths, total = _fit_font(d, caption, lw * 0.62, logo.height * 0.42, 6)
        cb = d.textbbox((0, 0), caption, font=font)
        cap_h = (cb[3] - cb[1]) + logo.height * 0.55
    y = int((h - logo.height - cap_h) / 2)
    im.alpha_composite(logo, ((w - logo.width) // 2, y))
    if caption:
        x = (w - total) / 2
        cy = y + logo.height + logo.height * 0.55 - cb[1]
        for c, cw in zip(caption, widths):
            d.text((x, cy), c, font=font, fill=(255, 255, 255, 200))
            x += cw + 6
    return im


def png_bytes(im):
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ---------------------------------------------------------------- glb io
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
    return json.loads(chunks[0x4E4F534A]), bytes(chunks[0x004E4942])


def write_glb(path, gltf, binary):
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * (-len(js) % 4)
    binary = bytes(binary) + b"\x00" * (-len(binary) % 4)
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(binary))
    out += struct.pack("<II", len(js), 0x4E4F534A) + js
    out += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(out)


def accessor_vec3(gltf, binary, index):
    a = gltf["accessors"][index]
    bv = gltf["bufferViews"][a["bufferView"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 12)
    return [struct.unpack_from("<3f", binary, start + i * stride) for i in range(a["count"])]


def quat_mul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return [aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz]


# ---------------------------------------------------------------- chest geometry
def chest_art_size(chest, width_px=1600):
    """Pixel size for chest artwork with the plate's own proportions, so nothing is stretched."""
    w = 2 * chest["half_width"]
    return width_px, round(width_px * (chest["z_top"] - chest["z_bottom"]) / w)


def chest_surface(shell, c):
    """A grid over the chest that follows the shell, lifted a hair off it so it never z-fights."""
    nx, nz = c["grid"]
    front = [p for p in shell if p[0] > 0.04]              # only the front face, never the back of the shell
    ys = [-c["half_width"] + 2 * c["half_width"] * i / (nx - 1) for i in range(nx)]
    zs = [c["z_bottom"] + (c["z_top"] - c["z_bottom"]) * j / (nz - 1) for j in range(nz)]
    # The upper envelope of the shell: the highest point within a radius wider than the grid spacing, so
    # the shell cannot bulge up between two grid points and show through the plate.
    field = [[None] * nx for _ in range(nz)]
    for j, z in enumerate(zs):
        for i, y in enumerate(ys):
            for r in (0.012, 0.018, 0.026):
                near = [p[0] for p in front if abs(p[1] - y) < r and abs(p[2] - z) < r]
                if near:
                    field[j][i] = max(near)
                    break
    for row in field:
        known = [v for v in row if v is not None]
        fallback = max(known) if known else 0.084
        for i, v in enumerate(row):
            if v is None:
                row[i] = fallback
    # Smooth out seams and screw heads, but never below the envelope: smoothing alone pulls the plate
    # under the top of the chest's curve, and the shell then shows through it there.
    envelope = [row[:] for row in field]
    for _ in range(2):
        field = [[sum(field[jj][ii] for jj in range(max(0, j - 1), min(nz, j + 2))
                      for ii in range(max(0, i - 1), min(nx, i + 2)))
                  / (len(range(max(0, j - 1), min(nz, j + 2))) * len(range(max(0, i - 1), min(nx, i + 2))))
                  for i in range(nx)] for j in range(nz)]
        field = [[max(field[j][i], envelope[j][i]) for i in range(nx)] for j in range(nz)]
    positions, uvs = [], []
    for j, z in enumerate(zs):
        for i, y in enumerate(ys):
            positions.append((field[j][i] + c["lift"], y, z))
            # Seen from the front the robot's left (+y) is the viewer's right, and v runs downwards.
            uvs.append(((y + c["half_width"]) / (2 * c["half_width"]),
                        (c["z_top"] - z) / (c["z_top"] - c["z_bottom"])))
    normals = []
    for j in range(nz):
        for i in range(nx):
            p = lambda jj, ii: positions[min(nz - 1, max(0, jj)) * nx + min(nx - 1, max(0, ii))]
            dy = [a - b for a, b in zip(p(j, i + 1), p(j, i - 1))]
            dz = [a - b for a, b in zip(p(j + 1, i), p(j - 1, i))]
            n = [dy[1] * dz[2] - dy[2] * dz[1], dy[2] * dz[0] - dy[0] * dz[2], dy[0] * dz[1] - dy[1] * dz[0]]
            if n[0] < 0:
                n = [-v for v in n]
            length = math.sqrt(sum(v * v for v in n)) or 1
            normals.append(tuple(v / length for v in n))
    indices = []
    for j in range(nz - 1):
        for i in range(nx - 1):
            a, b = j * nx + i, j * nx + i + 1
            cc, dd = (j + 1) * nx + i + 1, (j + 1) * nx + i
            indices += [a, b, cc, a, cc, dd]              # counter-clockwise seen from +x, the outside
    return positions, normals, uvs, indices


# ---------------------------------------------------------------- build
def build(chest_art, back_art, out=OUT, src=SRC, chest=None):
    chest = {**CHEST, **(chest or {})}
    gltf, binary = read_glb(src)
    gltf.pop("animations", None)                      # a still: the clips only cost bytes here

    decal_mat = next(i for i, m in enumerate(gltf["materials"]) if m.get("name") == "decal")
    mesh_i = next(mi for mi, mesh in enumerate(gltf["meshes"])
                  for p in mesh["primitives"] if p.get("material") == decal_mat)
    mesh = gltf["meshes"][mesh_i]
    shell_mat = next(i for i, m in enumerate(gltf["materials"]) if m.get("name") == "shell")
    shell = accessor_vec3(gltf, binary, next(p for p in mesh["primitives"] if p.get("material") == shell_mat)["attributes"]["POSITION"])
    mesh["primitives"] = [p for p in mesh["primitives"] if p.get("material") != decal_mat]   # the old strip goes

    chest_view = gltf["images"][gltf["textures"][gltf["materials"][decal_mat]["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]]["bufferView"]

    # Drop the accessors nothing points at any more: the animation keyframes and the old strip.
    live = set()
    for m in gltf["meshes"]:
        for p in m["primitives"]:
            live.update(p["attributes"].values())
            if "indices" in p:
                live.add(p["indices"])
            for t in p.get("targets", []):
                live.update(t.values())
    acc_remap = {old: new for new, old in enumerate(sorted(live))}
    gltf["accessors"] = [gltf["accessors"][old] for old in sorted(live)]
    for m in gltf["meshes"]:
        for p in m["primitives"]:
            p["attributes"] = {k: acc_remap[v] for k, v in p["attributes"].items()}
            if "indices" in p:
                p["indices"] = acc_remap[p["indices"]]
            if "targets" in p:
                p["targets"] = [{k: acc_remap[v] for k, v in t.items()} for t in p["targets"]]

    # Repack only the buffer views still referenced, swapping the chest image, then append the new data.
    used = set()
    for a in gltf["accessors"]:
        if "bufferView" in a:
            used.add(a["bufferView"])
    for im in gltf["images"]:
        used.add(im["bufferView"])
    packed, remap = bytearray(), {}
    old_views = gltf["bufferViews"]
    new_views = []
    for i in sorted(used, key=lambda k: old_views[k].get("byteOffset", 0)):
        bv = dict(old_views[i])
        start = bv.get("byteOffset", 0)
        data = png_bytes(chest_art) if i == chest_view else binary[start:start + bv["byteLength"]]
        packed += b"\x00" * (-len(packed) % 4)
        bv["byteOffset"], bv["byteLength"] = len(packed), len(data)
        packed += data
        remap[i] = len(new_views)
        new_views.append(bv)
    gltf["bufferViews"] = new_views
    for a in gltf["accessors"]:
        if "bufferView" in a:
            a["bufferView"] = remap[a["bufferView"]]
    for im in gltf["images"]:
        im["bufferView"] = remap[im["bufferView"]]

    def add_view(data, target=None):
        nonlocal packed
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

    def add_primitive(positions, normals, uvs, indices, material):
        pos = add_accessor(add_view(struct.pack(f"<{len(positions) * 3}f", *[v for p in positions for v in p]), 34962),
                           5126, len(positions), "VEC3",
                           min=[min(p[k] for p in positions) for k in range(3)],
                           max=[max(p[k] for p in positions) for k in range(3)])
        nrm = add_accessor(add_view(struct.pack(f"<{len(normals) * 3}f", *[v for n in normals for v in n]), 34962), 5126, len(normals), "VEC3")
        uv = add_accessor(add_view(struct.pack(f"<{len(uvs) * 2}f", *[v for u in uvs for v in u]), 34962), 5126, len(uvs), "VEC2")
        idx = add_accessor(add_view(struct.pack(f"<{len(indices)}H", *indices), 34963), 5123, len(indices), "SCALAR")
        mesh["primitives"].append({"attributes": {"POSITION": pos, "NORMAL": nrm, "TEXCOORD_0": uv},
                                   "indices": idx, "material": material})

    # chest: the decal material, which already points at the image we just swapped
    add_primitive(*chest_surface(shell, chest), decal_mat)

    # back: a flat A3 board. The print faces outwards only; the side against the robot is plain black,
    # because a double-sided print shows its artwork mirrored past the edges of the torso from the front.
    b = BOARD
    corners = lambda x: [(x, b["half_width"], b["z_top"]), (x, -b["half_width"], b["z_top"]),
                         (x, -b["half_width"], b["z_bottom"]), (x, b["half_width"], b["z_bottom"])]
    quad_uv = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    # Seen from behind the robot the viewer's right is -y, so u grows towards -y and v downwards.
    add_primitive(corners(b["x"]), [(-1.0, 0.0, 0.0)] * 4, quad_uv,
                  [0, 2, 1, 0, 3, 2],                 # counter-clockwise seen from -x, the outside
                  _board_material(gltf, add_view(png_bytes(back_art))))
    add_primitive(corners(b["x"] + 0.003), [(1.0, 0.0, 0.0)] * 4, quad_uv,
                  [0, 1, 2, 0, 2, 3],                 # counter-clockwise seen from +x, towards the robot
                  _backing_material(gltf))

    # the second robot: a copy of the node tree, sharing every mesh, turned half a turn
    first = gltf["scenes"][gltf.get("scene", 0)]["nodes"][0]
    copy_of = {}

    def clone(n):
        node = json.loads(json.dumps(gltf["nodes"][n]))
        gltf["nodes"].append(node)
        copy_of[n] = len(gltf["nodes"]) - 1
        node["children"] = [clone(c) for c in gltf["nodes"][n].get("children", [])]
        if not node["children"]:
            node.pop("children")
        return copy_of[n]

    second = clone(first)
    base_t = gltf["nodes"][first].get("translation", [0, 0, 0])
    base_r = gltf["nodes"][first].get("rotation", [0, 0, 0, 1])
    gltf["nodes"][first]["name"] = "robot_front"
    gltf["nodes"][first]["translation"] = [-SPACING, base_t[1], base_t[2]]
    gltf["nodes"][second]["name"] = "robot_back"
    gltf["nodes"][second]["translation"] = [SPACING, base_t[1], base_t[2]]
    gltf["nodes"][second]["rotation"] = quat_mul([0.0, 1.0, 0.0, 0.0], base_r)   # half a turn about glTF up
    gltf["scenes"][gltf.get("scene", 0)]["nodes"] = [first, second]

    gltf["buffers"] = [{"byteLength": len(packed)}]
    gltf.setdefault("asset", {})["generator"] = "brand_demo_glb"
    write_glb(out, gltf, packed)
    print(f"{out.name}: two robots, chest plate {2 * chest['half_width'] * 100:.0f} x "
          f"{(chest['z_top'] - chest['z_bottom']) * 100:.1f} cm, A3 board, {out.stat().st_size / 1e6:.2f} MB")


def _board_material(gltf, image_view):
    gltf["images"].append({"name": "adboard", "mimeType": "image/png", "bufferView": image_view})
    gltf["textures"].append({"sampler": 0, "source": len(gltf["images"]) - 1})
    gltf["materials"].append({
        "name": "board",
        "pbrMetallicRoughness": {"baseColorTexture": {"index": len(gltf["textures"]) - 1},
                                 "metallicFactor": 0.0, "roughnessFactor": 0.75},
    })
    return len(gltf["materials"]) - 1


def _backing_material(gltf):
    gltf["materials"].append({
        "name": "board_back",
        "pbrMetallicRoughness": {"baseColorFactor": [0.03, 0.03, 0.035, 1.0], "metallicFactor": 0.0, "roughnessFactor": 0.8},
    })
    return len(gltf["materials"]) - 1


if __name__ == "__main__":
    # Placeholders, not our own mark: the demo shows a client where their artwork goes.
    build(chest_art=plate(chest_art_size(CHEST), ["YOUR", "LOGO"], pad=8, radius=70, tracking=30),
          back_art=plate((1754, 2480), ["YOUR", "AD"], pad=10, radius=34, tracking=40))   # A3 at 150 dpi

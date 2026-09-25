#!/usr/bin/env python3
"""Replace the chest wordmark texture inside a .glb with our own.

    python3 tools/brand_glb.py src/models/montari.glb src/img/logo-chest.png

The model already carries a "decal" material whose only image is the wordmark printed on the torso, so
branding it is a texture swap: the geometry, UVs, animation and every other buffer stay untouched. The
binary chunk is repacked because the new PNG rarely has the old one's byte length.
"""
import json
import struct
import sys
import pathlib

GLB, PNG = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
IMAGE_NAME = "wordmark"


def read_glb(path):
    d = path.read_bytes()
    magic, version, length = struct.unpack("<III", d[:12])
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


gltf, binary = read_glb(GLB)
images = gltf.get("images", [])
idx = next((i for i, im in enumerate(images) if im.get("name") == IMAGE_NAME), 0 if images else None)
if idx is None:
    raise SystemExit("this model carries no image to brand")
target_view = images[idx]["bufferView"]
new_png = PNG.read_bytes()

# Repack every bufferView in its current order, substituting the texture, so no stale offset survives.
views = sorted(range(len(gltf["bufferViews"])), key=lambda i: gltf["bufferViews"][i].get("byteOffset", 0))
packed, offsets = bytearray(), {}
for i in views:
    bv = gltf["bufferViews"][i]
    start = bv.get("byteOffset", 0)
    data = new_png if i == target_view else bytes(binary[start:start + bv["byteLength"]])
    packed += b"\x00" * (-len(packed) % 4)          # accessors require 4-byte alignment
    offsets[i] = (len(packed), len(data))
    packed += data
for i, (off, ln) in offsets.items():
    gltf["bufferViews"][i]["byteOffset"] = off
    gltf["bufferViews"][i]["byteLength"] = ln
gltf["buffers"][0]["byteLength"] = len(packed)
gltf.setdefault("asset", {})["generator"] = "robotmonaco brand_glb"

write_glb(GLB, gltf, packed)
print(f"{GLB.name}: wordmark replaced with {PNG.name} ({len(new_png)} bytes), model now {GLB.stat().st_size} bytes")

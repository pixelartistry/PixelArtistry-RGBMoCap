"""Fix a Mixamo character for RGB MoCap (runs inside Blender, started by Fix_Mixamo_Character.bat).

Mixamo often embeds only some of a character's textures and leaves the rest as links to a
folder that only existed on Mixamo's server. RGB MoCap packs every texture on import and stops
with "Unable to pack file ... .fbm not found". This script:
  1. imports the Mixamo FBX (the rigged one you downloaded),
  2. if you also give it the file you uploaded to Mixamo, copies its materials and textures over
     (matched by material name), otherwise it drops the texture links that point nowhere,
  3. packs every texture into the file and saves <name>_fixed.fbx next to the Mixamo file.
The rig, the skinning and the mesh are not changed.

Usage: blender -b --python fix_mixamo_character.py -- <file> [<file>]
The rigged Mixamo FBX and the original upload may be given in any order.
"""
import os
import sys

import bpy


def load(path):
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise SystemExit(f"FIX: cannot read {os.path.basename(path)} - use FBX, GLB or OBJ.")
    return [o for o in bpy.data.objects if o not in before]


def image_ok(im):
    if im.packed_file:
        return True
    path = bpy.path.abspath(im.filepath) if im.filepath else ""
    return bool(path) and os.path.isfile(path)


def main(files):
    if not 1 <= len(files) <= 2:
        raise SystemExit("FIX: drop the rigged Mixamo FBX (and optionally the file you uploaded) onto the .bat.")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    loaded = []
    for f in files:
        objs = load(f)
        role = "MIX" if any(o.type == "ARMATURE" for o in objs) else "SRC"
        # Tag the materials right away, so the next file keeps its own names
        # (Blender would otherwise rename clashing materials to .001, .005 ...).
        for o in objs:
            if o.type == "MESH":
                for m in o.data.materials:
                    if m and not m.name.startswith(("MIX|", "SRC|")):
                        m.name = role + "|" + m.name
        loaded.append((f, objs, role))
    rigged = [(f, objs) for f, objs, role in loaded if role == "MIX"]
    if len(rigged) != 1:
        raise SystemExit("FIX: expected exactly one rigged file (the one downloaded from Mixamo).")
    mix_file, mix_objs = rigged[0]
    original = [objs for f, objs, role in loaded if role == "SRC"]
    mix_meshes = [o for o in mix_objs if o.type == "MESH"]

    if original:
        donors = {}
        for o in original[0]:
            if o.type == "MESH":
                for m in o.data.materials:
                    if m:
                        donors.setdefault(m.name[4:], m)
        biggest = max((o for o in original[0] if o.type == "MESH"), key=lambda o: len(o.data.polygons), default=None)
        for o in mix_meshes:
            for slot in o.material_slots:
                key = slot.material.name[4:] if slot.material else ""
                donor = donors.get(key)
                if donor is None and len(donors) == 1:
                    donor = next(iter(donors.values()))
                if donor is None and biggest is not None and len(o.material_slots) == 1 and biggest.data.materials:
                    donor = biggest.data.materials[0]
                if donor is not None:
                    print(f"FIX: {o.name}: material {key or '(none)'} <- textures from the original upload")
                    slot.material = donor
        for o in original[0]:
            bpy.data.objects.remove(o, do_unlink=True)

    # Drop texture links that still point nowhere, then pack everything into the file.
    for mat in bpy.data.materials:
        if not mat.use_nodes or mat.users == 0:  # replaced above, about to be purged
            continue
        for node in list(mat.node_tree.nodes):
            if node.type == "TEX_IMAGE" and node.image and not image_ok(node.image):
                print(f"FIX: removed a texture link that points nowhere ({mat.name})")
                mat.node_tree.nodes.remove(node)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    for im in bpy.data.images:
        if not im.packed_file and image_ok(im):
            im.pack()
    for m in bpy.data.materials:  # remove the tags again
        if m.name.startswith(("MIX|", "SRC|")):
            m.name = m.name[4:]
    used = [im for im in bpy.data.images if im.users and im.type == "IMAGE"]
    print(f"FIX: {len(used)} texture(s) embedded: " + ", ".join(f"{im.name} {im.size[0]}x{im.size[1]}" for im in used))

    out = os.path.splitext(mix_file)[0] + "_fixed.fbx"
    bpy.ops.object.select_all(action="DESELECT")
    for o in bpy.data.objects:
        if o.type in ("ARMATURE", "MESH"):
            o.select_set(True)
    bpy.ops.export_scene.fbx(filepath=out, use_selection=True, object_types={"ARMATURE", "MESH"},
                             add_leaf_bones=False, bake_anim=False, path_mode="COPY",
                             embed_textures=True, mesh_smooth_type="FACE")
    print("FIX_OUTPUT=" + out)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])

"""Fetch the two blank rigs and hairstyles used in this specific Blender scene."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent.parent
ASSETS = HERE / "assets"
REV = "5821923af517ac5fdc82505faa92a0d575fc1b1a"
ROOT_URL = "https://raw.githubusercontent.com/NafisRayan/Animate-Rigged-Humanoid-No-Blender/" + REV + "/"
PACK = "Universal Base Characters[Standard]/Universal Base Characters[Standard]/"
BODY = "Base Characters/Godot - UE/"
HAIR = "Hairstyles/Rigged to Head Bone/glTF (Godot -Unreal)/"
LOG = {}

def fetch(rel):
    url = ROOT_URL + quote(PACK + rel)
    with urlopen(Request(url, headers={"User-Agent":"Snow-Direct sculpt and rig study"}), timeout=40) as response:
        data = response.read()
    LOG[rel] = {"url":url, "sha256":hashlib.sha256(data).hexdigest()}
    return data

def pack_glb(entry):
    label, subdir, stem = entry
    doc = json.loads(fetch(subdir + stem + ".gltf"))
    data = bytearray(fetch(subdir + doc["buffers"][0]["uri"]))
    old_images, old_textures = doc.get("images", []), doc.get("textures", [])
    imgs, textures = [], []
    for mat in doc["materials"]:
        pbr = mat.get("pbrMetallicRoughness", {})
        idx = pbr.get("baseColorTexture", {}).get("index")
        output = {"metallicFactor":0, "roughnessFactor":.78}
        if idx is not None:
            im = old_images[old_textures[idx]["source"]]
            name = im["uri"]
            raw = fetch(subdir+name)
            data.extend(bytes((-len(data))%4))
            offset = len(data)
            data.extend(raw)
            vi = len(doc["bufferViews"])
            doc["bufferViews"].append({"buffer":0, "byteOffset":offset, "byteLength":len(raw)})
            output["baseColorTexture"] = {"index":len(textures)}
            textures.append({"source":len(imgs)})
            imgs.append({"mimeType":"image/png", "bufferView":vi, "name":im.get("name",name)})
        mat["pbrMetallicRoughness"] = output
        for key in ("normalTexture", "occlusionTexture", "emissiveTexture", "extensions"):
            mat.pop(key, None)
    doc.update(images=imgs, textures=textures, buffers=[{"byteLength":len(data)}])
    for key in ("extensionsUsed","extensionsRequired","animations"):
        doc.pop(key,None)
    encoded = json.dumps(doc,separators=(",",":")).encode()
    encoded += b" " * ((-len(encoded))%4)
    data.extend(bytes((-len(data))%4))
    glb = struct.pack("<4sII",b"glTF",2,28+len(encoded)+len(data))
    glb += struct.pack("<I4s",len(encoded),b"JSON")+encoded+struct.pack("<I4s",len(data),b"BIN\0")+data
    (ASSETS/(label+".glb")).write_bytes(glb)

def main():
    ASSETS.mkdir(parents=True,exist_ok=True)
    entries = [("Kate-body",BODY,"Superhero_Female_FullBody"),("James-body",BODY,"Superhero_Male_FullBody"),
               ("Kate-hair",HAIR,"Hair_Buns"),("James-hair",HAIR,"Hair_SimpleParted")]
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(pack_glb,entries))
    (ASSETS/"QUATERNIUS-LICENSE.txt").write_bytes(fetch("License_Standard.txt"))
    sound = HERE.parent/"TakeFive/output/openrouter/seedance-mini-480p-one-pass/sound/master.wav"
    script = HERE.parent/"TakeFive/examples/snow.txt"
    shutil.copyfile(sound,ASSETS/"radio-drama.wav")
    shutil.copyfile(script,HERE/"screenplay.txt")
    manifest = {"creator":"Quaternius", "creator_page":"https://quaternius.com/packs/universalbasecharacters.html",
                "upstream_revision":REV, "downloaded":dict(sorted(LOG.items())),
                "local_sources":{"radio-drama.wav":str(sound),"screenplay.txt":str(script)},
                "files":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ASSETS.iterdir()) if p.is_file() and p.name!="sources.json"}}
    (ASSETS/"sources.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf8")
    print("Prepared",len(entries),"rig assets and the audio track.")

if __name__=="__main__":
    main()

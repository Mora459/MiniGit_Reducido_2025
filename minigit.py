#!/usr/bin/env python3
"""
MiniGit (versión reducida)
Comandos: init, add <archivo>, commit <mensaje>, restore <id>
"""
import argparse
import os
import json
import hashlib
import shutil
from datetime import datetime
import uuid

MINIGIT_DIR = ".minigit"
COMMITS_DIR = os.path.join(MINIGIT_DIR, "commits")
OBJECTS_DIR = os.path.join(MINIGIT_DIR, "objects")
INDEX_FILE = os.path.join(MINIGIT_DIR, "index.json")


def ensure_repo():
    if not os.path.isdir(MINIGIT_DIR):
        raise SystemExit("No parece un repositorio MiniGit. Ejecuta 'minigit.py init' primero.")


def cmd_init(args):
    os.makedirs(COMMITS_DIR, exist_ok=True)
    os.makedirs(OBJECTS_DIR, exist_ok=True)
    if not os.path.exists(INDEX_FILE):
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump({"staged": []}, f, indent=2)
    print(f"Repositorio MiniGit inicializado en ./{MINIGIT_DIR}")


def read_index():
    if not os.path.exists(INDEX_FILE):
        return {"staged": []}
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def write_index(data):
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def hash_file_bytes(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def cmd_add(args):
    ensure_repo()
    path = args.file
    if not os.path.exists(path):
        raise SystemExit(f"Archivo no encontrado: {path}")
    rel_path = os.path.normpath(path)

    index = read_index()
    # avoid duplicates
    staged = [s for s in index.get("staged", []) if s["path"] != rel_path]

    # store hash metadata (no copy yet)
    sha = hash_file_bytes(rel_path)
    staged.append({"path": rel_path, "sha": sha})
    index["staged"] = staged
    write_index(index)
    print(f"Archivo añadido al área de preparación: {rel_path}")


def cmd_commit(args):
    ensure_repo()
    index = read_index()
    staged = index.get("staged", [])
    if not staged:
        print("Nada para commitear. El área de preparación está vacía.")
        return

    # commit id (puede usarse uuid o hash -> usamos uuid4 para simplicidad)
    commit_id = uuid.uuid4().hex[:12]
    timestamp = datetime.utcnow().isoformat() + "Z"

    files_metadata = []
    for entry in staged:
        path = entry["path"]
        if not os.path.exists(path):
            print(f"Advertencia: {path} ya no existe; se omitirá.")
            continue
        # generar nombre único para object: <sha>_<nombre>
        sha = hash_file_bytes(path)
        base_name = os.path.basename(path)
        object_name = f"{sha}_{base_name}"
        object_path = os.path.join(OBJECTS_DIR, object_name)
        # si el objeto ya existe (mismo contenido), no copiamos duplicado
        if not os.path.exists(object_path):
            shutil.copy2(path, object_path)
        files_metadata.append({
            "path": path,
            "object": object_name,
            "sha": sha
        })

    commit_obj = {
        "id": commit_id,
        "timestamp": timestamp,
        "message": args.message,
        "files": files_metadata
    }

    commit_file = os.path.join(COMMITS_DIR, f"{commit_id}.json")
    with open(commit_file, "w", encoding="utf-8") as f:
        json.dump(commit_obj, f, indent=2)

    # limpiar index
    write_index({"staged": []})
    print(f"Commit creado: {commit_id} con {len(files_metadata)} archivos.")


def cmd_restore(args):
    ensure_repo()
    commit_id = args.id
    commit_file = os.path.join(COMMITS_DIR, f"{commit_id}.json")
    if not os.path.exists(commit_file):
        raise SystemExit(f"No se encontró el commit con id {commit_id}")

    with open(commit_file, "r", encoding="utf-8") as f:
        commit_obj = json.load(f)

    restored = 0
    for fmeta in commit_obj.get("files", []):
        obj_name = fmeta["object"]
        object_path = os.path.join(OBJECTS_DIR, obj_name)
        target_path = fmeta["path"]
        if not os.path.exists(object_path):
            print(f"Objeto faltante: {obj_name} (no se puede restaurar {target_path})")
            continue
        # asegurar carpeta destino existe
        target_dir = os.path.dirname(target_path)
        if target_dir and not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(object_path, target_path)
        restored += 1

    print(f"Restaurados {restored} archivos desde el commit {commit_id}.")


def cmd_show_index(args):
    ensure_repo()
    index = read_index()
    print(json.dumps(index, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description="MiniGit reducido")
    sub = parser.add_subparsers(dest="cmd")

    p_init = sub.add_parser("init", help="Inicializa el repositorio mini")
    p_init.set_defaults(func=cmd_init)

    p_add = sub.add_parser("add", help="Agrega archivo al área de preparación")
    p_add.add_argument("file", help="ruta del archivo a añadir")
    p_add.set_defaults(func=cmd_add)

    p_commit = sub.add_parser("commit", help="Crea un commit con los archivos añadidos")
    p_commit.add_argument("message", help="mensaje del commit")
    p_commit.set_defaults(func=cmd_commit)

    p_restore = sub.add_parser("restore", help="Restaura archivos de un commit")
    p_restore.add_argument("id", help="id del commit (nombre del archivo json en commits/)")
    p_restore.set_defaults(func=cmd_restore)

    p_index = sub.add_parser("index", help="Muestra el índice (staging)")
    p_index.set_defaults(func=cmd_show_index)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)


if __name__ == "__main__":
    main()

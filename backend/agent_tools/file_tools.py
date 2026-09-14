"""
file_tools.py — File and Folder Management Tools for Kairos.

Provides cross-platform capabilities to:
1. Create folders on Desktop, Documents, Downloads, or specified custom paths.
2. Create files with optional text content.
3. Rename existing files or folders.
4. List contents of directories.
"""

import os
import shutil
from typing import Dict, Any, Optional

from config import platform_paths


def get_desktop_dir() -> str:
    user_home = os.path.expanduser("~")
    desktop_path = os.path.join(user_home, "Desktop")
    os.makedirs(desktop_path, exist_ok=True)
    return desktop_path


def resolve_path(raw_path: str, parent_dir: Optional[str] = None) -> str:
    """
    Resolves raw user input paths to absolute system paths.
    Supports shortcuts: 'desktop', 'documents', 'downloads', '~', relative names, etc.
    """
    user_home = os.path.expanduser("~")
    desktop_dir = get_desktop_dir()

    if not raw_path or not str(raw_path).strip():
        if parent_dir and str(parent_dir).strip():
            return resolve_path(str(parent_dir).strip())
        return desktop_dir

    raw = str(raw_path).strip().strip("\"'")
    raw_lower = raw.lower().replace("\\", "/")

    # Keyword locations
    if raw_lower in ("desktop", "on desktop", "in desktop"):
        return desktop_dir
    if raw_lower in ("documents", "my documents", "in documents"):
        return os.path.join(user_home, "Documents")
    if raw_lower in ("downloads", "in downloads"):
        return os.path.join(user_home, "Downloads")

    # Prefix checks
    if raw_lower.startswith("desktop/") or raw_lower.startswith("desktop\\"):
        sub = raw[8:].lstrip("/\\")
        return os.path.normpath(os.path.join(desktop_dir, sub))
    if raw_lower.startswith("documents/") or raw_lower.startswith("documents\\"):
        sub = raw[10:].lstrip("/\\")
        return os.path.normpath(os.path.join(user_home, "Documents", sub))
    if raw_lower.startswith("downloads/") or raw_lower.startswith("downloads\\"):
        sub = raw[10:].lstrip("/\\")
        return os.path.normpath(os.path.join(user_home, "Downloads", sub))

    # Tilde check
    if raw.startswith("~"):
        return os.path.normpath(os.path.expanduser(raw))

    # Absolute path
    if os.path.isabs(raw):
        return os.path.normpath(raw)

    # If parent_dir is specified
    if parent_dir and str(parent_dir).strip():
        p_res = resolve_path(str(parent_dir).strip())
        return os.path.normpath(os.path.join(p_res, raw))

    # Default relative paths to Desktop
    return os.path.normpath(os.path.join(desktop_dir, raw))


def create_folder(folder_name: str, parent_dir: Optional[str] = None) -> Dict[str, Any]:
    """Creates a new directory/folder at the specified location."""
    if not folder_name or not str(folder_name).strip():
        return {"success": False, "message": "Please specify a folder name or path."}

    target_path = resolve_path(folder_name, parent_dir)
    try:
        os.makedirs(target_path, exist_ok=True)
        folder_basename = os.path.basename(target_path) or target_path
        return {
            "success": True,
            "message": f"Successfully created folder '{folder_basename}' at '{target_path}'.",
            "path": target_path,
            "folder_name": folder_basename,
        }
    except Exception as e:
        return {"success": False, "message": f"Could not create folder at '{target_path}': {e}"}


def create_file(filename: str, content: str = "", parent_dir: Optional[str] = None) -> Dict[str, Any]:
    """Creates a new file with optional content at the specified location."""
    if not filename or not str(filename).strip():
        return {"success": False, "message": "Please specify a filename or path."}

    target_path = resolve_path(filename, parent_dir)
    try:
        parent_folder = os.path.dirname(target_path)
        if parent_folder:
            os.makedirs(parent_folder, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content or "")
        file_basename = os.path.basename(target_path)
        return {
            "success": True,
            "message": f"Successfully created file '{file_basename}' at '{target_path}'.",
            "path": target_path,
            "filename": file_basename,
        }
    except Exception as e:
        return {"success": False, "message": f"Could not create file at '{target_path}': {e}"}


def rename_file_or_folder(old_name: str, new_name: str, parent_dir: Optional[str] = None) -> Dict[str, Any]:
    """Renames or moves an existing file or folder to a new name/path."""
    if not old_name or not str(old_name).strip():
        return {"success": False, "message": "Please specify the current name or path of the file/folder."}
    if not new_name or not str(new_name).strip():
        return {"success": False, "message": "Please specify the new name or path."}

    old_path = resolve_path(old_name, parent_dir)
    new_path = resolve_path(new_name, parent_dir)

    if not os.path.exists(old_path):
        # Fallback check on Desktop if old_name was passed as bare name
        desktop_old = os.path.join(get_desktop_dir(), old_name)
        if os.path.exists(desktop_old):
            old_path = desktop_old
            new_path = os.path.join(get_desktop_dir(), new_name)
        else:
            return {"success": False, "message": f"Could not find file or folder at '{old_path}' to rename."}

    try:
        new_parent = os.path.dirname(new_path)
        if new_parent:
            os.makedirs(new_parent, exist_ok=True)
        shutil.move(old_path, new_path)
        old_base = os.path.basename(old_path) or old_path
        new_base = os.path.basename(new_path) or new_path
        return {
            "success": True,
            "message": f"Successfully renamed '{old_base}' to '{new_base}'.",
            "old_path": old_path,
            "new_path": new_path,
        }
    except Exception as e:
        return {"success": False, "message": f"Could not rename '{old_path}' to '{new_path}': {e}"}


def list_directory_contents(path: Optional[str] = None) -> Dict[str, Any]:
    """Lists files and folders inside a given directory."""
    target_path = resolve_path(path or "desktop")
    if not os.path.exists(target_path):
        return {"success": False, "message": f"Directory '{target_path}' does not exist."}
    try:
        entries = os.listdir(target_path)
        files = [e for e in entries if os.path.isfile(os.path.join(target_path, e))]
        folders = [e for e in entries if os.path.isdir(os.path.join(target_path, e))]
        return {
            "success": True,
            "path": target_path,
            "folders": folders[:25],
            "files": files[:50],
            "total": len(entries),
        }
    except Exception as e:
        return {"success": False, "message": f"Could not list directory '{target_path}': {e}"}

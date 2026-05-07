import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, List


BASE_WORKSPACE = Path("generated_code")


def ensure_workspace():
    BASE_WORKSPACE.mkdir(parents=True, exist_ok=True)


async def save_file(
    filename: str,
    content: str
) -> Dict[str, Any]:
    """
    Save content into a file.
    """

    try:
        ensure_workspace()

        filepath = BASE_WORKSPACE / filename

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "success",
            "message": f"File saved successfully",
            "filepath": str(filepath),
            "filename": filename,
            "size": len(content)
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def read_file(
    filename: str
) -> Dict[str, Any]:
    """
    Read file content.
    """

    try:
        filepath = BASE_WORKSPACE / filename

        if not filepath.exists():
            return {
                "status": "error",
                "message": f"File '{filename}' not found"
            }

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        return {
            "status": "success",
            "filename": filename,
            "content": content
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def append_file(
    filename: str,
    content: str
) -> Dict[str, Any]:
    """
    Append content to file.
    """

    try:
        ensure_workspace()

        filepath = BASE_WORKSPACE / filename

        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, "a", encoding="utf-8") as f:
            f.write(content)

        return {
            "status": "success",
            "message": "Content appended successfully",
            "filename": filename
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def delete_file(
    filename: str
) -> Dict[str, Any]:
    """
    Delete file.
    """

    try:
        filepath = BASE_WORKSPACE / filename

        if not filepath.exists():
            return {
                "status": "error",
                "message": "File not found"
            }

        filepath.unlink()

        return {
            "status": "success",
            "message": f"{filename} deleted successfully"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def list_files() -> Dict[str, Any]:
    """
    List all generated files.
    """

    try:
        ensure_workspace()

        files = []

        for path in BASE_WORKSPACE.rglob("*"):
            if path.is_file():
                files.append({
                    "filename": str(path.relative_to(BASE_WORKSPACE)),
                    "size": path.stat().st_size
                })

        return {
            "status": "success",
            "files": files,
            "total_files": len(files)
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def create_project(
    project_name: str
) -> Dict[str, Any]:
    """
    Create project directory structure.
    """

    try:
        ensure_workspace()

        project_path = BASE_WORKSPACE / project_name

        folders = [
            "src",
            "tests",
            "docs",
            "configs"
        ]

        for folder in folders:
            (project_path / folder).mkdir(
                parents=True,
                exist_ok=True
            )

        return {
            "status": "success",
            "project_path": str(project_path),
            "folders_created": folders
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def project_tree() -> Dict[str, Any]:
    """
    Return directory structure.
    """

    try:
        ensure_workspace()

        tree = []

        for path in BASE_WORKSPACE.rglob("*"):

            tree.append({
                "path": str(path.relative_to(BASE_WORKSPACE)),
                "type": "directory" if path.is_dir() else "file"
            })

        return {
            "status": "success",
            "tree": tree
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
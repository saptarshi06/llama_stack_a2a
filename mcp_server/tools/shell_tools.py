import subprocess
from pathlib import Path
from typing import Dict, Any


BASE_WORKSPACE = Path("generated_code")


async def run_python(
    filename: str
) -> Dict[str, Any]:
    """
    Execute python file.
    """

    try:
        filepath = BASE_WORKSPACE / filename

        if not filepath.exists():
            return {
                "status": "error",
                "message": f"{filename} not found"
            }

        result = subprocess.run(
            ["python", str(filepath)],
            capture_output=True,
            text=True,
            timeout=20
        )

        return {
            "status": "success",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "Execution timeout"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def run_command(
    command: str
) -> Dict[str, Any]:
    """
    Execute shell command.
    """

    SAFE_COMMANDS = [
        "dir",
        "ls",
        "pwd",
        "echo",
        "python --version",
        "pip list"
    ]

    try:

        allowed = any(
            command.startswith(cmd)
            for cmd in SAFE_COMMANDS
        )

        if not allowed:
            return {
                "status": "error",
                "message": "Command not allowed"
            }

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=BASE_WORKSPACE
        )

        return {
            "status": "success",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "Command timeout"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def install_package(
    package_name: str
) -> Dict[str, Any]:
    """
    Install python package.
    """

    try:

        result = subprocess.run(
            ["pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120
        )

        return {
            "status": "success",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "Installation timeout"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def run_pytest() -> Dict[str, Any]:
    """
    Run pytest inside generated_code workspace.
    """

    try:

        result = subprocess.run(
            ["pytest"],
            cwd=BASE_WORKSPACE,
            capture_output=True,
            text=True,
            timeout=60
        )

        return {
            "status": "success",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "Pytest timeout"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


async def lint_python_file(
    filename: str
) -> Dict[str, Any]:
    """
    Run flake8 linting on python file.
    """

    try:

        filepath = BASE_WORKSPACE / filename

        result = subprocess.run(
            ["flake8", str(filepath)],
            capture_output=True,
            text=True,
            timeout=30
        )

        return {
            "status": "success",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": "Lint timeout"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
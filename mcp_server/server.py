from mcp.server.fastmcp import FastMCP
import os
import subprocess

mcp = FastMCP("CodeAgentTools")


@mcp.tool()
async def save_code(filename: str, content: str):
    """
    Save generated code into a file.
    """

    os.makedirs("generated_code", exist_ok=True)
    filepath = os.path.join("generated_code", filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return {
        "status": "success",
        "filepath": filepath
    }

@mcp.tool()
async def read_file(filename: str):
    """
    Read file content.
    """

    filepath = os.path.join("generated_code", filename)
    if not os.path.exists(filepath):
        return {
            "status": "error",
            "message": "File not found"
        }
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    return {
        "status": "success",
        "content": content
    }


@mcp.tool()
async def list_files():
    """
    List generated files.
    """

    os.makedirs("generated_code", exist_ok=True)
    return {
        "files": os.listdir("generated_code")
    }

@mcp.tool()
async def run_python(filename: str):
    """
    Execute a python file.
    """

    filepath = os.path.join("generated_code", filename)
    try:
        result = subprocess.run(
            ["python", filepath],
            capture_output=True,
            text=True,
            timeout=15
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    mcp.run()
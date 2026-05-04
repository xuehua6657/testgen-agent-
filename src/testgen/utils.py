"""Utility functions for TestGen-Agent."""

import logging
import subprocess
import sys
from pathlib import Path

import colorama

colorama.init()

# Logging levels
LEVEL_COLORS = {
    logging.DEBUG: colorama.Fore.CYAN,
    logging.INFO: colorama.Fore.GREEN,
    logging.WARNING: colorama.Fore.YELLOW,
    logging.ERROR: colorama.Fore.RED,
    logging.CRITICAL: colorama.Fore.RED + colorama.Style.BRIGHT,
}

logger: logging.Logger | None = None


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure colored logging with appropriate level."""
    global logger
    if logger is not None:
        return logger

    logger = logging.getLogger("testgen")
    level = logging.DEBUG if verbose else logging.INFO
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    class ColoredFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            color = LEVEL_COLORS.get(record.levelno, "")
            reset = colorama.Style.RESET_ALL
            record.msg = f"{color}{record.msg}{reset}"
            return super().format(record)

    handler.setFormatter(ColoredFormatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the configured logger, setting up defaults if needed."""
    return setup_logging()


def extract_diff(repo_path: str | Path, ref: str = "HEAD") -> str:
    """Run git diff and return unified diff text.

    Args:
        repo_path: Path to git repository.
        ref: Git ref to diff against.

    Returns:
        Unified diff text, or empty string if no changes.
    """
    result = subprocess.run(
        ["git", "diff", ref, "--unified=3", "--stat"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git diff failed: {result.stderr.strip()}")
    return result.stdout


def extract_full_diff(repo_path: str | Path, ref: str = "HEAD") -> str:
    """Run git diff with full content (not just stat).

    Args:
        repo_path: Path to git repository.
        ref: Git ref to diff against.

    Returns:
        Full unified diff text.
    """
    result = subprocess.run(
        ["git", "diff", ref, "--unified=3"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git diff failed: {result.stderr.strip()}")
    return result.stdout


def detect_language(file_path: str) -> str:
    """Detect programming language from file extension.

    Args:
        file_path: Path to the file.

    Returns:
        Language identifier string.
    """
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
        ".cpp": "cpp",
        ".c": "c",
        ".cs": "csharp",
    }
    ext = Path(file_path).suffix.lower()
    return ext_map.get(ext, "unknown")


def find_test_file(
    source_path: str, test_dirs: list[str], base_dir: str | Path = "."
) -> str | None:
    """Find corresponding test file for a source file.

    Follows pytest conventions: test_<name>.py or <name>_test.py

    Args:
        source_path: Path to source file.
        test_dirs: List of directories to search for tests.
        base_dir: Base directory to resolve test_dirs against.

    Returns:
        Path to test file, or None if not found.
    """
    source = Path(source_path)
    name = source.stem
    base = Path(base_dir)

    for test_dir in test_dirs:
        # Try test_<name>.py
        test_file = base / test_dir / f"test_{name}.py"
        if test_file.exists():
            return str(test_file)

        # Try <name>_test.py
        test_file = base / test_dir / f"{name}_test.py"
        if test_file.exists():
            return str(test_file)

    return None


def read_file(path: str | Path) -> str:
    """Read file content safely.

    Args:
        path: Path to file.

    Returns:
        File content as string.
    """
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except UnicodeDecodeError:
        return ""


def safe_write_file(path: str | Path, content: str, append: bool = False) -> bool:
    """Write file with error handling and directory creation.

    Args:
        path: Path to write to.
        content: Content to write.
        append: If True, append to file instead of overwriting.

    Returns:
        True if successful, False otherwise.
    """
    try:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
        return True
    except OSError as e:
        get_logger().error(f"Failed to write file {path}: {e}")
        return False


def format_python_code(code: str) -> str:
    """Format Python code using ruff or black if available.

    Falls back to returning the code as-is if formatters are not installed.

    Args:
        code: Python code to format.

    Returns:
        Formatted code string.
    """
    # Try ruff first (faster)
    try:
        result = subprocess.run(
            ["ruff", "format", "-"],
            input=code,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try black
    try:
        result = subprocess.run(
            ["black", "-"],
            input=code,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return code


def extract_code_blocks(text: str, language: str = "python") -> list[str]:
    """Extract code blocks from markdown-formatted text.

    Handles ```python ... ``` and ``` ... ``` formats.

    Args:
        text: Markdown text containing code blocks.
        language: Language to filter for.

    Returns:
        List of extracted code strings.
    """
    import re

    # Try language-specific fence first
    pattern = rf"```{language}\s*\n(.*?)```"
    blocks = re.findall(pattern, text, re.DOTALL)

    if blocks:
        return [block.strip() for block in blocks]

    # Fall back to any fence
    pattern = r"```\s*\n(.*?)```"
    blocks = re.findall(pattern, text, re.DOTALL)

    if blocks:
        return [block.strip() for block in blocks]

    # If no fences found, return the whole text
    return [text.strip()] if text.strip() else []

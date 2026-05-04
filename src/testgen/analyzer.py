"""Code change analysis for TestGen-Agent."""

import re
from pathlib import Path

from testgen.config import TestGenConfig
from testgen.models import AnalysisResult, CodeChange
from testgen.utils import detect_language, get_logger, read_file


class CodeAnalyzer:
    """Analyzes git diffs to understand what changed and why."""

    # Patterns for function detection in various languages
    FUNCTION_PATTERNS = {
        "python": re.compile(
            r"^(?:\s*)(?:async\s+)?def\s+(\w+)\s*\(", re.MULTILINE
        ),
        "javascript": re.compile(
            r"(?:function\s+(\w+)|(\w+)\s*[:=]\s*(?:function|\([^)]*\)\s*=>))",
            re.MULTILINE,
        ),
        "go": re.compile(r"^func\s+(?:\([^)]+\)\s+)?(\w+)\s*\(", re.MULTILINE),
        "rust": re.compile(r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*[<(]", re.MULTILINE),
    }

    def __init__(self, config: TestGenConfig):
        self.config = config
        self.logger = get_logger()

    def parse_diff(self, diff_text: str) -> list[CodeChange]:
        """Parse unified diff text into CodeChange objects.

        Args:
            diff_text: Unified diff text from git diff.

        Returns:
            List of CodeChange objects, one per changed file.
        """
        if not diff_text.strip():
            return []

        changes = []
        current_file = None
        current_diff_lines: list[str] = []
        added_lines: list[int] = []
        removed_lines: list[int] = []

        for line in diff_text.split("\n"):
            # Detect file header: diff --git a/file b/file
            file_match = re.match(r"^diff --git a/(.+) b/(.+)$", line)
            if file_match:
                # Save previous file
                if current_file and current_diff_lines:
                    changes.append(self._build_change(
                        current_file,
                        "\n".join(current_diff_lines),
                        added_lines,
                        removed_lines,
                    ))

                current_file = file_match.group(2)
                current_diff_lines = [line]
                added_lines = []
                removed_lines = []
                continue

            if current_file is None:
                continue

            current_diff_lines.append(line)

            # Track line numbers (unified diff: +NNN)
            hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if hunk_match:
                current_line = int(hunk_match.group(1))
                continue

            # Track added/removed lines
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(current_line)
                current_line = current_line + 1 if 'current_line' in dir() else 0
            elif line.startswith("-") and not line.startswith("---"):
                removed_lines.append(current_line)
            elif not line.startswith("\\"):
                # Context line
                if 'current_line' in dir():
                    current_line = current_line + 1

        # Don't forget the last file
        if current_file and current_diff_lines:
            changes.append(self._build_change(
                current_file,
                "\n".join(current_diff_lines),
                added_lines,
                removed_lines,
            ))

        self.logger.info(f"Parsed {len(changes)} changed files from diff")
        return changes

    def _build_change(
        self,
        file_path: str,
        diff_text: str,
        added_lines: list[int],
        removed_lines: list[int],
    ) -> CodeChange:
        """Build a CodeChange from parsed diff data.

        Args:
            file_path: Path to the changed file.
            diff_text: Diff text for this file.
            added_lines: Line numbers that were added.
            removed_lines: Line numbers that were removed.

        Returns:
            CodeChange object.
        """
        language = detect_language(file_path)
        changed_functions = self._extract_changed_functions(diff_text, language)

        return CodeChange(
            file_path=file_path,
            diff_text=diff_text,
            added_lines=added_lines,
            removed_lines=removed_lines,
            changed_functions=changed_functions,
            language=language,
        )

    def _extract_changed_functions(self, diff_text: str, language: str) -> list[str]:
        """Extract function names from diff text.

        Args:
            diff_text: Diff text for a single file.
            language: Programming language.

        Returns:
            List of changed function names.
        """
        pattern = self.FUNCTION_PATTERNS.get(language)
        if not pattern:
            return []

        functions = set()
        for line in diff_text.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                match = pattern.search(line[1:])
                if match:
                    # Get the first non-None group
                    func_name = match.group(1) or match.group(2)
                    if func_name:
                        functions.add(func_name)

        return sorted(functions)

    def analyze_context(
        self, change: CodeChange, repo_path: str | Path
    ) -> dict:
        """Gather context around a code change.

        Args:
            change: The code change to analyze.
            repo_path: Path to git repository.

        Returns:
            Dictionary with source_code, existing_tests, imports, etc.
        """
        repo_path = Path(repo_path)
        source_path = repo_path / change.file_path
        source_code = read_file(source_path)

        # Find existing test file
        test_file = self._find_test_for_source(change.file_path, repo_path)
        existing_tests = read_file(test_file) if test_file else ""

        # Extract imports from source
        imports = self._extract_imports(source_code, change.language)

        return {
            "source_code": source_code,
            "existing_tests": existing_tests,
            "imports": imports,
        }

    def _find_test_for_source(self, source_path: str, repo_path: Path) -> str | None:
        """Find test file for a source file.

        Args:
            source_path: Relative path to source file.
            repo_path: Repository root path.

        Returns:
            Path to test file or None.
        """
        source = Path(source_path)
        name = source.stem

        for test_dir in self.config.test_dirs:
            for pattern in [f"test_{name}.py", f"{name}_test.py"]:
                test_file = repo_path / test_dir / source.parent / pattern
                if test_file.exists():
                    return str(test_file)

            # Also check flat test directory
            for pattern in [f"test_{name}.py", f"{name}_test.py"]:
                test_file = repo_path / test_dir / pattern
                if test_file.exists():
                    return str(test_file)

        return None

    def _extract_imports(self, source_code: str, language: str) -> list[str]:
        """Extract import statements from source code.

        Args:
            source_code: Full source code.
            language: Programming language.

        Returns:
            List of import statements.
        """
        if language == "python":
            pattern = re.compile(r"^(?:import\s+\S+|from\s+\S+\s+import\s+.+)$", re.MULTILINE)
        elif language in ("javascript", "typescript"):
            pattern = re.compile(r"^(?:import\s+.+|require\(.+\))$", re.MULTILINE)
        else:
            return []

        return pattern.findall(source_code)

    def assess_risk(self, changes: list[CodeChange]) -> str:
        """Assess change risk level based on scope and depth.

        Heuristics: number of files changed, lines changed vs total,
        whether core modules changed.

        Args:
            changes: List of code changes.

        Returns:
            Risk level: 'low', 'medium', or 'high'.
        """
        if not changes:
            return "low"

        num_files = len(changes)
        total_lines = sum(len(c.added_lines) + len(c.removed_lines) for c in changes)

        # High risk: many files or many lines
        if num_files > 10 or total_lines > 500:
            return "high"

        # Medium risk: moderate changes
        if num_files > 3 or total_lines > 100:
            return "medium"

        # Low risk: small, focused changes
        return "low"

    def run(self, diff_text: str, repo_path: str | Path) -> AnalysisResult:
        """Run full analysis pipeline.

        Args:
            diff_text: Unified diff text.
            repo_path: Path to git repository.

        Returns:
            AnalysisResult with all findings.
        """
        changes = self.parse_diff(diff_text)

        if not changes:
            return AnalysisResult(
                changes=[],
                summary="No code changes detected.",
                affected_modules=[],
                risk_level="low",
            )

        # Analyze context for each change
        affected_modules = []
        for change in changes:
            context = self.analyze_context(change, repo_path)
            if context["source_code"]:
                affected_modules.append(change.file_path)

        risk_level = self.assess_risk(changes)

        summary = (
            f"Found {len(changes)} changed files "
            f"with {sum(len(c.added_lines) for c in changes)} lines added, "
            f"{sum(len(c.removed_lines) for c in changes)} lines removed. "
            f"Risk level: {risk_level}."
        )

        return AnalysisResult(
            changes=changes,
            summary=summary,
            affected_modules=affected_modules,
            risk_level=risk_level,
        )

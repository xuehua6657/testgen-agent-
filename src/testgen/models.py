"""Data models for TestGen-Agent."""

from typing import TypedDict

from pydantic import BaseModel


class CodeChange(BaseModel):
    """A single changed file extracted from git diff."""

    file_path: str
    diff_text: str
    added_lines: list[int]
    removed_lines: list[int]
    changed_functions: list[str]
    language: str


class AnalysisResult(BaseModel):
    """Result of code analysis."""

    changes: list[CodeChange]
    summary: str
    affected_modules: list[str]
    risk_level: str  # "low", "medium", "high"


class TestSpec(BaseModel):
    """Specification for a single test case to generate."""

    source_file: str
    target_function: str
    test_type: str  # "unit", "integration", "edge_case"
    description: str
    input_params: dict[str, str]
    expected_behavior: str


class GeneratedTest(BaseModel):
    """A generated test case."""

    test_spec: TestSpec
    test_code: str
    file_path: str
    is_new_file: bool
    confidence: float


class ValidationResult(BaseModel):
    """Result of test validation."""

    test_index: int
    passed: bool
    score: float
    errors: list[str]


class AgentState(TypedDict, total=False):
    """LangGraph agent state."""

    repo_path: str
    ref: str
    diff_text: str
    analysis: AnalysisResult | None
    test_specs: list[TestSpec]
    generated_tests: list[GeneratedTest]
    validation_results: list[ValidationResult]
    errors: list[str]
    iteration: int
    final_output_path: str | None

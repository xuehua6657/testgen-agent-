"""CLI interface for TestGen-Agent."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from testgen import __version__
from testgen.agent import TestGenAgent
from testgen.ci import CIIntegration
from testgen.config import DEFAULT_CONFIG_TEMPLATE, TestGenConfig

app = typer.Typer(
    name="testgen",
    help="AI-powered automated test generation from code changes",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


@app.command()
def generate(
    repo: str = typer.Argument(".", help="Path to git repository"),
    ref: str = typer.Option("HEAD", "--ref", "-r", help="Git ref to diff against"),
    config: str = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Output directory for generated tests"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Verbose output"
    ),
):
    """Analyze code changes and generate unit tests.

    This command analyzes git diffs, uses an AI agent to understand
    the changes, and generates corresponding unit tests.
    """
    from testgen.utils import setup_logging

    setup_logging(verbose)

    console.print(Panel.fit(
        f"[bold]TestGen-Agent v{__version__}[/bold]\n"
        f"AI-powered test generation from code changes",
        title="TestGen",
    ))

    # Load configuration
    try:
        cfg = TestGenConfig.load(config)
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1)

    # Override output dir if specified
    if output:
        cfg.test_dirs = [output]

    # Validate repo path
    repo_path = Path(repo).resolve()
    if not (repo_path / ".git").exists():
        console.print(f"[red]Error: {repo_path} is not a git repository[/red]")
        raise typer.Exit(1)

    # Create and run agent
    agent = TestGenAgent(cfg)

    with console.status("[bold green]Generating tests...", spinner="dots"):
        result = agent.run(str(repo_path), ref)

    # Display results
    if result.get("errors"):
        for error in result["errors"]:
            console.print(f"[red]Error: {error}[/red]")
        raise typer.Exit(1)

    if result.get("final_output_path"):
        console.print(f"[green]Tests saved to: {result['final_output_path']}[/green]")

        # Show summary table
        if result.get("generated_tests"):
            table = Table(title="Generated Tests")
            table.add_column("File", style="cyan")
            table.add_column("Score", justify="right")
            table.add_column("Status", justify="center")

            for test in result["generated_tests"]:
                score = f"{test.confidence:.2f}"
                status = "[green]PASS[/green]" if test.confidence >= cfg.agent.min_confidence_score else "[red]FAIL[/red]"
                table.add_row(test.file_path, score, status)

            console.print(table)
    else:
        console.print("[yellow]No tests were generated[/yellow]")
        if result.get("generated_tests"):
            console.print("[dim]Generated tests failed validation[/dim]")


@app.command()
def validate(
    test_file: str = typer.Argument(..., help="Path to test file"),
    source: str = typer.Option(
        None, "--source", "-s", help="Corresponding source file"
    ),
    config: str = typer.Option(
        None, "--config", "-c", help="Path to config file"
    ),
):
    """Validate existing tests for syntax and quality."""
    from testgen.utils import read_file, setup_logging

    setup_logging()

    try:
        cfg = TestGenConfig.load(config)
    except (ValueError, FileNotFoundError) as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1)

    test_code = read_file(test_file)
    if not test_code:
        console.print(f"[red]Error: Cannot read {test_file}[/red]")
        raise typer.Exit(1)

    source_code = read_file(source) if source else ""

    from testgen.generator import TestGenerator
    from testgen.validator import TestValidator

    validator = TestValidator(cfg)
    generator = TestGenerator(cfg.llm)

    console.print(f"[bold]Validating: {test_file}[/bold]")

    # Syntax check
    syntax_ok, syntax_err = validator.syntax_check(test_code)
    console.print(f"  Syntax: {'[green]OK[/green]' if syntax_ok else f'[red]FAIL - {syntax_err}[/red]'}")

    if not syntax_ok:
        raise typer.Exit(1)

    # Import check
    import_ok, import_err = validator.import_check(test_code, source)
    console.print(f"  Imports: {'[green]OK[/green]' if import_ok else f'[red]FAIL - {import_err}[/red]'}")

    # Dry run
    dry_ok, dry_err = validator.dry_run(test_code)
    console.print(f"  Collection: {'[green]OK[/green]' if dry_ok else f'[yellow]SKIP - {dry_err}[/yellow]'}")

    # Quality check
    with console.status("[bold green]Checking quality...", spinner="dots"):
        score = validator.llm_quality_check(test_code, source_code, generator)

    console.print(f"  Quality: [bold]{score:.2f}/1.00[/bold]")

    passed = score >= cfg.agent.min_confidence_score
    console.print(
        f"\n  Overall: {'[green]PASS[/green]' if passed else '[red]FAIL[/red]'} "
        f"(threshold: {cfg.agent.min_confidence_score})"
    )


@app.command()
def ci_setup(
    provider: str = typer.Option(
        "github_actions", "--provider", "-p", help="CI provider"
    ),
    output: str = typer.Option(
        ".github/workflows", "--output", "-o", help="Output directory"
    ),
):
    """Generate CI pipeline configuration for test generation."""
    from testgen.utils import setup_logging

    setup_logging()

    console.print(f"[bold]Setting up CI integration for {provider}...[/bold]")

    ci = CIIntegration()

    try:
        workflow = ci.generate_workflow(provider)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    output_path = Path(output)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = "testgen.yml"
    full_path = output_path / filename

    if full_path.write_text(workflow):
        console.print(f"[green]Generated: {full_path}[/green]")
        console.print(
            f"[dim]Add your LLM API key as a secret and configure as needed[/dim]"
        )
    else:
        console.print(f"[red]Failed to write {full_path}[/red]")
        raise typer.Exit(1)


@app.command()
def config_init(
    path: str = typer.Argument(".", help="Directory to create config in"),
):
    """Create a default .testgen.yaml configuration file."""
    output_path = Path(path) / ".testgen.yaml"

    if output_path.exists():
        console.print(f"[yellow]Config already exists: {output_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit(0)

    if output_path.write_text(DEFAULT_CONFIG_TEMPLATE):
        console.print(f"[green]Created: {output_path}[/green]")
        console.print(
            f"[dim]Edit the file and set TESTGEN_LLM_API_KEY environment variable[/dim]"
        )
    else:
        console.print(f"[red]Failed to create config[/red]")
        raise typer.Exit(1)


@app.command()
def version():
    """Show the version."""
    console.print(f"testgen-agent v{__version__}")


if __name__ == "__main__":
    app()

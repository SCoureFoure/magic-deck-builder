"""Main CLI application entry point."""
import typer
from rich.console import Console

from src.cli import commands

app = typer.Typer(
    name="magic-deck-builder",
    help="Commander (EDH) deck builder CLI tool",
    add_completion=False,
)

# Add command groups
app.add_typer(commands.ingest_app, name="ingest", help="Data ingestion commands")
app.add_typer(commands.search_app, name="search", help="Search for cards and commanders")
app.add_typer(commands.generate_app, name="generate", help="Generate Commander decks")
app.add_typer(commands.eval_app, name="eval", help="Evaluation commands")

console = Console()


@app.command()
def version():
    """Show version information."""
    console.print("magic-deck-builder version 0.1.0")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()

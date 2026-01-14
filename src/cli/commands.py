"""CLI commands for the deck builder."""
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.config import settings
from src.database.engine import get_db, init_db
from src.engine.commander import find_commanders, is_commander_eligible, populate_commanders
from src.ingestion.bulk_ingest import download_and_ingest_bulk
from src.ingestion.scryfall_client import ScryfallClient

ingest_app = typer.Typer(help="Data ingestion commands")
search_app = typer.Typer(help="Search commands")
console = Console()


@ingest_app.command("bulk")
def ingest_bulk(
    bulk_type: str = typer.Argument(
        "oracle_cards", help="Bulk data type to ingest (oracle_cards, default_cards, etc.)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force re-download even if cached"
    ),
    init_tables: bool = typer.Option(
        True, "--init-tables/--no-init-tables", help="Initialize database tables if needed"
    ),
):
    """Download and ingest Scryfall bulk data.

    Examples:
        magic-deck-builder ingest bulk oracle_cards
        magic-deck-builder ingest bulk --force
    """
    console.print(f"[bold cyan]Magic Deck Builder - Bulk Ingestion[/bold cyan]")
    console.print(f"Bulk type: [yellow]{bulk_type}[/yellow]")
    console.print(f"Force download: [yellow]{force}[/yellow]")
    console.print()

    # Initialize database tables if requested
    if init_tables:
        with console.status("[bold green]Initializing database tables..."):
            init_db()
        console.print("[green]✓[/green] Database tables initialized")

    # Create client
    client = ScryfallClient()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            # Download bulk data
            task = progress.add_task("Fetching bulk data info...", total=None)
            bulk_info = client.get_bulk_data_info()
            progress.update(task, description=f"[green]✓[/green] Found {bulk_type} info")

            # Get database session and ingest
            with get_db() as db:
                progress.update(
                    task, description=f"Downloading and ingesting {bulk_type}..."
                )
                card_count = download_and_ingest_bulk(
                    db, client, bulk_type=bulk_type, force_download=force
                )

        console.print(
            f"[green]✓[/green] Successfully ingested [bold]{card_count}[/bold] cards"
        )

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        raise typer.Exit(1)


@ingest_app.command("file")
def ingest_file(
    file_path: Path = typer.Argument(..., help="Path to local Scryfall bulk JSON file"),
    init_tables: bool = typer.Option(
        True, "--init-tables/--no-init-tables", help="Initialize database tables if needed"
    ),
):
    """Ingest cards from a local Scryfall bulk JSON file.

    Examples:
        magic-deck-builder ingest file ./data/oracle_cards.json
    """
    console.print("[bold cyan]Magic Deck Builder - File Ingestion[/bold cyan]")
    console.print(f"File: [yellow]{file_path}[/yellow]")
    console.print()

    if not file_path.exists():
        console.print(f"[red]Error:[/red] File not found: {file_path}")
        raise typer.Exit(1)

    # Initialize database tables if requested
    if init_tables:
        with console.status("[bold green]Initializing database tables..."):
            init_db()
        console.print("[green]✓[/green] Database tables initialized")

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Ingesting cards from file...", total=None)

            from src.ingestion.bulk_ingest import ingest_bulk_file

            with get_db() as db:
                card_count = ingest_bulk_file(db, file_path)

            progress.update(task, description="[green]✓[/green] Ingestion complete")

        console.print(
            f"[green]✓[/green] Successfully ingested [bold]{card_count}[/bold] cards"
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# Search commands


@search_app.command("commander")
def search_commander(
    name: str = typer.Argument(..., help="Commander name to search for"),
    limit: int = typer.Option(10, "--limit", "-n", help="Maximum number of results"),
    populate: bool = typer.Option(
        False, "--populate", help="Populate commanders table first"
    ),
):
    """Search for commanders by name.

    Examples:
        python -m src.cli search commander "Atraxa"
        python -m src.cli search commander "Urza" --limit 5
        python -m src.cli search commander "Sisay" --populate
    """
    console.print(f"[bold cyan]Commander Search[/bold cyan]")
    console.print(f"Query: [yellow]{name}[/yellow]")
    console.print()

    try:
        with get_db() as db:
            # Populate commanders table if requested
            if populate:
                with console.status("Populating commanders table..."):
                    count = populate_commanders(db)
                console.print(f"[green]✓[/green] Populated {count} commanders")
                console.print()

            # Search for commanders
            results = find_commanders(db, name_query=name, limit=limit)

            if not results:
                console.print(f"[yellow]No commanders found matching '{name}'[/yellow]")
                console.print(
                    "\n[dim]Tip: Try importing cards first with:[/dim]"
                    "\n[cyan]python -m src.cli ingest bulk oracle_cards[/cyan]"
                )
                raise typer.Exit(0)

            # Display results in a table
            table = Table(title=f"Found {len(results)} commander(s)")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Type", style="magenta")
            table.add_column("Colors", style="yellow")
            table.add_column("CMC", justify="right", style="green")
            table.add_column("Eligibility", style="blue")

            for card in results:
                is_eligible, reason = is_commander_eligible(card)

                # Format color identity
                colors = "".join(card.color_identity) if card.color_identity else "C"

                # Format mana cost or just CMC
                cmc_display = (
                    f"{card.mana_cost} ({card.cmc})" if card.mana_cost else str(card.cmc)
                )

                # Truncate type line if too long
                type_display = (
                    card.type_line[:40] + "..."
                    if len(card.type_line) > 40
                    else card.type_line
                )

                table.add_row(
                    card.name,
                    type_display,
                    colors,
                    cmc_display,
                    reason if is_eligible else "Unknown",
                )

            console.print(table)

            # Show detailed view for first result if only one
            if len(results) == 1:
                card = results[0]
                console.print()
                console.print(
                    Panel(
                        f"[bold]{card.name}[/bold]\n"
                        f"{card.type_line}\n\n"
                        f"[dim]{card.oracle_text or 'No text'}[/dim]\n\n"
                        f"Mana Cost: {card.mana_cost or 'N/A'}\n"
                        f"Color Identity: {', '.join(card.color_identity) if card.color_identity else 'Colorless'}\n"
                        f"Commander Legal: {card.legalities.get('commander', 'unknown')}",
                        title="Card Details",
                        border_style="cyan",
                    )
                )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

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
from src.engine.deck_builder import generate_deck
from src.engine.validator import validate_deck
from src.ingestion.bulk_ingest import download_and_ingest_bulk
from src.ingestion.scryfall_client import ScryfallClient

ingest_app = typer.Typer(help="Data ingestion commands")
search_app = typer.Typer(help="Search commands")
generate_app = typer.Typer(help="Deck generation commands")
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


# Generate commands


@generate_app.command("deck")
def generate_deck_cli(
    commander_name: str = typer.Argument(..., help="Commander name for the deck"),
    output: Path = typer.Option(None, "--output", "-o", help="Output file path (optional)"),
    use_council: bool = typer.Option(False, "--council", help="Use council-based selection"),
    council_config: Path = typer.Option(
        None, "--council-config", help="Path to council config YAML"
    ),
):
    """Generate a 100-card Commander deck.

    Examples:
        python -m src.cli generate deck "Atraxa"
        python -m src.cli generate deck "Atraxa" --output my_deck.txt
    """
    console.print(f"[bold cyan]Deck Generation[/bold cyan]")
    console.print(f"Commander: [yellow]{commander_name}[/yellow]")
    console.print()

    try:
        with get_db() as db:
            # Find commander
            with console.status(f"Searching for commander '{commander_name}'..."):
                commanders = find_commanders(db, name_query=commander_name, limit=1)

            if not commanders:
                console.print(f"[red]Error:[/red] Commander '{commander_name}' not found")
                console.print(
                    f"\n[dim]Tip: Search for commanders with:[/dim]"
                    f"\n[cyan]python -m src.cli search commander \"{commander_name}\"[/cyan]"
                )
                raise typer.Exit(1)

            commander_card = commanders[0]

            # Get or create commander entry
            from src.engine.commander import create_commander_entry
            commander = create_commander_entry(db, commander_card)

            if not commander:
                console.print(f"[red]Error:[/red] Could not create commander entry")
                raise typer.Exit(1)

            # Seed roles if needed
            from src.database.seed_roles import seed_roles
            roles_added = seed_roles(db)
            if roles_added > 0:
                console.print(f"[green]✓[/green] Initialized {roles_added} card roles")

            # Generate deck
            with console.status("Generating deck..."):
                deck = generate_deck(
                    db,
                    commander,
                    constraints={
                        "use_council": use_council,
                        "council_config_path": str(council_config)
                        if council_config
                        else None,
                    },
                )

            # Validate deck
            is_valid, errors = validate_deck(deck)

            if not is_valid:
                console.print("[yellow]⚠[/yellow] Deck validation warnings:")
                for error in errors:
                    console.print(f"  • {error}")
                console.print()

            # Display deck summary
            console.print(f"[green]✓[/green] Generated deck with [bold]{len(deck.deck_cards)}[/bold] card entries")
            total_cards = sum(dc.quantity for dc in deck.deck_cards)
            console.print(f"[green]✓[/green] Total cards: [bold]{total_cards}[/bold]")
            console.print()

            # Group cards by role
            from collections import defaultdict
            role_groups: dict[str, list] = defaultdict(list)

            for deck_card in deck.deck_cards:
                role_name = deck_card.role.name if deck_card.role else "unknown"
                role_groups[role_name].append(deck_card)

            # Display by role
            for role_name in ["lands", "ramp", "draw", "removal", "synergy", "wincons", "flex"]:
                cards = role_groups.get(role_name, [])
                if not cards:
                    continue

                role_count = sum(dc.quantity for dc in cards)
                console.print(f"\n[bold cyan]{role_name.upper()}[/bold cyan] ({role_count}):")

                for deck_card in sorted(cards, key=lambda dc: dc.card.name):
                    quantity_str = f"{deck_card.quantity}x" if deck_card.quantity > 1 else "  "
                    console.print(f"  {quantity_str} {deck_card.card.name}")

            # Output to file if requested
            if output:
                with open(output, "w") as f:
                    f.write(f"Commander: {commander_card.name}\n\n")
                    for role_name in ["lands", "ramp", "draw", "removal", "synergy", "wincons", "flex"]:
                        cards = role_groups.get(role_name, [])
                        if not cards:
                            continue
                        role_count = sum(dc.quantity for dc in cards)
                        f.write(f"\n{role_name.upper()} ({role_count}):\n")
                        for deck_card in sorted(cards, key=lambda dc: dc.card.name):
                            quantity_str = f"{deck_card.quantity}x" if deck_card.quantity > 1 else "1"
                            f.write(f"{quantity_str} {deck_card.card.name}\n")

                console.print(f"\n[green]✓[/green] Deck saved to: {output}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)

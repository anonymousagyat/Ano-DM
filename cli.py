"""
NDM-Style CLI Interface for Ano-Download Manager (Ano-DM)
Features:
  1. Configurable connection streams (8, 16, 32, or custom).
  2. NDM-style multi-part visualization in terminal.
  3. Live per-adapter and per-part Rich telemetry.
  4. Safe pause & instant resume on Ctrl+C.
  5. High-speed binary assembly phase.
  6. Scriptable CLI arguments (e.g., `python cli.py <URL> --streams 32`).
"""

import sys
import os
import time
import argparse
from typing import List, Dict

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.text import Text
    USE_RICH = True
except ImportError:
    USE_RICH = False

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)

from network_scanner import get_active_interfaces
from engine import DualBondDownloader, sanitize_filename

console = Console() if USE_RICH else None


def format_bytes(byte_count: float) -> str:
    """Formats bytes into human-readable B, KB, MB, GB, TB."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if byte_count < 1024.0:
            return f"{byte_count:.2f} {unit}"
        byte_count /= 1024.0
    return f"{byte_count:.2f} PB"


def print_banner():
    title = "⚡ ANO-DOWNLOAD MANAGER (CLI MODE) ⚡"
    subtitle = "Multi-Interface Channel Bonding • Lock-Free Parts • Instant Resume • High-Speed Merge"
    if USE_RICH:
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]\n[dim]{subtitle}[/dim]", border_style="cyan"))
    else:
        print("=" * 70)
        print(f" {title}")
        print(f" {subtitle}")
        print("=" * 70)


def select_interfaces(auto_all: bool = False) -> List[Dict[str, str]]:
    """Scans and prompts user to pick network interfaces for bonding."""
    if USE_RICH:
        console.print("\n[bold yellow]🔍 Scanning network interfaces...[/bold yellow]")
    else:
        print("\nScanning network interfaces...")

    adapters = get_active_interfaces(test_internet=True)

    if not adapters:
        if USE_RICH:
            console.print("[bold red]❌ No active network adapters found![/bold red]")
        else:
            print("No active network adapters found!")
        sys.exit(1)

    online_adapters = [a for a in adapters if a["online"]]

    if auto_all:
        selected = online_adapters if online_adapters else adapters
    else:
        if USE_RICH:
            table = Table(title="Detected Network Interfaces", show_header=True, header_style="bold magenta")
            table.add_column("No.", style="cyan", width=4)
            table.add_column("Adapter Name", style="white")
            table.add_column("Type", style="green")
            table.add_column("IP Address", style="yellow")
            table.add_column("Internet Status", style="bold")

            for idx, iface in enumerate(adapters, 1):
                status = "[green]✔ Online[/green]" if iface["online"] else "[red]✖ Offline[/red]"
                table.add_row(str(idx), iface["name"], iface["type"], iface["ip"], status)
            console.print(table)
        else:
            print("\nDetected Network Interfaces:")
            for idx, iface in enumerate(adapters, 1):
                status = "Online" if iface["online"] else "Offline"
                print(f"  [{idx}] {iface['name']} ({iface['type']}) - IP: {iface['ip']} - {status}")

        default_prompt = ", ".join(str(i + 1) for i in range(len(adapters)) if adapters[i]["online"])
        choice = input(f"\nEnter adapter numbers to bond (comma separated, default: all online [{default_prompt}]): ").strip()

        if not choice:
            selected = online_adapters if online_adapters else adapters
        else:
            indices = [int(x.strip()) - 1 for x in choice.split(",") if x.strip().isdigit()]
            selected = [adapters[i] for i in indices if 0 <= i < len(adapters)]

        if not selected:
            selected = online_adapters

    if USE_RICH:
        console.print(f"\n[green]✔ Bonding active on {len(selected)} adapter(s):[/green]")
        for s in selected:
            console.print(f"   • [cyan]{s['name']}[/cyan] ({s['ip']})")
    else:
        print(f"\nBonding active on {len(selected)} adapter(s):")
        for s in selected:
            print(f"   * {s['name']} ({s['ip']})")

    return selected


def pick_connection_count(default_val: int = 16) -> int:
    """Lets user pick NDM parallel stream density."""
    if USE_RICH:
        console.print("\n[bold]Select Parallel Stream Density (NDM Style):[/bold]")
        console.print("  [cyan][1][/cyan] 8 Connections  (Lightweight)")
        console.print("  [cyan][2][/cyan] 16 Connections (Recommended - NDM Default) [bold green][Enter][/bold green]")
        console.print("  [cyan][3][/cyan] 32 Connections (Maximum Aggression)")
        console.print("  Or enter custom number (e.g. 4, 12, 24)")
        choice = console.input(f"[cyan]Choice (Default: {default_val}): [/cyan]").strip()
    else:
        print("\nSelect Parallel Stream Density:")
        print("  [1] 8 Connections")
        print("  [2] 16 Connections (Default - Press Enter)")
        print("  [3] 32 Connections")
        choice = input(f"Choice (Default: {default_val}): ").strip()

    if not choice or choice == "2":
        return 16
    elif choice == "1":
        return 8
    elif choice == "3":
        return 32
    elif choice.isdigit():
        return max(1, min(64, int(choice)))
    return default_val


def run_download(url: str, selected_interfaces: List[Dict[str, str]], num_connections: int, output_path: str = ""):
    downloads_dir = os.path.join(PROJECT_DIR, "downloads")
    temp_dir = os.path.join(downloads_dir, "temp")
    os.makedirs(downloads_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    downloader = DualBondDownloader(
        url=url,
        output_path=output_path,
        interfaces=selected_interfaces,
        num_connections=num_connections,
        temp_dir=temp_dir
    )

    if USE_RICH:
        console.print("\n[bold cyan]Probing remote server headers & range capability...[/bold cyan]")
    else:
        print("\nProbing remote server headers & range capability...")

    try:
        file_size, accepts_ranges, clean_filename = downloader.probe_file()
    except Exception as e:
        if USE_RICH:
            console.print(f"[bold red]✖ Error probing URL: {e}[/bold red]")
        else:
            print(f"Error probing URL: {e}")
        return

    target_path = output_path or os.path.join(downloads_dir, clean_filename)
    downloader.output_path = target_path

    if USE_RICH:
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Field", style="bold yellow")
        info_table.add_column("Value", style="bold white")
        info_table.add_row("File Name:", clean_filename)
        info_table.add_row("File Size:", format_bytes(file_size))
        info_table.add_row("Multi-Part Range Support:", "[green]✔ Enabled[/green]" if accepts_ranges else "[red]✖ No (Single Stream)[/red]")
        info_table.add_row("Save Destination:", target_path)
        info_table.add_row("Parallel Streams:", f"{num_connections} Parts")
        console.print(Panel(info_table, title="[bold]Target Metadata[/bold]", border_style="green"))
    else:
        print("-" * 50)
        print(f"File Name: {clean_filename}")
        print(f"File Size: {format_bytes(file_size)}")
        print(f"Ranges Supported: {accepts_ranges}")
        print(f"Destination: {target_path}")
        print(f"Parallel Streams: {num_connections}")
        print("-" * 50)

    start_time = time.time()

    try:
        if USE_RICH:
            with Live(console=console, refresh_per_second=8, transient=False) as live:
                def render_progress_rich(stats):
                    if stats.get("is_merging"):
                        prog = stats.get("merge_progress", 0.0) * 100
                        live.update(Panel(
                            f"[bold yellow]🔄 Assembling .part files into destination... {prog:.1f}%[/bold yellow]\n"
                            f"[dim]Performing high-speed binary concatenation...[/dim]",
                            border_style="yellow"
                        ))
                        return

                    downloaded = stats["downloaded_bytes"]
                    total = stats["total_bytes"]
                    pct = (downloaded / total * 100) if total > 0 else 0
                    combined_speed = format_bytes(stats["total_speed_bps"]) + "/s"

                    table = Table(show_header=True, header_style="bold blue", expand=True)
                    table.add_column("Adapter", style="cyan")
                    table.add_column("Current Speed", style="bold green", justify="right")
                    table.add_column("Total Pulled", style="white", justify="right")
                    table.add_column("Status", style="magenta")

                    for a in stats.get("adapters", []):
                        sp = format_bytes(a.get("speed_bps", 0.0)) + "/s"
                        pulled = format_bytes(a.get("total_bytes", 0))
                        status = a.get("status", "Active")
                        table.add_row(f"{a['name']} ({a['ip']})", sp, pulled, status)

                    parts = stats.get("parts", [])
                    segment_blocks = []
                    for p in parts[:32]:
                        if p.is_complete:
                            segment_blocks.append("[green]█[/green]")
                        elif p.downloaded_bytes > 0:
                            segment_blocks.append("[yellow]▒[/yellow]")
                        else:
                            segment_blocks.append("[dim]░[/dim]")
                    segment_map = "".join(segment_blocks)

                    summary_text = (
                        f"Combined Speed: [bold cyan]{combined_speed}[/bold cyan] | "
                        f"Progress: [bold green]{pct:.1f}%[/bold green] ({format_bytes(downloaded)} / {format_bytes(total)}) | "
                        f"Parts: {stats['completed_parts']}/{stats['total_parts']}\n"
                        f"Stream Map: {segment_map} [dim](█ Done | ▒ Active | ░ Queued)[/dim]"
                    )

                    live.update(Panel(table, subtitle=summary_text, border_style="cyan"))

                downloader.start(progress_callback=render_progress_rich)
        else:
            def render_progress_plain(stats):
                if stats.get("is_merging"):
                    prog = stats.get("merge_progress", 0.0) * 100
                    sys.stdout.write(f"\rAssembling final file... {prog:.1f}%")
                    sys.stdout.flush()
                    return

                downloaded = stats["downloaded_bytes"]
                total = stats["total_bytes"]
                pct = (downloaded / total * 100) if total > 0 else 0
                sp = format_bytes(stats["total_speed_bps"]) + "/s"
                sys.stdout.write(f"\r[{pct:5.1f}%] {format_bytes(downloaded)}/{format_bytes(total)} @ {sp} (Parts: {stats['completed_parts']}/{stats['total_parts']})")
                sys.stdout.flush()

            downloader.start(progress_callback=render_progress_plain)
            print()

        elapsed = time.time() - start_time
        avg_speed = (file_size / elapsed) if elapsed > 0 else 0

        if USE_RICH:
            console.print(Panel(
                f"[bold green]✔ Download & Assembly Complete in {elapsed:.2f} seconds![/bold green]\n"
                f"Average Aggregated Speed: [bold cyan]{format_bytes(avg_speed)}/s[/bold cyan]\n"
                f"File verified & saved to: [white]{target_path}[/white]",
                border_style="green"
            ))
        else:
            print("\n" + "=" * 70)
            print(f"Download & Assembly Complete in {elapsed:.2f} seconds!")
            print(f"Average Speed: {format_bytes(avg_speed)}/s")
            print(f"File saved to: {target_path}")
            print("=" * 70)

    except KeyboardInterrupt:
        downloader.stop()
        if USE_RICH:
            console.print(Panel(
                "[bold yellow]⏸ Download PAUSED by User.[/bold yellow]\n"
                f"All temporary .part files have been safely preserved in:\n[white]{temp_dir}[/white]\n"
                "[bold green]Run again anytime to resume instantly from this exact byte![/bold green]",
                border_style="yellow"
            ))
        else:
            print("\nDownload PAUSED. Part files preserved. Run again to resume instantly.")


def main():
    parser = argparse.ArgumentParser(description="Ano-Download Manager (Ano-DM) - Terminal CLI Mode")
    parser.add_argument("url", nargs="?", default="", help="Direct download URL (optional)")
    parser.add_argument("-s", "--streams", type=int, default=16, help="Parallel streams/connections (default: 16)")
    parser.add_argument("-o", "--output", default="", help="Custom output file destination path")
    parser.add_argument("-a", "--all-adapters", action="store_true", help="Auto-bond all online network adapters without prompting")
    args = parser.parse_args()

    print_banner()

    if args.url:
        # Non-interactive CLI one-liner
        selected_interfaces = select_interfaces(auto_all=True if args.all_adapters else False)
        run_download(args.url, selected_interfaces, args.streams, args.output)
    else:
        # Interactive Wizard
        selected_interfaces = select_interfaces(auto_all=False)
        num_connections = pick_connection_count(default_val=args.streams)

        default_test_url = "https://speed.cloudflare.com/__down?bytes=104857600"
        hetzner_test_url = "https://speed.hetzner.de/100MB.bin"

        if USE_RICH:
            console.print("\n[bold]Enter Download URL[/bold]")
            console.print("  [cyan][1][/cyan] Cloudflare 100MB Speedtest")
            console.print("  [cyan][2][/cyan] Hetzner 100MB Speedtest")
            console.print("  Or paste any custom download URL")
            user_input = console.input(f"\n[cyan]Choice or URL: [/cyan]").strip()
        else:
            print("\nEnter Download URL:")
            print("  [1] Cloudflare 100MB")
            print("  [2] Hetzner 100MB")
            print("  Or paste any custom download URL")
            user_input = input("\nChoice or URL: ").strip()

        if user_input == "1":
            url = default_test_url
        elif user_input == "2":
            url = hetzner_test_url
        elif not user_input:
            url = default_test_url
        else:
            url = user_input

        run_download(url, selected_interfaces, num_connections, args.output)


if __name__ == "__main__":
    main()

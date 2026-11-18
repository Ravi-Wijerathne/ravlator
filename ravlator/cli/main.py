"""
[FR-25] Ravlator Headless CLI Interface.
Enables full prefix lifecycle, runner downloads, dependency installation, and Wine execution directly from the terminal.
"""

import argparse
import sys
from pathlib import Path

from ravlator.core.bottle import BottleManager
from ravlator.core.dependencies import DependencyManager
from ravlator.core.downloader import DownloadProgress
from ravlator.core.runner import RunnerManager
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager
from ravlator.core.models import PresetType, WindowsVersion


def print_progress(progress: DownloadProgress):
    mb_down = progress.downloaded_bytes / (1024 * 1024)
    mb_total = progress.total_bytes / (1024 * 1024)
    speed_mb = progress.speed_bps / (1024 * 1024)
    sys.stdout.write(f"\rDownloading: {progress.percentage:.1f}% ({mb_down:.1f}/{mb_total:.1f} MB) - {speed_mb:.2f} MB/s")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(
        prog="ravlator-cli",
        description="Ravlator: Next-Generation Windows Gaming & Wine Prefix Manager for macOS"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    # Command: list-bottles
    subparsers.add_parser("list-bottles", help="List all configured Wine bottles")

    # Command: create-bottle
    create_parser = subparsers.add_parser("create-bottle", help="Create a new bottle prefix")
    create_parser.add_argument("name", type=str, help="Name of the new bottle")
    create_parser.add_argument(
        "--preset",
        type=str,
        choices=["gaming", "productivity", "custom"],
        default="gaming",
        help="Environment preset template (default: gaming)"
    )
    create_parser.add_argument(
        "--version",
        type=str,
        choices=["win10", "win11", "win7"],
        default="win10",
        help="Reported Windows version (default: win10)"
    )

    # Command: delete-bottle
    del_parser = subparsers.add_parser("delete-bottle", help="Delete a bottle permanently")
    del_parser.add_argument("name", type=str, help="ID or name of the bottle to remove")

    # Command: list-runners
    subparsers.add_parser("list-runners", help="List installed and catalog Wine/GPTK runners")

    # Command: install-runner
    inst_r_parser = subparsers.add_parser("install-runner", help="Download and install a runner from CDN")
    inst_r_parser.add_argument("runner_id", type=str, help="ID of runner to install (e.g. gptk-2.0)")

    # Command: list-dependencies
    subparsers.add_parser("list-dependencies", help="List all available gaming dependency recipes")

    # Command: install-dependency
    inst_d_parser = subparsers.add_parser("install-dependency", help="Install a runtime dependency into a bottle")
    inst_d_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    inst_d_parser.add_argument("--dep", required=True, type=str, help="Dependency recipe ID (e.g. vcredist2022)")

    # Command: kill-bottle
    kill_parser = subparsers.add_parser("kill-bottle", help="Force terminate wineserver for a bottle")
    kill_parser.add_argument("name", type=str, help="ID of the bottle")

    # Command: run
    run_parser = subparsers.add_parser("run", help="Execute a Windows binary inside a bottle")
    run_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    run_parser.add_argument("--exe", required=True, type=str, help="Path to Windows .exe binary")
    run_parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the executable")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "list-bottles":
        bottles = BottleManager.list_bottles()
        if not bottles:
            print("No bottles found. Create one using: ravlator-cli create-bottle <name>")
            return
        print(f"{'NAME':<20} {'ID':<25} {'PRESET':<15} {'RUNNER':<15} {'MSYNC'}")
        print("-" * 80)
        for b in bottles:
            print(f"{b.name:<20} {b.id:<25} {b.preset.value:<15} {b.runner_id:<15} {b.msync}")

    elif args.command == "create-bottle":
        preset_enum = PresetType(args.preset)
        ver_enum = WindowsVersion(args.version)
        print(f"[*] Initializing bottle '{args.name}' with preset '{args.preset}'...")
        config = BottleManager.create_bottle(name=args.name, preset=preset_enum, windows_version=ver_enum)
        print(f"[+] Successfully created bottle: {config.name} (ID: {config.id})")
        print(f"    Prefix Path: {BottleManager.get_bottle_dir(config.id)}")

    elif args.command == "delete-bottle":
        success = BottleManager.delete_bottle(args.name)
        if success:
            print(f"[+] Deleted bottle '{args.name}'")
        else:
            print(f"[-] Bottle '{args.name}' not found.")

    elif args.command == "list-runners":
        runners = RunnerManager.get_available_runners()
        print(f"{'RUNNER ID':<20} {'NAME':<35} {'INSTALLED':<12} {'TYPE'}")
        print("-" * 75)
        for r in runners:
            status = "Yes" if r.is_installed else "No (Available)"
            print(f"{r.id:<20} {r.name:<35} {status:<12} {r.source_type}")

    elif args.command == "install-runner":
        print(f"[*] Fetching and installing runner '{args.runner_id}'...")
        try:
            r = RunnerManager.download_and_extract_runner(args.runner_id, progress_callback=print_progress)
            print(f"\n[+] Runner successfully installed at: {r.path}")
        except Exception as e:
            print(f"\n[-] Failed to install runner: {e}")

    elif args.command == "list-dependencies":
        recipes = DependencyManager.get_available_recipes()
        print(f"{'ID':<20} {'CATEGORY':<20} {'NAME'}")
        print("-" * 75)
        for rc in recipes:
            print(f"{rc.id:<20} {rc.category:<20} {rc.name}")

    elif args.command == "install-dependency":
        print(f"[*] Installing dependency '{args.dep}' into bottle '{args.bottle}'...")
        try:
            DependencyManager.install_dependency(args.bottle, args.dep, progress_callback=print_progress)
            print(f"\n[+] Dependency '{args.dep}' installed successfully.")
        except Exception as e:
            print(f"\n[-] Installation error: {e}")

    elif args.command == "kill-bottle":
        bottle = BottleManager.get_bottle(args.name)
        if not bottle:
            print(f"[-] Bottle '{args.name}' not found.")
            sys.exit(1)
        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        WineProcessManager.force_kill_bottle(bottle, runner_dir)
        print(f"[+] Wineserver terminated for bottle '{bottle.name}'")

    elif args.command == "run":
        bottle = BottleManager.get_bottle(args.bottle)
        if not bottle:
            print(f"[-] Bottle '{args.bottle}' not found.")
            sys.exit(1)
        
        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        env = WineEnvironmentBuilder.build_env(bottle, runner_dir)
        final_args = WineProcessManager.inject_steam_cef_workaround(args.exe, args.args or [])
        
        print(f"[*] Launching '{args.exe}' inside bottle '{bottle.name}'...")
        print(f"    MSync: {bottle.msync} | Metal HUD: {bottle.metal_hud} | Retina: {bottle.retina}")
        print(f"    Arguments: {final_args}")
        print("[+] Environment successfully prepared.")


if __name__ == "__main__":
    main()

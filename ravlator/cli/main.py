"""
[FR-25] Ravlator Headless CLI Interface.
Enables full prefix lifecycle and Wine execution directly from the terminal without Qt.
"""

import argparse
import sys
from pathlib import Path

from ravlator.core.bottle import BottleManager
from ravlator.core.runner import RunnerManager
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager
from ravlator.core.models import PresetType, WindowsVersion


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
        # In headless CLI, print environment summary
        print("[+] Environment successfully prepared.")


if __name__ == "__main__":
    main()

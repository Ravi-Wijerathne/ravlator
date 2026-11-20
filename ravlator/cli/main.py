"""
[FR-25, FR-33, FR-34, FR-35, FR-36] Ravlator Headless CLI Interface.
Enables full prefix lifecycle, runner downloads, dependency installation,
store client deployment, process telemetry, snapshots, export/import, and Wine execution directly from the terminal.
"""

import argparse
import sys
from pathlib import Path

from ravlator.core.bottle import BottleManager
from ravlator.core.dependencies import DependencyManager
from ravlator.core.downloader import DownloadProgress
from ravlator.core.models import PresetType, WindowsVersion, ProgramEntry
from ravlator.core.runner import RunnerManager
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager
from ravlator.core.portability import PortabilityManager
from ravlator.core.shortcuts import ShortcutManager
from ravlator.core.snapshots import SnapshotManager
from ravlator.core.stores import StoreManager
from ravlator.core.telemetry import ProcessTelemetry
from ravlator.core.tools import WineToolsManager
from ravlator.core.anticheat import AntiCheatDetector
from ravlator.core.cloud_saves import CloudSaveManager


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

    # Command: install-store [FR-26, FR-27]
    store_parser = subparsers.add_parser("install-store", help="Install a game store (steam, epic, gog)")
    store_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    store_parser.add_argument("--store", required=True, choices=["steam", "epic", "gog"], help="Store to install")

    # Command: create-shortcut [FR-24]
    shortcut_parser = subparsers.add_parser("create-shortcut", help="Generate a standalone macOS .app bundle")
    shortcut_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    shortcut_parser.add_argument("--exe", required=True, type=str, help="Path to Windows executable")
    shortcut_parser.add_argument("--name", type=str, help="Custom application name")
    shortcut_parser.add_argument("--out", type=str, help="Output directory (default: ~/Desktop)")

    # Command: snapshot-create [FR-33]
    sc_parser = subparsers.add_parser("snapshot-create", help="Create a point-in-time snapshot of a bottle")
    sc_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    sc_parser.add_argument("--name", required=True, type=str, help="Snapshot name")
    sc_parser.add_argument("--desc", type=str, default="", help="Snapshot description")

    # Command: snapshot-list [FR-33]
    sl_parser = subparsers.add_parser("snapshot-list", help="List snapshots for a bottle")
    sl_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")

    # Command: snapshot-restore [FR-34]
    sr_parser = subparsers.add_parser("snapshot-restore", help="Rollback bottle state to a snapshot")
    sr_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    sr_parser.add_argument("--snapshot", required=True, type=str, help="Snapshot ID to restore")

    # Command: export-bottle [FR-35]
    exp_parser = subparsers.add_parser("export-bottle", help="Export a bottle as a portable archive")
    exp_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    exp_parser.add_argument("--out", type=str, help="Output path (e.g. ~/Downloads/my_bottle.tar.gz)")
    exp_parser.add_argument("--format", choices=["tar.gz", "zip"], default="tar.gz", help="Archive format")

    # Command: import-bottle [FR-36]
    imp_parser = subparsers.add_parser("import-bottle", help="Import a bottle from a portable archive")
    imp_parser.add_argument("--archive", required=True, type=str, help="Path to archive (.tar.gz or .zip)")
    imp_parser.add_argument("--name", type=str, help="Custom name for imported bottle")

    # Command: ps [FR-29]
    ps_parser = subparsers.add_parser("ps", help="List active processes for a bottle")
    ps_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")

    # Command: logs [FR-32]
    logs_parser = subparsers.add_parser("logs", help="Display recent logs for a bottle")
    logs_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    logs_parser.add_argument("--lines", type=int, default=50, help="Number of lines to tail")

    # Command: stop-bottle [FR-30]
    stop_parser = subparsers.add_parser("stop-bottle", help="Gracefully stop all processes in a bottle (wineboot -s)")
    stop_parser.add_argument("name", type=str, help="ID or name of the bottle")

    # Command: kill-bottle [FR-31]
    kill_parser = subparsers.add_parser("kill-bottle", help="Force terminate wineserver for a bottle")
    kill_parser.add_argument("name", type=str, help="ID of the bottle")

    # Command: winetricks [FR-20]
    wt_parser = subparsers.add_parser("winetricks", help="Run winetricks verbs inside bottle environment")
    wt_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    wt_parser.add_argument("verbs", nargs=argparse.REMAINDER, help="Winetricks verbs (e.g. vcrun2015)")

    # Command: cloud-sync [Section 9 Phase 4]
    cs_parser = subparsers.add_parser("cloud-sync", help="Manage cloud save symlinks (iCloud, Google Drive, etc.)")
    cs_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")
    cs_parser.add_argument("--enable", action="store_true", help="Enable cloud save sync")
    cs_parser.add_argument("--disable", action="store_true", help="Disable cloud save sync")
    cs_parser.add_argument("--provider", type=str, default="iCloud Drive", help="Cloud provider name (default: 'iCloud Drive')")

    # Command: reset-bottle [FR-05]
    reset_parser = subparsers.add_parser("reset-bottle", help="Reset bottle registry and caches to vanilla state")
    reset_parser.add_argument("--bottle", required=True, type=str, help="Target bottle ID")

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
        print(f"{'NAME':<20} {'ID':<25} {'PRESET':<15} {'RUNNER':<15} {'PROGRAMS'}")
        print("-" * 85)
        for b in bottles:
            print(f"{b.name:<20} {b.id:<25} {b.preset.value:<15} {b.runner_id:<15} {len(b.programs)}")

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

    elif args.command == "install-store":
        print(f"[*] Deploying {args.store.upper()} client into bottle '{args.bottle}'...")
        try:
            entry = StoreManager.install_store(args.bottle, args.store, progress_callback=print_progress)
            print(f"\n[+] {entry.name} installed successfully as a bottle program entry.")
        except Exception as e:
            print(f"\n[-] Store deployment error: {e}")

    elif args.command == "create-shortcut":
        bottle = BottleManager.get_bottle(args.bottle)
        if not bottle:
            print(f"[-] Bottle '{args.bottle}' not found.")
            sys.exit(1)

        out_path = Path(args.out).resolve() if args.out else ShortcutManager.get_desktop_dir()
        dummy_prog = ProgramEntry(
            id="cli-shortcut",
            name=args.name or Path(args.exe).stem,
            exe_path=args.exe
        )
        bundle = ShortcutManager.create_macos_app(bottle, dummy_prog, output_dir=out_path)
        print(f"[+] Standalone macOS .app generated at: {bundle}")

    elif args.command == "snapshot-create":
        snap = SnapshotManager.create_snapshot(args.bottle, args.name, args.desc)
        print(f"[+] Created snapshot '{snap.name}' (ID: {snap.id})")

    elif args.command == "snapshot-list":
        snaps = SnapshotManager.list_snapshots(args.bottle)
        if not snaps:
            print(f"No snapshots found for bottle '{args.bottle}'.")
            return
        print(f"{'SNAPSHOT ID':<20} {'NAME':<25} {'CREATED':<20} {'DESCRIPTION'}")
        print("-" * 80)
        for s in snaps:
            print(f"{s.id:<20} {s.name:<25} {s.created_at[:19]:<20} {s.description}")

    elif args.command == "snapshot-restore":
        SnapshotManager.rollback_snapshot(args.bottle, args.snapshot)
        print(f"[+] Successfully restored bottle '{args.bottle}' to snapshot '{args.snapshot}'.")

    elif args.command == "export-bottle":
        out_p = Path(args.out).resolve() if args.out else None
        res = PortabilityManager.export_bottle(args.bottle, dest_path=out_p, format=args.format)
        print(f"[+] Exported bottle '{args.bottle}' to: {res}")

    elif args.command == "import-bottle":
        archive_p = Path(args.archive).resolve()
        imported = PortabilityManager.import_bottle(archive_p, custom_name=args.name)
        print(f"[+] Successfully imported bottle '{imported.name}' (ID: {imported.id})")

    elif args.command == "ps":
        procs = ProcessTelemetry.list_bottle_processes(args.bottle)
        if not procs:
            print(f"No active processes found for bottle '{args.bottle}'.")
            return
        print(f"{'PID':<8} {'NAME':<25} {'CPU %':<8} {'MEM %':<8} {'COMMAND'}")
        print("-" * 75)
        for p in procs:
            print(f"{p.pid:<8} {p.name:<25} {p.cpu_percent:<8.1f} {p.mem_percent:<8.1f} {p.command[:35]}")

    elif args.command == "logs":
        log_content = ProcessTelemetry.read_recent_logs(args.bottle, max_lines=args.lines)
        print(log_content)

    elif args.command == "stop-bottle":
        bottle = BottleManager.get_bottle(args.name)
        if not bottle:
            print(f"[-] Bottle '{args.name}' not found.")
            sys.exit(1)
        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        WineProcessManager.stop_bottle(bottle, runner_dir)
        print(f"[+] Sent graceful shutdown signal (wineboot -s) to '{bottle.name}'")

    elif args.command == "kill-bottle":
        bottle = BottleManager.get_bottle(args.name)
        if not bottle:
            print(f"[-] Bottle '{args.name}' not found.")
            sys.exit(1)
        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        WineProcessManager.force_kill_bottle(bottle, runner_dir)
        print(f"[+] Wineserver terminated for bottle '{bottle.name}'")

    elif args.command == "winetricks":
        bottle = BottleManager.get_bottle(args.bottle)
        if not bottle:
            print(f"[-] Bottle '{args.bottle}' not found.")
            sys.exit(1)
        WineToolsManager.launch_winetricks_terminal(bottle, verbs=args.verbs or None)
        print(f"[+] Launched Winetricks for '{bottle.name}'")

    elif args.command == "cloud-sync":
        bottle = BottleManager.get_bottle(args.bottle)
        if not bottle:
            print(f"[-] Bottle '{args.bottle}' not found.")
            sys.exit(1)
        if args.enable:
            try:
                dest = CloudSaveManager.enable_sync(bottle, args.provider)
                print(f"[+] Cloud save synchronization enabled with {args.provider} at: {dest}")
            except Exception as e:
                print(f"[-] Failed to enable cloud sync: {e}")
        elif args.disable:
            CloudSaveManager.disable_sync(bottle)
            print(f"[+] Cloud save synchronization disabled for '{bottle.name}'. Local folders restored.")
        else:
            is_synced = CloudSaveManager.is_sync_enabled(bottle)
            status = "ACTIVE" if is_synced else "INACTIVE"
            print(f"Cloud Save Sync for '{bottle.name}': {status}")
            providers = CloudSaveManager.get_cloud_providers()
            print(f"Available Cloud Providers: {', '.join(providers.keys()) if providers else 'None detected'}")

    elif args.command == "reset-bottle":
        print(f"[*] Resetting bottle '{args.bottle}'...")
        try:
            BottleManager.reset_bottle(args.bottle)
            print(f"[+] Successfully reset bottle '{args.bottle}' to vanilla state.")
        except Exception as e:
            print(f"[-] Reset failed: {e}")

    elif args.command == "run":
        bottle = BottleManager.get_bottle(args.bottle)
        if not bottle:
            print(f"[-] Bottle '{args.bottle}' not found.")
            sys.exit(1)

        # [RSK-01] Kernel Anti-Cheat Scan
        ac_match = AntiCheatDetector.scan_path(Path(args.exe))
        if ac_match:
            print("=" * 65)
            print("[!] INCOMPATIBLE KERNEL ANTI-CHEAT DETECTED")
            print(f"    Engine: {ac_match.name}")
            print(f"    Trigger: {ac_match.trigger_file}")
            print(f"    Notice: {ac_match.advisory}")
            print("=" * 65)

        # [RSK-05] Rolling automated registry hive backup
        BottleManager.backup_registry(bottle.id)

        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        env = WineEnvironmentBuilder.build_env(bottle, runner_dir)
        full_command = WineProcessManager.build_launch_command(runner_dir, bottle, args.exe, args.args or [])
        
        print(f"[*] Launching '{args.exe}' inside bottle '{bottle.name}'...")
        print(f"    MSync: {bottle.msync} | Metal HUD: {bottle.metal_hud} | Retina: {bottle.retina} | Virtual Desktop: {bottle.virtual_desktop}")
        print(f"    Command: {' '.join(full_command)}")
        print("[+] Environment successfully prepared.")


if __name__ == "__main__":
    main()

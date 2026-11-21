"""
[FR-06, FR-20] Wine System Utilities & Registry Tooling Launcher.
Enables launching winecfg, regedit, wine cmd, and dynamic Windows version toggles.
Decoupled from GUI frameworks.
"""

import shlex
import subprocess
from pathlib import Path
from typing import Optional

from ravlator.core.bottle import BottleManager
from ravlator.core.models import BottleConfig, WindowsVersion
from ravlator.core.process import WineEnvironmentBuilder, WineProcessManager
from ravlator.core.runner import RunnerManager


class WineToolsManager:
    """Launches built-in Wine management utilities inside an isolated bottle."""

    @classmethod
    def launch_tool(cls, bottle: BottleConfig, tool_name: str, args: Optional[list] = None) -> subprocess.Popen:
        """Spawns an internal Wine tool (e.g. winecfg, regedit, cmd, taskmgr)."""
        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        wine_bin = WineProcessManager.get_wine_bin(runner_dir)
        env = WineEnvironmentBuilder.build_env(bottle, runner_dir)

        if not wine_bin.exists():
            raise FileNotFoundError(f"Wine binary not found in runner: {runner_dir}")

        cmd = [str(wine_bin), tool_name] + (args or [])
        return subprocess.Popen(cmd, env=env)

    @classmethod
    def launch_winecfg(cls, bottle: BottleConfig) -> subprocess.Popen:
        """[FR-06] Opens the Wine configuration panel."""
        return cls.launch_tool(bottle, "winecfg")

    @classmethod
    def launch_regedit(cls, bottle: BottleConfig) -> subprocess.Popen:
        """Opens the Windows Registry Editor inside the bottle."""
        return cls.launch_tool(bottle, "regedit")

    @classmethod
    def launch_taskmgr(cls, bottle: BottleConfig) -> subprocess.Popen:
        """Opens the Windows Task Manager inside the bottle."""
        return cls.launch_tool(bottle, "taskmgr")

    @classmethod
    def launch_terminal_cmd(cls, bottle: BottleConfig) -> None:
        """Opens macOS Terminal.app pre-configured inside the Wine command prompt."""
        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        env = WineEnvironmentBuilder.build_env(bottle, runner_dir)
        wine_bin = WineProcessManager.get_wine_bin(runner_dir)
        b_dir = BottleManager.get_bottle_dir(bottle.id)

        # Create temporary script for Terminal to run with secure shell quoting [VULN-03]
        script_path = b_dir / "launch_terminal.sh"
        export_cmds = "\n".join(f"export {k}={shlex.quote(str(v))}" for k, v in env.items())
        q_drive_c = shlex.quote(str(b_dir / "drive_c"))
        q_wine_bin = shlex.quote(str(wine_bin))
        safe_name = bottle.name.replace("\n", " ").replace("\r", " ")

        script_content = f"""#!/bin/sh
{export_cmds}
cd {q_drive_c}
echo "=== Ravlator: Wine Command Prompt ({safe_name}) ==="
exec {q_wine_bin} cmd
"""
        script_path.write_text(script_content)
        script_path.chmod(0o755)

        # Tell macOS to open in Terminal.app
        subprocess.run(["open", "-a", "Terminal", str(script_path)])

    @classmethod
    def set_windows_version(cls, bottle: BottleConfig, version: WindowsVersion) -> bool:
        """[FR-06] Configures the reported Windows version."""
        bottle.windows_version = version
        BottleManager.save_bottle_config(bottle)

        try:
            # Map WindowsVersion enum to winecfg parameter
            ver_arg = version.value  # 'win10', 'win11', 'win7'
            cls.launch_tool(bottle, "winecfg", ["-v", ver_arg])
            return True
        except Exception:
            return False

    @classmethod
    def get_winetricks_path(cls, runner_path: Path) -> Optional[Path]:
        """[FR-20] Locates winetricks script in runner or system paths."""
        candidates = [
            runner_path / "bin" / "winetricks",
            Path("/opt/homebrew/bin/winetricks"),
            Path("/usr/local/bin/winetricks")
        ]
        for c in candidates:
            if c.exists():
                return c
        return None

    @classmethod
    def launch_winetricks_terminal(cls, bottle: BottleConfig, verbs: Optional[list] = None) -> None:
        """
        [FR-20] Spawns winetricks inside macOS Terminal configured with bottle environment.
        """
        runner_dir = RunnerManager.get_runner_dir(bottle.runner_id)
        env = WineEnvironmentBuilder.build_env(bottle, runner_dir)
        wine_bin = WineProcessManager.get_wine_bin(runner_dir)
        b_dir = BottleManager.get_bottle_dir(bottle.id)

        wt_bin = cls.get_winetricks_path(runner_dir)
        if wt_bin:
            escaped_verbs = " ".join(shlex.quote(str(v)) for v in verbs) if verbs else ""
            cmd_str = f"{shlex.quote(str(wt_bin))} {escaped_verbs}".strip()
        else:
            cmd_str = 'echo "[-] winetricks was not found in runner or Homebrew.\nInstall it via: brew install winetricks"'

        script_path = b_dir / "launch_winetricks.sh"
        export_cmds = "\n".join(f"export {k}={shlex.quote(str(v))}" for k, v in env.items())
        q_b_dir = shlex.quote(str(b_dir))
        q_wine_bin = shlex.quote(str(wine_bin))
        safe_name = bottle.name.replace("\n", " ").replace("\r", " ")

        script_content = f"""#!/bin/sh
{export_cmds}
export WINE={q_wine_bin}
cd {q_b_dir}
echo "=== Ravlator: Winetricks ({safe_name}) ==="
{cmd_str}
"""
        script_path.write_text(script_content)
        script_path.chmod(0o755)
        subprocess.run(["open", "-a", "Terminal", str(script_path)])

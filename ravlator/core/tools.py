"""
[FR-06, FR-20] Wine System Utilities & Registry Tooling Launcher.
Enables launching winecfg, regedit, wine cmd, and dynamic Windows version toggles.
Decoupled from GUI frameworks.
"""

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

        # Create temporary script for Terminal to run
        script_path = b_dir / "launch_terminal.sh"
        export_cmds = "\n".join(f'export {k}="{v}"' for k, v in env.items())
        script_content = f"""#!/bin/sh
{export_cmds}
cd "{b_dir}/drive_c"
echo "=== Ravlator: Wine Command Prompt ({bottle.name}) ==="
"{wine_bin}" cmd
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

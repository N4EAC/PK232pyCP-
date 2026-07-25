param([string]$ProjectRoot = ".")
$ErrorActionPreference = "Stop"
$root = (Resolve-Path $ProjectRoot).Path
$ui = Join-Path $root "src\pk232py\ui"
$tncPath = Join-Path $ui "tnc_config_dialog.py"
$mainPath = Join-Path $ui "main_window.py"
$themeSource = Join-Path $PSScriptRoot "src\pk232py\ui\themes.py"
$themeTarget = Join-Path $ui "themes.py"
foreach ($p in @($tncPath,$mainPath,$themeTarget)) { if (-not (Test-Path $p)) { throw "Required source file not found: $p" } }
foreach ($p in @($tncPath,$mainPath,$themeTarget)) { if (-not (Test-Path "$p.original")) { Copy-Item $p "$p.original" } }
Copy-Item $themeSource $themeTarget -Force

$py = @'
from pathlib import Path
import sys
root = Path(sys.argv[1])
tnc_path = root / 'src/pk232py/ui/tnc_config_dialog.py'
main_path = root / 'src/pk232py/ui/main_window.py'

def replace_once(text, old, new, label):
    if new in text:
        return text
    if old not in text:
        raise SystemExit(f'Patch point not found: {label}. The upstream source may have changed.')
    return text.replace(old, new, 1)

t = tnc_path.read_text(encoding='utf-8')
t = replace_once(t,
'    port_name:         str  = ""\n',
'    model:             str  = "PK232MBX"\n    port_name:         str  = ""\n', 'TncConfig model field')
t = replace_once(t,
'        # Port selector with refresh button\n',
'        # Hardware selector\n        self._model_combo = QComboBox()\n        self._model_combo.addItem("AEA PK-232 / PK-232MBX", "PK232MBX")\n        self._model_combo.addItem("MFJ-1278 / MFJ-1278B (Terminal Mode)", "MFJ1278")\n        self._model_combo.currentIndexChanged.connect(self._on_model_changed)\n        form.addRow("Hardware:", self._model_combo)\n\n        # Port selector with refresh button\n', 'hardware selector')
t = replace_once(t,
'        info = QLabel(\n            "<small><i>TNC Model: AEA PK-232 / PK-232MBX &nbsp;|&nbsp;"\n            " Firmware: v7.1 / v7.2</i></small>"\n        )\n',
'        self._info = QLabel()\n        info = self._info\n', 'info label')
t = replace_once(t,
'    def _populate(self, cfg: TncConfig) -> None:\n        """Pre-fill widgets from *cfg*."""\n',
'    def _on_model_changed(self) -> None:\n        mfj = self._model_combo.currentData() == "MFJ1278"\n        self._hm_exit_cb.setEnabled(not mfj)\n        self._fast_init_cb.setEnabled(not mfj)\n        if mfj:\n            self._hm_exit_cb.setChecked(False)\n            self._fast_init_cb.setChecked(True)\n            self._rtscts_cb.setToolTip("MFJ-1278 cabling varies. Enable RTS/CTS only when wired.")\n            self._info.setText("<small><i>MFJ-1278 support: terminal/command mode. PK-232 binary Host Mode is disabled.</i></small>")\n        else:\n            self._info.setText("<small><i>TNC Model: AEA PK-232 / PK-232MBX &nbsp;|&nbsp; Firmware: v7.1 / v7.2</i></small>")\n\n    def _populate(self, cfg: TncConfig) -> None:\n        """Pre-fill widgets from *cfg*."""\n        idx = self._model_combo.findData(getattr(cfg, "model", "PK232MBX"))\n        self._model_combo.setCurrentIndex(max(0, idx))\n        self._on_model_changed()\n', 'populate model')
t = replace_once(t,
'        return TncConfig(\n            port_name',
'        return TncConfig(\n            model             = self._model_combo.currentData(),\n            port_name', 'return model')
tnc_path.write_text(t, encoding='utf-8')

m = main_path.read_text(encoding='utf-8')
m = replace_once(m,
'        if self._app_config.tnc.port:\n            self._config.port_name = self._app_config.tnc.port\n',
'        self._config.model = getattr(self._app_config.tnc, "model", "PK232MBX")\n        if self._app_config.tnc.port:\n            self._config.port_name = self._app_config.tnc.port\n', 'load model')
m = replace_once(m,
'            self._app_config.tnc.port  = self._config.port_name\n            self._app_config.tnc.tbaud = self._config.baudrate\n',
'            self._app_config.tnc.model = self._config.model\n            self._app_config.tnc.port  = self._config.port_name\n            self._app_config.tnc.tbaud = self._config.baudrate\n', 'save model')
m = replace_once(m,
'    def _on_connect_host(self) -> None:\n        """Connect, upload parameters and enter Host Mode automatically."""\n        if not self._open_connect_dialog():\n            return\n        self._connect_mode = "host"\n        self._serial.init_tnc()\n',
'    def _on_connect_host(self) -> None:\n        """Connect, upload parameters and enter Host Mode automatically."""\n        if not self._open_connect_dialog():\n            return\n        if self._config.model == "MFJ1278":\n            QMessageBox.information(self, "MFJ-1278 Terminal Mode",\n                "MFJ-1278 uses a different host protocol. This profile connects in terminal/command mode; PK-232 Host Mode is unavailable.")\n            self._connect_mode = "verbose"\n        else:\n            self._connect_mode = "host"\n        self._serial.init_tnc()\n', 'host protection')
m = replace_once(m,
'        connect_mode = self._connect_mode\n        fast_init    = self._config.fast_init\n',
'        connect_mode = self._connect_mode\n        is_mfj       = self._config.model == "MFJ1278"\n        fast_init    = self._config.fast_init or is_mfj\n        if is_mfj:\n            self._vt_append("[SYS] MFJ-1278 terminal profile active -- PK-232 parameter upload and Host Mode disabled\\n")\n            self._log_monitor("[SYS] Hardware: MFJ-1278 terminal compatibility")\n', 'MFJ fast init')
main_path.write_text(m, encoding='utf-8')
print('MFJ-1278 terminal compatibility patch applied.')
'@
$tmp = Join-Path $env:TEMP "pk232py_apply_mfj1278.py"
Set-Content -Path $tmp -Value $py -Encoding UTF8
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command py -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python was not found in PATH." }
& $python.Source $tmp $root
if ($LASTEXITCODE -ne 0) { throw "Source patch failed." }
Copy-Item (Join-Path $PSScriptRoot "build_windows_cyberpunk.ps1") (Join-Path $root "build_windows_cyberpunk.ps1") -Force
Copy-Item (Join-Path $PSScriptRoot "build.exe.bat") (Join-Path $root "build.exe.bat") -Force
Copy-Item (Join-Path $PSScriptRoot "PK232PY_Cyberpunk_MFJ1278.iss") (Join-Path $root "PK232PY_Cyberpunk_MFJ1278.iss") -Force
Write-Host "Cyberpunk + MFJ-1278 terminal compatibility installed." -ForegroundColor Cyan
Write-Host "Run build.exe.bat from the project root to build the EXE." -ForegroundColor Green

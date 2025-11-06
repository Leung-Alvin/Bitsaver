import os
import sys
import json
import time
import math
import ctypes
import hashlib
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit, QComboBox, QCheckBox,
    QTextEdit, QMessageBox, QProgressBar, QFileDialog, QRadioButton, QButtonGroup,
    QDialog, QDialogButtonBox, QFormLayout, QFrame
)

def run_powershell(ps_command: str) -> subprocess.CompletedProcess:
    exe = shutil.which("powershell") or shutil.which("powershell.exe")
    if not exe:
        raise RuntimeError("PowerShell not found in PATH.")
    return subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )

def is_windows() -> bool:
    return os.name == "nt"

@dataclass
class DiskInfo:
    number: int
    size: int
    bus_type: str
    friendly_name: str
    is_system: bool
    is_boot: bool
    is_readonly: bool
    is_removable: bool
    partition_style: str
    letters: List[str]

def run_powershell_json(ps_command: str) -> Any:
    cp = run_powershell(ps_command)
    if cp.returncode != 0:
        raise RuntimeError(cp.stderr.strip() or "Unknown PowerShell error.")
    text = cp.stdout.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from PowerShell: {e}\nOutput: {text[:1000]}")

def list_disks() -> List[DiskInfo]:
    if not is_windows():
        raise RuntimeError("Windows only.")
    ps = r"""
$disks = Get-Disk | Select-Object Number, Size, BusType, FriendlyName, IsSystem, IsBoot, IsReadOnly, IsRemovable, PartitionStyle
$result = @()
foreach ($d in $disks) {
    $letters = @()
    try {
        $letters = (Get-Partition -DiskNumber $d.Number | Where-Object { $_.DriveLetter } | Select-Object -ExpandProperty DriveLetter)
    } catch {}
    if ($letters -eq $null) { $letters = @() }
    $obj = [PSCustomObject]@{
        Number = $d.Number
        Size = $d.Size
        BusType = [string]$d.BusType
        FriendlyName = [string]$d.FriendlyName
        IsSystem = [bool]$d.IsSystem
        IsBoot = [bool]$d.IsBoot
        IsReadOnly = [bool]$d.IsReadOnly
        IsRemovable = [bool]$d.IsRemovable
        PartitionStyle = [string]$d.PartitionStyle
        Letters = $letters
    }
    $result += $obj
}
$result | ConvertTo-Json -Depth 4
"""
    data = run_powershell_json(ps)
    if data is None:
        return []
    if isinstance(data, dict):
        data = [data]
    out: List[DiskInfo] = []
    for d in data:
        out.append(DiskInfo(
            number=int(d.get("Number")),
            size=int(d.get("Size") or 0),
            bus_type=str(d.get("BusType") or ""),
            friendly_name=str(d.get("FriendlyName") or ""),
            is_system=bool(d.get("IsSystem")),
            is_boot=bool(d.get("IsBoot")),
            is_readonly=bool(d.get("IsReadOnly")),
            is_removable=bool(d.get("IsRemovable")),
            partition_style=str(d.get("PartitionStyle") or ""),
            letters=list(d.get("Letters") or [])
        ))
    return out

def get_hostname():
    ps = "hostname"
    result = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True)
    if result.returncode == 0:
        return (result.stdout)
    else:
        return ("Error:", result.stderr)

def get_bitlocker_status():
    ps = "Get-BitLockerVolume"
    result = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True)
    if result.returncode == 0:
        return (result.stdout)
    else:
        return ("Error:", result.stderr)

if __name__ == '__main__' :
    print("Computer Name:", get_hostname())
    disks = list_disks()
    for disk in disks:
            attrs = vars(disk)
            print('\n'.join("%s: %s" % item for item in attrs.items()))
            print('\n')

    #print(get_bitlocker_status())

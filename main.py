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

import pyuac

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
    disk_number: int
    size_bytes: int
    bus_type: str
    model_name: str
    is_system: bool
    is_boot: bool
    is_readonly: bool
    is_removable: bool
    partition_style: str
    letters: List[str]
    volume_type : str
    volume_status : str
    capacity_GB : float

    def __post_init__(self):
        if self.volume_type is None:
            self.volume_type = ''
        if self.volume_status is None:
            self.volume_status = ''
        if self.capacity_GB is None:
            self.capacity_GB = 0.00



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
            disk_number=int(d.get("Number")),
            size_bytes=int(d.get("Size") or 0),
            bus_type=str(d.get("BusType") or ""),
            model_name=str(d.get("FriendlyName") or ""),
            is_system=bool(d.get("IsSystem")),
            is_boot=bool(d.get("IsBoot")),
            is_readonly=bool(d.get("IsReadOnly")),
            is_removable=bool(d.get("IsRemovable")),
            partition_style=str(d.get("PartitionStyle") or ""),
            letters=list(d.get("Letters") or []),
            volume_type="",
            volume_status = "",
            capacity_GB=0.00
            )
        )
    return out

def get_hostname():
    ps = "hostname"
    result = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True)
    if result.returncode == 0:
        return (result.stdout)
    else:
        return ("Error:", result.stderr)

def get_bitlocker_status():
    ps = "Get-BitLockerVolume | Select-Object -Property VolumeType, MountPoint, CapacityGB, VolumeStatus | ConvertTo-Json"
    results = subprocess.run(["powershell", "-Command", ps ], capture_output=True, text=True)
    if results.returncode == 0:
        return (results.stdout)
    else:
        return ("Error:", results.stderr)


def main():
    print("Computer Name:", get_hostname())
    val = get_bitlocker_status()
    val_json = json.loads(val)
    for jso in val_json:
       jso['MountPoint'] = jso['MountPoint'].replace(':','')
       if jso['VolumeType'] == 0:
           jso['VolumeType'] = 'Operating System'
       elif jso['VolumeType'] == 1:
           jso['VolumeType'] = 'Data'
       else:
           raise ValueError('A new type of Volume has been found:',jso['VolumeType'])

       if jso['VolumeStatus'] == 0:
           jso['VolumeStatus'] = 'Fully Decrypted'
       elif jso['VolumeStatus'] == 1:
           jso['VolumeStatus'] = 'Fully Encrypted'
       else:
           raise ValueError('A new type of VolumeStatus has been found:', jso['VolumeStatus'])
    disks = list_disks()
    for i in range(len(disks)):
        disks[i].volume_type = val_json[i]['VolumeType']
        disks[i].volume_status= val_json[i]['VolumeStatus']
        disks[i].capacity_GB = val_json[i]['CapacityGB']
        attrs = vars(disks[i])
        attrs['letters'] = ''.join(attrs['letters'])
        print('\n'.join("%s: %s" % item for item in attrs.items()))
        print('\n')
    input("Press enter to close the window.")

if __name__ == '__main__' :
    if not pyuac.isUserAdmin():
        pyuac.runAsAdmin()
    else:
        main()

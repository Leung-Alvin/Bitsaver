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
from os import system
import hexdump
import msvcrt
import ctypes
import binascii

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QLineEdit, QComboBox, QCheckBox,
    QTextEdit, QMessageBox, QProgressBar, QFileDialog, QRadioButton, QButtonGroup,
    QDialog, QDialogButtonBox, QFormLayout, QFrame
)

import pyuac
RECOVERY_DIR = "./recovery_keys"
SECURE_STRING = "1234"
def run_powershell(ps_command: str) -> subprocess.CompletedProcess:
    exe = shutil.which("powershell") or shutil.which("powershell.exe")
    if not exe:
        raise RuntimeError("PowerShell not found in PATH.")
    return subprocess.run(
        [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
def parse_colon_lines(stdout: str):
    d = {}
    for line in stdout.splitlines():
        if ":" in line:
            k,v = line.split(":",1)
            d[k.strip()] = v.strip()
    return d

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

def select_disk(disk_number, disks):
    try:
        if disks[disk_number].is_boot == True:
            return ("Error: Cannot select Boot disk.")
        else:
            return disks[disk_number]
    except:
        return ("Error: Disk does not exist.")
def enable_bitlocker(mount_point, SECURE_STRING):
    formatted_mount_point = mount_point.replace("[","").replace(']',"")
    print(formatted_mount_point)
#    ps = "Enable-BitLocker -MountPoint " + "\""
#    results = subprocess.run(["powershell", "-Command", ps ], capture_output=True, text=True)
#    if results.returncode == 0:
#        return (results.stdout)
#    else:
#        return ("Error:", results.stderr)

def get_bitlocker_status():
    ps = "Get-BitLockerVolume | Select-Object -Property VolumeType, MountPoint, CapacityGB, VolumeStatus | ConvertTo-Json"
    results = subprocess.run(["powershell", "-Command", ps ], capture_output=True, text=True)
    if results.returncode == 0:
        return (results.stdout)
    else:
        return ("Error:", results.stderr)
def print_disks():
    #system('cls')
    print("Computer Name:", get_hostname())
    val = get_bitlocker_status()
    val_json = json.loads(val)
    if not isinstance(val_json,list):
        val_json = list() 
        val_json.append(json.loads(val))
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
        try:
            disks[i].volume_type = val_json[i]['VolumeType']
            disks[i].volume_status= val_json[i]['VolumeStatus']
            disks[i].capacity_GB = val_json[i]['CapacityGB']
        except:
            disks[i].volume_type = "Unknown"
            disks[i].volume_status = "Unknown"
        attrs = vars(disks[i])
        attrs['letters'] = ''.join(attrs['letters'])
        print('\n'.join("%s: %s" % item for item in attrs.items()))
        print('\n')

def short_print_disks():
    #system('cls')
    print('\n')
    val = get_bitlocker_status()
    val_json = json.loads(val)
    if not isinstance(val_json,list):
        val_json = list() 
        val_json.append(json.loads(val))
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
        try:
            disks[i].volume_status= val_json[i]['VolumeStatus']
        except:
            disks[i].volume_status = "Unknown"
        attrs = vars(disks[i])
        print("Disk Number:",attrs['disk_number'])
        print("Model Name:",attrs['model_name'])
        print("Boot Drive:",attrs['is_boot'])
        print("Drive Letter:",attrs['letters'])
        print("Bitlocker Status:",attrs['volume_status'])
        print('\n')

    choice = input("Enter Disk Number: ")
    print('\n')
    disk = select_disk(int(choice),disks)
    if isinstance(disk, DiskInfo):
        disk_menu(disk)
    else:
        print(disk)
def main_menu():
    while True:
        print("\n===Main Menu===")
        print("1. List Disks")
        print("2. Select Disk")
        print("3. Exit")
        choice = input("Enter choice: ")
        print('\n')

        if choice == "1":
            print_disks()

        elif choice == "2":
            short_print_disks()
        elif choice == "3":
            print("Ending")
            break
        else:
            print("Invalid Choice")

def disk_menu(disk):
    attrs = vars(disk) 
    ps = "Get-Disk " + str(attrs['disk_number']) +" | Select-Object Number, FriendlyName, LogicalSectorSize, @{Name='LBASectorCount'; Expression = { $_.Size / $_.LogicalSectorSize }}, Size"
    results = subprocess.run(["powershell", "-Command", ps ], capture_output=True, text=True)
    if results.returncode == 0:
        print(results.stdout)
    else:
        return ("Error:", results.stderr)
    disk_dict = parse_colon_lines(results.stdout)
    disk_num = disk_dict['Number']
    sector_size = disk_dict['LogicalSectorSize']
    num_sectors = disk_dict['LBASectorCount']
    while True:
        print("\n===Disk Menu===")
        print("1. Find Bitlocker Sector")
        print("2. Rebuild Bootlocker MBR")
        print("3. Read Boot Record")
        print("4. Exit")
        choice = input("Enter choice: ")
        print('\n')

        if choice == "1":
            found_sector = find_bitlocker_sector(int(sector_size), r"\\.\PhysicalDrive"+str(disk_num)) 
            partition_size = int(num_sectors) - int(found_sector)
            print("COUNT is ", partition_size)

        elif choice == "2":
            FS = input("Enter File System Type ('ntfs','fat32','exfat'): ")
            START_LBA = find_bitlocker_sector(int(sector_size), r"\\.\PhysicalDrive"+str(disk_num)) 
            COUNT = int(num_sectors) - START_LBA
            print(START_LBA,COUNT)
            disk_doppel(FS, START_LBA, COUNT, disk_num) 

        elif choice == "3":
            data = read_boot_record(disk_num)
            print(data)
        elif choice == "4":
            print("Ending")
            break
        else:
            print("Invalid Choice")

def read_boot_record(disk_number):
    disk_fd = os.open(r"\\.\PhysicalDrive"+str(disk_number), os.O_RDONLY | os.O_BINARY)
    data = os.read(disk_fd, 512)
    os.close(disk_fd)
    return(data)
def disk_doppel(fs, start, count, disk_number):
    disk_str = "disk" + str(disk_number) + ":."
    command = ".\\dd.exe boot(fs=" + fs +",start=" + str(start) + ",count=" + str(count)+"): " + disk_str
    #command = ".\\dd.exe /dl"
    print(command)
    result = subprocess.call(command)
    #print("Output:\n", result.stdout)

def main():
    print("Computer Name:", get_hostname())
    val = get_bitlocker_status()
    val_json = json.loads(val)
    if not isinstance(val_json,list):
        val_json = list() 
        print(json.loads(val))
        val_json = val_json.append(json.loads(val))
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
    print(select_disk(1,disks))

def test():
    print_disks()
    main_menu()
def find_bitlocker_sector(sector_size, dev_path):
    BLOCK_SECTORS = 128
    HEX_PATTERN = "2D4656452D46532D"
    GENERIC_READ  = 0x80000000
    FILE_SHARE_READ = 1
    OPEN_EXISTING = 3
    print("Looking for Hex Pattern " + HEX_PATTERN)

    CreateFile = ctypes.windll.kernel32.CreateFileW
    ReadFile   = ctypes.windll.kernel32.ReadFile
    SetFilePointer = ctypes.windll.kernel32.SetFilePointer
    CloseHandle = ctypes.windll.kernel32.CloseHandle

    handle = CreateFile(
        dev_path,
        GENERIC_READ,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        0,
        None
    )

    if handle == -1:
        raise OSError("Could not open raw device. Run as Administrator.")


    # -------------------------
    # PREPARE SEARCH PATTERN
    # -------------------------
    pattern = binascii.unhexlify(HEX_PATTERN)


    # -------------------------
    # GET DISK SIZE USING IOCTL
    # -------------------------
    import ctypes.wintypes as wt

    GET_LENGTH_INFO = 0x0007405C
    size_buf = ctypes.c_ulonglong()
    returned = ctypes.c_ulong(0)

    ioctl = ctypes.windll.kernel32.DeviceIoControl
    ok = ioctl(
        handle,
        GET_LENGTH_INFO,
        None, 0,
        ctypes.byref(size_buf), ctypes.sizeof(size_buf),
        ctypes.byref(returned),
        None
    )

    if not ok:
        raise OSError("Could not query disk size via DeviceIoControl.")

    disk_size = size_buf.value
    total_sectors = disk_size // sector_size

    print(f"Disk size: {disk_size:,} bytes")
    print(f"Total sectors: {total_sectors:,}")
    print(f"Searching for pattern: {HEX_PATTERN}")


    # -------------------------
    # MAIN SEARCH LOOP
    # -------------------------
    read_bytes = BLOCK_SECTORS * sector_size
    buffer = ctypes.create_string_buffer(read_bytes)
    bytes_read = ctypes.c_ulong(0)

    sector_index = 0
    matches = []

    print("\nStarting scan...\n")

    while sector_index < total_sectors:
        # seek to sector_index
        offset = sector_index * sector_size
        low = offset & 0xFFFFFFFF
        high = (offset >> 32) & 0xFFFFFFFF
        high_ptr = ctypes.c_long(high)

        SetFilePointer(handle, low, ctypes.byref(high_ptr), 0)

        # read block
        ok = ReadFile(handle, buffer, read_bytes, ctypes.byref(bytes_read), None)
        if not ok:
            print(f"Read failed at sector {sector_index}")
            break

        data = buffer.raw[:bytes_read.value]

        # search inside this block
        idx = data.find(pattern)
        if idx != -1:
            # Convert byte offset → sector #
            found_byte_offset = idx
            found_sector = sector_index + (found_byte_offset // sector_size)
            matches.append(found_sector)
            sector_offset = (found_sector - sector_index) * sector_size
            sector_data = data[sector_offset:sector_offset + sector_size]
            print(f"FOUND MATCH at sector {found_sector}")
            hexdump.hexdump(sector_data)
            print("=== END SECTOR ===\n")
            CloseHandle(handle)
            return found_sector

        sector_index += BLOCK_SECTORS


    print("\nScan complete.")
    if matches:
        print("Matches at sectors:", matches)
    else:
        print("No matches found.")    

def test_hexdump1(sector_size, LBA, dev_path):
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 1
    OPEN_EXISTING = 3
    CreateFile = ctypes.windll.kernel32.CreateFileW
    ReadFile = ctypes.windll.kernel32.ReadFile
    SetFilePointer = ctypes.windll.kernel32.SetFilePointer
    pattern =  "2D4656452D46532D"

    handle = CreateFile(dev_path, GENERIC_READ, FILE_SHARE_READ, None, OPEN_EXISTING, 0, None)

    if handle == -1:
        raise OSError("Could not open device. Run as Administrator.")

    offset = LBA * sector_size
    low = offset & 0xFFFFFFFF
    high = (offset >> 32) & 0xFFFFFFFF

    res = SetFilePointer(handle, low, ctypes.byref(ctypes.c_long(high)), 0)
    if res == 0xFFFFFFFF:
        raise OSError("Seek failed-invalid LBA or drive offset.")

    buffer = ctypes.create_string_buffer(sector_size)
    bytes_read = ctypes.c_ulong(0)

    ok = ReadFile(handle,buffer,sector_size, ctypes.byref(bytes_read), None)

    if not ok or bytes_read.value != sector_size:
        raise OSerror("Read failed-drive may deny raw I/O or sector out of range.")

    data = buffer.raw
    hexdump.hexdump(data)

    print(f"\nRead {sector_size} bytes from LBA {LBA} on {dev_path}")

if __name__ == '__main__':
    if not pyuac.isUserAdmin():
        pyuac.runAsAdmin()
    else:
        #main()
        test()

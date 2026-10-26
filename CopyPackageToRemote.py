# ==========================================================
#  Start of program
# ========================================================== 

import json
import os
import sys
import paramiko
from datetime import datetime

# ==========================================================
# Load Bench Details
# ==========================================================

def load_benches(json_file="benches.json"):
    try:
        with open(json_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[FAIL] Unable to read {json_file}: {e}")
        sys.exit(1)
# ==========================================================
# Connect SSH
# ==========================================================

def connect_to_bench(creds):

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy()
        )

        ssh.connect(
            hostname=creds["ip_address"],
            port=int(creds["port"]),
            username=creds["username"],
            password=creds["password"]
        )

        print(
            f"[PASS] Connected to "
            f"{creds['ip_address']}"
        )

        return ssh

    except Exception as e:
        print(f"[FAIL] Connection Failed : {e}")
        sys.exit(1)


# ==========================================================
# Ubuntu Version
# ==========================================================

def check_ubuntu_version(ssh):

    stdin, stdout, stderr = ssh.exec_command(
        "lsb_release -rs"
    )

    ubuntu_version = stdout.read().decode().strip()

    print(f"Ubuntu Version : {ubuntu_version}")

    if ubuntu_version.startswith("16"):
        print("[PASS] Ubuntu Supported")
        return True

    if ubuntu_version.startswith("24"):
        print(f"[FAIL] Ubuntu {ubuntu_version} not supported")
        return None

    elif ubuntu_version.startswith("16"):
        print(f"[PASS] Ubuntu Version : {ubuntu_version}")
        return ubuntu_version

    else:
        print(f"[FAIL] Unsupported Ubuntu Version : {ubuntu_version}")
        return None

# ==========================================================
# Find Folder
# ==========================================================

# ==========================================================
# Find Folder
# ==========================================================

def find_folder(ssh, folder_name):

    cmd = (
        f'find "/home/ubuntu" '
        f'-type d '
        f'-name "{folder_name}" '
        f'-not -path "*/backup/*" '
        f'-not -path "*/.local/share/Trash/*" '
        f'| head -1'
    )

    output, error = run_command(
        ssh,
        cmd
    )

    return output

# ==========================================================
# Run Command Helper
# ==========================================================

def run_command(ssh, cmd):

    stdin, stdout, stderr = ssh.exec_command(cmd)

    output = stdout.read().decode().strip()
    error = stderr.read().decode().strip()

    return output, error

# ==========================================================
# Main
# ==========================================================

benches = load_benches()

print("\nAvailable Benches:\n")

for i, bench in enumerate(benches.keys(), start=1):
    print(f"{i}. {bench}")

source_bench = input(
    "\nEnter Source Bench : "
).strip()

dest_bench = input(
    "Enter Destination Bench : "
).strip()

if source_bench not in benches:
    print("[FAIL] Invalid Source Bench")
    sys.exit(1)

if dest_bench not in benches:
    print("[FAIL] Invalid Destination Bench")
    sys.exit(1)

source_creds = benches[source_bench]
dest_creds = benches[dest_bench]

# ==========================================================
# SOURCE
# ==========================================================

print(
    f"\n========== SOURCE : {source_bench} =========="
)

source_ssh = connect_to_bench(source_creds)

if not check_ubuntu_version(source_ssh):
    sys.exit(1)

# ==========================================================
# Search AstraNT folders
# ==========================================================

firmware_folder = find_folder(
    source_ssh,
    "AstraNT_Firmware"
)

astrant_folder = find_folder(
    source_ssh,
    "AstraNT"
)

print(f"\nFirmware Folder : {firmware_folder}")
print(f"AstraNT Folder  : {astrant_folder}")

if not firmware_folder:
    print("[FAIL] AstraNT_Firmware Not Found")
    sys.exit(1)

if not astrant_folder:
    print("[FAIL] AstraNT Not Found")
    sys.exit(1)

print("[PASS] Required folders found")

# ==========================================================
# Create Release Package
# ==========================================================

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

release_folder = (f"/home/ubuntu/" f"AstraNT_Firmware_{timestamp}")

commands = [
    f'mkdir -p "{release_folder}"',
    f'cp -r "{astrant_folder}" "{release_folder}/"',
    f'cp -r "{firmware_folder}" "{release_folder}/"'
]

for cmd in commands:
    output, error = run_command(source_ssh, cmd)

    if error:
        print(f"[FAIL] {error}")
        sys.exit(1)

print( f"\n[PASS] Package Created:\n" f"{release_folder}")

# ==========================================================
# Verify Package On Source
# ==========================================================

print("\nPackage Contents:\n")

stdin, stdout, stderr = source_ssh.exec_command( f'ls -ltr "{release_folder}"' )

print(stdout.read().decode())

# ==========================================================
# DESTINATION
# ==========================================================

print(f"\n========== DESTINATION : " f"{dest_bench} ==========")

dest_ssh = connect_to_bench(dest_creds)

if not check_ubuntu_version(dest_ssh):
    sys.exit(1)

# ==========================================================
# Create release + backup folders
# ==========================================================

run_command( dest_ssh, 'mkdir -p "/home/ubuntu/release"')

run_command( dest_ssh, 'mkdir -p "/home/ubuntu/backup"')

# ==========================================================
# Move Existing Package To Backup
# ==========================================================

backup_cmd = (
    'find /home/ubuntu '
    '-maxdepth 1 '
    '-type d '
    '-name "AstraNT_Firmware_*" '
    '-exec mv {} /home/ubuntu/backup/ \\;'
)

output, error = run_command( dest_ssh, backup_cmd)

print( "[PASS] Existing Packages " "Moved To Backup")

# ==========================================================
# Copy Package To Destination
# ==========================================================

copy_cmd = (
    f'sshpass -p "{dest_creds["password"]}" '
    f'scp -r '
    f'-o StrictHostKeyChecking=no '
    f'-o UserKnownHostsFile=/dev/null '
    f'"{release_folder}" '
    f'{dest_creds["username"]}@'
    f'{dest_creds["ip_address"]}:'
    f'/home/ubuntu/'
)

print("\nCopying Package...")

stdin, stdout, stderr = source_ssh.exec_command(copy_cmd)
copy_error = stderr.read().decode()

if ( copy_error and "Warning:" not in copy_error ):
    print(f"[FAIL] {copy_error}")
    sys.exit(1)

print("[PASS] Package Copied")

# ==========================================================
# Verify Destination Package
# ==========================================================

verify_cmd = ( 'find /home/ubuntu ' '-maxdepth 1 ' '-type d ' '-name "AstraNT_Firmware_*" ' '| sort | tail -1')

stdin, stdout, stderr = dest_ssh.exec_command(verify_cmd)

latest_package = stdout.read().decode().strip()

if not latest_package:
    print("[FAIL] Verification Failed")
    sys.exit(1)

print(f"\n[PASS] Latest Package Found:\n" f"{latest_package}")

stdin, stdout, stderr = dest_ssh.exec_command(
    f'ls -ltr "{latest_package}"'
)

contents = stdout.read().decode()

print("\nPackage Contents:\n")
print(contents)

# ==========================================================
# Validate AstraNT Folder
# ==========================================================

check_astrant = ( f'test -d "{latest_package}/AstraNT" ' f'&& echo FOUND')

stdin, stdout, stderr = dest_ssh.exec_command(check_astrant)

if "FOUND" not in stdout.read().decode():
    print("[FAIL] AstraNT Missing")
    sys.exit(1)

# ==========================================================
# Validate AstraNT_Firmware Folder
# ==========================================================

check_firmware = ( f'test -d ' f'"{latest_package}/AstraNT_Firmware" ' f'&& echo FOUND')

stdin, stdout, stderr = dest_ssh.exec_command(check_firmware)

if "FOUND" not in stdout.read().decode():
    print("[FAIL] AstraNT_Firmware Missing")
    sys.exit(1)

# ==========================================================
# Backup Verification
# ==========================================================

print("\nBackup Folder Contents:\n")

stdin, stdout, stderr = dest_ssh.exec_command('ls -ltr /home/ubuntu/backup')

print(stdout.read().decode())

# ==========================================================
# Completed
# ==========================================================

print(
    "\n========================================"
)
print(
    "[PASS] Release Transfer Completed Successfully"
)
print(
    "========================================"
)

source_ssh.close()
dest_ssh.close()
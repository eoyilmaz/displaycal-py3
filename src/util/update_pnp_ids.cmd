@echo off

curl -o 20-acpi-vendor.hwdb https://raw.githubusercontent.com/systemd/systemd/master/hwdb/20-acpi-vendor.hwdb

python "%~dp0convert_hwdb_to_pnp_ids.py" 20-acpi-vendor.hwdb

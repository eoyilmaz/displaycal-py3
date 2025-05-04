curl -o 20-acpi-vendor.hwdb https://github.com/systemd/systemd/blob/master/hwdb/20-acpi-vendor.hwdb

python3 "`dirname \"$0\"`/convert_hwdb_to_pnp_ids.py" 20-acpi-vendor.hwdb

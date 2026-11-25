#!/bin/ash
set -eu

runtime_dir=/tmp/watchdog-mosquitto
rm -rf "$runtime_dir"
mkdir -p "$runtime_dir"

cp /run/watchdog/mosquitto.conf "$runtime_dir/mosquitto.conf"
cp /run/watchdog/acl "$runtime_dir/acl"
cp /run/watchdog/passwd "$runtime_dir/passwd"

chown -R mosquitto:mosquitto "$runtime_dir"
chmod 0700 "$runtime_dir" "$runtime_dir/mosquitto.conf" "$runtime_dir/acl" "$runtime_dir/passwd"

exec /docker-entrypoint.sh /usr/sbin/mosquitto -c "$runtime_dir/mosquitto.conf"

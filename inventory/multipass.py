#!/usr/bin/env python3

import ipaddress
import json
import subprocess
import sys

NETWORK = ipaddress.ip_network("10.200.74.0/24")

SERVERS = ["controlpanel"]
AGENTS = ["worker1", "worker2", "worker3"]
EXPECTED_VMS = SERVERS + AGENTS


def discover_vms():
    result = subprocess.run(
        ["multipass", "list", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )

    multipass_data = json.loads(result.stdout)

    discovered = {}

    for vm in multipass_data["list"]:
        name = vm["name"]

        if name not in EXPECTED_VMS:
            continue

        if vm["state"] != "Running":
            continue

        for address in vm["ipv4"]:
            ip = ipaddress.ip_address(address)

            if ip in NETWORK:
                discovered[name] = str(ip)
                break
        else:
            raise RuntimeError(
                f"No IP address found in {NETWORK} for {name}"
            )

    return discovered


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--host":
        print("{}")
        return

    discovered = discover_vms()

    inventory = {
        "rke2_servers": {
            "hosts": [
                name for name in SERVERS if name in discovered
            ]
        },
        "rke2_agents": {
            "hosts": [
                name for name in AGENTS if name in discovered
            ]
        },
        "rke2_cluster": {
            "children": ["rke2_servers", "rke2_agents"]
        },
        "_meta": {
            "hostvars": {
                name: {
                    "ansible_host": address,
                    "ansible_user": "ubuntu",
                }
                for name, address in discovered.items()
            }
        },
    }

    print(json.dumps(inventory, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Dynamic inventory error: {exc}", file=sys.stderr)
        sys.exit(1)

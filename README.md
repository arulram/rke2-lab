# RKE2 Lab

A hands-on Kubernetes lab built on Ubuntu 24.04 using Multipass, Ansible, and RKE2.

The project automates virtual machine provisioning, Kubernetes installation, worker-node joining, cluster validation, desktop kubeconfig configuration, and persistent storage deployment.

## Architecture

The lab runs four Ubuntu 24.04 virtual machines on an Ubuntu desktop host.

| VM | Kubernetes Role | vCPU | Memory | Disk |
|---|---|---:|---:|---:|
| controlpanel | RKE2 Server | 2 | 4 GB | 20 GB |
| worker1 | RKE2 Agent | 1 | 4 GB | 15 GB |
| worker2 | RKE2 Agent | 1 | 4 GB | 15 GB |
| worker3 | RKE2 Agent | 1 | 4 GB | 15 GB |

### Technology Stack

- Ubuntu 24.04 LTS
- Multipass
- Ansible
- RKE2
- Kubernetes
- Local Path Provisioner
- Python dynamic inventory

## Repository Structure

```text
rke2-lab/
├── ansible.cfg
├── README.md
├── .gitignore
├── docs/
│   └── BUILD_FROM_SCRATCH.md
├── group_vars/
│   ├── all.yml
│   └── rke2_cluster/
│       └── vault.yml
├── inventory/
│   └── multipass.py
├── playbooks/
│   ├── 00-build-rke2-lab.yml
│   ├── 00-provision-multipass-vms.yml
│   ├── 01-prepare-nodes.yml
│   ├── 02-install-rke2-server.yml
│   ├── 03-join-rke2-workers.yml
│   ├── 04-validate-rke2-cluster.yml
│   ├── 05-configure-desktop-kubeconfig.yml
│   ├── 06-install-local-path-storage.yml
│   └── 99-destroy-multipass-vms.yml
├── roles/
│   ├── local_path_storage/
│   ├── multipass_provision/
│   ├── rke2_agent/
│   └── rke2_server/
└── tmp/

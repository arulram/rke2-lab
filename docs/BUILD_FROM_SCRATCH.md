# RKE2 Lab — Build from Scratch

## 1. Purpose

This document describes how to build, validate, and destroy the RKE2 Kubernetes lab.

The build uses:

- Ubuntu 24.04 LTS as the host operating system.
- Multipass to create virtual machines.
- Ansible to configure the virtual machines.
- RKE2 as the Kubernetes distribution.
- Local Path Provisioner for persistent storage.

The Ansible playbooks and roles contain the implementation. This document describes the complete build procedure.

Run all Ansible commands from the repository root:

```bash
cd ~/projects/rke2-lab
```

## 2. Architecture

### 2.1 Host machine

| Component | Configuration |
|---|---|
| Operating system | Ubuntu 24.04 LTS |
| CPU | 8 cores |
| Memory | 31 GiB |
| Multipass | 1.17.2 |
| Ansible Core | 2.16.3 |
| Python | 3.12.3 |
| SSH | OpenSSH |

The host must have enough free disk space for the virtual machines.

### 2.2 Kubernetes virtual machines

The lab uses four Ubuntu 24.04 virtual machines.

| VM | Role | vCPU | Memory | Disk |
|---|---|---:|---:|---:|
| controlpanel | RKE2 server | 2 | 4 GB | 20 GB |
| worker1 | RKE2 agent | 1 | 4 GB | 15 GB |
| worker2 | RKE2 agent | 1 | 4 GB | 15 GB |
| worker3 | RKE2 agent | 1 | 4 GB | 15 GB |

Total allocation:

- 5 vCPU
- 16 GB RAM
- 65 GB virtual disk

Multipass assigns the VM IP addresses.

Do not hardcode VM IP addresses in Ansible files. The dynamic inventory discovers the current addresses.

### 2.3 Kubernetes components

| Component | Purpose |
|---|---|
| RKE2 server | Control plane and Kubernetes API |
| RKE2 agents | Worker nodes |
| containerd | Container runtime |
| CoreDNS | Cluster DNS |
| Canal | Pod networking |
| Local Path Provisioner | Local persistent volumes |

### 2.4 Network ports

| Port | Protocol | Purpose |
|---|---|---|
| 9345 | TCP | RKE2 node registration |
| 6443 | TCP | Kubernetes API |

The nodes must also communicate over the network for Kubernetes networking and cluster operation.

## 3. Repository structure

Repository location:

`~/projects/rke2-lab`

Important files and directories:

| Path | Purpose |
|---|---|
| `ansible.cfg` | Ansible configuration |
| `inventory/multipass.py` | Dynamic Multipass inventory |
| `group_vars/all.yml` | Shared configuration |
| `group_vars/rke2_cluster/vault.yml` | Encrypted RKE2 agent token |
| `roles/multipass_provision/` | VM provisioning |
| `roles/rke2_server/` | RKE2 server installation |
| `roles/rke2_agent/` | RKE2 agent installation |
| `roles/local_path_storage/` | Local Path Provisioner installation |
| `playbooks/00-build-rke2-lab.yml` | Master playbook for the complete build |
| `playbooks/00-provision-multipass-vms.yml` | Create virtual machines |
| `playbooks/01-prepare-nodes.yml` | Prepare Linux nodes |
| `playbooks/02-install-rke2-server.yml` | Install RKE2 server |
| `playbooks/03-join-rke2-workers.yml` | Join worker nodes |
| `playbooks/04-validate-rke2-cluster.yml` | Validate Kubernetes |
| `playbooks/05-configure-desktop-kubeconfig.yml` | Configure host kubectl access |
| `playbooks/06-install-local-path-storage.yml` | Install persistent storage |
| `playbooks/99-destroy-multipass-vms.yml` | Destroy virtual machines |
| `docs/BUILD_FROM_SCRATCH.md` | This build guide |
| `tmp/` | Temporary repository-local files |

Keep temporary files inside `tmp/`.

Do not use `/tmp` for Multipass cloud-init files. Multipass failed to load cloud-init configuration from that location in this environment.

## 4. Host preparation

Complete these steps on the Ubuntu host.

### 4.1 Install required software

Install and verify these tools:

- Multipass
- Ansible Core
- Python 3
- OpenSSH client
- kubectl

Check the installed versions:

```bash
multipass version
ansible --version
python3 --version
ssh -V
kubectl version --client
```

Install the required Ansible collection:

```bash
ansible-galaxy collection install community.general:8.3.0
```

Verify:

```bash
ansible-galaxy collection list community.general
```

### 4.2 Create the dedicated SSH key

Use a dedicated SSH key for this lab.

Create the key only if it does not already exist:

```bash
ssh-keygen -t ed25519 \
    -f ~/.ssh/rke2_lab_ed25519 \
    -C "rke2-lab"
```

Use a passphrase.

Start the SSH agent and add the key:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/rke2_lab_ed25519
```

Verify:

```bash
ssh-add -l
ls -l ~/.ssh/rke2_lab_ed25519*
```

Expected permissions:

- Private key: `600`
- Public key: `644`

Do not share the private key.

Preserve this key when you destroy and rebuild the lab.

### 4.3 Configure Ansible

The repository uses this `ansible.cfg` configuration:

```ini
[defaults]
inventory = ./inventory/multipass.py
remote_user = ubuntu
private_key_file = ~/.ssh/rke2_lab_ed25519
host_key_checking = True
interpreter_python = auto_silent
timeout = 15
forks = 4
retry_files_enabled = False
roles_path = ./roles

[ssh_connection]
ssh_args = -o IdentitiesOnly=yes
```

Host key checking must remain enabled.

The dynamic inventory uses the dedicated SSH key and the Ubuntu account.

### 4.4 Multipass QEMU network configuration

This lab uses the Multipass QEMU driver.

Multipass manages the virtual network used by the QEMU VMs. The current lab uses the `zone1` network bridge.

The current host configuration is:

| Setting | Value |
|---|---|
| Multipass driver | `qemu` |
| Bridged network setting | Not configured |
| Multipass bridge | `mpqemubrzone1` |
| Host bridge address | `10.200.74.1/24` |
| VM subnet | `10.200.74.0/24` |
| Multipass zone | `zone1` |

The physical Wi-Fi interface is separate from the Multipass bridge.

The VM provisioning role does not specify a network interface or zone. It relies on the default QEMU network selected by Multipass.

The Multipass bridge must be available before you provision the VMs.

#### Verify the Multipass network

Run:

```bash
multipass get local.driver
multipass get local.bridged-network
multipass networks
ip -br addr
```

Expected results:

- The Multipass driver is `qemu`.
- The bridged-network setting is empty.
- The `mpqemubrzone1` bridge exists.
- The bridge has an address in `10.200.74.0/24`.

Verify the host route:

```bash
ip route show dev mpqemubrzone1
```

Expected output:

```text
10.200.74.0/24 proto kernel scope link src 10.200.74.1
```

#### Verify the VM network

After provisioning, inspect each VM:

```bash
multipass info controlpanel
multipass info worker1
multipass info worker2
multipass info worker3
```

Each VM must:

- Be in `zone1`.
- Be in the `Running` state.
- Have an IPv4 address in `10.200.74.0/24`.

The dynamic inventory uses this subnet to discover the VM addresses.

Do not hardcode individual VM addresses in Ansible files.

If the Multipass subnet changes, update the `NETWORK` setting in `inventory/multipass.py` to match the VM subnet.

### 4.5 Configure the dynamic inventory

The inventory script is:

`inventory/multipass.py`

It performs these tasks:

1. Reads the Multipass instance list.
2. Finds the expected VM names.
3. Selects running instances.
4. Finds their IP addresses in the configured Multipass subnet.
5. Creates Ansible groups.

The inventory groups are:

- `rke2_servers`
- `rke2_agents`
- `rke2_cluster`

The configured subnet is:

`10.200.74.0/24`

The inventory script uses this subnet to select the correct VM addresses.

If Multipass uses a different subnet, update the `NETWORK` setting in `inventory/multipass.py`.

Do not hardcode individual VM addresses.

Make the script executable:

```bash
chmod 755 inventory/multipass.py
```

Before provisioning, inspect the inventory:

```bash
ansible-inventory --graph
```

The lab groups will be empty when the VMs do not exist. This is expected.

After provisioning, the inventory must show:

- One server: `controlpanel`
- Three agents: `worker1`, `worker2`, `worker3`

### 4.6 Configure the Ansible Vault variable

The file:

`group_vars/rke2_cluster/vault.yml`

contains the encrypted variable:

`rke2_agent_token`

Create a strong random token and encrypt it:

```bash
umask 077

openssl rand -hex 32 |
    ansible-vault encrypt_string \
    --stdin-name rke2_agent_token \
    > group_vars/rke2_cluster/vault.yml

chmod 600 group_vars/rke2_cluster/vault.yml
```

The resulting token is 64 hexadecimal characters.

The file contains an encrypted YAML variable. It is not an entirely encrypted Vault file.

Do not use `ansible-vault view` to inspect this file. That command expects an entirely encrypted file.

The server installation playbook loads this variable and requires the Vault password.

Worker nodes receive the RKE2 agent token from the server through Ansible.

Do not store tokens in plain-text variables or display them in terminal output.

Preserve this Vault file when you rebuild the lab. You do not need to create a new token for every build.

## 5. Build the cluster

The master playbook runs the complete build in the correct order.

Run all commands from the repository root:

```bash
cd ~/projects/rke2-lab
```

### 5.1 Check the master playbook

Run a syntax check before provisioning:

```bash
ansible-playbook \
    playbooks/00-build-rke2-lab.yml \
    --syntax-check \
    --ask-vault-pass
```

Enter the Ansible Vault password when prompted.

The syntax check must pass before you start the build.

### 5.2 Run the complete build

Run this single command:

```bash
ansible-playbook \
    playbooks/00-build-rke2-lab.yml \
    --ask-vault-pass
```

Enter the Ansible Vault password when prompted.

The master playbook runs these phases in order:

| Order | Playbook | Purpose |
|---:|---|---|
| 1 | `00-provision-multipass-vms.yml` | Create VMs and verify SSH |
| 2 | `01-prepare-nodes.yml` | Configure Linux prerequisites |
| 3 | `02-install-rke2-server.yml` | Install the RKE2 server |
| 4 | `03-join-rke2-workers.yml` | Install and join three workers |
| 5 | `04-validate-rke2-cluster.yml` | Validate Kubernetes nodes and pods |
| 6 | `05-configure-desktop-kubeconfig.yml` | Configure host kubectl access |
| 7 | `06-install-local-path-storage.yml` | Install persistent storage |

The master playbook installs Local Path Provisioner. It does not run the persistent storage test.

After the master playbook completes, run the manual storage test in Section 6.3.

The storage test verifies that a persistent volume retains data after pod recreation.

Ansible runs each imported playbook in the listed order.

Ansible stops when a task fails. It does not continue to the next phase.

The master playbook does not destroy VMs or retry failed installations.

#### Initial inventory warning

The first run can display this warning:

```text
[WARNING]: provided hosts list is empty, only localhost is available.
Note that the implicit localhost does not match 'all'
```

This warning is expected when no lab VMs exist.

The first play runs on the Ansible controller. It creates the VMs and refreshes the dynamic inventory.

The later plays use the refreshed inventory to connect to the four VMs.

Do not treat this initial warning as a build failure.

#### SSH host-key registration and validation

The provisioning playbook registers each VM's SSH host key before it tests SSH connectivity.

It performs these steps:

1. Retrieve each VM's ED25519 host public key through `multipass exec`.
2. Validate the retrieved public key.
3. Register the key in the desktop user's `~/.ssh/known_hosts` file.
4. Use the VM's dynamically discovered IP address as the host entry.
5. Verify that each VM's IP address exists in the desktop `known_hosts` file.
6. Wait for SSH connectivity.
7. Run the Ansible ping test against all four VMs.

Multipass provides a trusted, out-of-band method to retrieve the VM host keys. This avoids accepting an unknown SSH host key during the first connection.

The host-key verification task uses `delegate_to: localhost`. This makes Ansible run `ssh-keygen -F` on the desktop, where the `known_hosts` file exists.

Do not remove the `delegate_to: localhost` setting from this task.

Keep SSH host-key checking enabled in `ansible.cfg`:

```ini
host_key_checking = True
```

The playbook must complete SSH host-key validation, SSH connectivity checks, and Ansible ping tests before node preparation starts.

#### Linux node preparation checks

The second build phase prepares and validates all four Linux nodes.

The playbook checks these prerequisites:

| Check | Expected result |
|---|---|
| Operating system | Ubuntu 24.04 |
| Swap | Disabled |
| Overlay kernel module | Loaded |
| `br_netfilter` kernel module | Loaded |
| OverlayFS | Available |
| IPv4 forwarding | Enabled |
| Bridge iptables filtering | Enabled |
| Bridge IPv6 iptables filtering | Enabled |

The playbook does not disable swap.

It checks swap with:

```bash
swapon --noheadings
```

The command must return no output.

If swap is enabled, the playbook stops. Check the swap configuration on the affected VM. Disable swap using the appropriate operating system configuration before you rerun the playbook.

The playbook also checks the root filesystem:

```bash
df -PB1 /
```

It displays the filesystem capacity and available space for each node.

**Note:** The playbook does not enforce a minimum free-space requirement. Check the available space before you install RKE2.

The playbook also:

- Persists the `overlay` and `br_netfilter` modules.
- Loads both modules.
- Persists the required Kubernetes networking sysctls.
- Applies the sysctls.
- Verifies the active sysctl values.

The node preparation phase must complete successfully before RKE2 installation starts.

### 5.3 Validate the completed build

After the master playbook succeeds, check the virtual machines:

```bash
multipass list
```

Check the host kubeconfig:

```bash
ls -l ~/.kube/rke2-lab.yaml
```

Use the lab kubeconfig:

```bash
export KUBECONFIG=~/.kube/rke2-lab.yaml
```

Check Kubernetes nodes and pods:

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
```

#### Inspect Kubernetes system pods

The cluster validation playbook displays the status of pods in the `kube-system` namespace.

It does not assert that these pods are healthy.

Inspect their status:

```bash
kubectl get pods -n kube-system -o wide
```

Review the `STATUS` and `RESTARTS` columns.

Investigate unexpected states such as:

- `Pending`
- `CrashLoopBackOff`
- `ImagePullBackOff`
- `Error`

A pod with status `Completed` can be valid. Do not expect every system pod to remain in the `Running` state.

Use `kubectl describe pod` and `kubectl logs` to investigate any unexpected pod state.

Check persistent storage:

```bash
kubectl get storageclass
kubectl get pods -n local-path-storage
```

Expected results:

- Four VMs are running.
- All four Kubernetes nodes are `Ready`.
- Kubernetes system pod statuses have been inspected. No unexplained unhealthy pod states remain.
- The host can access the Kubernetes API.
- `local-path` is the default StorageClass.
- The Local Path Provisioner pod is running.

### 5.4 Run individual phases when troubleshooting

The master playbook is the normal build entry point.

Use an individual playbook only when you need to inspect or repeat a specific phase.

Run individual playbooks from the repository root.

| Playbook | Purpose |
|---|---|
| `00-provision-multipass-vms.yml` | Provision the virtual machines |
| `01-prepare-nodes.yml` | Prepare Linux nodes |
| `02-install-rke2-server.yml` | Install the RKE2 server |
| `03-join-rke2-workers.yml` | Join the worker nodes |
| `04-validate-rke2-cluster.yml` | Validate the cluster |
| `05-configure-desktop-kubeconfig.yml` | Configure host kubectl access |
| `06-install-local-path-storage.yml` | Install Local Path Provisioner |

The server installation requires the Vault password:

```bash
ansible-playbook \
    playbooks/02-install-rke2-server.yml \
    --ask-vault-pass
```

The other individual playbooks do not require the Vault password.

Do not rerun an installation playbook against an existing installation if its role refuses to overwrite existing state.

Inspect the failure and the current VM or cluster state before taking further action.

### 5.5 Recover from partial VM provisioning

The provisioning role does not automatically delete VMs if a later VM launch fails.

Inspect the current state:

```bash
multipass list
```

Correct the provisioning error.

Then use the destruction procedure in Section 8 to remove the existing lab VMs.

Run the master playbook again after cleanup.

### 5.6 Test persistent storage

The master playbook installs Local Path Provisioner. It does not run the end-to-end PVC persistence test.

Run the manual test in Section 6.3 after the build succeeds.

The test verifies that a PVC binds, accepts data, and retains that data after pod recreation.

## 6. Install persistent storage

### 6.1 Install Local Path Provisioner

Run:

```bash
ansible-playbook \
    playbooks/06-install-local-path-storage.yml
```

The role:

1. Downloads the pinned Local Path Provisioner manifest.
2. Applies the manifest to Kubernetes.
3. Checks for another default StorageClass.
4. Configures the `local-path` StorageClass as the default.
5. Waits for the provisioner deployment.
6. Validates the default StorageClass.

Current version:

`v0.0.37`

The provisioner uses this node-local directory:

`/opt/local-path-provisioner`

Validate:

```bash
kubectl get storageclass
kubectl get pods -n local-path-storage
```

Expected result:

- `local-path` exists.
- `local-path` is the default StorageClass.
- The Local Path Provisioner pod is running.

The role must stop if another StorageClass is already marked as default. Resolve that conflict before continuing.

### 6.2 Understand the storage model

Local Path Provisioner creates persistent volumes on individual Kubernetes nodes.

The provisioner uses this directory on the selected node:

`/opt/local-path-provisioner`

The current installation uses the default path from the pinned upstream manifest. The Ansible variable `local_path_storage_directory` does not currently control this path.

The `local-path` StorageClass uses these settings:

| Setting | Value |
|---|---|
| Provisioner | `rancher.io/local-path` |
| Reclaim policy | `Delete` |
| Volume binding mode | `WaitForFirstConsumer` |
| Default StorageClass | Yes |

Understand these storage limitations:

- Volumes are stored on individual nodes.
- Volumes are not replicated between nodes.
- Volumes are not shared between nodes.
- A volume depends on the node that stores its data.
- A node failure can make its local volumes unavailable.
- Deleting a PVC can delete its PV and the underlying data because the reclaim policy is `Delete`.

Use this provisioner for lab workloads. Do not treat it as production-grade shared or highly available storage.

The StorageClass uses `WaitForFirstConsumer`.

A PVC can remain `Pending` until a pod uses it. This is expected. Kubernetes selects a suitable node when it schedules the pod.

### 6.3 Test persistent storage

This test verifies that a PVC can bind and retain data after pod recreation.

The test uses:

| Setting | Value |
|---|---|
| Namespace | `storage-test` |
| PVC | `local-path-test-pvc` |
| Pod | `local-path-test-pod` |
| StorageClass | `local-path` |
| Capacity | `1Gi` |
| Access mode | `ReadWriteOnce` |
| Mount path | `/data` |

This test verifies persistence after pod recreation. It does not test node failure, volume migration, or data recovery.

Create the test directory:

```bash
mkdir -p tmp
```

Create the PVC manifest:

File: `tmp/storage-test-pvc.yaml`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: local-path-test-pvc
  namespace: storage-test
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 1Gi
```

Create the pod manifest:

File: `tmp/storage-test-pod.yaml`

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: local-path-test-pod
  namespace: storage-test
spec:
  containers:
    - name: busybox
      image: busybox:1.36
      command:
        - sh
        - -c
        - sleep 3600
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: local-path-test-pvc
```

Create the namespace:

```bash
kubectl create namespace storage-test
```

Apply the PVC:

```bash
kubectl apply -f tmp/storage-test-pvc.yaml
```

Check the PVC:

```bash
kubectl get pvc -n storage-test
```

The PVC can remain `Pending` at this stage. This is expected because the StorageClass uses `WaitForFirstConsumer`.

Create the pod:

```bash
kubectl apply -f tmp/storage-test-pod.yaml
```

Wait for the pod:

```bash
kubectl wait \
    --for=condition=Ready \
    pod/local-path-test-pod \
    -n storage-test \
    --timeout=180s

kubectl wait \
    --for=jsonpath='{.status.phase}'=Bound \
    pvc/local-path-test-pvc \
    -n storage-test \
    --timeout=180s
```

Check the PVC and pod:

```bash
kubectl get pvc -n storage-test
kubectl get pods -n storage-test -o wide
kubectl get pv
```

Expected result:

- The PVC is `Bound`.
- The pod is `Running`.
- The PV uses the `local-path` provisioner.

Write test data:

```bash
kubectl exec -n storage-test local-path-test-pod -- \
    sh -c 'echo persistent-data > /data/test.txt'
```

Read the data:

```bash
kubectl exec -n storage-test local-path-test-pod -- \
    cat /data/test.txt
```

Expected output:

```text
persistent-data
```

#### Verify data persistence after pod recreation

Delete the pod:

```bash
kubectl delete pod local-path-test-pod -n storage-test
```

Recreate the pod:

```bash
kubectl apply -f tmp/storage-test-pod.yaml
```

Wait for the pod:

```bash
kubectl wait \
    --for=condition=Ready \
    pod/local-path-test-pod \
    -n storage-test \
    --timeout=180s
```

Read the test data again:

```bash
kubectl exec -n storage-test local-path-test-pod -- \
    cat /data/test.txt
```

Expected output:

```text
persistent-data
```

The data must remain available after pod recreation.

#### Remove test resources

Delete the test namespace:

```bash
kubectl delete namespace storage-test

kubectl wait \
    --for=delete namespace/storage-test \
    --timeout=180s
```

Confirm that the test PVC and PV are removed:

```bash
kubectl get pvc -A
kubectl get pv
```

Remove the test manifests when you no longer need them:

```bash
rm -f \
    tmp/storage-test-pvc.yaml \
    tmp/storage-test-pod.yaml
```

## 7. Complete cluster validation

Run:

```bash
kubectl get nodes -o wide
kubectl get pods -A -o wide
kubectl get storageclass
kubectl get pvc -A
kubectl get pv
```

The lab is ready when:

- All four nodes are `Ready`.
- System pods are healthy.
- The host can access the Kubernetes API.
- `local-path` is the default StorageClass.
- The Local Path Provisioner pod is running.
- The PVC test succeeds.
- The test namespace and its resources have been removed.

## 8. Destroy the lab

Use the destruction playbook when you want to remove the virtual machines.

The playbook requires an explicit confirmation variable.

It targets only these lab VM names:

- `controlpanel`
- `worker1`
- `worker2`
- `worker3`

The playbook supports complete and partial lab deployments. It does not require all four VMs to exist. It deletes only existing VMs with the expected names.

The playbook does not delete unrelated Multipass VMs.

Syntax check:

```bash
ansible-playbook \
    playbooks/99-destroy-multipass-vms.yml \
    --syntax-check
```

The playbook stops existing Running VMs before deletion. It then removes the expected VMs with `multipass delete --purge`.

The playbook verifies that none of the expected VMs remain.

The playbook does not delete host-level files, including:

- SSH keys.
- Ansible repository files.
- Ansible Vault files.
- Desktop kubeconfig.

**Warning:** This operation permanently deletes existing lab VMs and their virtual disks.

Run only when you intend to destroy the lab:

```bash
ansible-playbook \
    playbooks/99-destroy-multipass-vms.yml \
    -e confirm_destroy_rke2_lab=DESTROY_RKE2_LAB_VMS
```

Verify:

```bash
multipass list
```

Confirm that these four names are absent:

- `controlpanel`
- `worker1`
- `worker2`
- `worker3`

Other Multipass instances may still exist. Their presence does not indicate a failed lab cleanup.

## 9. Prepare the host for another build

After destroying the VMs, review the host-side files.

### 9.1 Remove old SSH host keys

Multipass can assign different IP addresses after VM recreation.

Remove the old VM IP addresses from `known_hosts`.

Use the IP addresses from the previous inventory or build record.

For each old VM IP, run:

```bash
ssh-keygen -R <old-vm-ip>
```

Repeat for each old VM address.

Do not remove unrelated host keys.

### 9.2 Remove the old lab kubeconfig

First, preserve a copy if required.

Then remove only:

`~/.kube/rke2-lab.yaml`

Do not remove:

`~/.kube/config`

Do not remove the entire `~/.kube` directory.

The Kubernetes discovery cache can remain. It does not prevent a new cluster installation.

### 9.3 Clean temporary files

Review the repository's `tmp/` directory:

```bash
find tmp -maxdepth 1 -type f -printf '%p\n'
```

Remove old generated cloud-init and storage-test files.

Do not remove source templates or Ansible role files.

Keep the directory available for the next build.

### 9.4 Preserve security files

Keep these files:

- `~/.ssh/rke2_lab_ed25519`
- `~/.ssh/rke2_lab_ed25519.pub`
- `group_vars/rke2_cluster/vault.yml`

Do not display or publish private keys, Vault passwords, or registration tokens.

You do not need to generate a new SSH key or Vault token for every rebuild.

## 10. Known issues and solutions

### 10.1 Multipass cloud-init file errors

Multipass returned:

`Could not load cloud-init configuration: bad file`

The error occurred when the cloud-init file was stored under `/tmp`.

Solution:

Store generated cloud-init files under the repository's `tmp/` directory.

The provisioning role already uses this location.

### 10.2 Ansible Vault view error

The Vault file contains an encrypted YAML variable. It is not an entirely encrypted YAML file.

Therefore, this command can fail:

```bash
ansible-vault view group_vars/rke2_cluster/vault.yml
```

Run the server installation playbook with:

```bash
--ask-vault-pass
```

Do not re-encrypt the whole file unless you also change the playbook's handling of the file.

### 10.3 Dynamic VM addresses

Multipass can assign different IP addresses after VM recreation.

Do not hardcode the server IP in worker configuration.

Use the dynamic inventory and Ansible host variables.

If the Multipass subnet changes, update the `NETWORK` setting in `inventory/multipass.py`.

### 10.4 Ansible idempotency

Run the node preparation playbook more than once.

A second run should report no changes when the system is already configured.

If a task reports a change on every run, review its `changed_when` condition and file-management logic.

### 10.5 Local Path Provisioner PVC remains Pending

The StorageClass uses:

`WaitForFirstConsumer`

The PVC may remain `Pending` until a pod uses it.

Create the pod and inspect its scheduling status before treating this as an error.

### 10.6 Partial VM provisioning

The provisioning role does not automatically delete VMs if a later VM launch fails.

Inspect the current state:

```bash
multipass list
```

Correct the provisioning error.

Then run the destruction playbook with its required confirmation value. The playbook removes only existing VMs from the expected lab set.

Run provisioning again after cleanup.

## 11. Configuration reference

The main configuration file is:

`group_vars/all.yml`

It defines:

- RKE2 version
- RKE2 installation method
- Service names
- Configuration paths
- Data paths
- Registration and API ports
- Inventory group names
- Local Path Provisioner version
- Multipass image
- VM specifications
- SSH public key path
- Cloud-init template path

Current important values:

| Setting | Value |
|---|---|
| RKE2 version | `v1.36.6+rke2r1` |
| Multipass image | `24.04` |
| Local Path Provisioner version | `v0.0.37` |
| Registration port | `9345` |
| Kubernetes API port | `6443` |
| Inventory subnet | `10.200.74.0/24` |

Change shared settings in this file instead of duplicating values in playbooks.

The inventory subnet is configured separately in `inventory/multipass.py`.

Keep secrets in Ansible Vault.

## 12. Build completion criteria

A successful build must meet all of these conditions:

1. Four Multipass VMs are running.
2. Each VM's SSH host key is registered in the desktop user's `known_hosts` file.
3. Ansible can connect to all four VMs.
4. All Linux preflight checks pass.
5. The RKE2 server service is active.
6. All three RKE2 agent services are active.
7. Kubernetes reports four `Ready` nodes.
8. The host can access the Kubernetes API through the lab kubeconfig.
9. Kubernetes system pod statuses have been inspected. No unexplained unhealthy pod states remain.
10. Local Path Provisioner is running.
11. The `local-path` StorageClass is the default.
12. The PVC persistence test in Section 6.3 passes. Data remains available after pod recreation.
13. No storage test resources or temporary test manifests remain.

The master playbook does not run the manual PVC persistence test.

Run the checks in Section 5.3 after the master playbook succeeds. Then complete the manual storage test in Section 6.3.

When all conditions pass, the RKE2 lab build is complete.

# Examples

Starting points for authentication and VM provisioning. Replace hosts, pools,
switches, image names, and SSH keys before running anything.

## Authentication

`auth/config.yaml` is a CLI configuration file with two saved contexts, one
using the `sylve` realm and one using `pam`. `sylve login` writes this file for
you; if you copy the example, replace the tokens and keep it private:

```sh
cp auth/config.yaml ~/.config/sylve/config.yaml
chmod 600 ~/.config/sylve/config.yaml
```

For CI, skip the file and set `SYLVE_SERVER` and `SYLVE_TOKEN` instead.

## Cloud-init

- `cloud-init/user-data.yaml` — user, SSH key, packages, guest agent
- `cloud-init/meta-data.yaml` — instance ID and hostname
- `cloud-init/network-config.yaml` — optional DHCP network config

The user-data and meta-data pair is required for the CLI to flash a cloud
image onto the primary disk at create time. Setting cloud-init after creation
does not flash the image.

## VM YAML

`vm/fedora-cloud.yaml` defines a Fedora Cloud VM on an NVMe-backed zvol. Run
from this directory so the relative cloud-init paths resolve:

```sh
sylve vm create --file vm/fedora-cloud.yaml --dry-run -f yaml
sylve vm create --file vm/fedora-cloud.yaml --start --wait --yes
```

## Scripts

- `scripts/create-fedora-vm.sh` — creates the same VM with explicit flags.
  Override values with environment variables:
  `VM_NAME=web-01 NODE=node2.example.test ./scripts/create-fedora-vm.sh`
- `scripts/create-from-yaml.sh` — creates from `vm/fedora-cloud.yaml`.

Both scripts accept `DRY_RUN=1` to print the request without creating a VM.
Set `SYLVE_BIN` if `sylve` is not on `PATH`.

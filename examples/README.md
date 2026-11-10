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

Manage roles, permission groups, path grants, and OIDC realms with `sylve auth`:

```sh
sylve auth permissions -f json
sylve auth role set vm-operator --property privileges=VM.Audit,VM.PowerMgmt --dry-run -f json
sylve auth acl-group set ops --property members=alice@sylve,bob@pam --dry-run -f json
sylve auth grant set \
  --property path=/vms --property role=vm-operator \
  --property subject=ops --property subjectType=group --property propagate=true \
  --dry-run -f json
sylve auth realm set corp \
  --property issuer=https://idp.example.test --property clientId=sylve-ui \
  --property enabled=true --dry-run -f json
```

## Cloud-init

- `cloud-init/user-data.yaml`: user, SSH key, packages, guest agent
- `cloud-init/meta-data.yaml`: instance ID and hostname
- `cloud-init/network-config.yaml`: optional DHCP network config

The CLI requires the user-data and meta-data pair to flash a cloud image onto
the primary disk at create time. Setting cloud-init after creation
does not flash the image.

## VM YAML

`vm/fedora-cloud.yaml` defines a Fedora Cloud VM on an NVMe-backed zvol. Run
from this directory so the relative cloud-init paths resolve:

```sh
sylve vm create --file vm/fedora-cloud.yaml --dry-run -f yaml
sylve vm create --file vm/fedora-cloud.yaml --start --wait --yes
```

## Jail YAML

`jail/basic.yaml` defines a FreeBSD jail on a DHCP switch:

```sh
sylve jail create --file jail/basic.yaml --dry-run -f json
sylve jail create --file jail/basic.yaml --yes
```

## Scripts

- `scripts/create-fedora-vm.sh`: creates the same VM with explicit flags.
  Override values with environment variables:
  `VM_NAME=web-01 NODE=node2.example.test ./scripts/create-fedora-vm.sh`
- `scripts/create-from-yaml.sh`: creates from `vm/fedora-cloud.yaml`.

Both scripts accept `DRY_RUN=1` to print the request without creating a VM.
Set `SYLVE_BIN` if `sylve` is not on `PATH`.

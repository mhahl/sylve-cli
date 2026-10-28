# SYLVE-DOWNLOAD(1)

## NAME

`sylve-download` — list, start, upload, delete, and fetch ISO and disk images

## SYNOPSIS

```sh
sylve download COMMAND [ARGS ...]
```

## DESCRIPTION

`sylve download` manages ISO, cloud-init, and rootfs images stored on Sylve
nodes. It supports remote HTTP(S) and magnet downloads, local file uploads,
2-hour signed download URLs, and direct file downloads to the client machine.

## SUBCOMMANDS

| Subcommand | Description |
|---|---|
| `list` | List downloads across nodes |
| `show IDENTIFIER` | Show metadata for a download by ID, UUID, or filename |
| `start URL`, `create URL` | Queue a remote HTTP(S), magnet, or local-path download |
| `upload FILE` | Upload a local image file to a node |
| `delete ID...` | Delete one or more downloads (single or bulk delete) |
| `signed-url` | Generate a 2-hour signed download URL |
| `storage` | List download storage targets and default paths |
| `update ID` | Update download metadata (generic API command) |
| `utype` | List completed downloads by usage type (generic API command) |
| `abort-upload ID` | Abort a staged upload (generic API command) |
| `file UUID`, `file-with-name UUID FILENAME` | Download a completed file to a local path |

## OPTIONS

### `download list`

- `-n, --node NODE`, `-f, --format`, `-c, --column`, `--sort-column NAME`
  Standard node and output options.
- `--long`
  Add `UUID`, `Type`, `Usage Type`, and `Pool`.

### `download show`

- `IDENTIFIER` (required)
  Download ID, UUID, or filename.
- `-n, --node NODE`, `-f, --format`, `-c, --column`
  Standard node and output options.

### `download start` (`download create` is a hidden alias)

- `URL` (required)
  HTTP(S) URL, magnet URI, or server-local path.
- `--filename, -O NAME`
  Override the destination filename.
- `--type, -t TYPE`
  Image category: `uncategorized`, `cloud-init`, or `base-rootfs`
  (default: `uncategorized`).
- `--pool, -p POOL`
  Target ZFS pool (default: server default).
- `--extract / --no-extract`
  Automatically extract compressed archives (default: `--extract`).
- `--raw-convert / --no-raw-convert`
  Convert disk images to RAW format (default: `--no-raw-convert`).
- `--ignore-tls`
  Skip TLS certificate verification on the remote download URL.
- `-n, --node NODE`
  Target node.

### `download upload`

- `FILE` (required)
  Local file path to upload.
- `--type, -t TYPE`
  `uncategorized`, `cloud-init`, or `base-rootfs` (default: `uncategorized`).
- `--pool, -p POOL`
  Target ZFS pool.
- `--extract / --no-extract`
  Extract compressed archives (default: `--extract`).
- `--raw-convert / --no-raw-convert`
  Convert disk images to RAW format (default: `--no-raw-convert`).
- `-n, --node NODE`
  Target node.

### `download delete`

- `IDS...` (required)
  One or more download IDs.
- `-n, --node NODE`
  Target node.

### `download signed-url`

- `--uuid, -u UUID` (required)
  Download UUID.
- `--name, -f FILENAME` (required)
  Filename within the download.
- `-n, --node NODE`, `-f, --format`
  Target node and output format. Because `-f` is bound to both `--name` and
  `--format`, prefer the long flags `--name` and `--format`.

### `download storage`

- `-n, --node NODE`, `-f, --format`, `-c, --column`
  Standard node and output options.

### `download file`, `download file-with-name`, and Generic Subcommands

- `file UUID` and `file-with-name UUID FILENAME` require `--output, -o PATH` and
  accept `--param, -p KEY=VALUE` and `-n, --node NODE`.
- `update ID`, `utype`, and `abort-upload ID` accept `--data/-d`, `--param/-p`,
  `-y/--yes`, `-n/--node`, and `-f/--format`.

## EXIT STATUS

- `0` — Success.
- `1` — API or file I/O error, or aborted confirmation.
- `2` — Command-line usage error.

## EXAMPLES

List downloads across the cluster:

```sh
sylve download list
```

```text
Downloads
+----+---------------------+---------------------+---------+----------+---------+
| ID | Name                | Node                | Size    | Progress | Status  |
+----+---------------------+---------------------+---------+----------+---------+
| 1  | debian-13.iso       | node1.example.test  | 1.2 GiB |   100.0% | READY   |
| 2  | ubuntu-24.04.img    | node2.example.test  | 2.8 GiB |    42.0% | RUNNING |
+----+---------------------+---------------------+---------+----------+---------+
```

Start a remote download with explicit options:

```sh
sylve download start https://example.test/debian-13.iso \
  --filename debian-13.iso \
  --type cloud-init \
  --pool zroot \
  --no-extract \
  --raw-convert \
  --ignore-tls \
  --node node1.example.test
# Queued download debian-13.iso (UUID: 8f14...).
```

Upload a local image and delete downloads:

```sh
sylve download upload ./debian-13.iso --type base-rootfs --pool zroot --node node1.example.test
sylve download delete 1 --node node1.example.test
sylve download delete 2 3 4 --node node1.example.test
```

Generate a signed URL and fetch the file locally:

```sh
sylve download signed-url --uuid 8f14... --name debian-13.iso
sylve download file 8f14... --param token=... --output ./debian-13.iso
# Saved to debian-13.iso
```

Update download metadata via the generic endpoint:

```sh
sylve download update 1 --data '{"name":"debian-13-cloudinit.iso"}' --param validate=1 --node node1.example.test -f json
```

## SEE ALSO

[sylve(1)](../../README.md),
[sylve-vm(1)](vm.md),
[sylve-jail(1)](jail.md),
[sylve-options(7)](../global-options.md)

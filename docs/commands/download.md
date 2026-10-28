# sylve download

List, start, upload, delete, and fetch ISO and disk images.

## Synopsis

    sylve download COMMAND [ARGS]...

## Commands

| Command | Purpose |
|---|---|
| `list` | Downloads across nodes |
| `show IDENTIFIER` | Full download metadata |
| `start URL`, `create URL` | Start a download |
| `upload FILE` | Upload a local image |
| `delete ID...` | Delete one or more downloads |
| `signed-url` | Create a 2-hour signed URL |
| `storage` | List storage targets and default paths |
| `update ID` | Generic metadata update |
| `utype` | Generic completed-download choices |
| `abort-upload ID` | Generic staged-upload abort |
| `file UUID`, `file-with-name UUID FILENAME` | Download a completed file |

## Options

### `download list`

- `-n, --node NODE`
  Limit to one node.
- `-f, --format {table,json,yaml,value,csv}`
  Output format. Default: `table`.
- `-c, --column NAME`
  Select columns.
- `--sort-column NAME`
  Sort rows.
- `--long`
  Add `UUID`, `Type`, `Usage Type`, and `Pool`.

### `download show`

- `IDENTIFIER` (required)
  Download ID, UUID, or filename.
- `-n, --node NODE`, `-f, --format`, `-c, --column`.

### `download start` / `download create`

- `URL` (required)
  HTTP(S) URL, magnet URI, or server-local path.
- `--filename, -O NAME`
  Override the target filename.
- `--type, -t TYPE`
  `uncategorized`, `cloud-init`, or `base-rootfs`. Default: `uncategorized`.
- `--pool, -p POOL`
  ZFS pool. Default: server default.
- `--extract / --no-extract`
  Extract compressed archives. Default: `--extract`.
- `--raw-convert / --no-raw-convert`
  Convert disk images to RAW. Default: `--no-raw-convert`.
- `--ignore-tls`
  Ignore TLS verification on the remote URL.
- `-n, --node NODE`.

`start` and `create` are aliases.

### `download upload`

- `FILE` (required)
  Local file to upload.
- `--type, -t TYPE`
  `uncategorized`, `cloud-init`, or `base-rootfs`. Default: `uncategorized`.
- `--pool, -p POOL`
  Target ZFS pool.
- `--extract / --no-extract`
  Extract compressed archives. Default: `--extract`.
- `--raw-convert / --no-raw-convert`
  Convert disk images to RAW. Default: `--no-raw-convert`.
- `-n, --node NODE`.

### `download delete`

- `IDS...` (required)
  One or more download IDs. One ID uses a single delete; multiple IDs use bulk
  delete.
- `-n, --node NODE`.

### `download signed-url`

- `--uuid, -u UUID` (required)
  Download UUID.
- `--name, -f FILENAME` (required)
  Filename within the download.
- `-n, --node NODE`, `-f, --format`.

The short `-f` is bound to both `--name` and `--format`. Use the long forms in
this command.

### `download storage`

- `-n, --node NODE`, `-f, --format`, `-c, --column`.

### Generic and file commands

- `download update`, `utype`, `abort-upload`: `--data/-d`, `--param/-p`,
  `-y/--yes`, `-n/--node`, `-f/--format`.
- `download file UUID`: `--param/-p`, `--output/-o PATH` (required),
  `-n/--node`.
- `download file-with-name UUID FILENAME`: same options as `file`.

Path arguments:

| Command | Arguments |
|---|---|
| `update`, `abort-upload` | `id` |
| `file` | `uuid` |
| `file-with-name` | `uuid filename` |
| `utype` | none |

## Examples

### Minimal

    sylve download list

Output (illustrative):

    Downloads
    +----+---------------------+---------------------+---------+----------+---------+
    | ID | Name                | Node                | Size    | Progress | Status  |
    +----+---------------------+---------------------+---------+----------+---------+
    | 1  | debian-13.iso       | node1.example.test  | 1.2 GiB |   100.0% | READY   |
    | 2  | ubuntu-24.04.img    | node2.example.test  | 2.8 GiB |    42.0% | RUNNING |
    +----+---------------------+---------------------+---------+----------+---------+

### With every relevant option

    sylve download start https://example.test/debian-13.iso \
      --filename debian-13.iso \
      --type cloud-init \
      --pool zroot \
      --no-extract \
      --raw-convert \
      --ignore-tls \
      --node node1.example.test

Output (illustrative):

    Queued download debian-13.iso (UUID: 8f14...).

`--no-extract` disabled automatic extraction. `--raw-convert` enabled RAW
conversion. `--ignore-tls` applied only to the remote URL.

### Upload with every relevant option

    sylve download upload ./debian-13.iso \
      --type base-rootfs \
      --pool zroot \
      --extract \
      --no-raw-convert \
      --node node1.example.test

Output (illustrative):

    Uploaded 'debian-13.iso' successfully (UUID: 8f14...).

### Delete one and many

    sylve download delete 1 --node node1.example.test

Output:

    Deleted download #1.

    sylve download delete 2 3 4 --node node1.example.test

Output:

    Deleted 3 downloads.

### Signed URL

    sylve download signed-url --uuid 8f14... --name debian-13.iso

Output (illustrative):

    Signed Download URL
    +-------+--------------------------------------------------------------+
    | Field | Value                                                        |
    +-------+--------------------------------------------------------------+
    | url   | https://sylve.example.test/api/utilities/downloads/...?...    |
    +-------+--------------------------------------------------------------+

### Storage and file download

    sylve download storage --node node1.example.test

Output (illustrative):

    Default Download Paths
    +-------+----------------------+
    | Field | Value                |
    +-------+----------------------+
    | iso   | /zroot/downloads/iso |
    +-------+----------------------+

    sylve download file 8f14... --param token=... --output ./debian-13.iso

Output:

    Saved to debian-13.iso

`--output` is required. The signed capability parameters come from
`download signed-url`.

### Generic command with every option

    sylve download update 1 --data '{"name":"debian-13-cloudinit.iso"}' --param validate=1 --node node1.example.test -f json

Output (illustrative):

    {
      "id": 1,
      "name": "debian-13-cloudinit.iso"
    }

## Inputs

- The active context and token.
- `FILE` must exist and be readable.
- `--data` inline JSON/YAML or `@file`; `--param KEY=VALUE` repeated for query
  parameters.

## Outputs

- Progress and metadata tables.
- `file` and `file-with-name` write the requested path and print `Saved to
  PATH`.
- Exit `0` on success. Exit `1` on API error or aborted confirmation. Exit `2`
  on usage error.

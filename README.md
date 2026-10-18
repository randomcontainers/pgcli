# pgcli

Container images with [pgcli](https://www.pgcli.com/), a command-line client for PostgreSQL with auto-completion and syntax highlighting. `latest` also includes the PostgreSQL client programs, `psql`, `pg_dump`, `pg_restore` and the others. pgcli is installed from PyPI into a virtual environment on Ubuntu or Alpine, for `linux/amd64` and `linux/arm64`, and the images are rebuilt when pgcli publishes a release and when the base image changes.

This is an unofficial build, not affiliated with or endorsed by the pgcli project. Report problems with the image in this repository and problems with pgcli itself [upstream](https://github.com/dbcli/pgcli/issues).

## Quick start

Open pgcli on a database:

```sh
docker run --rm -it ghcr.io/randomcontainers/pgcli postgresql://app@db.example.com/shop
```

Interactive use needs `-it`. pgcli completes table and column names, SQL keywords and the backslash commands (`\dt`, `\d <table>`, `\l` and the rest, listed by `\?`) as you type. Without arguments the image prints `pgcli --help`.

Like `psql`, pgcli runs SQL given with `-c` or read from a file with `-f`, prints the result and exits:

```sh
# Run a query, with the password from your shell's PGPASSWORD
docker run --rm -e PGPASSWORD ghcr.io/randomcontainers/pgcli \
  -h db.example.com -U app -c 'select * from orders limit 10' shop

# Run the SQL in a file in the current directory
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" -e PGPASSWORD \
  ghcr.io/randomcontainers/pgcli -h db.example.com -U app -f report.sql shop
```

`-t` prints the rows only, without headers and the status line. pgcli may also print two lines about the time zone before the result; [Time zone](#time-zone) explains how to keep them out of a script's output.

The default image also has the PostgreSQL client programs. Run them by replacing the entrypoint, for example to dump a database:

```sh
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" -e PGPASSWORD --entrypoint pg_dump \
  ghcr.io/randomcontainers/pgcli -h db.example.com -U app -Fc -f shop.dump shop
```

## Connecting

A server on another host is reached by name or address. For a server on the Docker host itself, use `--network host -h 127.0.0.1` on Linux, or `-h host.docker.internal` with Docker Desktop. To connect through the server's Unix socket, mount its directory and pass it as the host, for example `-v /var/run/postgresql:/var/run/postgresql -h /var/run/postgresql`. Always pass the directory: the one libpq looks in without `-h` depends on which copy of libpq pgcli loads (see [What is in the image](#what-is-in-the-image)).

Give the user name with `-U`, in `PGUSER` or in a `postgresql://` URL. Otherwise pgcli takes the name of the account its UID has in the image: `ubuntu` on Ubuntu and `app` on Alpine for UID 1000, which is also the UID of the first user on most Linux hosts. For a UID with no account in the image, pgcli stops with a Python traceback ending in `OSError: No username set in the environment`, even when a `key=value` connection string names the user.

Passwords:

- `-e PGPASSWORD` passes the variable from your shell. Avoid `-e PGPASSWORD=secret` on the command line, which ends up in your shell history and in `ps` output.
- `HOME` is `/cache`, so libpq reads the password file from `/cache/.pgpass`. Mount yours with `--user "$(id -u):$(id -g)" -v "$HOME/.pgpass:/cache/.pgpass:ro"` and give the user with `-U`: libpq ignores the file unless its mode is 0600 or stricter, and with that mode only your UID can read it. `-e PGPASSFILE=/work/pgpass` points to another file.
- pgcli's keyring support is not installed, so it cannot store passwords. Its default config has `keyring = True`, which only writes a warning to pgcli's log file.

pgcli reads connection services from `/cache/.pg_service.conf`, or from the file named in `PGSERVICEFILE`; pass `service=<name>` in place of the database name. pgcli's own named connections go in the `[alias_dsn]` section of its config file and are used with `-D <alias>`.

TLS goes through libpq and the distro's OpenSSL. To check a server certificate signed by a public CA against the CA certificates of the image, add `sslrootcert=system`, which also turns on `sslmode=verify-full`:

```sh
docker run --rm -it ghcr.io/randomcontainers/pgcli \
  'postgresql://app@db.example.com/shop?sslrootcert=system'
```

For a private CA, mount its certificate and pass `sslmode=verify-full sslrootcert=/work/ca.crt`, or mount it at `/cache/.postgresql/root.crt`, where libpq looks by default.

`--ssh-tunnel` does not work: it needs the `sshtunnel` package, which is not installed, and pgcli stops with an error saying so. Open the tunnel on the host and connect to its local end instead.

## Time zone

pgcli sets the session time zone to the time zone of the container, so that timestamps are shown in local time. Pass yours with `-e TZ`:

```sh
docker run --rm -it -e TZ=Europe/Berlin ghcr.io/randomcontainers/pgcli postgresql://app@db.example.com/shop
```

Without `TZ`, the Ubuntu images use `Etc/UTC`. The Alpine images have no local time zone, so pgcli prints a warning to standard error and keeps the server's time zone.

pgcli compares the names of the two time zones as text, so `Etc/UTC` and `UTC` count as different. When they differ, it prints `Using local time zone <zone> (server uses <zone>)` and a hint to standard output before it runs `-c` or `-f`, and `-t` and `--less-chatty` do not suppress these lines. For scripts, pass a `TZ` equal to what `show time zone` returns on the server, or set `use_local_timezone = False` in the `[main]` section of pgcli's config to always keep the server's time zone. The config is `/cache/.config/pgcli/config`, or a file in `/work` given with `--pgclirc`:

```sh
printf '[main]\nuse_local_timezone = False\n' > pgclirc
docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/work" -e PGPASSWORD ghcr.io/randomcontainers/pgcli \
  --pgclirc pgclirc -h db.example.com -U app -t -c 'select count(*) from orders' shop
```

## What is in the image

| | slim | default |
|---|---|---|
| pgcli and its Python dependencies, installed from `requirements.lock` | yes | yes |
| libpq, the time zone data and `less`, from the distro | yes | yes |
| `psql`, `pg_dump`, `pg_restore`, `pg_basebackup`, `pg_isready` and the other PostgreSQL client programs | no | yes |

pgcli uses psycopg's pure Python implementation, which loads the distro's libpq (`libpq5` on Ubuntu, `libpq` on Alpine) at run time. pgcli shows long results through `less`. Its `\e` command needs an editor: the Alpine image has BusyBox `vi`, the Ubuntu image has none.

Not included: keyring support and `sshtunnel`, both optional extras of pgcli (see [Connecting](#connecting)), and psycopg's C and binary implementations.

The PostgreSQL client programs in `latest` are the [randomcontainers/postgresql-client](https://github.com/randomcontainers/postgresql-client) build, with its own copy of `libpq.so.5` in `/usr/local/lib`, which the programs load through their RUNPATH. psycopg looks up `libpq.so.5` by name and may get either that copy or the distro's, depending on the distro and the architecture. Both work with psycopg, but they are built differently. Without `-h`, postgresql-client's libpq looks for the server's socket in `/tmp`, Ubuntu's in `/var/run/postgresql` and Alpine's in `/run/postgresql`. Ubuntu's libpq can also look up connection parameters in LDAP, which postgresql-client's and Alpine's cannot.

## Default or slim

The default image (`latest`) has pgcli and the PostgreSQL client programs and is recommended for general use: `pg_dump`, `pg_restore` and `pg_isready` do what pgcli does not, and `psql` runs scripts written for it. Use `slim`, which has pgcli only, as the base when you build your own image.

The default image is also published as `ghcr.io/randomcontainers/pgcli-postgresql-client`, built in the [pgcli-postgresql-client](https://github.com/randomcontainers/pgcli-postgresql-client) repository with the same contents and a different digest.

## Tags

`<version>` is a pgcli release such as `4.7.1`. `<minor>` and `<major>` are its shorter forms, `4.7` and `4`, and follow the newest release in that series.

| Default (with the PostgreSQL client programs) | Slim | Base |
|---|---|---|
| `latest`, `<version>`, `<minor>`, `<major>` | `slim`, `<version>-slim`, `<minor>-slim`, `<major>-slim` | Ubuntu |
| `ubuntu`, `<version>-ubuntu`, `<minor>-ubuntu`, `<major>-ubuntu` | `slim-ubuntu`, `<version>-slim-ubuntu`, `<minor>-slim-ubuntu`, `<major>-slim-ubuntu` | Ubuntu |
| `<version>-ubuntu26.04` | `<version>-slim-ubuntu26.04` | Ubuntu 26.04 |
| `alpine`, `<version>-alpine`, `<minor>-alpine`, `<major>-alpine` | `slim-alpine`, `<version>-slim-alpine`, `<minor>-slim-alpine`, `<major>-slim-alpine` | Alpine |
| `<version>-alpine3.24` | `<version>-slim-alpine3.24` | Alpine 3.24 |

The images are currently built on Ubuntu 26.04 and Alpine 3.24. Tags without a distro version move to the next distro release when the project does; tags ending in `ubuntu26.04` or `alpine3.24` stay on that release and are no longer rebuilt once the project moves to the next one. Every tag of the current pgcli version, including the exact version, is rebuilt in place (see [Updates](#updates)), so pin a digest when you need the same bytes every time.

## Platforms

`linux/amd64` and `linux/arm64`, for both Ubuntu and Alpine. Both are built natively on GitHub-hosted runners, without emulation. The same `requirements.lock` is installed on all four combinations of distro and architecture. Most of it is pure Python; setproctitle and wcwidth come as glibc (`manylinux`) wheels on Ubuntu and musl (`musllinux`) wheels on Alpine.

## Files and permissions

The working directory is `/work`. The image runs as UID 1000, and any other UID works too: `HOME` is `/cache` for every user, and `/cache` can be written by anyone. Files that `-f` reads and that `\o` writes are relative to `/work`. How to get output files owned by you depends on how you run containers:

| Runtime | Flag |
|---|---|
| Docker on Linux (rootful), GitHub Actions | `--user "$(id -u):$(id -g)"` |
| Rootless Podman | `--userns=keep-id` |
| Rootless Docker | `--user 0:0` (root in the container is your user on the host) |
| Docker Desktop on macOS or Windows | none, file ownership is mapped for you |

pgcli keeps its config, history and log in `/cache/.config/pgcli/`, and writes a default `config` there the first time it starts. libpq reads `.pgpass`, `.pg_service.conf` and the certificates in `.postgresql/` from `/cache`. Mount a volume on `/cache` to keep them between runs:

```sh
docker run --rm -it --user "$(id -u):$(id -g)" -v pgcli-home:/cache \
  ghcr.io/randomcontainers/pgcli -h db.example.com -U app shop
```

`--pgclirc <file>` reads another config file, for example one in `/work`.

## Extending the slim image

Use a `slim` tag as the base for your own image. `slim`, `slim-ubuntu` and `slim-alpine` follow new pgcli releases and are rebuilt when its locked Python dependencies or the distro change. pgcli runs from a virtual environment in `/usr/local/lib/pgcli`; the `python3` on `PATH` is the distro's interpreter and cannot import pgcli. The distro packages pgcli needs are listed in `/usr/local/share/randomcontainers/pgcli/runtime-deps`. Switch to root to install more, for example an editor for `\e`, then back:

```dockerfile
FROM ghcr.io/randomcontainers/pgcli:slim-ubuntu@sha256:...
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends vim-tiny \
 && rm -rf /var/lib/apt/lists/*
ENV EDITOR=vim.tiny
USER 1000:1000
```

On Alpine, use `apk add --no-cache vim` and `EDITOR=vim`. The entrypoint is `["tini", "--", "pgcli"]`; set your own `ENTRYPOINT` if your image runs a script. To pick up new pgcli releases and base image fixes, let Dependabot or Renovate update the digest in your `FROM` line.

## Verifying

Each image has a build provenance attestation from this repository's GitHub Actions run, signed by the shared build workflow in `randomcontainers/ci`:

```sh
gh attestation verify oci://ghcr.io/randomcontainers/pgcli:latest \
  --repo randomcontainers/pgcli --signer-repo randomcontainers/ci
```

Images from `ghcr.io/randomcontainers/pgcli-postgresql-client` are built in that repository, so verify them with `--repo randomcontainers/pgcli-postgresql-client` and the same `--signer-repo`.

Each platform image also carries an SPDX SBOM that lists the distro and Python packages in it with their versions:

```sh
docker buildx imagetools inspect ghcr.io/randomcontainers/pgcli:latest --format '{{ json .SBOM }}'
```

pgcli and its Python dependencies are installed from [`requirements.lock`](requirements.lock), which pins every package to a version and its SHA-256 hashes, and pip refuses anything else. The URL and hash of each installed wheel are in `/usr/local/share/randomcontainers/pgcli/source`, and the installed versions in `buildinfo` next to it.

## Updates

The project checks [pgcli on PyPI](https://pypi.org/project/pgcli/) every 15 minutes. A release is picked up once it is 24 hours old and PyPI holds a provenance attestation showing it was published from the [dbcli/pgcli](https://github.com/dbcli/pgcli) repository. The new version and a regenerated `requirements.lock` are then committed together and the images are rebuilt. Only the newest release is built; tags of older versions stay as they were last built. Dependency versions in the lock must have been on PyPI for at least 7 days. The lock is also regenerated weekly at the same pgcli version, so new releases of dependencies such as psycopg and prompt_toolkit reach the current tags between pgcli releases. When a new lock would change the version of pgspecial or setproctitle, whose license texts are kept in `licenses/`, the update, including a new pgcli release, waits until those files are refreshed by hand (see [Building](#building)).

The images of the current version are also rebuilt when the Ubuntu or Alpine base image changes, the default ones when a new postgresql-client image is published, and all of them at least every 7 days, so distro security fixes, including those for libpq and OpenSSL, reach the current tags.

## Building

```sh
docker build -f Dockerfile.ubuntu --target slim --build-arg VERSION=<version> -t pgcli:local .
```

Use `Dockerfile.alpine` for the Alpine image. `<version>` must be the version pinned in `requirements.lock`; the build stops otherwise. The default image is generated from the `combos` section of `package.yml` by [randomcontainers/ci](https://github.com/randomcontainers/ci) and layers the postgresql-client image onto this one.

The command that produced `requirements.lock` is on its second line; it resolves for Python 3.14, the version on both bases. To regenerate the lock at the version in `package.yml`, run `rc lock requirements.lock` in this directory. `rc` is the command-line tool of randomcontainers/ci, and it needs uv on `PATH`. If a new lock changes the version of pgspecial or setproctitle, run `python3 scripts/bundled-licenses.py` to refresh `licenses/pgspecial-<version>/` and `licenses/setproctitle-<version>/`. The build fails until those directories match the installed versions.

## Licenses

pgcli is released under the [BSD 3-Clause license](https://github.com/dbcli/pgcli/blob/main/LICENSE.txt). It is pure Python, so the installed files are its source, and the wheel it was installed from is named in `/usr/local/share/randomcontainers/pgcli/source`. The slim image adds its Python dependencies, which are mostly under BSD and MIT licenses. wcwidth's license also carries Markus Kuhn's notice for the `wcwidth.c` it is derived from (HPND-Markus-Kuhn). pip (MIT) includes packages under the Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, MIT, MPL-2.0 and PSF-2.0 licenses. The complete SPDX expression is in the image's `org.opencontainers.image.licenses` label, and each package's license files are in `/usr/local/share/randomcontainers/pgcli/licenses/`.

psycopg is licensed under the GNU Lesser General Public License, version 3 (LGPL-3.0-only). It is pure Python too, so its source is in the image. The LGPL is written as additional permissions on top of the GNU GPL, version 3, and psycopg's wheel has only the LGPL text, so this repository adds the GPL text in [`licenses/GPL-3`](licenses/GPL-3) and the images have it in `/usr/local/share/randomcontainers/pgcli/licenses/psycopg/GPL-3`.

Some wheels contain code whose license text they do not include. This repository keeps those texts in [`licenses/`](licenses/), and the image has them in `/usr/local/share/randomcontainers/pgcli/licenses/<package>/`:

- pgspecial (BSD-3-Clause): its wheel has no license file, because its build tool picks up `LICENSE*`, `LICENCE*` and `COPYING*` files and pgspecial's is named `License.txt`. The file is taken from pgspecial's source release.
- setproctitle (BSD-3-Clause): its C extension is built with `spt_status.c` from PostgreSQL (PostgreSQL License) and `spt_strlcpy.c` from OpenBSD (ISC). Their notices, from the top of those files in setproctitle's source release, are in `LICENSE.spt_status` and `LICENSE.spt_strlcpy`.
- wcwidth (MIT): its width tables are generated from the Unicode Character Database, so the Unicode License v3 (Unicode-3.0) is added as `Unicode-3.0`.

libpq, the time zone data and `less` are distro packages and keep their own licenses; the SBOM lists them. `latest` also contains the PostgreSQL client programs, which are mainly licensed under the PostgreSQL License. The [postgresql-client repository](https://github.com/randomcontainers/postgresql-client#licenses) lists the other terms of code compiled into them and the license files that come with them. PostgreSQL and Postgres are registered trademarks of the PostgreSQL Community Association of Canada.

The files in this repository are available under the MIT license, see [LICENSE](LICENSE), except the license texts in `licenses/`, which keep their own terms.

## Requesting a tool

To suggest another tool, use the [Request a tool](https://github.com/randomcontainers/.github/issues/new?template=tool-request.yml) form.

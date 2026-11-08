# infra

Ansible for kilo.

Units this repo manages are called `lb-*`. Every one of them gets the shared hardening in
`/etc/systemd/system/lb-.service.d/10-hardening.conf`. Units that aren't `lb-*` are left alone.

## Running it

Every run goes through `infra` on kilo, as root. It takes a lock, gets a GitHub token,
pulls the `master` branch and runs `site.yml`. Any extra arguments are passed to `ansible-pull`.

```sh
infra --check --diff                     # show what would change
infra --tags common                      # base system only
infra --tags common -e os_upgrade=true   # pacman -Syu, then say whether a reboot is needed
infra --tags leaf -e ref=v1.4.2          # deploy one app at a ref
infra --tags leaf -e rollback=true       # go back to the previous release
infra --tags minecraft -e update=true    # run an external app's update command (backs up first)
```

`-e ref`, `-e rollback` and `-e update` only work together with `--tags` for that one app.

The server's hostname has to match its name in `inventory.ini` (`kilo`), because
`ansible-pull` picks its host by hostname. The first run builds `/opt/ansible` at the
version pinned in `group_vars/all/versions.yml`.

## Branches

This repo and the app repos use the same flow:

```
any branch --> stable ---> master
```

- **master** is production. kilo runs this repo from `master`.
- **stable** is for staging. Nothing deploys from it yet, because there is no staging environment. (TODO)
- Promotion PRs from `stable` to `master` must be merge commits. A squash or rebase gives
  the two branches different histories, and every later promotion would show old commits again.
- Feature branches can have any name. Only `stable` and `master` are protected.

**Deploys only accept commits that are on the app's `deploy_branch`** (`master` by default).
Whatever you pass as `-e ref` (a tag, a branch or a SHA), the run checks it against GitHub's compare
API and refuses anything that isn't on that branch. So tag releases on `master`.

Deploys are manual for now (`infra --tags <app> -e ref=<tag>`). Automatic deploys on new
tags will be opt-in per app.

Rulesets to import (Settings -> Rules -> Rulesets -> Import) are located at `.github/rulesets/app/{stable,master}.json`. The app versions don't require the `lint` check.

## Secrets
Consult higherups.

## Adding an app

Create `apps/<name>/app.yml`, and put any config templates next to it. Then add one line to `site.yml`:

```yaml
- { role: app, app_name: <name>, tags: [<name>] }
```

```yaml
description: what it is
owner: github-handle
tier: infra | personal
type: binary | node | external
user: service-user
repo: LitterbinCollective/repo      # binary, node
ref: v1.2.3                         # default ref; -e ref=… overrides it
deploy_branch: master               # refs must be on this branch (default master)
asset: name-linux-amd64.tar.gz      # binary: GitHub release asset ({ref} is substituted)
build: [npm ci, npm run build]      # node: run as the app user in the release dir
migrate: npm run migrate            # node: runs on deploy after the backup, only once cut over
rebuild: npm rebuild                # node: runs on the current release when Node changes
update: ./update.sh                 # external: run in the state dir with -e update=true
state: [uploads, db]                # created under /srv/<name>/
state_root: /srv/other              # optional, defaults to /srv/<name>
links: { cache: "{state}/cache" }   # symlinks from the release into state
config: [config.json.j2]            # rendered to /etc/<name>/config.json
env: { NODE_ENV: production }
hardening_overrides: [ProtectHome=tmpfs]
units:
  http:                             # -> lb-<name>-http.service; a key equal to <name> -> lb-<name>.service
    exec: "{current}/bin serve --data {state}"
    instances: [a, b]               # optional: makes it lb-<name>-http@.service with these instances
    working_dir: "{current}"
    writable: ["{state}"]
    restart: always
    timeout_stop: 120
    overrides: [MemoryDenyWriteExecute=no]
replaces: [old-unit]                # legacy units stopped and disabled at cutover
cutover: false
backup: { before_deploy: true, exclude: [], keep: 10 }
```

`{current}`, `{state}` and `{home}` stand for `/opt/<name>/current`, the state root and `/opt/<name>`.

## Moving an existing service over

1. Write `apps/<name>/app.yml` with `cutover: false` and deploy it. This installs the `lb-*` units
   and the release next to the old service, but starts nothing.
2. Stop the old service and copy its data into `/srv/<name>/`.
3. `touch /srv/<name>/.lb-migrated`
4. Set `cutover: true` and deploy again. This stops and disables the units listed in `replaces`,
   then enables and starts the `lb-*` units.
5. Leave the old unit files and code in place for a few weeks, then delete them.

If something breaks, set `cutover: false`, disable the `lb-*` units, and start the old unit again.

## Other files

- `owners.md` lists every unit on kilo with its owner and plan. On kilo, `bin/inventory` prints the live state.
- `examples/release-binary.yml` is a release workflow for app repos.
- `.github/rulesets/` holds the branch rulesets (see Branches).

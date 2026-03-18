# elyb

cli tool for building elyxcore plugins.

## init

```
elyb init <plugin-root> --refmap <path> [--outputdir <dir>] [--zipformat <ext>]
```

creates `.elyb/settings.json` in the current directory.

- `--outputdir` — where to put builds (default: `builds`)
- `--zipformat` — archive extension (default: `zip`)

## build

```
elyb build [--no-assets] [--compression 0-9] [--pass <password>] [--additional <path,...>] [--dry-run]
```

packs plugin into `{id}-{version}.{zipformat}`. if file already exists, saves as `-duplicate.N.`.

- `--no-assets` — exclude paths listed in `optionalAssets`
- `--compression` — zip compression level, 0-9 (default: 6)
- `--pass` — encrypt with AES password (requires `pip install pyzipper`)
- `--additional` — comma-separated extra paths to include
- `--dry-run` — print file list without building

## validate

```
elyb validate
```

checks refmap paths, metainfo fields, optionalAssets. exits 1 on errors.

## info

```
elyb info
```

prints current project state: id, version, paths, optionalAssets, builds.

## clean

```
elyb clean [--duplicates-only]
```

removes files from outputDir. `--duplicates-only` removes only `-duplicate.N.` files.

## watch

```
elyb watch [--no-assets] [--compression 0-9] [--interval <seconds>]
```

watches pluginRoot for changes and rebuilds automatically (default interval: 2s).

## optionalAssets

```
elyb add-ignore <path>
elyb del-ignore <path>
```

manages `optionalAssets` list in settings. used by `build --no-assets`.

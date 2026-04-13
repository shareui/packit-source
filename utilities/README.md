# elyb

cli tool for building elyxcore plugins.

> For non-release builds, it is not recommended to use --release

## init

```
elyb init <plugin-root> --refmap <path> [--outputdir <dir>] [--zipformat <ext>]
```

creates `.elyb/settings.json` in the current directory.

- `--outputdir` — where to put builds (default: `builds`)
- `--zipformat` — archive extension (default: `zip`)

## build

```
elyb build [--no-assets] [--compression 0-9] [--pass <password>] [--additional <path,...>] [--dry-run] [--release [-v]]
```

packs plugin into `{id}-{version}.{zipformat}`. if file already exists, saves as `-duplicate.N.`.

- `--no-assets` — exclude paths listed in `optionalAssets`
- `--compression` — zip compression level, 0-9 (default: 6)
- `--pass` — encrypt with AES password (requires `pip install pyzipper`)
- `--additional` — comma-separated extra paths to include
- `--dry-run` — print file list without building
- `--release` — compile `.py` files to `.pyc` via python3.11. files listed in `releaseIgnore` are kept as `.py`. requires python3.11 in PATH
- `-v` / `--verbose` — print compilation progress, only used with `--release`

## set-name

```
elyb set-name "<template>" [--release]
```

sets the output filename template. placeholders are any keys from metainfo: `{id}`, `{version}`, `{name}`, etc. unknown placeholders are left as-is.

```
elyb set-name "{name}_{id}_{version}"
# → builds/MyPlugin_shareui_myplugin_1.0.0.zip

elyb set-name "{id}-{version}-release" --release
# used only for --release builds
```

without `--release` writes to `buildName`. with `--release` writes to `buildNameRelease`. if `buildNameRelease` is not set, falls back to `buildName`, then to `{id}-{version}`.

## validate

```
elyb validate
```

checks refmap paths, metainfo fields, optionalAssets. exits 1 on errors.

## info

```
elyb info
```

prints current project state: id, version, paths, buildName, optionalAssets, builds.

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

## releaseIgnore

```
elyb add-release <path>
elyb del-release <path>
```

manages `releaseIgnore` list in settings. paths listed here are kept as `.py` during `build --release` instead of being compiled to `.pyc`.

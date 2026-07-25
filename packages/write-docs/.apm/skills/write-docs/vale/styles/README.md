# Vale styles

Two styles, both committed so the prose gate runs offline and deterministically.

## `WriteDocs/` -- house style, ours

The seven rules ported from the retired `slop-lint.py`, plus `NoUnicodeDash`.
Edit these freely. `vale sync` does not touch this directory: it removes only the
asset directory of a package it is installing, and no package is named
`WriteDocs`.

## `ai-tells/` -- vendored, MIT

[tbhb/vale-ai-tells](https://github.com/tbhb/vale-ai-tells) v1.25.0, fetched by
`vale sync` from the `Packages` URL pinned in `../.vale.ini`, then committed.
Copyright the vale-ai-tells authors, MIT licence; the release zip ships no
LICENSE file, so the attribution lives here.

**Do not hand-edit these files.** `vale sync` overwrites this directory wholesale.
Rule levels and disables are configured in `../.vale.ini` instead, which survives
a sync. Four rules are disabled and four demoted there, each with the measured
reason -- read those comments before re-enabling anything.

To take a newer upstream version: bump the pinned URL in `../.vale.ini`, run
`vale sync`, re-run the corpus calibration (`apm run slop-lint`), and re-check
the disable list against the new rule set.

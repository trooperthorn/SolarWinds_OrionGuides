## What this changes

<!-- One or two sentences. What will a reader be able to do that they could not before? -->

## Checks

```bash
make check
```

`make check` runs the tool tests, validates every SWQL statement in the repository
against the extracted schema, asserts the generated data is intact, confirms every entity
name mentioned in prose exists, and resolves every relative link.

- [ ] `make check` passes
- [ ] Every entity, property, verb and parameter I named was looked up, not recalled
- [ ] Anything I could not verify is marked as unverified, with a note on how a reader
      confirms it on their own server

## If you regenerated anything

Files under `data/` and `docs/reference/` are generated. Edit the generator, not the
output.

- [ ] `make data` and `make docs-reference` were re-run, and the result is committed

## Notes for review

<!-- Anything you are unsure about, or that you deliberately left unverified and why. -->

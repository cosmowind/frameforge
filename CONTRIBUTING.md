# Contributing to FrameForge

Thanks for looking. A few ground rules keep this repo usable.

## Package boundaries

The packages under `packages/` are deliberately independent. `codec-hmd` must not import
from `library`; `library` must not import from `platform`. If two packages need to
share code, put it in a third one or copy it deliberately and say why in the commit.

The one exception is the parameter contract: `platform` and `delivery-client` both
depend on the shape of `stereo-upload-params/*.zh-CN.json`. Changing that shape is a
breaking change for both.

## Never commit real data

This repository ships **synthetic** samples. If you add a sample, it must be invented:

- No real operator names, phone numbers, or email addresses.
- No real device serial numbers, volume serials, or hostnames.
- No real session paths.
- No credentials, of any kind.

`git diff --cached` before you push. If in doubt, run the leak scan in
`docs/SANITIZATION.md` — the same one used before the initial publication.

## Adding a sample

Prefer a generated file with an obviously fake value (`a1b2c3d4e5f60001`,
`HEADMOUNT-0001`, `op01`) over a redacted real one. A redacted value still leaks its
shape and length.

## Style

- Python: 4-space indent, type hints on public functions, no bare `except:`.
- TypeScript: strict mode, no `any` in exported signatures.
- Comments explain *why*, not *what*. The codebase is Chinese-commented; keep that
  convention for the code you touch, and write new prose in English.

## Pull requests

One capability per PR. Describe what changed and how you verified it — a command that
reproduces the behaviour is worth more than a paragraph.

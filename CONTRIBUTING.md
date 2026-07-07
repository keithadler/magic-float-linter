# Contributing to exact

Thanks for looking. This project is small, focused, and takes correctness
seriously - a linter that cries wolf is worse than no linter, so the bar for
what fires is deliberately high.

## The two most useful things you can contribute

1. **A real finding in a real package.** If `exact` flagged something in a
   published library and you've confirmed it's a genuine hand-typed constant -
   truncated or wrong - open an issue with the "Finding report" template. Those
   are the whole point of the tool.
2. **A false positive.** If `exact` flagged something that is *not* a magic
   constant, that's a bug in the tool and I want to know. Open an issue with the
   "False positive" template. The confidence gate is tuned to make these rare;
   each one is a chance to make it rarer.

## Development setup

```
git clone https://github.com/keithadler/magic-float-linter
cd magic-float-linter
pip install -e '.[dev]'
```

## Before opening a pull request

```
pytest            # the full suite must pass
ruff check .      # lint clean
exact src/        # the tool self-lints its own source; keep it clean
```

New behavior needs a test. The recognition engine is heavily tested by
example (`tests/`), and that's the right place to pin down a new constant, a
new tier, or a fixed false positive: add the literal and assert what `exact`
should say about it.

## Adding a constant to the table

Constants live in the recognition table with a form, a suggestion, and
sometimes a note. Two rules keep the table honest:

- **Every entry raises the evidence bar for every other entry** (the gate
  charges `log10(table size)` per match), so an entry has to earn its place -
  it should be a constant that genuinely appears hand-typed in real code, not
  every number with a name.
- **Prefer distinctive over merely correct.** A value that collides with common
  unrelated numbers (see the `[0, 0.5, 0.5, 1]` sequence story in the README)
  will produce misleading matches and should not be added.

If you're not sure whether something belongs, open an issue first and we can
talk it through before you write code.

## Scope

`exact` finds hand-typed exact constants in Python source. Things that are
explicitly *out* of scope (and why) are listed under "Scope and limitations" in
the README. Multi-language support is on the roadmap; if that's what you want to
work on, open an issue to coordinate before starting - it's a large change.

## Conduct

Be kind and assume good faith. This is a side project maintained in spare time;
patience is appreciated in both directions.

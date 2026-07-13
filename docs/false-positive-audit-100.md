# Large-scale false-positive audit: 100 popular non-scientific packages

**Date:** 2026-07-07. **Tool:** exact at commit `9912875`. **Method:** installed
100 of the most widely-used non-scientific Python packages into a single clean
Python 3.14 venv and ran `exact <pkg-dir> --exclude-tests --exit-zero
--format json` against each package's installed source tree. Every finding was
inspected by hand.

## Why this audit

[The corpus study](corpus-study.md) and [the AI/ML study](ai-ml-corpus-study.md)
scan the code that's *supposed* to contain mathematical constants - proving the
tool finds real bugs. [The first false-positive audit](false-positive-audit.md)
checked six ordinary packages to prove the tool stays quiet where it should.
This is that same accuracy test scaled up by more than an order of magnitude: if
the confidence gate is even slightly too permissive, running against 100 large
codebases full of ordinary numbers - version numbers, timeouts, buffer sizes,
byte counts, coordinates - is where the false positives would pile up.

The packages are deliberately **not** numeric or scientific. They are web
frameworks, HTTP clients, serializers, parsers, CLI toolkits, ORMs, database
drivers, cloud SDKs, dev tools, async runtimes, and utilities - the plumbing of
the Python ecosystem. Almost nothing in this code should be a recognized
mathematical constant.

## The 100 packages

**Web frameworks & APIs:** django, flask, fastapi, starlette, tornado, aiohttp,
sanic, bottle, falcon, pyramid, litestar, quart, djangorestframework,
strawberry-graphql, connexion.
**HTTP & networking:** requests, httpx, urllib3, httpcore, websockets, paramiko,
requests-oauthlib, certifi, charset-normalizer, idna.
**Serialization & parsing:** pyyaml, toml, tomlkit, orjson, ujson, msgpack,
jsonschema, lxml, beautifulsoup4, html5lib, markupsafe, defusedxml, xmltodict,
python-dotenv, configobj.
**CLI / terminal / TUI:** click, typer, rich, textual, prompt-toolkit, colorama,
tqdm, questionary, fire, blessed, pygments, tabulate.
**ORM & database:** sqlalchemy, peewee, tortoise-orm, pymongo, redis, asyncpg,
alembic, mongoengine, databases, elasticsearch.
**Cloud / infra / ops:** boto3, botocore, google-api-python-client, kubernetes,
docker, fabric, troposphere, azure-core.
**Dev tools / testing / packaging:** pytest, tox, black, flake8, isort, mypy,
pylint, coverage, hypothesis, faker, pre-commit, nox, pip, setuptools, wheel,
virtualenv, build, twine.
**Async & task queues:** celery, anyio, trio, gevent, rq, kombu.
**Utilities / date-time:** attrs, typing-extensions, python-dateutil, arrow,
jinja2, tenacity.

## Result

| | |
|---|---|
| packages installed | 100 |
| scanned (have Python source) | 99 |
| C-extension only, no Python to scan | 1 (ujson) |
| **total findings across all 99** | **1** |
| truncations | 0 |
| near-misses (likely typos) | 0 |
| false positives | 0 |

**The single finding, in Django, is correct - not a bug and not a false
positive.** It is the same recognition documented in the first audit:
`django/contrib/gis/measure.py` defines the exact, internationally-defined
mile-to-meters factor `1609.344` at full precision. The tool recognizes correct
code; it does not flag it as truncated or as a typo. Every other package - 98 of
them - produced **zero** findings across its entire installed source tree, at
every recognition tier and every finding code.

(ujson ships only as a compiled C extension - there is no Python source in its
installed package, so there is nothing for a Python-AST-based linter to read.
It is counted as unscanned rather than as a zero, to be exact about what was
actually examined.)

## What this establishes

The "finds real precision bugs" claim rests on the corpus and AI/ML studies.
This is the other half - the claim that the tool is **quiet on ordinary code** -
made at a scale where a miscalibrated confidence gate would be obvious. Ninety-
nine large, real-world codebases, a single finding, and that finding is a
correct constant the library itself got right. Nothing to triage, nothing to
suppress, no wall of noise for a team to wade through before they trust it.

Combined with [the direct calibration check](docs/confidence-calibration.md)
(42,000 random literals, empirical false-positive rate below the formula's own
prediction at every threshold), the accuracy story is now evidenced from three
independent directions: the formula in isolation, ordinary application code, and
the code that's supposed to be full of constants.

## Reproduction

```
python -m venv venv
venv/bin/pip install exact-linter
venv/bin/pip install django flask fastapi ...   # the 100 packages above
# for each package, scan its installed directory:
venv/bin/exact venv/lib/python3.*/site-packages/<pkg> --exclude-tests --exit-zero
```

Note that a handful of these packages (ujson, and in part orjson, msgpack, lxml,
asyncpg, gevent) are compiled extensions with little or no Python source; their
zero/near-zero findings reflect that there is little Python to scan, not only
that the code is clean. The bulk of the 99 - the frameworks, SDKs, and dev
tools - are large, pure-Python trees, and those are where the null result
carries its weight. Findings will drift as these packages release new versions;
the numbers above are current as of the study date.

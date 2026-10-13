# padan

*Padan* (Indonesian): to match, to correspond. *Padanan* is a translator's word for an equivalent term.

LLM-assisted partner API integration. Given a travel partner's API specification, padan produces a field
mapping onto a canonical booking schema, a generated client and a validation suite. Deterministic rules
resolve what they can with high precision; the LLM only sees the fields the rules abstain on.

## Development

```bash
uv sync
make check   # ruff, mypy --strict, pytest: the same three checks CI requires
```

## Licence

MIT, covering this repository's code and labels. Third-party API specifications are fetched from their
sources and remain under their providers' terms; they are not redistributed here.

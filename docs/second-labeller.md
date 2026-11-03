# Labelling 13 fields for padan: instructions for the second labeller

Thank you for helping. This takes about an hour.

## What padan does

padan reads a travel partner's booking API documentation and maps each of the partner's fields onto
one canonical booking schema: for example, Viator's `booker.email` is the booking's `contact.email`.
To measure how well it does, I labelled every field by hand. Your labels on a sample tell us how far a
second person agrees with mine, which is how reliable my answer key is.

## What you get

- `viator-partner.second-labeller.yaml`: 13 fields from Viator's booking API. Each has the endpoint,
  whether it is a request or a response, the field's path, its type and its documentation (`evidence`).
- `targets.md`: every canonical target you can choose, with what it means. `[critical]` marks the ones
  where a wrong value costs money or a trip (prices, status, dates, vouchers and tickets).

## What to do

For each field, read its `evidence` and fill in `target` with exactly one of:

| Answer | When |
| --- | --- |
| a target from `targets.md`, e.g. `'contact.email'` | the field carries that value (in a request: padan writes that value into it) |
| `'NONE'` | the field carries nothing the schema holds (message metadata, codes only the partner uses, …) |
| `'ASK_PARTNER'` | it probably carries a target, but the documentation does not say enough to be sure |

For a canonical target, also fill in `kind`: `'direct'` if the value is copied as is, `'transform'` if
it needs a simple conversion (a date from a date-time, cents to an amount, a code to one of our
values), or `'derived'` if it needs several fields or a recipe. Leave `kind` as `''` for `NONE` and
`ASK_PARTNER`. You may add a line `  note: '...'` to any field if you want to explain.

Two examples from a different partner (not in your sample):

```yaml
  paths: ['productId']
  evidence: 'The product ID for this booking.'
  target: 'items[].product_id'
  kind: 'direct'

  paths: ['uuid']
  evidence: 'A unique UUID to identify the booking. Setting this value acts like an idempotency key …'
  target: 'NONE'
  kind: ''
```

## Rules

- **Work from the evidence in the sheet only.** Don't look up Viator's site or ask anyone.
- **No AI tools** (ChatGPT, Copilot, Claude or others), not even to tidy the file.
- If you are unsure, `ASK_PARTNER` is a perfectly good answer.
- Note your start and end time and send them back with the file.

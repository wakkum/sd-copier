# Problem-report endpoint

A Cloudflare Worker that receives problem reports from the app, stores the
full log in R2, and opens a GitHub issue summarising it.

## Why this exists

The app needs to report errors without the user having a GitHub account or
any account at all. Opening an issue requires a token, and a token shipped
inside a distributed binary is extractable with a text editor, so the app
cannot hold one. It lives here instead, as a Worker secret: the app posts
anonymously, the Worker authenticates as you.

## What it does with a report

1. Stores the full log in R2 under `reports/YYYY-MM/<timestamp>_<uuid>.txt`.
2. Opens an issue containing the version, platform, language, machine name,
   anything the user typed, and the last 200 log lines, with the R2 key for
   the full file.

If the issue cannot be opened the report is still in R2 and the app is told
it partially succeeded, rather than being told it failed and discarding it.

## Deploy

```bash
wrangler r2 bucket create sd-copier-reports
wrangler secret put GITHUB_TOKEN     # fine-grained PAT, Issues: read+write, on the reports repo only
wrangler secret put REPORT_KEY       # any random string; see "On the key" below
wrangler deploy
```

Then put the deployed URL into `REPORT_ENDPOINT` in `app.py`, and the same
`REPORT_KEY` into `REPORT_KEY` beside it, and rebuild.

Optional rate limiting:

```bash
wrangler kv namespace create REPORTS_KV
# paste the id into wrangler.toml, uncomment the block, redeploy
```

Optional, recommended: an R2 lifecycle rule expiring `reports/` after 90
days, so old logs do not accumulate indefinitely.

## On the key

`REPORT_KEY` ships inside the app, so it is extractable and is **not**
security. It is friction: it stops the endpoint being hit by anything that
merely finds the URL. The endpoint is designed to be safe when open:

- bodies capped at 256 KB, rejected before being read into memory
- at most 12 issues opened per hour when the KV namespace is bound
- the GitHub token is scoped to one private repo, issues only
- nothing the request sends is executed or trusted; it is stored and quoted

Worst case, someone wastes free-tier quota. Rotate the key by setting a new
secret and shipping a new build.

## Privacy

Reports contain folder names, drive labels, file paths and the machine name.
Point `GITHUB_REPO` at a **private** repo. The app asks the user before every
upload and shows what is being sent.

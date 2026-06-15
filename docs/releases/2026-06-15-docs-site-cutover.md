# docs.rocketride.org release + rocketride-docs sunset (2026-06-15)

DevOps handoff for cutting over the documentation site to the monorepo and
retiring the standalone `rocketride-org/rocketride-docs` repo.

---

## Slack message (copy/paste)

> :rocket: **Docs release request - docs.rocketride.org (today)**
>
> We're cutting over docs.rocketride.org to the monorepo. The old
> `rocketride-org/rocketride-docs` repo is being sunset - safe to delete once
> this deploy is verified (docs now live in `rocketride-server`).
>
> **Deploy**
> - Workflow: **Docs** (`.github/workflows/docs.yml`) - builds
>   `node scripts/build.js docs:build` -> `dist/docs` -> GitHub Pages.
> - :warning: It triggers on **push to `develop`** and **manual run** only -
>   **not on `main`**. For today's release, please **run it manually**: Actions ->
>   *Docs* -> *Run workflow* -> pick the ref we're releasing. (Merging to `main`
>   by itself will not deploy.)
>
> **One-time Pages/domain cutover** (old repo currently owns the domain)
> 1. On **rocketride-docs**: remove the `docs.rocketride.org` custom domain from
>    its Pages settings and disable its Pages/deploy workflow.
> 2. On **rocketride-server**: Settings -> Pages -> Source = **GitHub Actions**,
>    then set custom domain = **docs.rocketride.org** (GitHub writes the CNAME on
>    deploy; no CNAME file lives in the repo). Enable *Enforce HTTPS* once the cert
>    issues.
> 3. DNS unchanged: `docs.rocketride.org` CNAME -> `rocketride-org.github.io`.
>
> **What's shipping**
> - New **CLI quick start** + **Python/TypeScript SDK install cards**.
> - **5 new Concept pages** (Performance, Security Model, Error Handling, Advanced
>   Agents, Best Practices).
> - **3 Examples** (RAG, Webhook, Document Extraction) and a **new Integrations
>   section** (Anthropic, Qdrant, PostgreSQL, Neo4j, Aparavi AQL, Firecrawl).
> - **MCP** "pipelines as tools" guide + new **Observability** page; full
>   **self-hosting** rewrite.
> - **Site rebrand**: wordmark logo, Discord navbar link, restructured footer +
>   socials, new favicon, themed search.
> - Docs **build/generator** updates (gather/llms/spine) + node service
>   descriptions; "Web Hook" -> "Webhook" rename.
> - Last-mile accuracy pass (removed docs for an unshipped SDK method, fixed a few
>   source-drift items). ~100 redirects preserve old URLs.
>
> **Verify after deploy**
> - https://docs.rocketride.org loads over HTTPS (valid cert).
> - A couple of old URLs 301 to their new routes (redirects.ts).
> - Search works; spot-check a few new pages (CLI, an integration).
>
> Once that's green, **delete `rocketride-org/rocketride-docs`**. Ping me with the
> deploy run link and I'll smoke-test. Thanks! :pray:

---

## Deploy reference (for the record)

| Item | Value |
| --- | --- |
| Workflow | `.github/workflows/docs.yml` (name: **Docs**) |
| Triggers | `push` to `develop` (path-filtered) + `workflow_dispatch` (**no `main` trigger**) |
| Build | `node scripts/build.js docs:build` (gather -> index -> compile) |
| Output | `dist/docs` |
| Deploy | `actions/upload-pages-artifact` + `actions/deploy-pages@v4` -> GitHub Pages |
| Pages source | Must be **GitHub Actions** (required by the deploy-pages action) |
| Domain | `url: https://docs.rocketride.org/`, `baseUrl: /` in `packages/docs/docusaurus.config.ts`; no CNAME file (set in repo Pages settings) |
| Old-URL redirects | `packages/docs/redirects.ts` |

Notes:
- A custom domain attaches to only one repo's Pages at a time, so it must be
  detached from `rocketride-docs` before it can be set on `rocketride-server`.
- No file in the monorepo references `rocketride-docs`, so deleting the old repo
  is clean once the deploy is verified.

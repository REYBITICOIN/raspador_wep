# Agency Router + MCP Architecture

## Purpose

Use the Agency Agents catalog as small specialists without loading hundreds of prompts into every request. The router searches metadata first and loads one agent body only when a bounded task requires it.

## Components

1. **Browser Extension** collects visible marketplace evidence and sends authorized requests to the local API.
2. **FastAPI Control Plane** validates requests, records evidence, calculates margins, and exposes the Agency router.
3. **Agency Router** provides search, inspect, and load operations across the pinned Agency Agents submodule.
4. **Tool Gateway / MCP** will expose named tools with least-privilege scopes instead of unrestricted desktop access.
5. **Approval Gate** blocks publication, credential access, deletion, payments, and account changes until explicit approval.
6. **Audit Log** records agent, task, tool, target, result, timestamp, and approval identity.

## Current API

- `GET /v1/agency/status`
- `GET /v1/agency/search?q=...`
- `GET /v1/agency/agents/{slug}`
- `POST /v1/agency/load`

Loading an agent creates a task-specific prompt but does not authorize execution.

## Permission levels

| Level | Allowed |
| --- | --- |
| Observe | Read visible page data and non-secret project files |
| Analyze | Search, compare, calculate, and draft |
| Prepare | Create a draft listing or proposed file change |
| Execute with approval | Publish, send, modify account data, or write outside project |
| Forbidden | Extract passwords/tokens, bypass CAPTCHA, disable security, or conceal actions |

## Marketplace workflow

1. Product Importer
2. Evidence Collector
3. Image Curator
4. Measurement Validator
5. SEO Researcher
6. Commercial Writer
7. Margin Analyst
8. Marketplace Validator
9. Human Approval
10. Official API Publisher

Each stage receives only the structured output of the prior stage, its own bounded task, and the minimum tools required.


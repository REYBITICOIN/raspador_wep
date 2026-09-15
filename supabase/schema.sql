create extension if not exists pgcrypto;
create extension if not exists vector;

create type public.job_status as enum ('queued','running','completed','failed','cancelled');
create type public.provider_kind as enum ('ollama','nvidia','grok');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text,
  created_at timestamptz not null default now()
);

create table public.sources (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  base_url text not null,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  unique(user_id, base_url)
);

create table public.crawl_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  source_id uuid references public.sources(id) on delete set null,
  target_url text not null,
  instruction text not null,
  status public.job_status not null default 'queued',
  requested_provider public.provider_kind,
  started_at timestamptz,
  completed_at timestamptz,
  error_code text,
  created_at timestamptz not null default now()
);

create table public.pages (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid not null references public.crawl_jobs(id) on delete cascade,
  url text not null,
  title text,
  content_hash text not null,
  http_status integer,
  content_text text,
  captured_at timestamptz not null default now(),
  unique(job_id, url, content_hash)
);

create table public.extractions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid not null references public.crawl_jobs(id) on delete cascade,
  page_id uuid references public.pages(id) on delete cascade,
  schema_version text not null default '1',
  data jsonb not null default '{}'::jsonb,
  confidence numeric(5,4),
  created_at timestamptz not null default now()
);

create table public.products (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  extraction_id uuid references public.extractions(id) on delete set null,
  source_url text not null,
  title text not null,
  description text,
  price numeric(14,2),
  currency char(3),
  availability text,
  images jsonb not null default '[]'::jsonb,
  attributes jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table public.model_runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid references public.crawl_jobs(id) on delete set null,
  provider public.provider_kind not null,
  model text not null,
  input_tokens integer,
  output_tokens integer,
  latency_ms integer,
  estimated_cost_usd numeric(12,6),
  success boolean not null,
  error_code text,
  created_at timestamptz not null default now()
);

create table public.provider_settings (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  provider public.provider_kind not null,
  enabled boolean not null default false,
  model text,
  daily_budget_usd numeric(10,2) not null default 0,
  secret_configured boolean not null default false,
  updated_at timestamptz not null default now(),
  unique(user_id, provider)
);

create table public.audit_logs (
  id bigint generated always as identity primary key,
  user_id uuid references auth.users(id) on delete set null,
  action text not null,
  entity_type text,
  entity_id text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index crawl_jobs_user_created_idx on public.crawl_jobs(user_id, created_at desc);
create index crawl_jobs_status_idx on public.crawl_jobs(status) where status in ('queued','running');
create index pages_job_idx on public.pages(job_id);
create index extractions_job_idx on public.extractions(job_id);
create index products_user_created_idx on public.products(user_id, created_at desc);
create index model_runs_user_created_idx on public.model_runs(user_id, created_at desc);
create index audit_logs_user_created_idx on public.audit_logs(user_id, created_at desc);

alter table public.profiles enable row level security;
alter table public.sources enable row level security;
alter table public.crawl_jobs enable row level security;
alter table public.pages enable row level security;
alter table public.extractions enable row level security;
alter table public.products enable row level security;
alter table public.model_runs enable row level security;
alter table public.provider_settings enable row level security;
alter table public.audit_logs enable row level security;

create policy profiles_owner_all on public.profiles for all to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);
create policy sources_owner_all on public.sources for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy crawl_jobs_owner_all on public.crawl_jobs for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy pages_owner_all on public.pages for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy extractions_owner_all on public.extractions for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy products_owner_all on public.products for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy model_runs_owner_select on public.model_runs for select to authenticated using ((select auth.uid()) = user_id);
create policy provider_settings_owner_all on public.provider_settings for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy audit_logs_owner_select on public.audit_logs for select to authenticated using ((select auth.uid()) = user_id);

grant usage on schema public to authenticated;
grant select, insert, update, delete on public.profiles, public.sources, public.crawl_jobs, public.pages, public.extractions, public.products, public.provider_settings to authenticated;
grant select on public.model_runs, public.audit_logs to authenticated;


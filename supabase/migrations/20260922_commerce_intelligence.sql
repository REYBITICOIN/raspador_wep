-- Commerce Intelligence: historical evidence, costs, SEO and A/B tests.
create table public.monitored_products (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  channel text not null check (channel in ('mercadolivre','shopee','amazon','meta','website')),
  external_item_id text,
  canonical_url text not null,
  title text not null,
  seller text,
  currency text not null default 'BRL',
  active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, channel, canonical_url)
);

create table public.market_observations (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  monitored_product_id uuid not null references public.monitored_products(id) on delete cascade,
  price numeric(14,2) check (price is null or price >= 0),
  availability text,
  stock integer check (stock is null or stock >= 0),
  sales_estimate integer check (sales_estimate is null or sales_estimate >= 0),
  confidence numeric(5,4) check (confidence is null or confidence between 0 and 1),
  evidence jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now()
);

create table public.product_costs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  acquisition_cost numeric(14,2) not null default 0 check (acquisition_cost >= 0),
  packaging_cost numeric(14,2) not null default 0 check (packaging_cost >= 0),
  shipping_cost numeric(14,2) not null default 0 check (shipping_cost >= 0),
  tax_percent numeric(7,4) not null default 0 check (tax_percent between 0 and 100),
  other_cost numeric(14,2) not null default 0 check (other_cost >= 0),
  currency text not null default 'BRL',
  valid_from timestamptz not null default now(),
  valid_to timestamptz,
  created_at timestamptz not null default now(),
  check (valid_to is null or valid_to > valid_from)
);

create table public.keyword_observations (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  keyword text not null,
  channel text not null,
  category text,
  rank integer check (rank is null or rank > 0),
  search_volume integer check (search_volume is null or search_volume >= 0),
  source text not null,
  evidence jsonb not null default '{}'::jsonb,
  observed_at timestamptz not null default now()
);

create table public.ab_experiments (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  listing_id uuid references public.marketplace_listings(id) on delete cascade,
  name text not null,
  dimension text not null check (dimension in ('title','image','price','description')),
  status text not null default 'draft' check (status in ('draft','running','paused','completed','cancelled')),
  started_at timestamptz,
  ended_at timestamptz,
  created_at timestamptz not null default now(),
  check (ended_at is null or started_at is null or ended_at > started_at)
);

create table public.ab_variants (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  experiment_id uuid not null references public.ab_experiments(id) on delete cascade,
  label text not null,
  payload jsonb not null default '{}'::jsonb,
  is_control boolean not null default false,
  created_at timestamptz not null default now(),
  unique (experiment_id, label)
);

create table public.ab_metrics (
  id bigint generated always as identity primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  variant_id uuid not null references public.ab_variants(id) on delete cascade,
  impressions integer not null default 0 check (impressions >= 0),
  visits integer not null default 0 check (visits >= 0),
  conversions integer not null default 0 check (conversions >= 0),
  revenue numeric(14,2) not null default 0 check (revenue >= 0),
  observed_at timestamptz not null default now()
);

create table public.market_opportunities (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  channel text not null,
  category text not null,
  title text not null,
  demand_score numeric(6,3) check (demand_score is null or demand_score between 0 and 100),
  competition_score numeric(6,3) check (competition_score is null or competition_score between 0 and 100),
  margin_score numeric(6,3) check (margin_score is null or margin_score between 0 and 100),
  evidence jsonb not null default '{}'::jsonb,
  detected_at timestamptz not null default now()
);

create index monitored_products_user_channel_idx on public.monitored_products(user_id, channel, active);
create index market_observations_product_time_idx on public.market_observations(monitored_product_id, observed_at desc);
create index market_observations_user_time_idx on public.market_observations(user_id, observed_at desc);
create index product_costs_product_valid_idx on public.product_costs(product_id, valid_from desc);
create index keyword_observations_user_keyword_time_idx on public.keyword_observations(user_id, keyword, observed_at desc);
create index ab_experiments_user_status_idx on public.ab_experiments(user_id, status);
create index ab_variants_experiment_idx on public.ab_variants(experiment_id);
create index ab_metrics_variant_time_idx on public.ab_metrics(variant_id, observed_at desc);
create index market_opportunities_user_time_idx on public.market_opportunities(user_id, detected_at desc);

alter table public.monitored_products enable row level security;
alter table public.market_observations enable row level security;
alter table public.product_costs enable row level security;
alter table public.keyword_observations enable row level security;
alter table public.ab_experiments enable row level security;
alter table public.ab_variants enable row level security;
alter table public.ab_metrics enable row level security;
alter table public.market_opportunities enable row level security;

create policy monitored_products_owner_all on public.monitored_products for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy market_observations_owner_all on public.market_observations for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy product_costs_owner_all on public.product_costs for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy keyword_observations_owner_all on public.keyword_observations for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy ab_experiments_owner_all on public.ab_experiments for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy ab_variants_owner_all on public.ab_variants for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy ab_metrics_owner_all on public.ab_metrics for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy market_opportunities_owner_all on public.market_opportunities for all to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.monitored_products, public.market_observations, public.product_costs, public.keyword_observations, public.ab_experiments, public.ab_variants, public.ab_metrics, public.market_opportunities to authenticated;
grant usage, select on sequence public.market_observations_id_seq, public.keyword_observations_id_seq, public.ab_metrics_id_seq to authenticated;


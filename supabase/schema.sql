-- Quals Lingo database: run this once in the Supabase SQL editor (Dashboard > SQL Editor > New query > paste > Run).
-- It is safe to run again: every statement is idempotent.
--
-- Everything the app stores lives in one table of JSON documents addressed by a path, for example
--   data/users/<user id>/state   one person's progress (only they can read or write it)
--   league/<user id>             weekly league row (everyone signed in can read; only the owner writes)
--   slots/<id>                   mock board and study session bookings (everyone signed in can read and join)
--   reports/<user id>, subs/<user id>   flagged questions and suggested questions (owner and coordinators)
--   config/main, custom/<id>     coordinator notice and coordinator-added questions (coordinators write)
-- Progress is keyed by question ids, so shipping new app code never touches it.

create table if not exists public.docs (
  path        text primary key,
  coll        text generated always as (split_part(path, '/', 1)) stored,
  data        jsonb not null default '{}'::jsonb,
  owner       uuid not null default auth.uid() references auth.users(id) on delete cascade,
  updated_at  timestamptz not null default now()
);
create index if not exists docs_coll_idx on public.docs (coll);

create table if not exists public.profiles (
  id    uuid primary key references auth.users(id) on delete cascade,
  name  text not null default ''
);

-- Coordinators: add yourself with
--   insert into public.admins (user_id) select id from auth.users where email = 'you@example.com';
create table if not exists public.admins (
  user_id uuid primary key references auth.users(id) on delete cascade
);

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.admins where user_id = auth.uid());
$$;

-- Which paths a signed-in user may write.
create or replace function public.can_write(p text) returns boolean
language sql stable security definer set search_path = public as $$
  select case split_part(p, '/', 1)
    when 'data'    then p like 'data/users/' || auth.uid()::text || '/%'
    when 'league'  then p = 'league/'  || auth.uid()::text
    when 'reports' then p = 'reports/' || auth.uid()::text or public.is_admin()
    when 'subs'    then p = 'subs/'    || auth.uid()::text or public.is_admin()
    when 'slots'   then auth.uid() is not null
    when 'config'  then public.is_admin()
    when 'custom'  then public.is_admin()
    else false end;
$$;

-- Which paths a signed-in user may read.
create or replace function public.can_read(p text, own uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select case split_part(p, '/', 1)
    when 'league' then auth.uid() is not null
    when 'slots'  then auth.uid() is not null
    when 'config' then auth.uid() is not null
    when 'custom' then auth.uid() is not null
    else own = auth.uid() or public.is_admin() end;
$$;

alter table public.docs     enable row level security;
alter table public.profiles enable row level security;
alter table public.admins   enable row level security;

drop policy if exists docs_read   on public.docs;
drop policy if exists docs_insert on public.docs;
drop policy if exists docs_update on public.docs;
drop policy if exists docs_delete on public.docs;
create policy docs_read   on public.docs for select to authenticated using (public.can_read(path, owner));
create policy docs_insert on public.docs for insert to authenticated with check (public.can_write(path) and owner = auth.uid());
create policy docs_update on public.docs for update to authenticated using (public.can_write(path)) with check (public.can_write(path));
create policy docs_delete on public.docs for delete to authenticated using (owner = auth.uid() or public.is_admin());

drop policy if exists profiles_read  on public.profiles;
drop policy if exists profiles_write on public.profiles;
drop policy if exists profiles_upd   on public.profiles;
create policy profiles_read  on public.profiles for select to authenticated using (true);
create policy profiles_write on public.profiles for insert to authenticated with check (id = auth.uid());
create policy profiles_upd   on public.profiles for update to authenticated using (id = auth.uid()) with check (id = auth.uid());

drop policy if exists admins_read on public.admins;
create policy admins_read on public.admins for select to authenticated using (user_id = auth.uid());

-- Keep updated_at fresh and the owner fixed after the first write.
create or replace function public.docs_touch() returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  if tg_op = 'UPDATE' then new.owner := old.owner; end if;
  return new;
end $$;
drop trigger if exists docs_touch on public.docs;
create trigger docs_touch before insert or update on public.docs for each row execute function public.docs_touch();

-- Deep merge used by "join a session", "leave feedback" and similar partial updates, done atomically on the server.
create or replace function public.jsonb_deep_merge(a jsonb, b jsonb) returns jsonb
language sql immutable as $$
  select case
    when jsonb_typeof(a) = 'object' and jsonb_typeof(b) = 'object' then
      coalesce((select jsonb_object_agg(k,
        case when a ? k and b ? k then public.jsonb_deep_merge(a -> k, b -> k)
             when b ? k then b -> k else a -> k end)
        from (select jsonb_object_keys(a) k union select jsonb_object_keys(b)) keys), '{}'::jsonb)
    else b end;
$$;

create or replace function public.doc_merge(p_path text, p_patch jsonb) returns void
language plpgsql security invoker set search_path = public as $$
begin
  if not public.can_write(p_path) then raise exception 'not allowed' using errcode = '42501'; end if;
  insert into public.docs (path, data) values (p_path, p_patch)
  on conflict (path) do update set data = public.jsonb_deep_merge(public.docs.data, excluded.data);
end $$;

-- Live updates for the league, bookings, coordinator notice and custom questions.
do $$ begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and tablename = 'docs') then
    alter publication supabase_realtime add table public.docs;
  end if;
end $$;

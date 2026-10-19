grant select, insert, update, delete on all tables in schema public to authenticated;
grant execute on all functions in schema public to authenticated;
insert into auth.users values ('00000000-0000-0000-0000-00000000000a','a@x'),('00000000-0000-0000-0000-00000000000b','b@x'),('00000000-0000-0000-0000-00000000000c','coord@x');
insert into public.admins values ('00000000-0000-0000-0000-00000000000c');
set role authenticated;
-- user A
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-00000000000a',false);
insert into public.docs(path,data) values ('data/users/00000000-0000-0000-0000-00000000000a/state','{"lessons":3,"ts":1}');
insert into public.docs(path,data) values ('league/00000000-0000-0000-0000-00000000000a','{"xp":40}');
insert into public.docs(path,data) values ('slots/s1','{"host":"a","people":{}}');
insert into public.docs(path,data) values ('data/users/00000000-0000-0000-0000-00000000000a/state','{"lessons":4,"ts":2}') on conflict (path) do update set data=excluded.data;
select 'A sees own state', data->>'lessons' from public.docs where path like 'data/users/%';
-- user B
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-00000000000b',false);
select 'B sees others state rows (expect 0)', count(*) from public.docs where path like 'data/users/%';
select 'B sees league', count(*) from public.docs where coll='league';
select public.doc_merge('slots/s1','{"people":{"b":{"role":"examiner"}}}');
select 'merged slot', data from public.docs where path='slots/s1';
do $$ begin
  begin insert into public.docs(path,data) values ('data/users/00000000-0000-0000-0000-00000000000a/state','{"hack":1}'); raise notice 'FAIL: B wrote A state';
  exception when others then raise notice 'ok: B blocked writing A state (%)', sqlerrm; end;
  begin update public.docs set data='{"xp":9999}' where path='league/00000000-0000-0000-0000-00000000000a'; if found then raise notice 'FAIL: B updated A league'; else raise notice 'ok: B cannot update A league'; end if; end;
  begin insert into public.docs(path,data) values ('config/main','{"notice":"x"}'); raise notice 'FAIL: B wrote config';
  exception when others then raise notice 'ok: B blocked writing config'; end;
  begin perform public.doc_merge('league/00000000-0000-0000-0000-00000000000a','{"xp":1}'); raise notice 'FAIL: merge into A league';
  exception when others then raise notice 'ok: merge blocked on A league'; end;
end $$;
-- coordinator
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-00000000000c',false);
insert into public.docs(path,data) values ('config/main','{"notice":"Mocks Friday"}');
select 'coord is_admin', public.is_admin();
select 'coord sees all state rows', count(*) from public.docs where path like 'data/users/%';
-- profiles
insert into public.profiles values ('00000000-0000-0000-0000-00000000000c','Coord');
reset role;
select 'owners fixed', path, owner from public.docs order by path;

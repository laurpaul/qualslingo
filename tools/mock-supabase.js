/* Test double for vendor/supabase.js: an in-memory Supabase that persists to localStorage("mock-server"),
   so tests can sign up, reload, and check that progress survives. Used only by tools/test_site.py. */
(function(){
  const K="mock-server";
  const load=()=>{try{return JSON.parse(localStorage.getItem(K))||{users:{},docs:{},profiles:{},admins:[]}}catch(e){return {users:{},docs:{},profiles:{},admins:[]}}};
  const store=v=>localStorage.setItem(K,JSON.stringify(v));
  const merge=(a,b)=>{if(a&&b&&typeof a==="object"&&typeof b==="object"&&!Array.isArray(a)&&!Array.isArray(b)){const o=Object.assign({},a);for(const k in b)o[k]=k in a?merge(a[k],b[k]):b[k];return o}return b};
  window.supabase={createClient(){
    let listeners=[]; const sessKey="ql-auth";
    const getS=()=>{try{return JSON.parse(localStorage.getItem(sessKey))}catch(e){return null}};
    const emit=(e,s)=>listeners.forEach(f=>f(e,s));
    const me=()=>{const s=getS();return s&&s.user&&s.user.id};
    function q(table){
      let filt=[],op="select",payload=null,single=false;
      const api={
        select(){return api},eq(c,v){filt.push(r=>r[c]===v);return api},in(c,vs){filt.push(r=>vs.includes(r[c]));return api},limit(){return api},
        maybeSingle(){single=true;return api},
        upsert(row){op="upsert";payload=row;return api},
        delete(){op="delete";return api},
        then(res,rej){return Promise.resolve().then(()=>{
          const S=load(); const uid=me();
          if(table==="docs"){
            const rows=Object.entries(S.docs).map(([path,d])=>({path,coll:path.split("/")[0],data:d.data,owner:d.owner}));
            const can=p=>p.startsWith("data/users/")?p.startsWith("data/users/"+uid+"/"):["league","reports","subs"].includes(p.split("/")[0])?p.endsWith("/"+uid):p.split("/")[0]==="slots";
            const read=r=>["league","slots","config","custom"].includes(r.coll)||r.owner===uid;
            if(op==="upsert"){if(!uid||!can(payload.path))return {error:{message:"rls",code:"42501"}};const old=S.docs[payload.path];S.docs[payload.path]={data:payload.data,owner:old?old.owner:uid};store(S);return {error:null}}
            let out=rows.filter(read).filter(r=>filt.every(f=>f(r)));
            if(op==="delete"){out.forEach(r=>{if(r.owner===uid)delete S.docs[r.path]});store(S);return {error:null}}
            return single?{data:out[0]||null,error:null}:{data:out,error:null};
          }
          if(table==="profiles"){
            if(op==="upsert"){S.profiles[payload.id]=payload.name;store(S);return {error:null}}
            const out=Object.entries(S.profiles).map(([id,name])=>({id,name})).filter(r=>filt.every(f=>f(r)));
            return single?{data:out[0]||null,error:null}:{data:out,error:null};
          }
          return {data:null,error:null};
        }).then(res,rej)}
      };return api;
    }
    return {
      auth:{
        onAuthStateChange(f){listeners.push(f);return {data:{subscription:{unsubscribe(){}}}}},
        async getSession(){return {data:{session:getS()}}},
        async signInWithPassword({email,password}){const S=load();const u=Object.values(S.users).find(u=>u.email===email&&u.pw===password);if(!u)return {error:{message:"Invalid login credentials"}};const s={user:{id:u.id,email,user_metadata:{name:u.name}}};localStorage.setItem(sessKey,JSON.stringify(s));setTimeout(()=>emit("SIGNED_IN",s));return {data:{session:s},error:null}},
        async signUp({email,password,options}){const S=load();const id="u-"+Math.random().toString(36).slice(2,10);S.users[id]={id,email,pw:password,name:options&&options.data&&options.data.name};store(S);const s={user:{id,email,user_metadata:{name:S.users[id].name}}};localStorage.setItem(sessKey,JSON.stringify(s));setTimeout(()=>emit("SIGNED_IN",s));return {data:{session:s},error:null}},
        async signOut(){localStorage.removeItem(sessKey);return {error:null}},
        async resetPasswordForEmail(){return {error:null}},async updateUser(){return {error:null}}
      },
      from:q,
      async rpc(name,args){const S=load();const uid=me();if(name==="is_admin")return {data:S.admins.includes(uid)};if(name==="doc_merge"){const old=S.docs[args.p_path];S.docs[args.p_path]={data:merge(old?old.data:{},args.p_patch),owner:old?old.owner:uid};store(S);return {error:null}}return {data:null}},
      channel(){const ch={_p:{},on(){return ch},subscribe(cb){setTimeout(()=>cb&&cb("SUBSCRIBED"));return ch},presenceState(){return ch._p},track(o){ch._p={me:[o]};return Promise.resolve()}};return ch},
      removeChannel(){return Promise.resolve()}
    };
  }};
})();

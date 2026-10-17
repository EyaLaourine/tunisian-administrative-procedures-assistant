/* Actual HTTP tests, permitted only inside the disposable, network-isolated fixture container.
 * No production candidates, data, credentials, volumes, ports or external network are used.
 */
const assert = require('node:assert/strict');
assert.equal(process.env.N8N_API_REVIEW_SANDBOX, '1');
assert.equal(require('node:os').hostname(), 'tnaa-api-review-sandbox');
const {UpdateWorkflowPublicDto} = require('/usr/local/lib/node_modules/n8n/node_modules/@n8n/api-types');
let cookie = '', apiKey = '';
const passed = [], observations = [];
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const copy = x => structuredClone(x);
async function call(method, path, body, auth = 'api') {
  const headers = {'Content-Type':'application/json'};
  if (auth === 'api' && apiKey) headers['X-N8N-API-KEY'] = apiKey;
  if (auth === 'session' && cookie) headers.Cookie = cookie;
  const r = await fetch('http://127.0.0.1:5678'+path, {method, headers, ...(body === undefined?{}:{body:JSON.stringify(body)})});
  const raw = await r.text(); let data; try {data = JSON.parse(raw);} catch {data = null;}
  return {status:r.status, data, cookies:r.headers.getSetCookie()};
}
function check(name, condition) { assert.ok(condition, name); passed.push(name); }
function bodyOf(w) {return {name:w.name, nodes:copy(w.nodes), connections:copy(w.connections), settings:copy(w.settings)};}
async function get(id) {const r=await call('GET','/api/v1/workflows/'+id);assert.equal(r.status,200);return r.data;}
async function put(id, body, suffix='?publishIfActive=false', keyAuth='api') {
  return call('PUT','/api/v1/workflows/'+id+suffix,body,keyAuth);
}
async function pollWebhook(expected) {
  for (let i=0;i<70;i++) {
    const r=await call('POST','/webhook/neutral-api-review',{},'none');
    if (r.status===200 && r.data?.text===expected) return r;
    if (i===69) throw new Error('Fixture webhook did not converge to expected version');
    await pause(500);
  }
}
(async()=>{
  // Health can turn green before REST routes exist; wait for the actual auth route.
  for(let i=0;i<100;i++) {try {if((await call('GET','/api/v1/workflows/neutral',undefined,'none')).status===401)break;}catch{} if(i===99)throw Error('Sandbox API startup failed');await pause(500);}
  let r=await call('POST','/rest/owner/setup',{email:'fixture@example.invalid',firstName:'Neutral',lastName:'Fixture',password:'NeutralFixtureOnly-9264!'},'none');
  assert.equal(r.status,200,'fixture owner setup status'); cookie=r.cookies.map(x=>x.split(';')[0]).join('; '); assert.ok(cookie,'fixture session cookie missing');
  r=await call('POST','/rest/api-keys',{label:'Disposable neutral fixture',expiresAt:Math.floor(Date.now()/1000)+3600,scopes:['workflow:create','workflow:read','workflow:update','workflow:activate','credential:create']},'session');
  assert.equal(r.status,200,'fixture API key creation status');apiKey=r.data.data.rawApiKey;assert.ok(apiKey,'fixture API key missing');
  check('unauthenticated workflow GET rejected',(await call('GET','/api/v1/workflows/neutral',undefined,'none')).status===401);
  r=await call('POST','/api/v1/credentials',{name:'Neutral fixture credential',type:'httpHeaderAuth',data:{name:'X-Neutral-Fixture',value:'neutral-fixture-value'}});
  assert.equal(r.status,200);const credential={id:r.data.id,name:r.data.name};
  const w={name:'Neutral isolated API fixture',nodes:[
    {id:'neutral-webhook',name:'Neutral webhook',type:'n8n-nodes-base.webhook',typeVersion:2,webhookId:'neutral-webhook-id',position:[0,0],parameters:{httpMethod:'POST',path:'neutral-api-review',responseMode:'responseNode',options:{}}},
    {id:'neutral-response',name:'Neutral response',type:'n8n-nodes-base.respondToWebhook',typeVersion:1.4,position:[300,0],parameters:{respondWith:'json',responseBody:'{"text":"neutral original"}',options:{}}},
    {id:'neutral-disabled-http',name:'Neutral disabled HTTP',type:'n8n-nodes-base.httpRequest',typeVersion:4.2,disabled:true,position:[300,300],parameters:{url:'http://127.0.0.1:1/never-called',authentication:'genericCredentialType',genericAuthType:'httpHeaderAuth',options:{}},credentials:{httpHeaderAuth:credential}}
  ],connections:{'Neutral webhook':{main:[[{node:'Neutral response',type:'main',index:0}]]}},settings:{executionOrder:'v1',saveDataSuccessExecution:'none',saveDataErrorExecution:'none',saveManualExecutions:false}};
  check('installed DTO accepts neutral payload',UpdateWorkflowPublicDto.safeParse(w).success);
  for(const field of ['id','active','versionId','activeVersionId','createdAt','projectId'])check('installed DTO rejects '+field,!UpdateWorkflowPublicDto.safeParse({...w,[field]:field==='active'?true:'neutral'}).success);
  check('installed DTO rejects missing required name',!UpdateWorkflowPublicDto.safeParse({...w,name:undefined}).success);
  r=await call('POST','/api/v1/workflows',w);assert.equal(r.status,200);const id=r.data.id;const original=await get(id);
  check('creation preserves explicit node IDs',JSON.stringify(original.nodes.map(n=>n.id))===JSON.stringify(w.nodes.map(n=>n.id)));
  r=await put(id,bodyOf(original));assert.equal(r.status,200);
  check('inactive update remains unpublished',!r.data.active&&!r.data.activeVersionId);
  r=await call('POST',`/api/v1/workflows/${id}/publish`,{versionId:r.data.versionId});assert.equal(r.status,200);await pollWebhook('neutral original');
  const before=await get(id);const changed=bodyOf(before);changed.nodes[1].parameters.responseBody='{"text":"neutral updated"}';
  changed.nodes.push({id:'neutral-note',name:'Neutral note',type:'n8n-nodes-base.stickyNote',typeVersion:1,position:[0,-200],parameters:{content:'Neutral fixture annotation',width:400,height:200,color:5}});
  r=await put(id,changed);assert.equal(r.status,200);const saved=await get(id);
  check('PUT preserves workflow ID',saved.id===id);
  check('PUT preserves all submitted node IDs',JSON.stringify(saved.nodes.map(n=>n.id))===JSON.stringify(changed.nodes.map(n=>n.id)));
  check('PUT preserves connections',JSON.stringify(saved.connections)===JSON.stringify(changed.connections));
  check('PUT preserves credential reference',JSON.stringify(saved.nodes[2].credentials)===JSON.stringify(changed.nodes[2].credentials));
  check('PUT preserves webhook path',saved.nodes[0].parameters.path==='neutral-api-review');
  check('draft save keeps old publication',saved.active&&saved.activeVersionId===before.activeVersionId&&saved.versionId!==saved.activeVersionId);
  await pollWebhook('neutral original');passed.push('old webhook response survives draft update');
  r=await call('POST',`/api/v1/workflows/${id}/publish`,{versionId:saved.versionId});assert.equal(r.status,200);await pollWebhook('neutral updated');
  const published=await get(id);
  check('explicit publish selects exact saved version',published.active&&published.activeVersionId===saved.versionId&&published.activeVersion.versionId===saved.versionId);
  check('published snapshot matches candidate graph',JSON.stringify(published.activeVersion.nodes)===JSON.stringify(changed.nodes));
  const auto=bodyOf(published);auto.nodes[1].parameters.responseBody='{"text":"neutral automatic"}';r=await put(id,auto,'?publishIfActive=true');assert.equal(r.status,200);await pollWebhook('neutral automatic');passed.push('automatic republication supported with sufficient scope');
  // A deliberately limited fixture key proves the documented partial-success failure mode.
  r=await call('POST','/rest/api-keys',{label:'Disposable update-only fixture',expiresAt:Math.floor(Date.now()/1000)+3600,scopes:['workflow:read','workflow:update']},'session');assert.equal(r.status,200);
  const fullKey=apiKey;apiKey=r.data.data.rawApiKey;
  const partial=bodyOf(await get(id));partial.nodes[1].parameters.responseBody='{"text":"neutral draft only"}';r=await put(id,partial,'?publishIfActive=true');
  const limitedStatus=r.status;apiKey=fullKey;const partialSaved=await get(id);
  check('missing publish scope returns 403 after draft save',limitedStatus===403&&partialSaved.nodes[1].parameters.responseBody===partial.nodes[1].parameters.responseBody);
  await pollWebhook('neutral automatic');passed.push('403 publication failure leaves previous webhook response live');
  r=await put(id,bodyOf(before));assert.equal(r.status,200);const restoredDraft=await get(id);
  r=await call('POST',`/api/v1/workflows/${id}/publish`,{versionId:restoredDraft.versionId});assert.equal(r.status,200);await pollWebhook('neutral original');
  const restored=await get(id);
  check('rollback restores original graph and publication',restored.id===id&&restored.active&&JSON.stringify(restored.nodes)===JSON.stringify(before.nodes)&&JSON.stringify(restored.connections)===JSON.stringify(before.connections));
  r=await put(id,{...bodyOf(restored),active:false});check('HTTP rejects read-only active field',[400,422].includes(r.status));observations.push({test:'read_only_active',status:r.status});
  r=await put('neutral-nonexistent',bodyOf(restored));check('PUT missing ID does not create workflow',r.status===404);
  // Exercise successful/error output isolation using a local neutral HTTP fixture only.
  let upstreamStatus=200;
  const http=require('node:http');
  const upstream=http.createServer((_req,res)=>{res.writeHead(upstreamStatus,{'Content-Type':'application/json'});res.end('{"text":"neutral upstream"}');});
  await new Promise(resolve=>upstream.listen(18111,'127.0.0.1',resolve));
  try {
    const errors={name:'Neutral isolated error branches',nodes:[
      {id:'neutral-error-webhook',name:'Neutral error webhook',type:'n8n-nodes-base.webhook',typeVersion:2,position:[0,0],parameters:{httpMethod:'POST',path:'neutral-error-review',responseMode:'responseNode',options:{}}},
      {id:'neutral-upstream',name:'Neutral upstream',type:'n8n-nodes-base.httpRequest',typeVersion:4.2,position:[300,0],onError:'continueErrorOutput',parameters:{url:'http://127.0.0.1:18111',options:{timeout:2000}}},
      {id:'neutral-ok',name:'Neutral OK',type:'n8n-nodes-base.respondToWebhook',typeVersion:1.4,position:[600,0],parameters:{respondWith:'json',responseBody:'{"text":"neutral success"}',options:{responseCode:200}}},
      {id:'neutral-error',name:'Neutral error',type:'n8n-nodes-base.respondToWebhook',typeVersion:1.4,position:[600,200],parameters:{respondWith:'json',responseBody:'{"text":"neutral unavailable","error":"agent_unavailable"}',options:{responseCode:503}}}
    ],connections:{'Neutral error webhook':{main:[[{node:'Neutral upstream',type:'main',index:0}]]},'Neutral upstream':{main:[[{node:'Neutral OK',type:'main',index:0}],[{node:'Neutral error',type:'main',index:0}]]}},settings:copy(w.settings)};
    r=await call('POST','/api/v1/workflows',errors);assert.equal(r.status,200);const eid=r.data.id;
    r=await call('POST',`/api/v1/workflows/${eid}/publish`,{versionId:r.data.versionId});assert.equal(r.status,200);
    for(let i=0;i<70;i++){r=await call('POST','/webhook/neutral-error-review',{},'none');if(r.status===200)break;if(i===69)throw Error('Error fixture publication failed');await pause(500);}
    check('real n8n error branch does not intercept successful upstream',r.status===200&&r.data?.text==='neutral success');
    for(const status of [401,429,503]){
      upstreamStatus=status;r=await call('POST','/webhook/neutral-error-review',{},'none');
      check('real n8n maps upstream '+status+' to sanitized 503',r.status===503&&r.data?.error==='agent_unavailable'&&!('detail' in r.data));
    }
  } finally {await new Promise(resolve=>upstream.close(resolve));}
  console.log(JSON.stringify({status:'passed',tests:passed.length,passed,observations,fixture_only:true,external_network:false,live_requests:0,publication_convergence:'polled fixture webhook, bounded 35s'}));
})().catch(error=>{console.log(JSON.stringify({status:'failed',error_type:error.name,stage_assertion:error.message.split('\n')[0],passed,live_requests:0}));process.exitCode=1;});

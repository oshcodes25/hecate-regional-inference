import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const root=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
await fs.mkdir(out,{recursive:true});
const target=(await(await fetch('http://127.0.0.1:9235/json')).json()).find(t=>t.type==='page');
const ws=new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
let id=0;const pending=new Map(),exceptions=[],requests=[];
ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);clearTimeout(p.timer);m.error?p.reject(m.error):p.resolve(m.result);}}else if(m.method==='Runtime.exceptionThrown')exceptions.push(m.params);else if(m.method==='Network.requestWillBeSent')requests.push(m.params.request.url);});
function call(method,params={}){return new Promise((resolve,reject)=>{const key=++id;const timer=setTimeout(()=>reject(new Error(method+' timeout')),20000);pending.set(key,{resolve,reject,timer});ws.send(JSON.stringify({id:key,method,params}));});}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function ready(){for(let i=0;i<100;i++){if(await evaluate('document.readyState==="complete"&&Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0)'))return;await new Promise(r=>setTimeout(r,50));}throw new Error('Images did not load');}
async function screenshot(name){const r=await call('Page.captureScreenshot',{format:'png'});await fs.writeFile(path.join(out,name),Buffer.from(r.data,'base64'));}
await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
await call('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
const layouts=[];
for(const [name,width,height]of [['desktop',1440,1100],['mobile',390,844],['small-mobile',320,812]]){
  await call('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile:name!=='desktop'});
  await call('Page.navigate',{url:pathToFileURL(path.join(root,'index.html')).href});await ready();
  const state=await evaluate(`({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,white:getComputedStyle(document.body).backgroundColor==='rgb(255, 255, 255)',images:Array.from(document.images).map(i=>({src:i.getAttribute('src'),width:i.naturalWidth,alt:!!i.alt})),exampleRows:document.querySelectorAll('.measurements tbody tr').length,allRows:document.querySelectorAll('#all-results tbody tr').length,missingAnchors:Array.from(document.querySelectorAll('a[href^="#"]')).filter(a=>!document.querySelector(a.getAttribute('href'))).length})`);
  if(state.width!==width||state.scrollWidth>width||!state.white||state.images.length!==10||state.images.some(i=>!i.width||!i.alt)||state.exampleRows!==3||state.allRows!==11||state.missingAnchors)throw new Error(JSON.stringify(state));
  layouts.push({name,...state});
  await screenshot(name+'-top.png');
  if(name==='small-mobile')continue;
  for(const section of ['results','execution-figure','reproduce']){
    await evaluate(`document.getElementById('${section}').scrollIntoView({block:'start',behavior:'instant'})`);await screenshot(name+'-'+section+'.png');
  }
  for(const section of ['equivalence-check','all-results']){
    await evaluate(`document.querySelector('#${section} summary').click();document.getElementById('${section}').scrollIntoView({block:'start',behavior:'instant'})`);
    if(!await evaluate(`document.getElementById('${section}').open`))throw new Error('Disclosure failed');
    await screenshot(name+'-'+section+'.png');
  }
}
const hrefs=await evaluate('Array.from(document.querySelectorAll("a[href]")).map(a=>a.href)');
for(const href of hrefs){const u=new URL(href);if(u.protocol==='file:'&&!u.hash)await fs.access(decodeURIComponent(u.pathname));}
if(exceptions.length)throw new Error(JSON.stringify(exceptions));
const remote=requests.filter(s=>/^https?:/.test(s));if(remote.length)throw new Error(JSON.stringify(remote));
const result={status:'passed',offline:true,layouts,links:hrefs.length,exceptions,remoteRequests:remote,modelRuns:0};
await fs.writeFile(path.join(out,'browser-check.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({status:'passed',layouts:layouts.length,links:hrefs.length,figureImages:10,exampleRows:3,allRows:11,offline:true}));ws.close();

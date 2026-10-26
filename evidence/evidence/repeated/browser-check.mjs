import fs from 'node:fs/promises';
import path from 'node:path';
const out=process.argv[2];
const targets=await (await fetch('http://127.0.0.1:9233/json')).json();
const target=targets.find(t=>t.type==='page');
if(!target)throw new Error('No isolated QA page');
const ws=new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
let id=0;const pending=new Map(),exceptions=[];
ws.addEventListener('message',event=>{const message=JSON.parse(event.data);if(message.id){const p=pending.get(message.id);if(p){pending.delete(message.id);clearTimeout(p.timer);message.error?p.reject(message.error):p.resolve(message.result);}}else if(message.method==='Runtime.exceptionThrown')exceptions.push(message.params);});
function call(method,params={}){return new Promise((resolve,reject)=>{const key=++id;const timer=setTimeout(()=>reject(new Error(method+' timeout')),15000);pending.set(key,{resolve,reject,timer});ws.send(JSON.stringify({id:key,method,params}));});}
async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
async function shot(name){const r=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});await fs.writeFile(path.join(out,name),Buffer.from(r.data,'base64'));}
await call('Page.enable');await call('Runtime.enable');await call('Network.enable');
await call('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1080,deviceScaleFactor:1,mobile:false});
await call('Page.navigate',{url:process.argv[3]});
for(let i=0;i<100;i++){if(await evaluate('document.readyState === "complete" && typeof DATA !== "undefined" && document.images.length === 1 && document.images[0].complete && document.images[0].naturalWidth>0'))break;await new Promise(r=>setTimeout(r,50));}
const desktop=await evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,requests:DATA.length,figureDecoded:document.images[0].naturalWidth>0})');
const checks=await evaluate(`(()=>{const checks=[];for(let i=0;i<DATA.length;i++){select.value=i;select.dispatchEvent(new Event('change'));for(const limit of [255,32])for(const diff of [false,true]){ceiling.value=limit;difference.checked=diff;ceiling.dispatchEvent(new Event('input'));difference.dispatchEvent(new Event('change'));const r=DATA[i];for(const name of ['full','halo','regional']){const canvas=document.getElementById(name);if(canvas.width!==r.shape[1]||canvas.height!==r.shape[0])throw Error('Canvas geometry differs');const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;for(let j=0;j<r.arrays[name].length;j++){const raw=diff?Math.abs(r.arrays[name][j]-r.arrays.full[j]):r.arrays[name][j];const target=Math.min(255,Math.round(raw*255/limit));if(pixels[4*j]!==target||pixels[4*j+1]!==target||pixels[4*j+2]!==target||pixels[4*j+3]!==255)throw Error('Rendered prediction differs');}}checks.push({request:i,ceiling:limit,difference:diff,allPredictionPixelsChecked:true});}}select.value=0;ceiling.value=255;difference.checked=false;select.dispatchEvent(new Event('change'));return checks;})()`);
await evaluate('scrollTo(0,0)');await shot('repeated-desktop-top.png');
await evaluate('document.getElementById("case").scrollIntoView({block:"start"})');await shot('repeated-desktop-viewer.png');
await evaluate('select.value=10;select.dispatchEvent(new Event("change"))');await shot('repeated-desktop-large.png');
await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
await evaluate('select.value=0;select.dispatchEvent(new Event("change"));scrollTo(0,0)');
const mobile=await evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})');await shot('repeated-mobile-top.png');
await evaluate('document.getElementById("case").scrollIntoView({block:"start"})');await shot('repeated-mobile-viewer.png');
const result={status:'passed',offline:true,desktop,mobile,checks,exceptions};
if(desktop.width!==1440||desktop.scrollWidth>1440||mobile.width!==390||mobile.scrollWidth>390||desktop.requests!==11||!desktop.figureDecoded||exceptions.length)throw Error(JSON.stringify(result));
await fs.writeFile(path.join(out,'browser-check.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({status:result.status,offline:true,desktop,mobile,states:checks.length,exceptions:exceptions.length}));ws.close();

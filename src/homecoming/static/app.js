'use strict';
const $ = (id) => document.getElementById(id);
const state = {connected:false, bootstrap:null, results:null, selected:null, routeKind:'bus', routeSeq:0,
  draft:0, extractSeq:0, walkSeq:0, pick:'start', markers:{}, pdfUrl:null};
const esc = value => String(value ?? '').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = (n,d=1) => n==null ? 'Unavailable' : Number(n).toLocaleString('en-HK',{maximumFractionDigits:d});
const minutes = n => n==null ? '—' : `${fmt(n/60)} min`;
const distance = n => n==null ? '—' : n>=1000 ? `${fmt(n/1000,2)} km` : `${fmt(n,0)} m`;
const show = (id,visible=true) => $(id).classList.toggle('hidden',!visible);
async function api(path, options={}) {
  const response = await fetch(path,{credentials:'same-origin',...options});
  let body; try { body=await response.json(); } catch { throw new Error('The local app returned an unreadable response. Please retry.'); }
  if(!response.ok) {
    const detail=typeof body.detail==='string' ? body.detail : Array.isArray(body.detail) ? body.detail.map(x=>x.msg).join('; ') : 'The request could not be completed.';
    throw new Error(detail);
  }
  return body;
}
const post = (path, body) => api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function notice(message, success=false) { $('notice').textContent=message; $('notice').className='notice'+(success?' success':''); }
async function pollJob(id, current=()=>true) {
  for(let attempt=0;attempt<600;attempt++) {
    if(!current()) return null;
    const job=await api('/api/jobs/'+encodeURIComponent(id));
    if(job.status==='done') return job.result;
    if(job.status==='failed') throw new Error(job.error);
    await new Promise(resolve=>setTimeout(resolve,1000));
  }
  throw new Error('This operation is taking longer than expected. You can retry shortly.');
}
function setConnection(connected) {
  state.connected=connected;
  $('connection-button').classList.toggle('connected',connected);
  $('connection-label').textContent=connected?'DeepSeek connected':'Connect DeepSeek';
  show('disconnect-button',connected);
}
function connectionDialog() { $('connection-error').textContent=''; $('connection-dialog').showModal(); }
$('connection-button').addEventListener('click',connectionDialog);
for(const id of ['close-connection','skip-connection']) $(id).addEventListener('click',()=>$('connection-dialog').close());
$('connection-form').addEventListener('submit',async e=>{
  e.preventDefault(); $('connect-submit').disabled=true; $('connection-error').textContent='';
  try { await post('/api/connection',{api_key:$('api-key').value.trim()});setConnection(true);$('api-key').value='';$('connection-dialog').close();notice('DeepSeek is connected. Upload a form, or review your parameters and search.',true); }
  catch(error) { $('connection-error').textContent=error.message; }
  finally { $('connect-submit').disabled=false; }
});
$('disconnect-button').addEventListener('click',async()=>{await api('/api/connection',{method:'DELETE'});setConnection(false);$('api-key').value='';$('connection-dialog').close();});
function setView(walk) {
  show('find-view',!walk);show('walk-view',walk);
  $('find-tab').classList.toggle('active',!walk);$('walk-tab').classList.toggle('active',walk);
  if(walk) loadPointMap().catch(error=>notice(error.message));
}
$('find-tab').addEventListener('click',()=>setView(false));$('walk-tab').addEventListener('click',()=>setView(true));
function setStep(step) { for(const [key,num] of [['upload',1],['review',2],['results',3]]) $('step-'+key).classList.toggle('current',num===step); }
function draftChanged() {
  state.draft++; $('review-status').textContent=state.results?'Changes awaiting confirmation':'Awaiting your review';
  if(state.results) { $('submit-caption').textContent='Preferences changed. Press Yes, search to update results.';$('submit-caption').classList.add('stale-caption'); }
}
$('preferences-form').addEventListener('input',draftChanged);
$('preferences-form').addEventListener('change',draftChanged);
$('manual-button').addEventListener('click',()=>{setStep(2);$('applicant-name').focus();$('review-status').textContent='Fill in your preferences';});
$('dropzone').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();$('pdf-input').click();}});
for(const event of ['dragenter','dragover']) $('dropzone').addEventListener(event,e=>{e.preventDefault();$('dropzone').classList.add('dragover');});
for(const event of ['dragleave','drop']) $('dropzone').addEventListener(event,e=>{e.preventDefault();$('dropzone').classList.remove('dragover');});
$('dropzone').addEventListener('drop',e=>{if(e.dataTransfer.files[0]) upload(e.dataTransfer.files[0]);});
$('pdf-input').addEventListener('change',e=>{if(e.target.files[0]) upload(e.target.files[0]);});
function applyExtraction(profile) {
  $('applicant-name').value=profile.applicant_name||'';
  $('household-size').value=profile.household_size||'';
  $('district-select').value=profile.housing_district||'';
  for(const input of document.querySelectorAll('[name=wheelchair]')) {input.checked=profile.wheelchair_required!==null&&input.value===String(profile.wheelchair_required);input.required=true;}
  $('hospital-select').value='';
  if(profile.hospital_mentioned) {
    const match=state.bootstrap.hospitals.find(r=>r.name.toLowerCase()===profile.hospital_mentioned.toLowerCase());
    if(match) $('hospital-select').value=match.id;
  }
  const issues=[...(profile.issues||[])];
  if(profile.wheelchair_required===null) issues.push('Choose general walking or wheelchair routes before submitting.');
  if(profile.hospital_mentioned&&!$('hospital-select').value) issues.push(`Hospital mentioned: ${profile.hospital_mentioned}. Please select it from the hospital list.`);
  $('extraction-evidence').innerHTML=(issues.length?'<strong>Please review</strong><ul>'+issues.map(i=>`<li>${esc(i)}</li>`).join('')+'</ul>':'<p>Fields extracted. Please check the prefilled values.</p>')+
    (profile.evidence?.length?'<details><summary>See extraction evidence</summary>'+profile.evidence.map(x=>`<p>Page ${esc(x.page)} · ${esc(x.text)}</p>`).join('')+'</details>':'');
  show('extraction-evidence');$('review-status').textContent='Awaiting operator review';
  $('extract-status').className='extract-status';$('extract-status').textContent='Details prefilled. Review the form, choose a hospital if needed, then press Yes, search.';
  setStep(2);state.draft++;
  // Deliberately no form submission, search, or overview request here.
}
async function upload(file) {
  const sequence=++state.extractSeq;
  if(!file.name.toLowerCase().endsWith('.pdf')||file.size>15*1024*1024) {notice('Choose a PDF smaller than 15 MB.');return;}
  $('upload-label').textContent=file.name;$('upload-caption').textContent='Choose another PDF to replace this file';
  if(state.pdfUrl) URL.revokeObjectURL(state.pdfUrl);
  state.pdfUrl=URL.createObjectURL(file);$('pdf-preview').src=state.pdfUrl;show('pdf-preview-wrap');
  if(!state.connected) {notice('Connect DeepSeek to extract this PDF, then choose the file again. You can also enter the parameters manually.');connectionDialog();return;}
  const revision=state.draft;
  $('extract-status').className='extract-status busy';$('extract-status').textContent='Reading the application with DeepSeek…';show('extract-status');show('extraction-evidence',false);
  try {
    const form=new FormData();form.append('file',file);
    const job=await api('/api/extract',{method:'POST',body:form});
    const result=await pollJob(job.job_id,()=>sequence===state.extractSeq);
    if(!result||sequence!==state.extractSeq)return;
    if(revision!==state.draft) {
      $('extract-status').className='extract-status';$('extract-status').textContent='Extraction is ready. You edited the form while it was being read. ';
      const button=document.createElement('button');button.className='text-button';button.type='button';button.textContent='Apply extracted fields';button.onclick=()=>applyExtraction(result);$('extract-status').append(button);
    } else applyExtraction(result);
  } catch(error) {if(sequence===state.extractSeq){$('extract-status').className='extract-status';$('extract-status').textContent=error.message+' You can continue with manual input.';}}
}
function parameters() {
  const wheelchair=document.querySelector('[name=wheelchair]:checked');
  if(!wheelchair) throw new Error('Choose general walking or wheelchair routes.');
  const weights={bus:Number($('bus-weight').value),mtr:Number($('mtr-weight').value),hospital:Number($('hospital-weight').value)};
  if(Object.values(weights).some(n=>!Number.isFinite(n)||n<0)||Object.values(weights).every(n=>n===0))throw new Error('Use nonnegative priorities with at least one greater than zero.');
  return {applicant_name:$('applicant-name').value.trim(),household_size:$('household-size').value?Number($('household-size').value):null,
    housing_district:$('district-select').value||null,wheelchair:wheelchair.value==='true',hospital_id:$('hospital-select').value||null,scenario:$('scenario-select').value,weights};
}
$('preferences-form').addEventListener('submit',async e=>{
  e.preventDefault();$('search-button').disabled=true;show('notice',false);
  try {
    const p=parameters();
    const result=await post('/api/search',{confirmed:true,parameters:p});
    state.results=result;state.selected=null;state.routeSeq++;
    renderResults();show('input-area',false);show('results-area');setStep(3);
    $('submit-caption').textContent='Review first. Nothing is submitted automatically.';$('submit-caption').classList.remove('stale-caption');
    $('results-area').scrollIntoView({behavior:'smooth',block:'start'});
    if(state.connected) requestOverview(result.search_id);else renderOverviewUnavailable();
  } catch(error) {notice(error.message);}
  finally {$('search-button').disabled=false;}
});
$('edit-preferences').addEventListener('click',()=>{show('input-area');setStep(2);$('input-area').scrollIntoView({behavior:'smooth'});});
function renderResults() {
  const r=state.results,p=r.parameters;
  $('results-title').textContent=p.applicant_name?`${p.applicant_name}’s next chapter.`:'A closer look at your options.';
  const hospital=state.bootstrap.hospitals.find(h=>h.id===p.hospital_id);
  const labels=[p.housing_district||'All areas',p.wheelchair?'Wheelchair routes':'General walking',hospital?.name||'Nearest reachable hospital'];
  if(p.household_size)labels.push(`${p.household_size} household member${p.household_size===1?'':'s'}`);
  if(p.scenario==='baseline')labels.push('Baseline evidence');
  $('profile-chips').innerHTML=labels.map(t=>`<span>${esc(t)}</span>`).join('');
  $('estate-count').textContent=`${r.estates.length} estates`;
  $('list-footer').textContent=`${r.complete} complete · ${r.incomplete} incomplete. Missing routes stay visible without a numeric rank.`;
  $('estate-filter').value='';renderEstateList();
  if(r.estates.length) selectEstate(r.estates[0].id);
  else $('estate-detail').innerHTML='<div class="empty-result">No estates match these preferences.</div>';
}
function renderEstateList() {
  const term=$('estate-filter').value.toLowerCase();
  const rows=state.results.estates.filter(r=>(r.name_en+' '+r.name_zh_hant).toLowerCase().includes(term));
  $('estate-list').innerHTML=rows.map(r=>`<button type="button" role="listitem" class="estate-card${state.selected?.id===r.id?' selected':''}" data-estate="${esc(r.id)}" aria-label="${esc(r.rank?'Rank '+r.rank+', ':'')}${esc(r.name_en)}"><span class="estate-rank">${r.rank??'—'}</span><span class="estate-card-main"><strong>${esc(r.name_en)}</strong><span class="estate-zh">${esc(r.name_zh_hant||'')}</span><span class="estate-metrics"><span>Bus ${minutes(r.bus_time_s)}</span><span>MTR ${minutes(r.mtr_time_s)}</span><span>Hospital ${distance(r.hospital_distance_m)}</span></span></span>${r.final_cost==null?'<span class="incomplete-tag">Incomplete</span>':`<span class="estate-score">${fmt(r.final_cost,2)}<small>COST / 100</small></span>`}</button>`).join('')||'<div class="empty-result">No matching estates in this list.</div>';
  $('estate-list').querySelectorAll('[data-estate]').forEach(button=>button.onclick=()=>selectEstate(button.dataset.estate));
}
$('estate-filter').addEventListener('input',renderEstateList);
function selectEstate(id) {
  state.selected=state.results.estates.find(r=>r.id===id);state.routeKind='bus';renderEstateList();renderDetail();
}
function renderDetail() {
  const r=state.selected;
  $('estate-detail').innerHTML=`<div class="detail-heading"><div><p class="eyebrow">${r.rank?'RANK '+r.rank:'INCOMPLETE RESULT'} · ${esc(r.housing_district)}</p><h2>${esc(r.name_en)}</h2><div class="zh-name">${esc(r.name_zh_hant||'')}</div></div><div class="large-score">${r.final_cost==null?'—':fmt(r.final_cost,2)}<small>${r.final_cost==null?'No total cost':'COST / 100'}</small></div></div><div class="route-tabs" role="tablist">${[['bus','Bus stop'],['mtr','MTR access'],['hospital','Hospital']].map(([key,label])=>`<button class="route-tab${key===state.routeKind?' active':''}" role="tab" aria-selected="${key===state.routeKind}" data-kind="${key}">${label}</button>`).join('')}</div><div id="route-content"></div>${breakdown(r)}`;
  $('estate-detail').querySelectorAll('[data-kind]').forEach(button=>button.onclick=()=>{
    state.routeKind=button.dataset.kind;
    $('estate-detail').querySelectorAll('[data-kind]').forEach(b=>{b.classList.toggle('active',b===button);b.setAttribute('aria-selected',String(b===button));});
    loadRoute();
  });loadRoute();
}
function breakdown(r) {
  const weights=state.results.policy.normalised_weights;
  return `<section class="cost-breakdown"><h3>How this estate compares</h3>${['bus','mtr','hospital'].map(k=>`<div class="cost-row"><span>${k==='mtr'?'MTR':k[0].toUpperCase()+k.slice(1)} <small>${fmt(weights[k]*100,0)}%</small></span><div class="cost-bar"><span style="width:${r[k+'_scaled_cost']??0}%"></span></div><span>${r[k+'_scaled_cost']==null?'Unavailable':fmt(r[k+'_scaled_cost'],2)+' / 100'}</span></div>`).join('')}<p class="formula-note">Component cost = 100 × x / (x + k). Reference values: bus 10 min, MTR 15 min, hospital 5 km. The total is the weighted sum; lower is better.${r.missing_components.length?' Missing required components: '+esc(r.missing_components.join(', '))+'.':''}</p></section>`;
}
async function loadRoute(targetOverride) {
  const r=state.selected,kind=state.routeKind,sequence=++state.routeSeq;
  const targets=r[kind+'_targets'];
  if(!targets.length) {
    $('route-content').innerHTML=`<div class="no-route">No reachable ${kind==='mtr'?'MTR access point':kind==='bus'?'bus stop':'hospital'} in this saved calculation.${r[kind+'_reason']?'<br>'+esc(readableReason(r[kind+'_reason'])):''}</div>`;return;
  }
  const target=targets.find(t=>t.id===targetOverride)||targets[0];
  $('route-content').innerHTML='<p class="muted loading-text">Loading the prepared route…</p>';
  try {
    const p=state.results.parameters;
    const query=new URLSearchParams({estate_id:r.id,target_id:target.id,wheelchair:p.wheelchair,scenario:p.scenario});
    const route=await api('/api/route?'+query);
    if(sequence!==state.routeSeq)return;
    const value=kind==='hospital'?distance(route.cost):minutes(route.cost);
    $('route-content').innerHTML=`<div class="destination-heading">${esc(target.name)}</div><p class="route-measurements"><strong>${value}</strong> ${kind==='hospital'?'pedestrian-network distance':'modelled walking time'}${route.map&&kind!=='hospital'?' · '+distance(route.map.distance_m):''}</p>${targets.length>1?`<label class="tied-select">Equally ranked destinations<select id="tied-target">${targets.map(t=>`<option value="${esc(t.id)}" ${t.id===target.id?'selected':''}>${esc(t.name)}</option>`).join('')}</select></label>`:''}<div id="estate-map"></div>${routeNotes(route)}`;
    if($('tied-target'))$('tied-target').onchange=e=>loadRoute(e.target.value);
    if(route.map) mapViewer($('estate-map'),route.map.files,route.map.title,false);
    else $('estate-map').innerHTML='<div class="no-route">This route’s map is still being prepared. Its saved cost is shown above.</div>';
  } catch(error) {if(sequence===state.routeSeq)$('route-content').innerHTML=`<div class="no-route">${esc(error.message)}</div>`;}
}
function readableReason(s) {return String(s).replaceAll('_',' ').replaceAll(';','; ');}
function routeNotes(route) {
  const warnings=route.warnings||[];const notes=[];
  if(route.shared_general_hospital)notes.push('Hospital distance uses the general walking network, including in wheelchair mode. It is not a verified wheelchair-accessible hospital journey.');
  if(warnings.includes('long_connector')||warnings.includes('connector_above_threshold'))notes.push('Includes a longer assumed connection between a map point and the pedestrian network.');
  if(route.uses_estimated_time)notes.push(`Includes ${fmt(route.estimated_seconds)} seconds of reviewed estimated traversal time.`);
  if(warnings.includes('reviewed_hospital_origin_override'))notes.push('Uses this estate’s reviewed hospital-only network connection.');
  notes.push('Endpoint connections are approximate; entrance levels are unverified. Vehicle journeys, waiting times and live closures are outside this model.');
  return notes.map(n=>`<p class="route-note">${esc(n)}</p>`).join('');
}
function mapViewer(container,files,title,runtime) {
  const local={mode:'static',hd:false,format:'webp',generation:0};
  container.innerHTML=`<div class="map-controls"><div class="segmented"><button type="button" data-display="static" class="active">Static</button><button type="button" data-display="svg">Interactive SVG</button></div><div class="segmented quality-controls"><button type="button" data-quality="standard" class="active">Standard</button><button type="button" data-quality="hd">HD</button></div><div class="segmented format-controls"><button type="button" data-format="webp" class="active">WebP</button><button type="button" data-format="png">PNG</button></div></div><div class="map-viewer"></div><div class="map-downloads"><span class="map-help">Prepared route · offline context</span><a class="map-download" download>Download WebP ↓</a></div>`;
  const viewer=container.querySelector('.map-viewer'),download=container.querySelector('.map-download');
  const asset=files.standard.split('/').pop().replace('.webp','');
  function pngUrl(){return '/api/export/png?'+new URLSearchParams({asset,hd:local.hd,runtime});}
  async function update() {
    const generation=++local.generation;
    container.querySelector('.interactive-map-legend')?.remove();
    container.querySelectorAll('[data-display]').forEach(b=>b.classList.toggle('active',b.dataset.display===local.mode));
    container.querySelectorAll('[data-quality]').forEach(b=>b.classList.toggle('active',(b.dataset.quality==='hd')===local.hd));
    container.querySelectorAll('[data-format]').forEach(b=>b.classList.toggle('active',b.dataset.format===local.format));
    container.querySelector('.quality-controls').classList.toggle('hidden',local.mode==='svg');container.querySelector('.format-controls').classList.toggle('hidden',local.mode==='svg');
    container.querySelector('.map-help').textContent=local.mode==='svg'?'Scroll to zoom · drag to pan · DTM terrain + original paths · hover for costs':'DTM terrain + original paths · '+(local.hd?'3000 px HD':'1200 px standard');
    if(local.mode==='svg') {
      download.href=files.svg;download.textContent='Download SVG ↓';
      viewer.innerHTML='<p class="empty-result loading-text">Loading vector route…</p>';
      try {const response=await fetch(files.svg);if(!response.ok)throw new Error('Vector map unavailable.');const text=await response.text();if(generation!==local.generation)return;
        // Only app-generated SVG from a fixed same-origin asset URL is inserted.
        viewer.innerHTML=text;const svg=viewer.querySelector('svg');svg.setAttribute('aria-label',title);
        // The page already provides the route title. Keep exported map captions
        // in the download, but avoid floating paper labels when panning here.
        svg.querySelectorAll(':scope > rect, :scope > text[x="28"], :scope > text[x="890"], :scope > path').forEach(node=>node.remove());
        const legend=document.createElement('div');legend.className='interactive-map-legend';
        legend.innerHTML='<span><i style="background:#0755c9"></i>Route</span><span><i style="background:#a64b00"></i>Assumed connection</span><span><i style="background:#00745b"></i>Lift</span><span><i style="background:#783eb4"></i>Estimated time</span><small>DTM / paths: Lands Department · © OpenStreetMap contributors</small>';
        viewer.after(legend);installZoom(svg,viewer);
      } catch(error) {if(generation===local.generation)viewer.innerHTML=`<p class="empty-result">${esc(error.message)}</p>`;}
    } else {
      const url=local.format==='png'?pngUrl():local.hd?files.hd:files.standard;
      download.href=url;download.textContent=`Download ${local.format.toUpperCase()} ↓`;
      viewer.innerHTML=`<img src="${esc(url)}" alt="${esc(title)}" decoding="async">`;
    }
  }
  container.querySelectorAll('[data-display]').forEach(b=>b.onclick=()=>{local.mode=b.dataset.display;update();});
  container.querySelectorAll('[data-quality]').forEach(b=>b.onclick=()=>{local.hd=b.dataset.quality==='hd';update();});
  container.querySelectorAll('[data-format]').forEach(b=>b.onclick=()=>{local.format=b.dataset.format;update();});update();
}
function installZoom(svg,viewer,initial=[0,0,1000,700]) {
  let view=[...initial],drag=null,detailTimer=null,detailRequest=null;
  const bounds=svg.dataset.contextBounds?svg.dataset.contextBounds.split(' ').map(Number):null;
  const detail=svg.querySelector('#local-path-detail');
  const markers=detail?[...svg.querySelectorAll(':scope > circle')]:[];
  async function updateDetail() {
    if(!detail||!svg.isConnected)return;
    if(detailRequest)detailRequest.abort();
    detailRequest=new AbortController();
    const [cx,cy]=svg.dataset.center.split(' ').map(Number),scale=Number(svg.dataset.gridScale);
    const [x,y,w,h]=view;
    // Add a small buffer so detail persists during the next short pan.
    const pad=w*.12;
    const params=new URLSearchParams({left:cx+(x-pad-500)/scale,right:cx+(x+w+pad-500)/scale,
      bottom:cy+(365-y-h-pad)/scale,top:cy+(365-y+pad)/scale,cx,cy,scale});
    const requestedView=view.join(' ');
    try {
      const response=await fetch('/api/map/context?'+params,{signal:detailRequest.signal});
      if(!response.ok)return;
      const paths=await response.text();
      if(svg.isConnected&&requestedView===view.join(' ')){
        detail.innerHTML=paths;
        svg.querySelector('#pedestrian-background').style.opacity=paths?'0':'1';
      }
    } catch(error) { /* The complete prepared basemap remains available. */ }
  }
  const apply=()=>{
    if(bounds){
      view[0]=Math.max(bounds[0],Math.min(bounds[0]+bounds[2]-view[2],view[0]));
      view[1]=Math.max(bounds[1],Math.min(bounds[1]+bounds[3]-view[3],view[1]));
    }
    svg.setAttribute('viewBox',view.join(' '));
    const markerScale=view[2]/initial[2];
    for(const marker of svg.querySelectorAll('.endpoint-marker')){
      marker.setAttribute('transform',`translate(${marker.dataset.x} ${marker.dataset.y}) scale(${markerScale})`);
    }
    for(const marker of markers){
      marker.setAttribute('r',11*markerScale);marker.setAttribute('stroke-width',3*markerScale);
      const label=marker.nextElementSibling;
      if(label?.tagName==='text'){label.setAttribute('font-size',11*markerScale);label.setAttribute('y',Number(marker.getAttribute('cy'))+4*markerScale);}
    }
    if(detail){
      svg.querySelector('#pedestrian-background').style.opacity='1';detail.innerHTML='';
      clearTimeout(detailTimer);detailTimer=setTimeout(updateDetail,180);
    }
  };
  const coordinate=e=>{const p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;return p.matrixTransform(svg.getScreenCTM().inverse());};
  const zoom=(factor,point={x:view[0]+view[2]/2,y:view[1]+view[3]/2})=>{const maxWidth=bounds?Math.min(bounds[2],bounds[3]*initial[2]/initial[3]):2200;const width=Math.max(40,Math.min(maxWidth,view[2]*factor)),ratio=width/view[2];view=[point.x-(point.x-view[0])*ratio,point.y-(point.y-view[1])*ratio,width,width*initial[3]/initial[2]];apply();};
  svg.addEventListener('wheel',e=>{e.preventDefault();zoom(e.deltaY>0?1.15:.87,coordinate(e));},{passive:false});
  const pointers=new Map();let pinch=null;
  svg.addEventListener('pointerdown',e=>{pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});svg.setPointerCapture(e.pointerId);if(pointers.size===1)drag={x:e.clientX,y:e.clientY,view:[...view]};if(pointers.size===2){const p=[...pointers.values()];pinch=Math.hypot(p[0].x-p[1].x,p[0].y-p[1].y);drag=null;}});
  svg.addEventListener('pointermove',e=>{if(!pointers.has(e.pointerId))return;pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});if(pointers.size===2){const p=[...pointers.values()],d=Math.hypot(p[0].x-p[1].x,p[0].y-p[1].y);if(pinch&&d)zoom(pinch/d);pinch=d;}else if(drag){const rect=svg.getBoundingClientRect();view=[drag.view[0]-(e.clientX-drag.x)*drag.view[2]/rect.width,drag.view[1]-(e.clientY-drag.y)*drag.view[3]/rect.height,drag.view[2],drag.view[3]];apply();}});
  const release=e=>{pointers.delete(e.pointerId);drag=null;pinch=null;};svg.addEventListener('pointerup',release);svg.addEventListener('pointercancel',release);
  const controls=document.createElement('div');controls.className='zoom-controls';controls.innerHTML='<button type="button" aria-label="Zoom in">+</button><button type="button" aria-label="Zoom out">−</button><button type="button" aria-label="Reset map zoom">Reset</button>';
  const buttons=controls.querySelectorAll('button');buttons[0].onclick=()=>zoom(.75);buttons[1].onclick=()=>zoom(1.33);buttons[2].onclick=()=>{view=[...initial];apply();};viewer.append(controls);
  apply();
}
function renderOverviewUnavailable() { $('overview-content').innerHTML='<p class="muted">Your estate ranking is ready. Connect DeepSeek to add an explanation of the top three.</p>';show('retry-overview');$('retry-overview').textContent='Generate overview ✧'; }
async function requestOverview(searchId) {
  if(!state.results||state.results.search_id!==searchId)return;
  $('overview-content').innerHTML='<p class="muted loading-text">DeepSeek is explaining the top three using the computed costs and your confirmed preferences…</p>';show('retry-overview',false);
  try {
    const job=await post('/api/overview/'+encodeURIComponent(searchId),{});
    const overview=await pollJob(job.job_id,()=>state.results?.search_id===searchId);
    if(!overview||state.results?.search_id!==searchId)return;
    $('overview-content').innerHTML=`<p>${esc(overview.summary)}</p><div class="overview-three">${overview.top_three.map((item,i)=>{const estate=state.results.estates.find(r=>r.id===item.estate_id);return `<div><strong>${i+1}. ${esc(estate.name_en)}</strong><p>${esc(item.explanation)}</p></div>`;}).join('')}</div>${overview.note?`<p class="formula-note">${esc(overview.note)}</p>`:''}`;
  } catch(error) {if(state.results?.search_id===searchId){$('overview-content').innerHTML=`<p class="muted">${esc(error.message)} The computed ranking remains available.</p>`;show('retry-overview');$('retry-overview').textContent='Retry ↻';}}
}
$('retry-overview').addEventListener('click',()=>{if(!state.connected)connectionDialog();else if(state.results)requestOverview(state.results.search_id);});
async function loadPointMap() {
  if($('point-map').querySelector('svg'))return;
  const response=await fetch('/api/map/overview');if(!response.ok)throw new Error('The point-selection map could not be loaded. You can enter coordinates instead.');
  $('point-map').innerHTML=await response.text();
  const overview=$('point-map').querySelector('svg');
  let pointerOrigin=null,suppressClick=false;
  overview.addEventListener('pointerdown',e=>{pointerOrigin={x:e.clientX,y:e.clientY};suppressClick=false;});
  overview.addEventListener('pointermove',e=>{if(pointerOrigin&&Math.hypot(e.clientX-pointerOrigin.x,e.clientY-pointerOrigin.y)>5)suppressClick=true;});
  overview.addEventListener('pointerup',()=>{pointerOrigin=null;});
  installZoom(overview,$('point-map'),[0,0,1000,650]);
  $('point-map').onclick=async e=>{
    const svg=$('point-map').querySelector('svg'),p=svg.createSVGPoint();p.x=e.clientX;p.y=e.clientY;
    if(!svg.contains(e.target)||suppressClick)return;
    const local=p.matrixTransform(svg.getScreenCTM().inverse());
    const x=Number(svg.dataset.xmin)+local.x/Number(svg.dataset.scale),y=Number(svg.dataset.ymax)-local.y/Number(svg.dataset.scale);
    try {const gps=await api('/api/coordinates?'+new URLSearchParams({x,y}));const which=state.pick;
      $(which+'-lat').value=gps.latitude.toFixed(6);$(which+'-lon').value=gps.longitude.toFixed(6);$(which+'-location').value='';
      updateMarkers();state.pick=which==='start'?'end':'start';pickLabel();
    } catch(error){notice(error.message);}
  };
  updateMarkers();
}
function pickLabel() {$('pick-instruction').textContent=state.pick==='start'?'CLICK THE MAP TO SET START':'CLICK THE MAP TO SET DESTINATION';$('point-map').classList.add('picking');}
$('pick-start').onclick=()=>{state.pick='start';pickLabel();};$('pick-end').onclick=()=>{state.pick='end';pickLabel();};
async function updateMarkers() {
  const svg=$('point-map').querySelector('svg');if(!svg)return;
  svg.querySelectorAll('.endpoint-marker').forEach(n=>n.remove());
  // Projection for marker placement is obtained from known grid coordinates for
  // named places, or a small server conversion for arbitrary entered points.
  for(const which of ['start','end']) {
    const lat=Number($(which+'-lat').value),lon=Number($(which+'-lon').value);if(!$(which+'-lat').value||!$(which+'-lon').value)continue;
    const named=[...state.bootstrap.estates,...state.bootstrap.locations].find(r=>Math.abs(r.latitude-lat)<.000002&&Math.abs(r.longitude-lon)<.000002);
    let grid;if(named)grid={x:named.x,y:named.y};else grid=await api('/api/grid?'+new URLSearchParams({latitude:lat,longitude:lon})).catch(()=>null);
    if(!grid)continue;
    const x=(grid.x-Number(svg.dataset.xmin))*Number(svg.dataset.scale),y=(Number(svg.dataset.ymax)-grid.y)*Number(svg.dataset.scale);
    const g=document.createElementNS('http://www.w3.org/2000/svg','g');g.setAttribute('class','endpoint-marker');g.dataset.x=x;g.dataset.y=y;
    const markerScale=Number(svg.getAttribute('viewBox').split(' ')[2])/1000;
    g.setAttribute('transform',`translate(${x} ${y}) scale(${markerScale})`);
    g.innerHTML=`<circle r="10" fill="${which==='start'?'#176957':'#b98548'}" stroke="white" stroke-width="3"/><text y="4" text-anchor="middle" font-family="sans-serif" font-size="11" fill="white">${which==='start'?'S':'E'}</text>`;svg.append(g);
  }
}
for(const which of ['start','end']) {
  $(which+'-location').onchange=()=>{const id=$(which+'-location').value,place=[...state.bootstrap.estates,...state.bootstrap.locations].find(r=>r.id===id);if(place){$(which+'-lat').value=place.latitude;$(which+'-lon').value=place.longitude;updateMarkers();}};
  for(const field of ['lat','lon'])$(which+'-'+field).addEventListener('change',()=>{$(which+'-location').value='';updateMarkers();});
}
$('swap-points').onclick=()=>{for(const field of ['location','lat','lon']){const a=$('start-'+field),b=$('end-'+field),v=a.value;a.value=b.value;b.value=v;}updateMarkers();};
$('clear-points').onclick=()=>{state.walkSeq++;for(const which of ['start','end'])for(const field of ['location','lat','lon'])$(which+'-'+field).value='';updateMarkers();show('walk-result',false);$('walk-status').textContent='Choose two points to begin.';state.pick='start';pickLabel();};
$('example-walk').onclick=()=>{$('start-lat').value=22.280111;$('start-lon').value=114.130386;$('end-lat').value=22.28113;$('end-lon').value=114.12856;$('start-location').value='';$('end-location').value='';updateMarkers();$('walk-status').textContent='Example points set: Lee Shau Kee Hall → Kennedy Town Exit A. Press Find a walk.';};
$('walk-form').addEventListener('submit',async e=>{
  e.preventDefault();const sequence=++state.walkSeq;$('walk-button').disabled=true;$('walk-status').className='walk-status loading-text';$('walk-status').textContent='Connecting the points and calculating the fastest permitted walk…';show('walk-result',false);
  const endpoint=which=>({latitude:Number($(which+'-lat').value),longitude:Number($(which+'-lon').value),label:$(which+'-location').selectedOptions[0]?.value?$(which+'-location').selectedOptions[0].text:which==='start'?'Start':'Destination'});
  try {const job=await post('/api/walk',{start:endpoint('start'),end:endpoint('end'),wheelchair:$('walk-wheelchair').checked});const result=await pollJob(job.job_id,()=>sequence===state.walkSeq);if(!result||sequence!==state.walkSeq)return;
    $('walk-status').textContent=result.message;
    if(result.status==='ok'){
      $('walk-result').innerHTML=`<div class="walk-result-summary">${minutes(result.time_s)} <span class="muted">· ${distance(result.distance_m)}</span></div><div id="walk-route-map"></div><p class="route-note">Assumed flat endpoint connections; source heights are unknown. Times use the saved slope and lift model, without waits or live access checks.</p>${result.attachments.filter(a=>a.warnings.length).map(a=>`<p class="formula-note">${esc(a.endpoint==='point:start'?'Start':'Destination')}: ${esc(a.warnings.map(readableReason).join('; '))}${a.connector_m!=null?' · '+distance(a.connector_m)+' connector':''}</p>`).join('')}`;mapViewer($('walk-route-map'),result.assets,'Start → Destination walking route',true);show('walk-result');
    }
  } catch(error){if(sequence===state.walkSeq)$('walk-status').textContent=error.message;}
  finally {if(sequence===state.walkSeq)$('walk-status').classList.remove('loading-text');$('walk-button').disabled=false;}
});
$('reset-session').onclick=async()=>{state.extractSeq++;state.walkSeq++;await post('/api/reset',{});if(state.pdfUrl)URL.revokeObjectURL(state.pdfUrl);location.reload();};
async function bootstrap() {
  $('search-button').disabled=true;
  try {
    state.bootstrap=await api('/api/bootstrap');setConnection(state.bootstrap.connected);
    for(const hospital of state.bootstrap.hospitals){const option=new Option(hospital.name,hospital.id);$('hospital-select').add(option);}
    for(const which of ['start','end']) {
      for(const [label,places] of [['Estates',state.bootstrap.estates],['Hospitals & MTR access',state.bootstrap.locations]]) {
        const group=document.createElement('optgroup');group.label=label;for(const place of places)group.append(new Option(place.name,place.id));$(which+'-location').append(group);
      }
    }
    if(!state.connected)connectionDialog();
  } catch(error){notice(error.message+' Reload the page after checking the local data bundle.');}
  finally {$('search-button').disabled=!state.bootstrap;}
}
bootstrap();

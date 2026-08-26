let adminData=null;
function showOnly(id){["userView","adminLoginView","adminView"].forEach(x=>document.getElementById(x).classList.toggle("hidden",x!==id))}
function routeByHash(){location.hash.toLowerCase()==="#admin"?showOnly("adminLoginView"):showOnly("userView")}
window.addEventListener("hashchange",routeByHash);window.addEventListener("load",routeByHash);

function demoUserLogin(){const m=userMsg;m.textContent="Demo user login UI is ready. Connect it to your production auth provider.";m.classList.remove("hidden","error")}

async function adminLogin(){
 const password=adminPassword.value;
 const r=await fetch("/api/admin/login",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({password})});
 if(!r.ok){adminLoginMsg.textContent="Admin login failed.";adminLoginMsg.classList.remove("hidden");adminLoginMsg.classList.add("error");return}
 adminPassword.value="";await loadAdmin()
}
async function adminLogout(){await fetch("/api/admin/logout",{method:"POST",credentials:"include"});location.hash="";showOnly("userView")}
async function loadAdmin(){const r=await fetch("/api/admin/dashboard",{credentials:"include"});if(!r.ok){showOnly("adminLoginView");return}adminData=await r.json();showOnly("adminView");renderAdmin()}
function esc(v){return String(v??"").replace(/[&<>"']/g,s=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[s]))}

function renderAdmin(){const c=adminData.counts;statIncidents.textContent=c.live_incidents;statPending.textContent=c.pending_reports;statCameras.textContent=c.camera_count;statUsers.textContent=c.active_users;renderSettings();renderReports();renderCameras();renderUsers()}
const desc={voice_alerts:"Master switch for supported voice alerts.",background_driving_mode:"Native driving mode may keep location active while driving.",community_reports:"Accept community reports.",camera_layer:"Show camera data where permitted.",traffic_layer:"Show live traffic.",hazard_layer:"Show hazards/roadworks.",admin_2fa_required:"Require owner second factor.",default_country:"Fallback jurisdiction.",camera_warning_mode:"Apply country-by-country camera rules.",app_name:"Public display name."}
function boolRow(k,v){return `<div class="setting-row"><div class="meta"><strong>${esc(k.replaceAll("_"," "))}</strong><small>${esc(desc[k]||"")}</small></div><div class="switch ${v?"on":""}" onclick="updateSetting('${k}',${!v})"></div></div>`}
function scalarRow(k,v){return `<div class="setting-row"><div class="meta"><strong>${esc(k.replaceAll("_"," "))}</strong><small>${esc(desc[k]||"")}</small></div><input style="max-width:260px" value="${esc(v)}" onchange="updateSetting('${k}',this.value)"></div>`}
function renderSettings(){const s=adminData.settings;const q=["voice_alerts","background_driving_mode","community_reports","camera_layer","traffic_layer","hazard_layer"];quickSettings.innerHTML=q.map(k=>typeof s[k]==="boolean"?boolRow(k,s[k]):scalarRow(k,s[k])).join("");allSettings.innerHTML=Object.entries(s).map(([k,v])=>typeof v==="boolean"?boolRow(k,v):scalarRow(k,v)).join("")}
async function updateSetting(k,v){const r=await fetch(`/api/admin/settings/${encodeURIComponent(k)}`,{method:"PUT",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({value:v})});if(r.ok){adminData.settings[k]=v;renderSettings()}}

function renderReports(){const rows=adminData.reports.map(r=>`<tr><td>${esc(r.type)}</td><td>${esc(r.location)}</td><td>${esc(r.reported_by)}</td><td><span class="status ${esc(r.status)}">${esc(r.status)}</span></td><td class="row-actions"><button onclick="setReportStatus(${r.id},'verified')">Verify</button><button onclick="setReportStatus(${r.id},'pending')">Pending</button><button class="reject" onclick="setReportStatus(${r.id},'rejected')">Reject</button></td></tr>`).join("");reportsTable.innerHTML=`<table><thead><tr><th>Type</th><th>Location</th><th>Reporter</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows}</tbody></table>`}
async function setReportStatus(id,status){const r=await fetch(`/api/admin/reports/${id}/status`,{method:"PUT",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify({status})});if(r.ok)await loadAdmin()}

function renderCameras(){const rows=adminData.cameras.map(c=>`<tr><td>${esc(c.camera_type)}</td><td>${esc(c.location)}</td><td>${esc(c.speed_limit??"—")}</td><td>${esc(c.confidence)}%</td><td>${c.enabled?"Enabled":"Disabled"}</td><td><button class="reject" onclick="deleteCamera(${c.id})">Delete</button></td></tr>`).join("");cameraTable.innerHTML=`<table><thead><tr><th>Type</th><th>Location</th><th>Limit</th><th>Confidence</th><th>State</th><th></th></tr></thead><tbody>${rows}</tbody></table>`}
async function addCamera(){const p={camera_type:cameraType.value,location:cameraLocation.value,speed_limit:cameraSpeed.value?Number(cameraSpeed.value):null,confidence:Number(cameraConfidence.value||50),enabled:true};const r=await fetch("/api/admin/cameras",{method:"POST",credentials:"include",headers:{"Content-Type":"application/json"},body:JSON.stringify(p)});if(r.ok){cameraLocation.value="";cameraSpeed.value="";await loadAdmin()}}
async function deleteCamera(id){const r=await fetch(`/api/admin/cameras/${id}`,{method:"DELETE",credentials:"include"});if(r.ok)await loadAdmin()}

function renderUsers(){const rows=adminData.users.map(u=>`<tr><td>${esc(u.name)}</td><td>${esc(u.role)}</td><td>${u.active?"Active":"Disabled"}</td></tr>`).join("");usersTable.innerHTML=`<table><thead><tr><th>Name</th><th>Role</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>`}
document.querySelectorAll(".nav").forEach(b=>b.addEventListener("click",()=>{document.querySelectorAll(".nav").forEach(x=>x.classList.remove("active"));b.classList.add("active");document.querySelectorAll(".tab").forEach(x=>x.classList.add("hidden"));document.getElementById(b.dataset.tab+"Tab").classList.remove("hidden");pageTitle.textContent=b.textContent}))

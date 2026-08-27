let currentUser = null;
let map = null;
let userMarker = null;
let userAccuracyCircle = null;
let currentPosition = null;
let watchId = null;
let incidentLayer = null;
let cameraLayer = null;
let trafficFlowLayer = null;
let trafficIncidentLayer = null;
let trafficEnabledByUser = true;
let trafficConfigured = false;
let trafficRefreshTimer = null;
let adminData = null;

const byId = (id) => document.getElementById(id);

function showOnly(id){
  ["userAuthView","userAppView","adminLoginView","adminView"].forEach(x=>{
    const el = byId(x);
    if (el) el.classList.toggle("hidden", x !== id);
  });
}

async function routeByHash(){
  if (location.hash.toLowerCase() === "#admin"){
    stopGpsWatch();
    showOnly("adminLoginView");
    return;
  }

  try{
    const r = await fetch("/api/auth/me", {credentials:"include"});
    if (r.ok){
      const data = await r.json();
      currentUser = data.user;
      await openUserApp();
      return;
    }
  }catch(_){}

  stopGpsWatch();
  showOnly("userAuthView");
}

window.addEventListener("hashchange", routeByHash);
window.addEventListener("load", routeByHash);

function showAuthTab(tab){
  byId("loginForm").classList.toggle("hidden", tab !== "login");
  byId("registerForm").classList.toggle("hidden", tab !== "register");
  byId("loginTabBtn").classList.toggle("active", tab === "login");
  byId("registerTabBtn").classList.toggle("active", tab === "register");
  setUserAuthMessage("");
}

function setUserAuthMessage(message, isError=false){
  const el = byId("userAuthMsg");
  if (!message){
    el.classList.add("hidden");
    return;
  }
  el.textContent = message;
  el.classList.remove("hidden");
  el.classList.toggle("error", isError);
}

async function userRegister(){
  setUserAuthMessage("");
  const payload = {
    name: byId("registerName").value.trim(),
    email: byId("registerEmail").value.trim(),
    password: byId("registerPassword").value
  };
  const r = await fetch("/api/auth/register", {
    method:"POST", credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(payload)
  });
  const data = await r.json().catch(()=>({}));
  if (!r.ok){
    setUserAuthMessage(data.detail || "Could not create account.", true);
    return;
  }
  currentUser = data.user;
  await openUserApp();
}

async function userLogin(){
  setUserAuthMessage("");
  const payload = {
    email: byId("loginEmail").value.trim(),
    password: byId("loginPassword").value
  };
  const r = await fetch("/api/auth/login", {
    method:"POST", credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(payload)
  });
  const data = await r.json().catch(()=>({}));
  if (!r.ok){
    setUserAuthMessage(data.detail || "Login failed.", true);
    return;
  }
  currentUser = data.user;
  await openUserApp();
}

async function userLogout(){
  stopGpsWatch();

  if (map && trafficFlowLayer && map.hasLayer(trafficFlowLayer)) {
    map.removeLayer(trafficFlowLayer);
  }

  if (map && trafficIncidentLayer && map.hasLayer(trafficIncidentLayer)) {
    map.removeLayer(trafficIncidentLayer);
  }

  await fetch("/api/auth/logout", {
    method:"POST",
    credentials:"include"
  });

  currentUser = null;
  location.hash = "";
  showOnly("userAuthView");
}

async function openUserApp(){
  showOnly("userAppView");

  byId("userGreeting").textContent =
    currentUser ? `Hi ${currentUser.name}` : "Live map";

  ensureMap();
  await refreshMapData();
  startGpsWatch();

  setTimeout(()=>{
    if (map) map.invalidateSize();
  }, 50);
}

function ensureMap(){
  if (map) return;

  map = L.map("map", {
    zoomControl:true
  }).setView([53.5511, 9.9937], 12);

  L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      maxZoom:19,
      attribution:'&copy; OpenStreetMap contributors'
    }
  ).addTo(map);

  incidentLayer = L.layerGroup().addTo(map);
  cameraLayer = L.layerGroup().addTo(map);

  trafficFlowLayer = L.tileLayer(
    "/api/traffic/flow/{z}/{x}/{y}",
    {
      tileSize:256,
      opacity:.88,
      zIndex:250,
      maxZoom:22,
      updateWhenIdle:false,
      keepBuffer:3
    }
  );

  trafficIncidentLayer = L.tileLayer(
    "/api/traffic/incidents/{z}/{x}/{y}",
    {
      tileSize:256,
      opacity:.92,
      zIndex:260,
      maxZoom:22,
      updateWhenIdle:false,
      keepBuffer:3
    }
  );

  if (!trafficRefreshTimer){
    trafficRefreshTimer = setInterval(()=>{
      if (trafficConfigured && trafficEnabledByUser){
        if (trafficFlowLayer) trafficFlowLayer.redraw();
        if (trafficIncidentLayer) trafficIncidentLayer.redraw();
      }
    }, 60000);
  }
}

function startGpsWatch(){
  if (!navigator.geolocation){
    setGpsBadge("GPS not supported", false);
    return;
  }

  if (watchId !== null) return;

  setGpsBadge("Requesting GPS…", false);

  watchId = navigator.geolocation.watchPosition(
    onGpsPosition,
    onGpsError,
    {
      enableHighAccuracy:true,
      maximumAge:5000,
      timeout:15000
    }
  );
}

function stopGpsWatch(){
  if (watchId !== null && navigator.geolocation){
    navigator.geolocation.clearWatch(watchId);
  }

  watchId = null;
}

function onGpsPosition(pos){
  currentPosition = {
    lat: pos.coords.latitude,
    lng: pos.coords.longitude,
    accuracy: pos.coords.accuracy,
    speed: pos.coords.speed
  };

  const latlng = [
    currentPosition.lat,
    currentPosition.lng
  ];

  if (!userMarker){
    userMarker = L.circleMarker(
      latlng,
      {
        radius:9,
        color:"#ffffff",
        weight:3,
        fillColor:"#2d70d6",
        fillOpacity:1
      }
    )
    .addTo(map)
    .bindPopup("<strong>Your live GPS location</strong>");
  }else{
    userMarker.setLatLng(latlng);
  }

  if (!userAccuracyCircle){
    userAccuracyCircle = L.circle(
      latlng,
      {
        radius:currentPosition.accuracy,
        color:"#2d70d6",
        weight:1,
        fillOpacity:.08
      }
    ).addTo(map);
  }else{
    userAccuracyCircle.setLatLng(latlng);
    userAccuracyCircle.setRadius(currentPosition.accuracy);
  }

  if (!map.__centeredOnUser){
    map.setView(latlng, 15);
    map.__centeredOnUser = true;
  }

  const speedKmh =
    currentPosition.speed != null &&
    currentPosition.speed >= 0
      ? Math.round(currentPosition.speed * 3.6)
      : null;

  setGpsBadge(
    speedKmh === null
      ? `GPS live · ±${Math.round(currentPosition.accuracy)}m`
      : `GPS live · ${speedKmh} km/h`,
    true
  );
}

function onGpsError(err){
  const messages = {
    1:"Location permission denied",
    2:"GPS position unavailable",
    3:"GPS request timed out"
  };

  setGpsBadge(
    messages[err.code] || "GPS error",
    false
  );
}

function setGpsBadge(text, good){
  const el = byId("gpsBadge");

  if (!el) return;

  el.textContent = text;
  el.classList.toggle("good", !!good);
  el.classList.toggle("warning", !good);
}

function centerOnUser(){
  if (map && currentPosition){
    map.setView(
      [
        currentPosition.lat,
        currentPosition.lng
      ],
      16
    );

    if (userMarker){
      userMarker.openPopup();
    }
  }else{
    startGpsWatch();
    setGpsBadge("Waiting for GPS…", false);
  }
}

const reportStyle = {
  camera: {
    color:"#2d70d6",
    emoji:"📷"
  },

  police: {
    color:"#3159b8",
    emoji:"🚓"
  },

  accident: {
    color:"#d63b32",
    emoji:"🚗"
  },

  hazard: {
    color:"#e09b18",
    emoji:"⚠️"
  },

  roadwork: {
    color:"#d97818",
    emoji:"🚧"
  },

  traffic: {
    color:"#17a65b",
    emoji:"🚦"
  }
};

async function refreshMapData(){
  if (!map) return;

  const r = await fetch(
    "/api/map-data",
    {
      credentials:"include"
    }
  );

  if (r.status === 401){
    await userLogout();
    return;
  }

  if (!r.ok) return;

  const data = await r.json();

  incidentLayer.clearLayers();
  cameraLayer.clearLayers();

  data.reports.forEach(item=>{
    const style =
      reportStyle[item.type] ||
      {
        color:"#666",
        emoji:"•"
      };

    const marker = L.circleMarker(
      [
        item.lat,
        item.lng
      ],
      {
        radius:9,
        color:"#fff",
        weight:2,
        fillColor:style.color,
        fillOpacity:.95
      }
    );

    marker.bindPopup(`
      <div class="popup-title">
        ${style.emoji} ${esc(item.type)}
      </div>

      <div>
        ${esc(item.location || "Reported location")}
      </div>

      <div class="popup-meta">
        Community verified
      </div>
    `);

    marker.addTo(incidentLayer);
  });

  data.cameras.forEach(item=>{
    const marker = L.marker(
      [
        item.lat,
        item.lng
      ],
      {
        title:`Camera: ${item.location}`
      }
    );

    const limit =
      item.speed_limit
        ? `${item.speed_limit} km/h`
        : "Speed unknown";

    marker.bindPopup(`
      <div class="popup-title">
        📷 ${esc(item.camera_type)} camera
      </div>

      <div>
        ${esc(item.location)}
      </div>

      <div class="popup-meta">
        ${esc(limit)} · confidence ${esc(item.confidence)}%
      </div>
    `);

    marker.addTo(cameraLayer);
  });

  byId("incidentBadge").textContent =
    `${data.reports.length} verified reports`;

  trafficConfigured =
    !!data.settings.traffic_available;

  const adminTrafficEnabled =
    data.settings.traffic_layer !== false;

  applyTrafficLayerState(
    adminTrafficEnabled
  );
}

function applyTrafficLayerState(
  adminTrafficEnabled=true
){
  const badge = byId("trafficBadge");
  const legend = byId("trafficLegend");

  if (!badge || !map) return;

  if (!trafficConfigured){

    if (
      trafficFlowLayer &&
      map.hasLayer(trafficFlowLayer)
    ){
      map.removeLayer(trafficFlowLayer);
    }

    if (
      trafficIncidentLayer &&
      map.hasLayer(trafficIncidentLayer)
    ){
      map.removeLayer(trafficIncidentLayer);
    }

    badge.textContent =
      "Traffic API not configured";

    badge.classList.remove(
      "on",
      "off"
    );

    badge.classList.add("error");

    if (legend){
      legend.classList.add("hidden");
    }

    return;
  }

  if (!adminTrafficEnabled){

    if (
      trafficFlowLayer &&
      map.hasLayer(trafficFlowLayer)
    ){
      map.removeLayer(trafficFlowLayer);
    }

    if (
      trafficIncidentLayer &&
      map.hasLayer(trafficIncidentLayer)
    ){
      map.removeLayer(trafficIncidentLayer);
    }

    badge.textContent =
      "Traffic disabled by admin";

    badge.classList.remove(
      "on",
      "error"
    );

    badge.classList.add("off");

    if (legend){
      legend.classList.add("hidden");
    }

    return;
  }

  if (trafficEnabledByUser){

    if (
      trafficFlowLayer &&
      !map.hasLayer(trafficFlowLayer)
    ){
      trafficFlowLayer.addTo(map);
    }

    if (
      trafficIncidentLayer &&
      !map.hasLayer(trafficIncidentLayer)
    ){
      trafficIncidentLayer.addTo(map);
    }

    badge.textContent =
      "Live Traffic ON";

    badge.classList.remove(
      "off",
      "error"
    );

    badge.classList.add("on");

    if (legend){
      legend.classList.remove("hidden");
    }

  }else{

    if (
      trafficFlowLayer &&
      map.hasLayer(trafficFlowLayer)
    ){
      map.removeLayer(trafficFlowLayer);
    }

    if (
      trafficIncidentLayer &&
      map.hasLayer(trafficIncidentLayer)
    ){
      map.removeLayer(trafficIncidentLayer);
    }

    badge.textContent =
      "Traffic OFF";

    badge.classList.remove(
      "on",
      "error"
    );

    badge.classList.add("off");

    if (legend){
      legend.classList.add("hidden");
    }
  }
}

function toggleTrafficLayer(){
  if (!trafficConfigured){
    applyTrafficLayerState(true);
    return;
  }

  trafficEnabledByUser =
    !trafficEnabledByUser;

  applyTrafficLayerState(true);
}

async function refreshAllLiveData(){
  await refreshMapData();

  if (
    trafficConfigured &&
    trafficEnabledByUser
  ){
    if (trafficFlowLayer){
      trafficFlowLayer.redraw();
    }

    if (trafficIncidentLayer){
      trafficIncidentLayer.redraw();
    }
  }
}

function openReportSheet(){
  const el = byId("reportSheet");

  el.classList.remove("hidden");

  byId("reportMsg")
    .classList
    .add("hidden");
}

function closeReportSheet(){
  byId("reportSheet")
    .classList
    .add("hidden");
}

async function submitReport(type){
  const msg = byId("reportMsg");

  msg.classList.add("hidden");

  if (!currentPosition){

    msg.textContent =
      "GPS location is not ready yet. Allow location access and try again.";

    msg.classList.remove(
      "hidden",
      "error"
    );

    msg.classList.add("error");

    startGpsWatch();

    return;
  }

  const r = await fetch(
    "/api/reports",
    {
      method:"POST",
      credentials:"include",

      headers:{
        "Content-Type":"application/json"
      },

      body:JSON.stringify({
        type,
        lat:currentPosition.lat,
        lng:currentPosition.lng,
        location:"User GPS report"
      })
    }
  );

  const data =
    await r.json().catch(()=>({}));

  if (!r.ok){

    msg.textContent =
      data.detail ||
      "Could not submit report.";

    msg.classList.remove("hidden");

    msg.classList.add("error");

    return;
  }

  msg.textContent =
    `${type} report sent for admin/community verification.`;

  msg.classList.remove(
    "hidden",
    "error"
  );

  setTimeout(
    closeReportSheet,
    1400
  );
}

function esc(v){
  return String(v ?? "")
    .replace(
      /[&<>"']/g,
      s=>({
        "&":"&amp;",
        "<":"&lt;",
        ">":"&gt;",
        '"':"&quot;",
        "'":"&#039;"
      })[s]
    );
}


/* ==========================
   ADMIN
========================== */

async function adminLogin(){

  const r = await fetch(
    "/api/admin/login",
    {
      method:"POST",

      credentials:"include",

      headers:{
        "Content-Type":"application/json"
      },

      body:JSON.stringify({
        password:
          byId("adminPassword").value
      })
    }
  );

  if (!r.ok){

    const msg =
      byId("adminLoginMsg");

    msg.textContent =
      "Admin login failed.";

    msg.classList.remove("hidden");

    msg.classList.add("error");

    return;
  }

  byId("adminPassword").value = "";

  await loadAdmin();
}

async function adminLogout(){

  await fetch(
    "/api/admin/logout",
    {
      method:"POST",
      credentials:"include"
    }
  );

  location.hash = "";

  showOnly("userAuthView");

  routeByHash();
}

async function loadAdmin(){

  const r = await fetch(
    "/api/admin/dashboard",
    {
      credentials:"include"
    }
  );

  if (!r.ok){
    showOnly("adminLoginView");
    return;
  }

  adminData =
    await r.json();

  showOnly("adminView");

  renderAdmin();
}

function renderAdmin(){

  const c =
    adminData.counts;

  byId("statIncidents")
    .textContent =
    c.live_incidents;

  byId("statPending")
    .textContent =
    c.pending_reports;

  byId("statCameras")
    .textContent =
    c.camera_count;

  byId("statUsers")
    .textContent =
    c.active_users;

  renderSettings();

  renderReports();

  renderCameras();

  renderUsers();
}

const settingDescriptions = {

  voice_alerts:
    "Master switch for supported voice alerts.",

  background_driving_mode:
    "Native driving mode may keep location active while driving.",

  community_reports:
    "Accept community reports.",

  camera_layer:
    "Show camera data where permitted.",

  traffic_layer:
    "Show live traffic when a provider is connected.",

  hazard_layer:
    "Show hazards/roadworks.",

  admin_2fa_required:
    "Require owner second factor.",

  default_country:
    "Fallback jurisdiction.",

  camera_warning_mode:
    "Apply country-by-country camera rules.",

  app_name:
    "Public display name."
};

function boolRow(k,v){

  return `
    <div class="setting-row">

      <div class="meta">

        <strong>
          ${esc(k.replaceAll("_"," "))}
        </strong>

        <small>
          ${esc(settingDescriptions[k]||"")}
        </small>

      </div>

      <div
        class="switch ${v?"on":""}"
        onclick="updateSetting('${k}',${!v})">
      </div>

    </div>
  `;
}

function scalarRow(k,v){

  return `
    <div class="setting-row">

      <div class="meta">

        <strong>
          ${esc(k.replaceAll("_"," "))}
        </strong>

        <small>
          ${esc(settingDescriptions[k]||"")}
        </small>

      </div>

      <input
        style="max-width:260px"
        value="${esc(v)}"
        onchange="updateSetting('${k}',this.value)"
      >

    </div>
  `;
}

function renderSettings(){

  const s =
    adminData.settings;

  const q = [
    "voice_alerts",
    "background_driving_mode",
    "community_reports",
    "camera_layer",
    "traffic_layer",
    "hazard_layer"
  ];

  byId("quickSettings")
    .innerHTML =
    q.map(k=>
      typeof s[k] === "boolean"
        ? boolRow(k,s[k])
        : scalarRow(k,s[k])
    ).join("");

  byId("allSettings")
    .innerHTML =
    Object.entries(s)
      .map(([k,v])=>
        typeof v === "boolean"
          ? boolRow(k,v)
          : scalarRow(k,v)
      )
      .join("");
}

async function updateSetting(k,v){

  const r = await fetch(
    `/api/admin/settings/${encodeURIComponent(k)}`,
    {
      method:"PUT",

      credentials:"include",

      headers:{
        "Content-Type":"application/json"
      },

      body:JSON.stringify({
        value:v
      })
    }
  );

  if (r.ok){

    adminData.settings[k] = v;

    renderSettings();
  }
}

function renderReports(){

  const rows =
    adminData.reports
      .map(r=>`

        <tr>

          <td>
            ${esc(r.type)}
          </td>

          <td>
            ${esc(r.location)}
          </td>

          <td>
            ${esc(r.reported_by)}
          </td>

          <td>
            ${
              r.lat != null
                ? Number(r.lat).toFixed(5)
                : "—"
            }
          </td>

          <td>
            ${
              r.lng != null
                ? Number(r.lng).toFixed(5)
                : "—"
            }
          </td>

          <td>

            <span class="status ${esc(r.status)}">
              ${esc(r.status)}
            </span>

          </td>

          <td class="row-actions">

            <button
              onclick="setReportStatus(${r.id},'verified')">
              Verify
            </button>

            <button
              onclick="setReportStatus(${r.id},'pending')">
              Pending
            </button>

            <button
              class="reject"
              onclick="setReportStatus(${r.id},'rejected')">
              Reject
            </button>

          </td>

        </tr>

      `)
      .join("");

  byId("reportsTable").innerHTML = `

    <table>

      <thead>

        <tr>
          <th>Type</th>
          <th>Location</th>
          <th>Reporter</th>
          <th>Lat</th>
          <th>Lng</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>

      </thead>

      <tbody>
        ${rows}
      </tbody>

    </table>
  `;
}

async function setReportStatus(
  id,
  status
){

  const r = await fetch(
    `/api/admin/reports/${id}/status`,
    {
      method:"PUT",

      credentials:"include",

      headers:{
        "Content-Type":"application/json"
      },

      body:JSON.stringify({
        status
      })
    }
  );

  if (r.ok){
    await loadAdmin();
  }
}

function renderCameras(){

  const rows =
    adminData.cameras
      .map(c=>`

        <tr>

          <td>
            ${esc(c.camera_type)}
          </td>

          <td>
            ${esc(c.location)}
          </td>

          <td>
            ${esc(c.speed_limit??"—")}
          </td>

          <td>
            ${esc(c.confidence)}%
          </td>

          <td>
            ${
              c.lat != null
                ? Number(c.lat).toFixed(5)
                : "—"
            }
          </td>

          <td>
            ${
              c.lng != null
                ? Number(c.lng).toFixed(5)
                : "—"
            }
          </td>

          <td>
            ${
              c.enabled
                ? "Enabled"
                : "Disabled"
            }
          </td>

          <td>

            <button
              class="reject"
              onclick="deleteCamera(${c.id})">
              Delete
            </button>

          </td>

        </tr>

      `)
      .join("");

  byId("cameraTable").innerHTML = `

    <table>

      <thead>

        <tr>
          <th>Type</th>
          <th>Location</th>
          <th>Limit</th>
          <th>Confidence</th>
          <th>Lat</th>
          <th>Lng</th>
          <th>State</th>
          <th></th>
        </tr>

      </thead>

      <tbody>
        ${rows}
      </tbody>

    </table>
  `;
}

async function addCamera(){

  const payload = {

    camera_type:
      byId("cameraType").value,

    location:
      byId("cameraLocation").value,

    speed_limit:
      byId("cameraSpeed").value
        ? Number(
            byId("cameraSpeed").value
          )
        : null,

    confidence:
      Number(
        byId("cameraConfidence").value
        || 50
      ),

    lat:
      byId("cameraLat").value
        ? Number(
            byId("cameraLat").value
          )
        : null,

    lng:
      byId("cameraLng").value
        ? Number(
            byId("cameraLng").value
          )
        : null,

    enabled:true
  };

  const r = await fetch(
    "/api/admin/cameras",
    {
      method:"POST",

      credentials:"include",

      headers:{
        "Content-Type":"application/json"
      },

      body:
        JSON.stringify(payload)
    }
  );

  if (r.ok){

    [
      "cameraLocation",
      "cameraSpeed",
      "cameraLat",
      "cameraLng"
    ]
    .forEach(id=>{
      byId(id).value="";
    });

    await loadAdmin();
  }
}

async function deleteCamera(id){

  const r = await fetch(
    `/api/admin/cameras/${id}`,
    {
      method:"DELETE",
      credentials:"include"
    }
  );

  if (r.ok){
    await loadAdmin();
  }
}

function renderUsers(){

  const staffRows =
    (adminData.users||[])
      .map(u=>`

        <tr>

          <td>
            ${esc(u.name)}
          </td>

          <td>
            ${esc(u.role)}
          </td>

          <td>
            ${
              u.active
                ? "Active"
                : "Disabled"
            }
          </td>

        </tr>

      `)
      .join("");

  byId("usersTable").innerHTML = `

    <table>

      <thead>

        <tr>
          <th>Name</th>
          <th>Role</th>
          <th>Status</th>
        </tr>

      </thead>

      <tbody>
        ${staffRows}
      </tbody>

    </table>
  `;

  const appRows =
    (adminData.app_users||[])
      .map(u=>`

        <tr>

          <td>
            ${esc(u.name)}
          </td>

          <td>
            ${esc(u.email)}
          </td>

          <td>
            ${
              u.active
                ? "Active"
                : "Disabled"
            }
          </td>

        </tr>

      `)
      .join("");

  byId("appUsersTable").innerHTML = `

    <table>

      <thead>

        <tr>
          <th>Name</th>
          <th>Email</th>
          <th>Status</th>
        </tr>

      </thead>

      <tbody>

        ${
          appRows ||
          '<tr><td colspan="3">No registered app users yet.</td></tr>'
        }

      </tbody>

    </table>
  `;
}

document
  .querySelectorAll(".nav")
  .forEach(btn=>{

    btn.addEventListener(
      "click",
      ()=>{

        document
          .querySelectorAll(".nav")
          .forEach(x=>
            x.classList.remove("active")
          );

        btn.classList.add("active");

        document
          .querySelectorAll(".tab")
          .forEach(x=>
            x.classList.add("hidden")
          );

        byId(
          btn.dataset.tab+"Tab"
        )
        .classList
        .remove("hidden");

        byId("pageTitle")
          .textContent =
          btn.textContent;
      }
    );
  });

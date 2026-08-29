
function safeLocalGet(key, fallback=null){
  try{
    const value = window.localStorage.getItem(key);
    return value === null ? fallback : value;
  }catch(_){
    return fallback;
  }
}

function safeLocalSet(key, value){
  try{
    window.localStorage.setItem(key, value);
  }catch(_){}
}

let currentUser = null;
let map = null;
let userMarker = null;
let userAccuracyCircle = null;
let userHeadingMarker = null;
let navDestinationMarker = null;
let lastNavigationCameraUpdateAt = 0;
let currentPosition = null;
let watchId = null;
let incidentLayer = null;
let cameraLayer = null;
let trafficFlowLayer = null;
let trafficIncidentLayer = null;
let trafficEnabledByUser = true;
let trafficConfigured = false;
let trafficRefreshTimer = null;
let proximityTargets = [];
let proximitySettings = {
  enabled:true,
  voice:true,
  maxDistanceM:1200,
  urgentDistanceM:400,
  cooldownS:300,
  language:"en-GB",
  defaultCountry:"DE",
  cameraWarningMode:"country_compliance"
};
let voiceEnabledByUser = safeLocalGet("roadpulse_voice", "on") !== "off";
let lastAlertedAt = new Map();
let cameraCountdownState = new Map();
const CAMERA_COUNTDOWN_STEPS = [500, 400, 300, 200, 100];
let dismissedUntil = new Map();
let currentProximityTarget = null;
let proximityEvalTimer = null;
let navigationActive = false;
let navDestination = null;
let navRoute = null;
let navRouteLayer = null;
let navRouteOutlineLayer = null;
let navRoutePoints = [];
let navInstructions = [];
let navCurrentInstructionIndex = 0;
let navLastProgressIndex = 0;
let navLastRerouteAt = 0;
let navLastTrafficRefreshAt = 0;
let navSearchTimer = null;
let navSearchResults = [];
let navRequestInFlight = false;
let navInstructionAnnouncements = new Set();
let navFollowMode = true;
let navWakeLock = null;
let navBaseSummary = null;
const storedNavigationMode = safeLocalGet("roadpulse_nav_mode", "car");
let navigationMode = ["car","pedestrian","bicycle"].includes(storedNavigationMode)
  ? storedNavigationMode
  : "car";
let favoriteDestinations = loadStoredDestinations("roadpulse_favorites");
let recentDestinations = loadStoredDestinations("roadpulse_recent");
let navAudioContext = null;
let navLastChimeKey = null;
let mapBearingDeg = Number(safeLocalGet("roadpulse_map_bearing", "0")) || 0;
let routeRotateRedrawTimer = null;
let navigationHeadingUp = false;
let navSearchAbortController = null;
let navSearchRequestSeq = 0;
let lastGpsFixAt = 0;
let gpsWatchStartedAt = 0;
let lastRawGpsFix = null;
let lastReliableHeading = null;
let lastReliableHeadingAt = 0;
let currentDisplayPosition = null;
let lastUserMapGestureAt = 0;
let mapResizeTimer = null;
let rotateTouchPointers = new Map();
let rotateTouchState = null;
let rotateTouchRaf = 0;
let rotateTouchPendingBearing = 0;
let walkingLiveViewStream = null;
let navSpeechVoices = [];
let adminData = null;



const SUPPORTED_APP_LANGUAGES = [
  "en-GB","de-DE","it-IT","fr-FR","es-ES","nl-NL","pt-PT","pl-PL",
  "cs-CZ","da-DK","sv-SE","fi-FI","nb-NO","hu-HU","tr-TR","sk-SK",
  "sl-SI","lt-LT","el-GR","bg-BG","ru-RU","ar"
];

let userLanguage = "en-GB";

const UI_TRANSLATIONS = {
  "en-GB":{
    logout:"Log out", search:"Where do you want to go?", nextRoad:"Next road",
    destination:"Destination", voiceOn:"Voice ON", voiceOff:"Voice OFF",
    online:"Online", offline:"Offline", navigate:"Navigate", myGps:"My GPS",
    report:"Report", refresh:"Refresh", follow:"Following", followOff:"Follow",
    overview:"Overview", save:"Save", route:"Route", trafficDelay:"Traffic delay",
    distance:"Distance", drive:"Drive", walk:"Walk", cycle:"Bike", driveMode:"Drive", walkMode:"Walk", cycleMode:"Bike", eta:"ETA", arrived:"You have arrived", liveView:"Live View", compass:"Compass", rotateMap:"Rotate map", resetNorth:"North up",
    routeUpdated:"Route updated.", voiceEnabled:"Voice alerts enabled.",
    hazardAhead:"Hazard ahead", accidentAhead:"Accident ahead",
    roadworkAhead:"Roadwork ahead", trafficAhead:"Traffic ahead",
    policeAhead:"Police report ahead", roadAlertAhead:"Road alert ahead",
    inMeters:"in {n} meters"
  },
  "de-DE":{
    logout:"Abmelden", search:"Wohin möchtest du fahren?", nextRoad:"Nächste Straße",
    destination:"Ziel", voiceOn:"Stimme AN", voiceOff:"Stimme AUS",
    online:"Online", offline:"Offline", navigate:"Navigation", myGps:"Mein GPS",
    report:"Melden", refresh:"Aktualisieren", follow:"Folge Route", followOff:"Folgen",
    overview:"Übersicht", save:"Speichern", route:"Route", trafficDelay:"Verkehrsverzögerung",
    distance:"Entfernung", drive:"Fahrzeit", walk:"Zu Fuß", cycle:"Rad", driveMode:"Auto", walkMode:"Zu Fuß", cycleMode:"Fahrrad", eta:"Ankunft", arrived:"Ziel erreicht", liveView:"Live View", compass:"Kompass", rotateMap:"Karte drehen", resetNorth:"Nordausrichtung",
    routeUpdated:"Route aktualisiert.", voiceEnabled:"Sprachhinweise aktiviert.",
    hazardAhead:"Gefahr voraus", accidentAhead:"Unfall voraus",
    roadworkAhead:"Baustelle voraus", trafficAhead:"Verkehr voraus",
    policeAhead:"Polizeimeldung voraus", roadAlertAhead:"Straßenhinweis voraus",
    inMeters:"in {n} Metern"
  },
  "it-IT":{
    logout:"Esci", search:"Dove vuoi andare?", nextRoad:"Prossima strada",
    destination:"Destinazione", voiceOn:"Voce ON", voiceOff:"Voce OFF",
    online:"Online", offline:"Offline", navigate:"Naviga", myGps:"Il mio GPS",
    report:"Segnala", refresh:"Aggiorna", follow:"Segui", followOff:"Segui",
    overview:"Panoramica", save:"Salva", route:"Percorso", trafficDelay:"Ritardo traffico",
    distance:"Distanza", drive:"Durata", walk:"A piedi", cycle:"Bici", driveMode:"Auto", walkMode:"A piedi", cycleMode:"Bici", eta:"Arrivo", arrived:"Sei arrivato",
    routeUpdated:"Percorso aggiornato.", voiceEnabled:"Avvisi vocali attivati.",
    hazardAhead:"Pericolo più avanti", accidentAhead:"Incidente più avanti",
    roadworkAhead:"Lavori stradali più avanti", trafficAhead:"Traffico più avanti",
    policeAhead:"Segnalazione polizia più avanti", roadAlertAhead:"Avviso stradale più avanti",
    inMeters:"tra {n} metri"
  },
  "fr-FR":{
    logout:"Déconnexion", search:"Où voulez-vous aller ?", nextRoad:"Prochaine route",
    destination:"Destination", voiceOn:"Voix ON", voiceOff:"Voix OFF",
    online:"En ligne", offline:"Hors ligne", navigate:"Naviguer", myGps:"Mon GPS",
    report:"Signaler", refresh:"Actualiser", follow:"Suivi", followOff:"Suivre",
    overview:"Aperçu", save:"Enregistrer", route:"Itinéraire", trafficDelay:"Retard trafic",
    distance:"Distance", drive:"Durée", walk:"À pied", cycle:"Vélo", driveMode:"Voiture", walkMode:"À pied", cycleMode:"Vélo", eta:"Arrivée", arrived:"Vous êtes arrivé",
    routeUpdated:"Itinéraire mis à jour.", voiceEnabled:"Alertes vocales activées.",
    hazardAhead:"Danger devant", accidentAhead:"Accident devant",
    roadworkAhead:"Travaux devant", trafficAhead:"Trafic devant",
    policeAhead:"Signalement police devant", roadAlertAhead:"Alerte routière devant",
    inMeters:"dans {n} mètres"
  },
  "es-ES":{
    logout:"Salir", search:"¿A dónde quieres ir?", nextRoad:"Próxima vía",
    destination:"Destino", voiceOn:"Voz ON", voiceOff:"Voz OFF",
    online:"En línea", offline:"Sin conexión", navigate:"Navegar", myGps:"Mi GPS",
    report:"Reportar", refresh:"Actualizar", follow:"Siguiendo", followOff:"Seguir",
    overview:"Vista general", save:"Guardar", route:"Ruta", trafficDelay:"Retraso tráfico",
    distance:"Distancia", drive:"Duración", walk:"A pie", cycle:"Bici", driveMode:"Coche", walkMode:"A pie", cycleMode:"Bici", eta:"Llegada", arrived:"Has llegado",
    routeUpdated:"Ruta actualizada.", voiceEnabled:"Avisos de voz activados.",
    hazardAhead:"Peligro más adelante", accidentAhead:"Accidente más adelante",
    roadworkAhead:"Obras más adelante", trafficAhead:"Tráfico más adelante",
    policeAhead:"Aviso de policía más adelante", roadAlertAhead:"Aviso vial más adelante",
    inMeters:"en {n} metros"
  },
  "nl-NL":{
    logout:"Uitloggen", search:"Waar wil je naartoe?", nextRoad:"Volgende weg",
    destination:"Bestemming", voiceOn:"Stem AAN", voiceOff:"Stem UIT",
    online:"Online", offline:"Offline", navigate:"Navigeren", myGps:"Mijn GPS",
    report:"Melden", refresh:"Vernieuwen", follow:"Volgen", followOff:"Volgen",
    overview:"Overzicht", save:"Opslaan", route:"Route", trafficDelay:"Vertraging",
    distance:"Afstand", drive:"Rijtijd", walk:"Lopen", cycle:"Fiets", driveMode:"Auto", walkMode:"Lopen", cycleMode:"Fiets", eta:"Aankomst", arrived:"Je bent aangekomen",
    routeUpdated:"Route bijgewerkt.", voiceEnabled:"Spraakmeldingen ingeschakeld.",
    hazardAhead:"Gevaar verderop", accidentAhead:"Ongeval verderop",
    roadworkAhead:"Wegwerkzaamheden verderop", trafficAhead:"Verkeer verderop",
    policeAhead:"Politiemelding verderop", roadAlertAhead:"Wegmelding verderop",
    inMeters:"over {n} meter"
  },
  "pt-PT":{
    logout:"Sair", search:"Para onde quer ir?", nextRoad:"Próxima estrada",
    destination:"Destino", voiceOn:"Voz ON", voiceOff:"Voz OFF",
    online:"Online", offline:"Offline", navigate:"Navegar", myGps:"Meu GPS",
    report:"Reportar", refresh:"Atualizar", follow:"Seguindo", followOff:"Seguir",
    overview:"Visão geral", save:"Guardar", route:"Rota", trafficDelay:"Atraso no trânsito",
    distance:"Distância", drive:"Duração", walk:"A pé", cycle:"Bicicleta", driveMode:"Carro", walkMode:"A pé", cycleMode:"Bicicleta", eta:"Chegada", arrived:"Chegou ao destino",
    routeUpdated:"Rota atualizada.", voiceEnabled:"Alertas de voz ativados.",
    hazardAhead:"Perigo à frente", accidentAhead:"Acidente à frente",
    roadworkAhead:"Obras à frente", trafficAhead:"Trânsito à frente",
    policeAhead:"Alerta de polícia à frente", roadAlertAhead:"Alerta rodoviário à frente",
    inMeters:"em {n} metros"
  },
  "pl-PL":{
    logout:"Wyloguj", search:"Dokąd chcesz jechać?", nextRoad:"Następna droga",
    destination:"Cel", voiceOn:"Głos WŁ.", voiceOff:"Głos WYŁ.",
    online:"Online", offline:"Offline", navigate:"Nawiguj", myGps:"Mój GPS",
    report:"Zgłoś", refresh:"Odśwież", follow:"Prowadzenie", followOff:"Podążaj",
    overview:"Przegląd", save:"Zapisz", route:"Trasa", trafficDelay:"Opóźnienie",
    distance:"Dystans", drive:"Czas jazdy", walk:"Pieszo", cycle:"Rower", driveMode:"Auto", walkMode:"Pieszo", cycleMode:"Rower", eta:"Przyjazd", arrived:"Dotarłeś do celu",
    routeUpdated:"Trasa zaktualizowana.", voiceEnabled:"Wskazówki głosowe włączone.",
    hazardAhead:"Niebezpieczeństwo przed tobą", accidentAhead:"Wypadek przed tobą",
    roadworkAhead:"Roboty drogowe przed tobą", trafficAhead:"Korek przed tobą",
    policeAhead:"Zgłoszenie policji przed tobą", roadAlertAhead:"Ostrzeżenie drogowe",
    inMeters:"za {n} metrów"
  },
  "tr-TR":{
    logout:"Çıkış", search:"Nereye gitmek istiyorsun?", nextRoad:"Sonraki yol",
    destination:"Hedef", voiceOn:"Ses AÇIK", voiceOff:"Ses KAPALI",
    online:"Çevrimiçi", offline:"Çevrimdışı", navigate:"Navigasyon", myGps:"GPS'im",
    report:"Bildir", refresh:"Yenile", follow:"Takip", followOff:"Takip et",
    overview:"Genel görünüm", save:"Kaydet", route:"Rota", trafficDelay:"Trafik gecikmesi",
    distance:"Mesafe", drive:"Sürüş", walk:"Yürüme", cycle:"Bisiklet", driveMode:"Araç", walkMode:"Yürü", cycleMode:"Bisiklet", eta:"Varış", arrived:"Hedefe ulaştınız",
    routeUpdated:"Rota güncellendi.", voiceEnabled:"Sesli uyarılar açıldı.",
    hazardAhead:"İleride tehlike", accidentAhead:"İleride kaza",
    roadworkAhead:"İleride yol çalışması", trafficAhead:"İleride trafik",
    policeAhead:"İleride polis bildirimi", roadAlertAhead:"İleride yol uyarısı",
    inMeters:"{n} metre sonra"
  }
};

function detectInitialLanguage(){
  const browser = (navigator.language || "en-GB").toLowerCase();
  const exact = SUPPORTED_APP_LANGUAGES.find(x=>x.toLowerCase() === browser);
  if (exact) return exact;

  const prefix = browser.split("-")[0];
  const pref = SUPPORTED_APP_LANGUAGES.find(x=>x.toLowerCase().startsWith(prefix+"-") || x.toLowerCase() === prefix);
  return pref || "en-GB";
}

function t(key){
  const dict = UI_TRANSLATIONS[userLanguage] || UI_TRANSLATIONS["en-GB"];
  return dict[key] || UI_TRANSLATIONS["en-GB"][key] || key;
}

function changeAppLanguage(language){
  if (!SUPPORTED_APP_LANGUAGES.includes(language)){
    language = "en-GB";
  }

  userLanguage = language;
  safeLocalSet("roadpulse_language", userLanguage);
  applyAppLanguage();

  // Recalculate active route so TomTom returns road names/instructions
  // in the newly selected language.
  if (navigationActive && navDestination){
    calculateNavigationRoute(true);
  }else{
    refreshMapData();
  }
}

function initializeLanguageSafe(){
  try{
    const stored = safeLocalGet("roadpulse_language", "");
    if (stored && SUPPORTED_APP_LANGUAGES.includes(stored)){
      userLanguage = stored;
    }else{
      userLanguage = detectInitialLanguage();
    }
  }catch(_){
    userLanguage = "en-GB";
  }
}

function applyAppLanguage(){
  const select = byId("appLanguageSelect");
  if (select) select.value = userLanguage;

  document.documentElement.lang = userLanguage;
  document.documentElement.dir = userLanguage === "ar" ? "rtl" : "ltr";

  const logout = byId("logoutBtn");
  if (logout) logout.textContent = t("logout");

  const search = byId("destinationSearchInput");
  if (search) search.placeholder = t("search");

  const nextRoad = byId("nextRoadLabel");
  if (nextRoad) nextRoad.textContent = t("nextRoad");

  const navDest = byId("navDestinationName");
  if (navDest && !navigationActive) navDest.textContent = t("destination");

  updateVoiceBadge();
  updateNetworkBadge();
  updateBottomNavigationLabels();
  updateRouteControlLabels();
  updateNavigationModeUI();
}

function updateBottomNavigationLabels(){
  const buttons = document.querySelectorAll(".bottom-nav button span");
  if (buttons.length >= 4){
    buttons[0].textContent = t("navigate");
    buttons[1].textContent = t("myGps");
    buttons[2].textContent = t("report");
    buttons[3].textContent = t("refresh");
  }
}

function updateRouteControlLabels(){
  const follow = byId("followRouteBtn");
  if (follow){
    follow.textContent = navFollowMode ? `◎ ${t("follow")}` : `◎ ${t("followOff")}`;
  }

  const summary = byId("routeSummaryCard");
  if (!summary) return;
  const labels = summary.querySelectorAll(":scope > div > span");
  if (labels.length >= 4){
    labels[0].textContent = t("eta");
    labels[1].textContent = navigationMode === "pedestrian"
      ? t("walk")
      : (navigationMode === "bicycle" ? t("cycle") : t("drive"));
    labels[2].textContent = t("distance");
    labels[3].textContent = t("trafficDelay");
  }

  const controls = summary.querySelectorAll(".route-control-btn");
  if (controls.length >= 4){
    controls[1].textContent = `▱ ${t("overview")}`;
    controls[2].textContent = `☆ ${t("save")}`;
    controls[3].textContent = `↻ ${t("route")}`;
  }

  const liveBtn = byId("walkingLiveViewBtn");
  if (liveBtn){
    liveBtn.textContent = `◉ ${t("liveView") || "Live View"}`;
  }
}

function setNavigationMode(mode){
  const nextMode = ["car","pedestrian","bicycle"].includes(mode) ? mode : "car";
  if (navigationMode === nextMode){
    updateNavigationModeUI();
    return;
  }

  navigationMode = nextMode;
  if (navigationMode === "pedestrian"){
    stopNavigationHeadingUp(true);
  }
  safeLocalSet("roadpulse_nav_mode", navigationMode);
  updateNavigationModeUI();

  if (navigationActive && navDestination && currentPosition){
    calculateNavigationRoute(true);
  }
}

function updateNavigationModeUI(){
  const carBtn = byId("navModeCarBtn");
  const walkBtn = byId("navModeWalkBtn");
  const bikeBtn = byId("navModeBikeBtn");
  const summary = byId("routeSummaryCard");
  const durationLabel = byId("routeDurationLabel");

  if (carBtn){
    carBtn.classList.toggle("active", navigationMode === "car");
    carBtn.textContent = `🚗 ${t("driveMode")}`;
  }
  if (walkBtn){
    walkBtn.classList.toggle("active", navigationMode === "pedestrian");
    walkBtn.textContent = `🚶 ${t("walkMode")}`;
  }
  if (bikeBtn){
    bikeBtn.classList.toggle("active", navigationMode === "bicycle");
    bikeBtn.textContent = `🚲 ${t("cycleMode")}`;
  }

  if (durationLabel){
    durationLabel.textContent = navigationMode === "pedestrian"
      ? t("walk")
      : (navigationMode === "bicycle" ? t("cycle") : t("drive"));
  }

  if (summary){
    const nonTraffic = navigationMode === "pedestrian" || navigationMode === "bicycle";
    summary.classList.toggle("walking-mode", navigationMode === "pedestrian");
    summary.classList.toggle("cycling-mode", navigationMode === "bicycle");
    summary.classList.toggle("nontraffic-mode", nonTraffic);
  }

  document.body.classList.toggle("walking-navigation", navigationMode === "pedestrian" && navigationActive);
  document.body.classList.toggle("cycling-navigation", navigationMode === "bicycle" && navigationActive);
  document.body.classList.toggle("car-navigation", navigationMode === "car" && navigationActive);

  const modeBadge = byId("navModeBadge");
  if (modeBadge){
    const modeText = navigationMode === "pedestrian"
      ? `🚶 ${t("walkMode")}`
      : (navigationMode === "bicycle" ? `🚲 ${t("cycleMode")}` : `🚗 ${t("driveMode")}`);
    modeBadge.textContent = modeText;
    modeBadge.dataset.mode = navigationMode;
  }

  const liveViewBtn = byId("walkingLiveViewBtn");
  if (liveViewBtn){
    liveViewBtn.classList.toggle("hidden", navigationMode !== "pedestrian");
  }

  updateTrafficClarity();
  renderDestinationMarker();
}

function localizedInMeters(n){
  return t("inMeters").replace("{n}", String(n));
}

function localizedAlertTitle(type){
  const keys = {
    accident:"accidentAhead",
    hazard:"hazardAhead",
    roadwork:"roadworkAhead",
    traffic:"trafficAhead",
    police:"policeAhead"
  };
  return t(keys[type] || "roadAlertAhead");
}

function loadStoredDestinations(key){
  try{
    const value = JSON.parse(safeLocalGet(key, "[]") || "[]");
    return Array.isArray(value) ? value.slice(0,12) : [];
  }catch(_){
    return [];
  }
}

function saveStoredDestinations(key, items){
  try{
    safeLocalSet(key, JSON.stringify(items.slice(0,12)));
  }catch(_){}
}

function sameDestination(a,b){
  if (!a || !b) return false;
  return (
    Math.abs(Number(a.lat)-Number(b.lat)) < 0.00001 &&
    Math.abs(Number(a.lng)-Number(b.lng)) < 0.00001
  );
}

const byId = (id) => document.getElementById(id);

function showOnly(id){
  ["userAuthView","userAppView","adminLoginView","adminView"].forEach(x=>{
    const el = byId(x);
    if (el) el.classList.toggle("hidden", x !== id);
  });
}

async function routeByHash(){
  const isAdmin =
    location.hash.toLowerCase() === "#admin";

  if (isAdmin){
    try{
      stopGpsWatch();
    }catch(_){}

    showOnly("adminLoginView");
    return;
  }

  try{
    const r = await fetch(
      "/api/auth/me",
      {credentials:"include"}
    );

    if (r.ok){
      const data = await r.json();
      currentUser = data.user;

      try{
        await openUserApp();
      }catch(err){
        console.error("RoadPulse user app open error:", err);
        showOnly("userAuthView");
      }

      return;
    }
  }catch(err){
    console.error("RoadPulse auth check error:", err);
  }

  try{
    stopGpsWatch();
  }catch(_){}

  showOnly("userAuthView");
}

window.addEventListener("hashchange", routeByHash);
window.addEventListener("load", async ()=>{
  try{
    initializeLanguageSafe();
    applyAppLanguage();
    updateNetworkBadge();
    bindDestinationSearchControls();
  }catch(err){
    console.error("RoadPulse UI init warning:", err);
  }

  try{
    await routeByHash();
  }catch(err){
    console.error("RoadPulse route/auth boot error:", err);

    if (location.hash.toLowerCase() === "#admin"){
      showOnly("adminLoginView");
    }else{
      showOnly("userAuthView");
    }
  }

  window.__ROADPULSE_BOOT_OK__ = true;
  console.log("RoadPulse Web V1.4 mobile navigation fix loaded");
});
window.addEventListener("online", updateNetworkBadge);
window.addEventListener("offline", updateNetworkBadge);
document.addEventListener("visibilitychange", ()=>{
  if (document.visibilityState !== "visible") return;

  if (navigationActive){
    requestNavigationWakeLock();
  }

  const gpsStale = !lastGpsFixAt || (Date.now() - lastGpsFixAt > 15000);
  if (gpsStale){
    startGpsWatch(true);
  }

  scheduleMapResize();
});


function updateNetworkBadge(){
  const badge = byId("networkBadge");
  if (!badge) return;

  const online = navigator.onLine !== false;
  badge.textContent = online ? t("online") : t("offline");
  badge.classList.toggle("offline", !online);
}

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

  try{
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
  }catch(err){
    console.error("RoadPulse registration error:", err);
    setUserAuthMessage("Network unavailable. Please try again.", true);
  }
}

async function userLogin(){
  setUserAuthMessage("");
  const payload = {
    email: byId("loginEmail").value.trim(),
    password: byId("loginPassword").value
  };

  try{
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
  }catch(err){
    console.error("RoadPulse login error:", err);
    setUserAuthMessage("Network unavailable. Please try again.", true);
  }
}

async function userLogout(){
  stopGpsWatch();
  stopNavigation(false);

  navSearchAbortController?.abort();
  navSearchAbortController = null;
  navSearchRequestSeq++;

  if (navSearchTimer){
    clearTimeout(navSearchTimer);
    navSearchTimer = null;
  }

  if (proximityEvalTimer){
    clearInterval(proximityEvalTimer);
    proximityEvalTimer = null;
  }
  if (map && trafficFlowLayer && map.hasLayer(trafficFlowLayer)) map.removeLayer(trafficFlowLayer);
  if (map && trafficIncidentLayer && map.hasLayer(trafficIncidentLayer)) map.removeLayer(trafficIncidentLayer);
  try{
    await fetch("/api/auth/logout", {method:"POST", credentials:"include"});
  }catch(err){
    console.warn("RoadPulse logout request failed:", err);
  }
  currentUser = null;
  location.hash = "";
  showOnly("userAuthView");
}

async function openUserApp(){
  showOnly("userAppView");
  applyAppLanguage();
  bindDestinationSearchControls();
  byId("userGreeting").textContent = currentUser ? `Hi ${currentUser.name}` : "Live map";
  ensureMap();
  await refreshMapData();
  startGpsWatch();
  scheduleMapResize();
  setTimeout(scheduleMapResize, 300);

  if (!proximityEvalTimer){
    proximityEvalTimer = setInterval(()=>{
      evaluateProximityAlerts();
    }, 2000);
  }
}

function ensureMap(){
  if (map) return;

  const rotatePluginReady = typeof L.Map?.prototype?.setBearing === "function";

  map = L.map("map", {
    zoomControl:true,
    dragging:true,
    touchZoom:true,
    doubleClickZoom:true,
    scrollWheelZoom:true,
    boxZoom:true,
    keyboard:true,
    zoomAnimation:true,
    fadeAnimation:true,
    markerZoomAnimation:true,
    inertia:true,
    inertiaDeceleration:2600,
    inertiaMaxSpeed:1800,
    easeLinearity:0.2,

    // Google-Maps-style gestures: one finger pans; two fingers pinch and twist.
    // Rotation is handled only by leaflet-rotate, not by custom touch listeners.
    rotate:rotatePluginReady,
    bearing:rotatePluginReady ? normalizeBearing(mapBearingDeg) : 0,
    // RoadPulse owns touch rotation with a small dead-zone. The plug-in's
    // built-in touchRotate deliberately waits for ~30 degrees, which feels
    // unresponsive on phones. Pinch zoom is still handled natively by Leaflet.
    touchRotate:false,
    dragRotate:rotatePluginReady,
    shiftKeyRotate:rotatePluginReady,
    rotateClockwise:true,
    preventPageGestures:true,
    rotateControl:false
  }).setView([53.5511, 9.9937], 12);

  map.createPane("basemap");
  map.getPane("basemap").style.zIndex = 200;

  map.createPane("traffic");
  map.getPane("traffic").style.zIndex = 260;
  map.getPane("traffic").style.pointerEvents = "none";

  map.createPane("route");
  map.getPane("route").style.zIndex = 430;
  map.getPane("route").style.pointerEvents = "none";

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom:19,
    pane:"basemap",
    attribution:'&copy; OpenStreetMap contributors',
    updateWhenIdle:false,
    keepBuffer:4
  }).addTo(map);

  incidentLayer = L.layerGroup().addTo(map);
  cameraLayer = L.layerGroup().addTo(map);

  trafficFlowLayer = L.tileLayer("/api/traffic/flow/{z}/{x}/{y}", {
    tileSize:256,
    opacity:.88,
    pane:"traffic",
    maxZoom:22,
    updateWhenIdle:false,
    keepBuffer:3
  });

  trafficIncidentLayer = L.tileLayer("/api/traffic/incidents/{z}/{x}/{y}", {
    tileSize:256,
    opacity:.92,
    pane:"traffic",
    maxZoom:22,
    updateWhenIdle:false,
    keepBuffer:3
  });

  if (!trafficRefreshTimer){
    trafficRefreshTimer = setInterval(()=>{
      if (trafficConfigured && trafficEnabledByUser){
        trafficFlowLayer && trafficFlowLayer.redraw();
        trafficIncidentLayer && trafficIncidentLayer.redraw();
      }
    }, 60000);
  }

  const noteUserGesture = ()=>{
    lastUserMapGestureAt = Date.now();
  };

  const container = map.getContainer();
  container.addEventListener("pointerdown", noteUserGesture, {passive:true});
  container.addEventListener("touchstart", noteUserGesture, {passive:true});
  container.addEventListener("wheel", noteUserGesture, {passive:true});

  const stopFollowForUserGesture = ()=>{
    if (!navigationActive) return;
    navFollowMode = false;
    updateFollowButton();
  };

  map.on("dragstart", ()=>{
    noteUserGesture();
    stopFollowForUserGesture();
  });

  map.on("zoomstart", ()=>{
    if (Date.now() - lastUserMapGestureAt < 800){
      stopFollowForUserGesture();
    }
  });

  // Rotation is a user gesture too. While navigating, rotating the map should
  // release automatic follow so the camera does not fight the user's fingers.
  map.on("rotatestart", ()=>{
    stopNavigationHeadingUp(false);
    noteUserGesture();
    stopFollowForUserGesture();
  });

  map.on("rotate", ()=>{
    const bearing = Number(map?.getBearing?.());
    if (!Number.isFinite(bearing)) return;

    mapBearingDeg = normalizeBearing(bearing);
    updateRoadPulseCompass();
    if (currentDisplayPosition){
      updateUserHeadingMarker(
        [currentDisplayPosition.lat,currentDisplayPosition.lng],
        currentDisplayPosition.heading
      );
    }

    // Some mobile GPUs defer SVG repaint during a bearing change. Redraw the
    // navigation path after the fingers settle so the route can never vanish.
    clearTimeout(routeRotateRedrawTimer);
    routeRotateRedrawTimer = setTimeout(()=>{
      try{ navRouteOutlineLayer?.redraw?.(); }catch(_){}
      try{ navRouteLayer?.redraw?.(); }catch(_){}
      try{ navRouteOutlineLayer?.bringToFront?.(); }catch(_){}
      try{ navRouteLayer?.bringToFront?.(); }catch(_){}
    }, 70);

    if (!navigationHeadingUp){
      clearTimeout(window.__roadpulseBearingSaveTimer);
      window.__roadpulseBearingSaveTimer = setTimeout(()=>{
        safeLocalSet("roadpulse_map_bearing", String(Math.round(mapBearingDeg * 10) / 10));
      }, 180);
    }
  });

  installRoadPulseMapGestures();
  applyRoadPulseMapBearing(mapBearingDeg, false);
  scheduleMapResize();
}

function scheduleMapResize(){
  clearTimeout(mapResizeTimer);
  mapResizeTimer = setTimeout(()=>{
    try{
      map?.invalidateSize?.({pan:false});
    }catch(_){}
  }, 90);
}

window.addEventListener("resize", scheduleMapResize, {passive:true});
window.addEventListener("orientationchange", ()=>{
  scheduleMapResize();
  setTimeout(scheduleMapResize, 350);
}, {passive:true});
window.visualViewport?.addEventListener?.("resize", scheduleMapResize, {passive:true});

function normalizeBearing(value){
  let n = Number(value || 0) % 360;
  if (n < 0) n += 360;
  return n;
}

function nullableFiniteNumber(value){
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function blendBearing(fromDeg,toDeg,amount){
  const from = normalizeBearing(fromDeg);
  const delta = shortestBearingDelta(from,toDeg);
  const alpha = Math.max(0,Math.min(1,Number(amount) || 0));
  return normalizeBearing(from + delta * alpha);
}

function headingScreenRotation(heading,mapBearing){
  return normalizeBearing(Number(heading) + Number(mapBearing || 0));
}

function routeSnapDistanceLimit(mode,accuracy){
  const base = mode === "pedestrian" ? 12 : (mode === "bicycle" ? 18 : 25);
  const cap = mode === "pedestrian" ? 30 : (mode === "bicycle" ? 45 : 60);
  const gpsAllowance = Math.max(0,Number(accuracy) || 0) * 0.25;
  return Math.min(cap,base + gpsAllowance);
}

function updateRoadPulseCompass(){
  const compass = byId("mapCompassBtn");
  if (!compass) return;

  const rounded = Math.round(normalizeBearing(mapBearingDeg));
  compass.style.setProperty("--map-bearing", `${-rounded}deg`);
  compass.classList.toggle("rotated", rounded !== 0);
  compass.classList.toggle("north-up", rounded === 0);
  compass.title = rounded === 0
    ? "Map is north-up"
    : `Reset map to north (${rounded}°)`;
  compass.setAttribute("aria-label", compass.title);
}

function applyRoadPulseMapBearing(value, persist=true){
  const next = normalizeBearing(value);

  if (map && typeof map.setBearing === "function"){
    map.setBearing(next);
    const actual = Number(map.getBearing?.());
    mapBearingDeg = Number.isFinite(actual) ? normalizeBearing(actual) : next;
  }else{
    mapBearingDeg = 0;
  }

  updateRoadPulseCompass();

  if (persist){
    safeLocalSet("roadpulse_map_bearing", String(Math.round(mapBearingDeg * 10) / 10));
  }
}

function shortestBearingDelta(fromDeg,toDeg){
  let d = normalizeBearing(toDeg) - normalizeBearing(fromDeg);
  while (d > 180) d -= 360;
  while (d < -180) d += 360;
  return d;
}

function resetMapBearing(event){
  try{ event?.preventDefault?.(); }catch(_){}
  try{ event?.stopPropagation?.(); }catch(_){}

  if (!map || typeof map.setBearing !== "function"){
    mapBearingDeg = 0;
    updateRoadPulseCompass();
    safeLocalSet("roadpulse_map_bearing", "0");
    return;
  }

  // Do not let a previous heading-up animation immediately rotate the map back.
  stopNavigationHeadingUp(false);

  const startBearing = normalizeBearing(Number(map.getBearing?.()) || 0);
  const delta = shortestBearingDelta(startBearing, 0);

  if (Math.abs(delta) < 0.35){
    map.setBearing(0);
    mapBearingDeg = 0;
    updateRoadPulseCompass();
    safeLocalSet("roadpulse_map_bearing", "0");
    return;
  }

  const startedAt = performance.now();
  const duration = 190;
  const easeOut = t => 1 - Math.pow(1 - t, 3);

  const frame = now=>{
    const t = Math.min(1, (now - startedAt) / duration);
    const bearing = normalizeBearing(startBearing + delta * easeOut(t));
    map.setBearing(bearing);
    if (t < 1){
      requestAnimationFrame(frame);
      return;
    }
    map.setBearing(0);
    mapBearingDeg = 0;
    updateRoadPulseCompass();
    safeLocalSet("roadpulse_map_bearing", "0");
  };
  requestAnimationFrame(frame);
}

function stopNavigationHeadingUp(resetNorth=false){
  const wasActive = navigationHeadingUp;
  try{ map?.stopHeadingUp?.(); }catch(_){}
  navigationHeadingUp = false;

  if (resetNorth && wasActive && map && typeof map.setBearing === "function"){
    applyRoadPulseMapBearing(0);
  }
}

function installRoadPulseHighSensitivityRotation(){
  if (!map || typeof map.setBearing !== "function") return;

  const el = map.getContainer();
  if (!el || el.dataset.roadpulseSmoothRotate === "1") return;
  el.dataset.roadpulseSmoothRotate = "1";

  const touchPoint = event=>({x:event.clientX, y:event.clientY});
  const angleBetween = (a,b)=>Math.atan2(b.y-a.y, b.x-a.x) * 180 / Math.PI;
  const getPair = ()=>{
    if (rotateTouchPointers.size !== 2) return null;
    return Array.from(rotateTouchPointers.values());
  };

  const beginPair = ()=>{
    const pair = getPair();
    if (!pair) return;
    rotateTouchState = {
      startAngle:angleBetween(pair[0], pair[1]),
      startBearing:normalizeBearing(Number(map.getBearing?.()) || 0),
      active:false
    };
  };

  const scheduleBearing = bearing=>{
    rotateTouchPendingBearing = normalizeBearing(bearing);
    if (rotateTouchRaf) return;
    rotateTouchRaf = requestAnimationFrame(()=>{
      rotateTouchRaf = 0;
      try{ map.setBearing(rotateTouchPendingBearing); }catch(err){
        console.warn("RoadPulse touch rotation failed", err);
      }
    });
  };

  el.addEventListener("pointerdown", event=>{
    if (event.pointerType !== "touch") return;
    rotateTouchPointers.set(event.pointerId, touchPoint(event));
    if (rotateTouchPointers.size === 2) beginPair();
  }, {passive:true});

  el.addEventListener("pointermove", event=>{
    if (event.pointerType !== "touch" || !rotateTouchPointers.has(event.pointerId)) return;
    rotateTouchPointers.set(event.pointerId, touchPoint(event));

    const pair = getPair();
    if (!pair || !rotateTouchState) return;

    const angle = angleBetween(pair[0], pair[1]);
    const delta = shortestBearingDelta(rotateTouchState.startAngle, angle);

    // A tiny dead-zone prevents accidental rotation during a straight pinch,
    // while still starting much sooner than the plug-in's ~30 degree threshold.
    if (!rotateTouchState.active){
      if (Math.abs(delta) < 3.5) return;
      rotateTouchState.active = true;
      noteRoadPulseRotationGesture();
    }

    scheduleBearing(rotateTouchState.startBearing + delta);
  }, {passive:true});

  const finishPointer = event=>{
    if (event.pointerType !== "touch") return;
    rotateTouchPointers.delete(event.pointerId);
    if (rotateTouchPointers.size < 2){
      rotateTouchState = null;
      const bearing = normalizeBearing(Number(map.getBearing?.()) || mapBearingDeg || 0);
      mapBearingDeg = bearing;
      updateRoadPulseCompass();
      safeLocalSet("roadpulse_map_bearing", String(Math.round(bearing * 10) / 10));
    }else{
      beginPair();
    }
  };

  el.addEventListener("pointerup", finishPointer, {passive:true});
  el.addEventListener("pointercancel", finishPointer, {passive:true});
  el.addEventListener("lostpointercapture", finishPointer, {passive:true});
}

function installRoadPulseMapGestures(){
  if (!map) return;

  try{ map.dragging?.enable(); }catch(_){}
  try{ map.touchZoom?.enable(); }catch(_){}
  try{ map.doubleClickZoom?.enable(); }catch(_){}
  try{ map.scrollWheelZoom?.enable(); }catch(_){}

  if (typeof map.setBearing !== "function"){
    console.error("RoadPulse: leaflet-rotate did not load; map rotation is unavailable.");
    return;
  }

  // Avoid two rotation engines reacting to the same fingers. Desktop rotation
  // remains owned by leaflet-rotate; phones use RoadPulse's low-dead-zone layer.
  try{ map.touchRotate?.disable?.(); }catch(_){}
  try{ map.dragRotate?.enable?.(); }catch(_){}
  try{ map.shiftKeyRotate?.enable?.(); }catch(_){}

  const el = map.getContainer();
  if (el){
    el.style.touchAction = "none";
    el.style.overscrollBehavior = "none";
  }

  const compass = byId("mapCompassBtn");
  if (compass && compass.dataset.roadpulseCompassBound !== "1"){
    compass.dataset.roadpulseCompassBound = "1";
    try{ L.DomEvent.disableClickPropagation(compass); }catch(_){}
    try{ L.DomEvent.disableScrollPropagation(compass); }catch(_){}
    compass.addEventListener("pointerdown", event=>event.stopPropagation());
    compass.addEventListener("touchstart", event=>event.stopPropagation(), {passive:true});
  }

  installRoadPulseHighSensitivityRotation();
}

function noteRoadPulseRotationGesture(){
  stopNavigationHeadingUp(false);
  lastUserMapGestureAt = Date.now();
  if (navigationActive){
    navFollowMode = false;
    updateFollowButton();
  }
}

function startGpsWatch(force=false){
  if (!navigator.geolocation){
    setGpsBadge("GPS not supported", false);
    return;
  }

  if (force){
    if (watchId !== null){
      try{ navigator.geolocation.clearWatch(watchId); }catch(_){}
      watchId = null;
    }
    lastRawGpsFix = null;
    lastReliableHeading = null;
    lastReliableHeadingAt = 0;
  }

  if (watchId !== null) return;

  gpsWatchStartedAt = Date.now();
  setGpsBadge("Requesting GPS…", false);

  watchId = navigator.geolocation.watchPosition(
    onGpsPosition,
    onGpsError,
    {
      enableHighAccuracy:true,
      maximumAge:1000,
      timeout:20000
    }
  );
}

function stopGpsWatch(){
  if (watchId !== null && navigator.geolocation){
    try{ navigator.geolocation.clearWatch(watchId); }catch(_){}
  }
  watchId = null;
  gpsWatchStartedAt = 0;
}

function onGpsPosition(pos){
  if (!pos?.coords) return;

  const rawLat = Number(pos.coords.latitude);
  const rawLng = Number(pos.coords.longitude);
  const rawAccuracy = Number(pos.coords.accuracy);
  const timestamp = Number(pos.timestamp) || Date.now();

  if (
    !Number.isFinite(rawLat) ||
    !Number.isFinite(rawLng) ||
    rawLat < -90 || rawLat > 90 ||
    rawLng < -180 || rawLng > 180
  ){
    return;
  }

  if (Date.now() - timestamp > 30000 || timestamp > Date.now() + 5000){
    return;
  }

  const accuracy = Number.isFinite(rawAccuracy) && rawAccuracy > 0
    ? rawAccuracy
    : 9999;

  if (accuracy > 2000){
    setGpsBadge(`GPS weak · ±${Math.round(accuracy)}m`, false);
    return;
  }

  let lat = rawLat;
  let lng = rawLng;
  let speed = nullableFiniteNumber(pos.coords.speed);
  let nativeHeading = nullableFiniteNumber(pos.coords.heading);

  speed = speed != null && speed >= 0 && speed <= 100 ? speed : null;
  nativeHeading = nativeHeading != null && nativeHeading >= 0 && nativeHeading <= 360
    ? normalizeBearing(nativeHeading)
    : null;

  const previous = currentPosition;
  const previousRaw = lastRawGpsFix;
  let rawDistance = null;
  let dt = null;
  let impliedSpeed = null;
  let derivedHeading = null;

  if (previousRaw?.timestamp){
    if (timestamp <= previousRaw.timestamp) return;

    dt = Math.max(0.05, (timestamp - previousRaw.timestamp) / 1000);
    rawDistance = haversineMeters(
      previousRaw.lat,
      previousRaw.lng,
      rawLat,
      rawLng
    );
    impliedSpeed = rawDistance / dt;

    const jumpAllowance = Math.max(
      120,
      accuracy * 2.5,
      Number(previousRaw.accuracy || 0) * 2.5
    );

    if (
      dt < 10 &&
      rawDistance > jumpAllowance &&
      impliedSpeed > 75 &&
      (accuracy > 25 || impliedSpeed > 100)
    ){
      setGpsBadge("GPS stabilizing…", false);
      return;
    }

    if (
      Number(previous?.accuracy || 9999) <= 60 &&
      accuracy > 120 &&
      rawDistance > Math.max(90, accuracy * 0.6)
    ){
      setGpsBadge(`GPS weak · ±${Math.round(accuracy)}m`, false);
      return;
    }

    const noiseFloor = Math.max(
      3,
      Math.min(18,Math.max(accuracy,Number(previousRaw.accuracy || accuracy)) * 0.30)
    );

    if (
      speed == null &&
      dt <= 10 &&
      rawDistance >= noiseFloor &&
      Number.isFinite(impliedSpeed) &&
      impliedSpeed <= 65
    ){
      speed = impliedSpeed;
    }

    const headingDistanceFloor = Math.max(4,noiseFloor);
    if (
      dt <= 10 &&
      rawDistance >= headingDistanceFloor &&
      impliedSpeed >= 0.7 &&
      impliedSpeed <= 65
    ){
      derivedHeading = bearingDegrees(
        previousRaw.lat,
        previousRaw.lng,
        rawLat,
        rawLng
      );
    }
  }

  if (previous?.timestamp && previousRaw?.timestamp){

    let alpha = accuracy <= 15
      ? 1
      : accuracy <= 35
        ? 0.82
        : accuracy <= 80
          ? 0.58
          : 0.36;

    if (speed != null && speed >= 3){
      alpha = Math.max(alpha, 0.88);
    }

    lat = previous.lat + (rawLat - previous.lat) * alpha;
    lng = previous.lng + (rawLng - previous.lng) * alpha;

  }

  let heading = null;
  let headingSource = "none";
  const movingSpeed = Number(speed || 0);

  if (nativeHeading != null && movingSpeed >= 0.7){
    heading = nativeHeading;
    headingSource = "native";
  }else if (derivedHeading != null && (movingSpeed >= 0.7 || Number(impliedSpeed || 0) >= 0.7)){
    heading = derivedHeading;
    headingSource = "derived";
  }else if (
    movingSpeed >= 0.7 &&
    lastReliableHeading != null &&
    timestamp - lastReliableHeadingAt <= 3000
  ){
    heading = lastReliableHeading;
    headingSource = "held";
  }

  if (heading != null && previousRaw?.timestamp && previous?.heading != null){
    const turnSize = angleDifference(previous.heading,heading);
    const smoothing = turnSize > 75
      ? 0.78
      : (headingSource === "native" ? 0.58 : 0.66);
    heading = blendBearing(previous.heading,heading,smoothing);
  }

  if (heading != null && headingSource !== "held"){
    lastReliableHeading = heading;
    lastReliableHeadingAt = timestamp;
  }

  lastRawGpsFix = {
    lat:rawLat,
    lng:rawLng,
    accuracy,
    timestamp
  };

  currentPosition = {
    lat,
    lng,
    rawLat,
    rawLng,
    accuracy,
    speed,
    heading,
    headingSource,
    timestamp
  };
  lastGpsFixAt = Date.now();

  const displayPosition = renderGpsPosition();
  const latlng = displayPosition
    ? [displayPosition.lat,displayPosition.lng]
    : [currentPosition.lat,currentPosition.lng];

  const waitMs = gpsWatchStartedAt ? Date.now() - gpsWatchStartedAt : 0;
  const canUseInitialFix = currentPosition.accuracy <= 100 || waitMs >= 10000;

  if (!map.__centeredOnUser && canUseInitialFix){
    const initialZoom = currentPosition.accuracy <= 25
      ? 17
      : currentPosition.accuracy <= 80
        ? 15
        : 13;

    map.setView(latlng, initialZoom, {animate:false});
    map.__centeredOnUser = true;
    map.__initialGpsAccuracy = currentPosition.accuracy;
  }else if (
    map.__centeredOnUser &&
    !navigationActive &&
    Number(map.__initialGpsAccuracy || 9999) > 100 &&
    currentPosition.accuracy <= 60 &&
    currentPosition.accuracy < Number(map.__initialGpsAccuracy) * 0.6 &&
    Date.now() - lastUserMapGestureAt > 2500
  ){
    map.__initialGpsAccuracy = currentPosition.accuracy;
    map.flyTo(latlng, 16, {animate:true, duration:.45});
  }

  const speedKmh = currentPosition.speed != null && currentPosition.speed >= 0
    ? Math.round(currentPosition.speed * 3.6)
    : null;

  const gpsGood = currentPosition.accuracy <= 100;
  setGpsBadge(
    `${gpsGood ? "GPS live" : "GPS weak"} · ±${Math.round(currentPosition.accuracy)}m`,
    gpsGood
  );

  const speedBadge = byId("speedBadge");
  if (speedBadge){
    speedBadge.textContent = `${speedKmh ?? 0} km/h`;
  }

  evaluateProximityAlerts();
  updateNavigationProgress();

  if (
    navigationActive &&
    navFollowMode &&
    map
  ){
    updateNavigationCamera();
  }
}

function renderGpsPosition(){
  if (!map || !currentPosition) return null;

  const display = getNavigationDisplayPosition(currentPosition);
  currentDisplayPosition = display;

  const displayLatLng = [display.lat,display.lng];
  const rawLatLng = [currentPosition.lat,currentPosition.lng];

  if (!userMarker){
    userMarker = L.circleMarker(displayLatLng, {
      radius:9,
      color:"#ffffff",
      weight:3,
      fillColor:"#2d70d6",
      fillOpacity:1,
      interactive:false
    }).addTo(map);
  }else{
    userMarker.setLatLng(displayLatLng);
  }

  // The accuracy circle stays on the filtered GPS fix. Only the visual
  // navigation marker is route-matched, so GPS uncertainty remains honest.
  if (!userAccuracyCircle){
    userAccuracyCircle = L.circle(rawLatLng, {
      radius:Math.min(currentPosition.accuracy, 1500),
      color:"#2d70d6",
      weight:1,
      fillOpacity:.08,
      interactive:false
    }).addTo(map);
  }else{
    userAccuracyCircle.setLatLng(rawLatLng);
    userAccuracyCircle.setRadius(Math.min(currentPosition.accuracy, 1500));
  }

  updateUserHeadingMarker(displayLatLng,display.heading);
  return display;
}

function onGpsError(err){
  const messages = {
    1:"Location permission denied",
    2:"GPS position unavailable",
    3:"GPS request timed out"
  };
  setGpsBadge(messages[err.code] || "GPS error", false);

  // Do not repeatedly prompt after an explicit denial. For temporary mobile GPS
  // failures/timeouts, restart a stale watcher after a short pause.
  if (err?.code !== 1){
    setTimeout(()=>{
      if (
        document.visibilityState === "visible" &&
        (!lastGpsFixAt || Date.now() - lastGpsFixAt > 20000)
      ){
        startGpsWatch(true);
      }
    }, 5000);
  }
}

function setGpsBadge(text, good){
  const el = byId("gpsBadge");
  if (!el) return;
  el.textContent = text;
  el.classList.toggle("good", !!good);
  el.classList.toggle("warning", !good);
}

function centerOnUser(){
  if (navigationActive){
    navFollowMode = true;
    updateFollowButton();
  }

  if (map && currentPosition){
    const zoom = navigationActive ? navigationFollowZoom() : Math.max(16, map.getZoom());
    const display = getNavigationDisplayPosition(currentPosition);
    currentDisplayPosition = display;
    map.stop();
    map.flyTo(
      [display.lat,display.lng],
      zoom,
      {animate:true, duration:.45}
    );
  }else{
    startGpsWatch(true);
    setGpsBadge("Waiting for GPS…", false);
  }
}


function navigationModeColor(){
  if (navigationMode === "pedestrian") return "#006cff";
  if (navigationMode === "bicycle") return "#009fbd";
  return "#5b2aef";
}

function navigationFollowZoom(){
  const speed = Math.max(0, Number(currentPosition?.speed || 0));

  if (navigationMode === "pedestrian"){
    return 18;
  }

  if (navigationMode === "bicycle"){
    if (speed >= 7.0) return 16;
    if (speed >= 3.5) return 17;
    return 18;
  }

  // Car: wider view as speed increases.
  if (speed >= 27.8) return 14; // ~100 km/h
  if (speed >= 16.7) return 15; // ~60 km/h
  if (speed >= 8.3) return 16;  // ~30 km/h
  return 17;
}

function updateNavigationCamera(force=false){
  if (!map || !currentPosition || !navigationActive || !navFollowMode) return;

  const now = Date.now();
  if (!force && now - lastNavigationCameraUpdateAt < 700) return;
  lastNavigationCameraUpdateAt = now;

  const display = getNavigationDisplayPosition(currentPosition);
  currentDisplayPosition = display;
  const target = [display.lat,display.lng];
  const zoom = navigationFollowZoom();
  const cameraHeading = nullableFiniteNumber(display.heading);

  try{ map.stop(); }catch(_){}

  const headingUpMinSpeed = navigationMode === "car" ? 2.0 : 1.2;
  if (
    navigationMode !== "pedestrian" &&
    Number(currentPosition.speed || 0) >= headingUpMinSpeed &&
    cameraHeading != null &&
    typeof map.setHeading === "function"
  ){
    navigationHeadingUp = true;
    map.setHeading(cameraHeading,{ease:0.22,deadzone:0.8});
  }

  if (Math.abs(map.getZoom() - zoom) >= 1){
    map.setView(target, zoom, {
      animate:true,
      pan:{animate:true, duration:.28},
      zoom:{animate:true}
    });
  }else{
    map.panTo(target, {
      animate:true,
      duration:.28,
      noMoveStart:true
    });
  }
}

function updateUserHeadingMarker(latlng,displayHeading=currentPosition?.heading){
  if (!map || !currentPosition) return;

  const heading = nullableFiniteNumber(displayHeading);
  const speed = Math.max(0, Number(currentPosition.speed || 0));
  const hasHeading = heading != null && heading >= 0 && speed >= 0.7;

  if (!hasHeading){
    if (userHeadingMarker && map.hasLayer(userHeadingMarker)){
      map.removeLayer(userHeadingMarker);
    }
    return;
  }

  const bearing = nullableFiniteNumber(map.getBearing?.()) ?? mapBearingDeg;
  const screenHeading = headingScreenRotation(heading,bearing);

  const icon = L.divIcon({
    className:"roadpulse-heading-marker-wrap",
    html:`<div class="roadpulse-heading-marker" style="transform:rotate(${screenHeading}deg)">▲</div>`,
    iconSize:[34,34],
    iconAnchor:[17,17]
  });

  if (!userHeadingMarker){
    userHeadingMarker = L.marker(latlng,{
      icon,
      interactive:false,
      keyboard:false,
      zIndexOffset:1200
    }).addTo(map);
  }else{
    if (!map.hasLayer(userHeadingMarker)) userHeadingMarker.addTo(map);
    userHeadingMarker.setLatLng(latlng);
    userHeadingMarker.setIcon(icon);
  }
}

function renderDestinationMarker(){
  if (!map){
    return;
  }

  if (!navDestination){
    clearDestinationMarker();
    return;
  }

  const color = navigationModeColor();
  const icon = L.divIcon({
    className:"roadpulse-destination-marker-wrap",
    html:`<div class="roadpulse-destination-pin" style="--pin-color:${color}"><span>●</span></div>`,
    iconSize:[38,48],
    iconAnchor:[19,45]
  });

  const latlng = [Number(navDestination.lat), Number(navDestination.lng)];

  if (!navDestinationMarker){
    navDestinationMarker = L.marker(latlng,{
      icon,
      zIndexOffset:1050,
      title:navDestination.name || "Destination"
    }).addTo(map);
  }else{
    if (!map.hasLayer(navDestinationMarker)) navDestinationMarker.addTo(map);
    navDestinationMarker.setLatLng(latlng);
    navDestinationMarker.setIcon(icon);
  }
}

function clearDestinationMarker(){
  if (map && navDestinationMarker && map.hasLayer(navDestinationMarker)){
    map.removeLayer(navDestinationMarker);
  }
  navDestinationMarker = null;
}

function updateTrafficClarity(){
  if (!trafficFlowLayer || !trafficIncidentLayer) return;

  let flowOpacity = .88;
  let incidentOpacity = .92;

  if (navigationActive){
    if (navigationMode === "car"){
      flowOpacity = .42;
      incidentOpacity = .70;
    }else{
      flowOpacity = .17;
      incidentOpacity = .34;
    }
  }

  trafficFlowLayer.setOpacity(flowOpacity);
  trafficIncidentLayer.setOpacity(incidentOpacity);

  const legend = byId("trafficLegend");
  if (legend){
    legend.classList.toggle("navigation-muted", navigationActive);
  }
}

const reportStyle = {
  camera:  {color:"#2d70d6", emoji:"📷"},
  police:  {color:"#3159b8", emoji:"🚓"},
  accident:{color:"#d63b32", emoji:"🚗"},
  hazard:  {color:"#e09b18", emoji:"⚠️"},
  roadwork:{color:"#d97818", emoji:"🚧"},
  traffic: {color:"#17a65b", emoji:"🚦"}
};

async function refreshMapData(){
  if (!map) return;

  try{
    const r = await fetch("/api/map-data", {credentials:"include"});

    if (r.status === 401){
      await userLogout();
      return;
    }

    if (!r.ok){
      throw new Error(`Map data HTTP ${r.status}`);
    }

    const data = await r.json();
    const reports = Array.isArray(data?.reports) ? data.reports : [];
    const cameras = Array.isArray(data?.cameras) ? data.cameras : [];
    const settings = data?.settings || {};

    incidentLayer?.clearLayers();
    cameraLayer?.clearLayers();

    reports.forEach(item=>{
      const lat = Number(item.lat);
      const lng = Number(item.lng);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

      const style = reportStyle[item.type] || {color:"#666", emoji:"•"};
      const marker = L.circleMarker([lat,lng], {
        radius:9, color:"#fff", weight:2, fillColor:style.color, fillOpacity:.95
      });
      marker.bindPopup(`
        <div class="popup-title">${style.emoji} ${esc(item.type)}</div>
        <div>${esc(item.location || "Reported location")}</div>
        <div class="popup-meta">Community verified</div>
      `);
      marker.addTo(incidentLayer);
    });

    cameras.forEach(item=>{
      const lat = Number(item.lat);
      const lng = Number(item.lng);
      if (!Number.isFinite(lat) || !Number.isFinite(lng)) return;

      const marker = L.marker([lat,lng], {
        title:`Camera: ${item.location || ""}`
      });
      const limit = item.speed_limit ? `${item.speed_limit} km/h` : "Speed unknown";
      marker.bindPopup(`
        <div class="popup-title">📷 ${esc(item.camera_type || "fixed")} camera</div>
        <div>${esc(item.location || "Camera location")}</div>
        <div class="popup-meta">${esc(limit)} · confidence ${esc(item.confidence ?? "—")}%</div>
      `);
      marker.addTo(cameraLayer);
    });

    const incidentBadge = byId("incidentBadge");
    if (incidentBadge){
      incidentBadge.textContent = `${reports.length} verified reports`;
    }

    proximitySettings = {
      enabled: settings.proximity_alerts !== false,
      voice: settings.voice_alerts !== false,
      maxDistanceM: Number(settings.alert_distance_m || 1200),
      urgentDistanceM: Number(settings.urgent_alert_distance_m || 400),
      cooldownS: Number(settings.alert_repeat_cooldown_s || 300),
      language: settings.voice_language || "en-GB",
      defaultCountry: settings.default_country || "DE",
      cameraWarningMode: settings.camera_warning_mode || "country_compliance"
    };

    proximityTargets = buildProximityTargets({
      ...data,
      reports,
      cameras,
      settings
    });
    updateVoiceBadge();
    evaluateProximityAlerts();

    trafficConfigured = !!settings.traffic_available;
    const adminTrafficEnabled = settings.traffic_layer !== false;
    applyTrafficLayerState(adminTrafficEnabled);
  }catch(err){
    console.error("RoadPulse map data refresh failed:", err);
    updateNetworkBadge();

    const trafficBadge = byId("trafficBadge");
    if (trafficBadge){
      trafficBadge.textContent = navigator.onLine === false
        ? "Traffic offline"
        : "Traffic unavailable";
      trafficBadge.classList.remove("on","off");
      trafficBadge.classList.add("error");
    }
  }
}

function applyTrafficLayerState(adminTrafficEnabled=true){
  const badge = byId("trafficBadge");
  const legend = byId("trafficLegend");
  if (!badge || !map) return;

  if (!trafficConfigured){
    if (trafficFlowLayer && map.hasLayer(trafficFlowLayer)) map.removeLayer(trafficFlowLayer);
    if (trafficIncidentLayer && map.hasLayer(trafficIncidentLayer)) map.removeLayer(trafficIncidentLayer);
    badge.textContent = "Traffic API not configured";
    badge.classList.remove("on","off");
    badge.classList.add("error");
    legend && legend.classList.add("hidden");
    return;
  }

  if (!adminTrafficEnabled){
    if (trafficFlowLayer && map.hasLayer(trafficFlowLayer)) map.removeLayer(trafficFlowLayer);
    if (trafficIncidentLayer && map.hasLayer(trafficIncidentLayer)) map.removeLayer(trafficIncidentLayer);
    badge.textContent = "Traffic disabled by admin";
    badge.classList.remove("on","error");
    badge.classList.add("off");
    legend && legend.classList.add("hidden");
    return;
  }

  if (trafficEnabledByUser){
    if (trafficFlowLayer && !map.hasLayer(trafficFlowLayer)) trafficFlowLayer.addTo(map);
    if (trafficIncidentLayer && !map.hasLayer(trafficIncidentLayer)) trafficIncidentLayer.addTo(map);
    badge.textContent = "Live Traffic ON";
    badge.classList.remove("off","error");
    badge.classList.add("on");
    legend && legend.classList.remove("hidden");
  }else{
    if (trafficFlowLayer && map.hasLayer(trafficFlowLayer)) map.removeLayer(trafficFlowLayer);
    if (trafficIncidentLayer && map.hasLayer(trafficIncidentLayer)) map.removeLayer(trafficIncidentLayer);
    badge.textContent = "Traffic OFF";
    badge.classList.remove("on","error");
    badge.classList.add("off");
    legend && legend.classList.add("hidden");
  }

  updateTrafficClarity();
}

function toggleTrafficLayer(){
  if (!trafficConfigured){
    applyTrafficLayerState(true);
    return;
  }
  trafficEnabledByUser = !trafficEnabledByUser;
  applyTrafficLayerState(true);
}

async function refreshAllLiveData(){
  await refreshMapData();
  if (trafficConfigured && trafficEnabledByUser){
    trafficFlowLayer && trafficFlowLayer.redraw();
    trafficIncidentLayer && trafficIncidentLayer.redraw();
  }
}




function bindDestinationSearchControls(){
  const input = byId("destinationSearchInput");
  const goBtn = byId("destinationSearchGoBtn");

  if (!input || input.dataset.roadpulseSearchBound === "1"){
    updateDestinationActionButton();
    return;
  }

  input.dataset.roadpulseSearchBound = "1";
  input.addEventListener("input", onDestinationSearchInput);
  input.addEventListener("keydown", onDestinationSearchKeydown);
  input.addEventListener("focus", ()=>{
    if (!input.value.trim()) renderDestinationQuickList();
  });

  if (goBtn) goBtn.addEventListener("click", manualDestinationSearch);
  updateDestinationActionButton();
  console.log("RoadPulse destination search controls bound");
}

function updateDestinationActionButton(){
  const btn = byId("destinationSearchGoBtn");
  if (!btn) return;

  const ready = !!navDestination && !navigationActive;
  btn.textContent = ready ? "GO →" : "Search";
  btn.title = ready ? "Start navigation" : "Search destination";
  btn.classList.toggle("ready", ready);
  document.body.classList.toggle("destination-ready", ready);
}

async function manualDestinationSearch(){
  const input = byId("destinationSearchInput");
  if (!input) return;

  if (navDestination && !navigationActive){
    await startNavigation();
    return;
  }

  const q = input.value.trim();
  if (q.length < 2){
    const box = byId("destinationResults");
    if (box){
      box.innerHTML = '<div class="destination-result"><div class="destination-result-icon">⌕</div><div><strong>Type at least 2 letters</strong><small>Example: Frankfurt Hbf</small></div></div>';
      box.classList.remove("hidden");
    }
    return;
  }

  if (navSearchTimer){
    clearTimeout(navSearchTimer);
    navSearchTimer = null;
  }

  await searchDestinations(q);
}

function focusDestinationSearch(){
  const input = byId("destinationSearchInput");
  if (input){
    input.focus();
    input.select();

    if (!input.value.trim()){
      renderDestinationQuickList();
    }
  }
}

function onDestinationSearchKeydown(event){
  if (event.key === "Escape"){
    byId("destinationResults")?.classList.add("hidden");
    return;
  }

  if (event.key === "Enter"){
    event.preventDefault();
    if (navSearchResults.length > 0){
      chooseDestinationResult(0);
    }else{
      manualDestinationSearch();
    }
  }
}

function onDestinationSearchInput(){
  const input = byId("destinationSearchInput");
  const clearBtn = byId("clearDestinationBtn");
  if (!input) return;

  const q = input.value.trim();
  navSearchResults = [];

  if (navDestination && !navigationActive && q !== navDestination.name){
    navDestination = null;
    updateDestinationActionButton();
  }
  clearBtn?.classList.toggle("hidden", q.length === 0);

  if (navSearchTimer){
    clearTimeout(navSearchTimer);
  }

  if (q.length < 2){
    navSearchAbortController?.abort();
    navSearchAbortController = null;
    navSearchRequestSeq++;
    byId("destinationResults")?.classList.add("hidden");
    renderDestinationQuickList();
    return;
  }

  byId("destinationQuickList")?.classList.add("hidden");

  navSearchTimer = setTimeout(()=>{
    searchDestinations(q);
  }, 320);
}

async function searchDestinations(q){
  const resultsBox = byId("destinationResults");
  if (!resultsBox) return;

  const query = String(q || "").trim();
  if (query.length < 2) return;

  const requestSeq = ++navSearchRequestSeq;
  navSearchAbortController?.abort();
  navSearchAbortController = new AbortController();

  resultsBox.innerHTML =
    '<div class="destination-result"><div class="destination-result-icon">…</div><div><strong>Searching</strong><small>Finding destinations near you</small></div></div>';
  resultsBox.classList.remove("hidden");

  const params = new URLSearchParams({
    q:query,
    limit:"6",
    language: userLanguage || "en-GB"
  });

  if (currentPosition){
    params.set("lat", currentPosition.lat);
    params.set("lng", currentPosition.lng);
  }

  try{
    const r = await fetch(
      `/api/navigation/search?${params.toString()}`,
      {
        credentials:"include",
        signal:navSearchAbortController.signal
      }
    );

    const data = await r.json().catch(()=>({}));

    if (!r.ok){
      throw new Error(data.detail || "Search failed");
    }

    const currentQuery = byId("destinationSearchInput")?.value.trim() || "";
    if (requestSeq !== navSearchRequestSeq || currentQuery !== query){
      return;
    }

    navSearchResults = Array.isArray(data.results) ? data.results : [];
    renderDestinationResults();
  }catch(err){
    if (err?.name === "AbortError") return;
    if (requestSeq !== navSearchRequestSeq) return;

    navSearchResults = [];
    resultsBox.innerHTML =
      `<div class="destination-result"><div class="destination-result-icon">!</div><div><strong>Search unavailable</strong><small>${esc(err.message || "Please try again")}</small></div></div>`;
  }finally{
    if (requestSeq === navSearchRequestSeq){
      navSearchAbortController = null;
    }
  }
}

function renderDestinationResults(){
  const box = byId("destinationResults");
  if (!box) return;

  if (navSearchResults.length === 0){
    box.innerHTML =
      '<div class="destination-result"><div class="destination-result-icon">⌕</div><div><strong>No results</strong><small>Try a street, city or place name</small></div></div>';
    box.classList.remove("hidden");
    return;
  }

  box.innerHTML = navSearchResults.map((item,index)=>{
    const saved = favoriteDestinations.some(x=>sameDestination(x,item));
    return `
      <div class="destination-result">
        <button class="destination-result-icon" onclick="chooseDestinationResult(${index})">⌖</button>
        <button class="destination-result-main" onclick="chooseDestinationResult(${index})" style="background:transparent;color:inherit;text-align:left;padding:0;border-radius:0">
          <strong>${esc(item.name)}</strong>
          <small>${esc(item.address || "")}</small>
        </button>
        <button
          class="destination-result-save ${saved ? "saved" : ""}"
          onclick="toggleFavoriteSearchResult(event,${index})"
          title="Save destination"
        >${saved ? "★" : "☆"}</button>
      </div>
    `;
  }).join("");

  box.classList.remove("hidden");
}

function chooseDestinationResult(index){
  unlockNavigationAudio();
  const item = navSearchResults[index];
  if (!item) return;

  navDestination = {
    name:item.name,
    address:item.address,
    lat:Number(item.lat),
    lng:Number(item.lng)
  };

  const input = byId("destinationSearchInput");
  if (input) input.value = item.name;

  byId("destinationResults")?.classList.add("hidden");
  byId("destinationQuickList")?.classList.add("hidden");
  byId("clearDestinationBtn")?.classList.remove("hidden");
  rememberRecentDestination(navDestination);
  renderDestinationMarker();
  updateDestinationActionButton();
}

function clearDestinationSearch(){
  navSearchAbortController?.abort();
  navSearchAbortController = null;
  navSearchRequestSeq++;

  const input = byId("destinationSearchInput");
  if (input) input.value = "";
  navSearchResults = [];

  if (navigationActive){
    stopNavigation();
  }else{
    navDestination = null;
    clearDestinationMarker();
    updateDestinationActionButton();
  }

  byId("destinationResults")?.classList.add("hidden");
  byId("destinationQuickList")?.classList.add("hidden");
  byId("clearDestinationBtn")?.classList.add("hidden");
}

async function startNavigation(){
  if (!navDestination){
    focusDestinationSearch();
    return;
  }

  if (!currentPosition){
    setGpsBadge("Waiting for GPS to start route…", false);
    startGpsWatch();
    return;
  }

  await calculateNavigationRoute(false);
}

async function calculateNavigationRoute(isReroute=false){
  if (!currentPosition || !navDestination || navRequestInFlight){
    return;
  }

  navRequestInFlight = true;

  const search = byId("destinationSearchInput");
  search?.closest(".destination-search")?.classList.add("navigation-loading");

  try{
    const r = await fetch("/api/navigation/route", {
      method:"POST",
      credentials:"include",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        origin_lat:currentPosition.lat,
        origin_lng:currentPosition.lng,
        destination_lat:navDestination.lat,
        destination_lng:navDestination.lng,
        destination_name:navDestination.name,
        language:userLanguage || "en-GB",
        travel_mode:navigationMode
      })
    });

    const data = await r.json().catch(()=>({}));
    if (!r.ok){
      throw new Error(data.detail || "Could not calculate route");
    }

    applyNavigationRoute(data, isReroute);
  }catch(err){
    const card = byId("navigationCard");
    if (card){
      card.classList.remove("hidden");
      byId("navManeuverIcon").textContent = "!";
      byId("navInstruction").textContent = "Route unavailable";
      byId("navInstructionDistance").textContent = "";
      byId("navDestinationName").textContent =
        err.message || "Please try again";
    }
  }finally{
    navRequestInFlight = false;
    search?.closest(".destination-search")?.classList.remove("navigation-loading");
  }
}

function applyNavigationRoute(data, isReroute=false){
  navRoute = data;
  if (["car","pedestrian","bicycle"].includes(data.travelMode)) navigationMode = data.travelMode;
  safeLocalSet("roadpulse_nav_mode", navigationMode);
  navRoutePoints = normalizeRoutePoints(data.points,currentPosition);
  if (navRoutePoints.length < 2){
    throw new Error("Route provider returned invalid geometry");
  }
  navInstructions = data.instructions || [];
  navCurrentInstructionIndex = 0;
  navLastProgressIndex = 0;
  navInstructionAnnouncements.clear();
  navigationActive = true;
  navFollowMode = true;
  updateDestinationActionButton();
  navBaseSummary = data.summary || {};
  navLastRerouteAt = Date.now();
  navLastTrafficRefreshAt = Date.now();

  document.body.classList.add("navigation-active");

  if (navRouteLayer && map) map.removeLayer(navRouteLayer);
  if (navRouteOutlineLayer && map) map.removeLayer(navRouteOutlineLayer);

  const routeStyle = navigationMode === "pedestrian"
    ? {color:"#006cff", weight:9, dashArray:null}
    : navigationMode === "bicycle"
      ? {color:"#009fbd", weight:9, dashArray:"14 7"}
      : {color:"#5b2aef", weight:9, dashArray:null};

  navRouteOutlineLayer = L.polyline(navRoutePoints, {
    pane:"route",
    color:"#ffffff",
    weight:routeStyle.weight + 8,
    opacity:.98,
    lineJoin:"round",
    lineCap:"round",
    dashArray:routeStyle.dashArray
  }).addTo(map);

  navRouteLayer = L.polyline(navRoutePoints, {
    pane:"route",
    color:routeStyle.color,
    weight:routeStyle.weight,
    opacity:1,
    lineJoin:"round",
    lineCap:"round",
    dashArray:routeStyle.dashArray
  }).addTo(map);

  requestAnimationFrame(()=>{
    try{ navRouteOutlineLayer?.redraw?.(); }catch(_){}
    try{ navRouteLayer?.redraw?.(); }catch(_){}
    try{ navRouteOutlineLayer?.bringToFront?.(); }catch(_){}
    try{ navRouteLayer?.bringToFront?.(); }catch(_){}
  });

  renderDestinationMarker();
  renderGpsPosition();
  updateTrafficClarity();

  if (!isReroute){
    try{
      map.fitBounds(navRouteLayer.getBounds(), {
        paddingTopLeft:[70,120],
        paddingBottomRight:[70,140],
        maxZoom:navigationMode === "pedestrian" ? 17 : 16
      });
    }catch(_){}
  }

  byId("navigationCard")?.classList.remove("hidden");
  byId("routeSummaryCard")?.classList.remove("hidden");
  byId("destinationResults")?.classList.add("hidden");
  byId("destinationQuickList")?.classList.add("hidden");

  updateNavigationModeUI();
  updateFollowButton();
  requestNavigationWakeLock();
  updateRouteSummary(data.summary || {});
  updateNavigationProgress();
  updateNavigationCamera(true);

  if (isReroute && voiceEnabledByUser && proximitySettings.voice){
    speakNavigationMessage(t("routeUpdated"));
  }
}

function normalizeRoutePoints(points,origin){
  if (!Array.isArray(points)) return [];

  const pairs = points
    .filter(point=>Array.isArray(point) && point.length >= 2)
    .map(point=>[Number(point[0]),Number(point[1])])
    .filter(point=>Number.isFinite(point[0]) && Number.isFinite(point[1]));

  if (pairs.length < 2) return [];

  const validLatLng = point=>
    point[0] >= -90 && point[0] <= 90 &&
    point[1] >= -180 && point[1] <= 180;

  const directValid = pairs.every(validLatLng);
  const swapped = pairs.map(point=>[point[1],point[0]]);
  const swappedValid = swapped.every(validLatLng);

  if (!directValid && swappedValid) return swapped;
  if (!directValid) return [];
  if (!swappedValid || !origin) return pairs;

  const originLat = Number(origin.lat);
  const originLng = Number(origin.lng);
  if (!Number.isFinite(originLat) || !Number.isFinite(originLng)) return pairs;

  const directDistance = haversineMeters(originLat,originLng,pairs[0][0],pairs[0][1]);
  const swappedDistance = haversineMeters(originLat,originLng,swapped[0][0],swapped[0][1]);

  // Route geometry should start near the requested origin. Swap only when the
  // evidence is overwhelming, avoiding accidental flips near 0° latitude.
  if (swappedDistance < 5000 && swappedDistance * 5 < directDistance){
    return swapped;
  }

  return pairs;
}

function updateRouteSummary(summary){
  byId("routeEta").textContent =
    formatArrivalTime(summary.arrivalTime);

  byId("routeDuration").textContent =
    formatDuration(summary.travelTimeSeconds || 0);

  byId("routeDistance").textContent =
    formatRouteDistance(summary.lengthMeters || 0);

  const delay = Number(summary.trafficDelaySeconds || 0);
  byId("routeDelay").textContent = (navigationMode === "pedestrian" || navigationMode === "bicycle")
    ? "—"
    : (delay > 30 ? `+${formatDuration(delay)}` : "None");
  updateNavigationModeUI();
}

function formatArrivalTime(value){
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleTimeString([], {
    hour:"2-digit",
    minute:"2-digit"
  });
}

function formatDuration(seconds){
  const mins = Math.max(0, Math.round(Number(seconds || 0) / 60));
  if (mins < 60) return `${mins} min`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

function formatRouteDistance(meters){
  const m = Number(meters || 0);
  if (m < 1000) return `${Math.round(m)} m`;
  return `${(m/1000).toFixed(m < 10000 ? 1 : 0)} km`;
}

function stopNavigation(clearDestination=true){
  stopNavigationHeadingUp(true);
  closeWalkingLiveView();
  navigationActive = false;
  navRoute = null;
  navRoutePoints = [];
  navInstructions = [];
  navCurrentInstructionIndex = 0;
  navLastProgressIndex = 0;
  navInstructionAnnouncements.clear();
  navBaseSummary = null;
  navFollowMode = true;
  releaseNavigationWakeLock();

  document.body.classList.remove("navigation-active");
  document.body.classList.remove("walking-navigation");
  document.body.classList.remove("cycling-navigation");
  document.body.classList.remove("car-navigation");

  if (navRouteLayer && map) map.removeLayer(navRouteLayer);
  if (navRouteOutlineLayer && map) map.removeLayer(navRouteOutlineLayer);
  navRouteLayer = null;
  navRouteOutlineLayer = null;

  byId("navigationCard")?.classList.add("hidden");
  byId("routeSummaryCard")?.classList.add("hidden");

  if (clearDestination){
    navDestination = null;
    clearDestinationMarker();
    const input = byId("destinationSearchInput");
    if (input) input.value = "";
    byId("clearDestinationBtn")?.classList.add("hidden");
  }else{
    renderDestinationMarker();
  }

  updateTrafficClarity();
  renderGpsPosition();
  updateDestinationActionButton();
  updateFollowButton();
}

async function manualReroute(){
  if (!navigationActive || !navDestination) return;
  navLastRerouteAt = 0;
  await calculateNavigationRoute(true);
}

function updateNavigationProgress(){
  if (
    !navigationActive ||
    !currentPosition ||
    navRoutePoints.length < 2
  ){
    return;
  }

  const nearest = nearestRoutePoint(
    currentPosition.lat,
    currentPosition.lng
  );

  if (!nearest) return;

  navLastProgressIndex = Math.max(
    navLastProgressIndex,
    nearest.index
  );

  updateRemainingRouteSummary();

  const nextIndex = findNextInstructionIndex(navLastProgressIndex);
  if (nextIndex >= 0){
    navCurrentInstructionIndex = nextIndex;
    const instruction = navInstructions[nextIndex];
    renderNavigationInstruction(instruction);
    syncWalkingLiveViewInstruction();
    maybeSpeakTurnInstruction(instruction, nextIndex);
  }

  const now = Date.now();
  const speed = Number(currentPosition.speed || 0);

  const walking = navigationMode === "pedestrian";
  const cycling = navigationMode === "bicycle";
  const offRouteDistance = walking ? 45 : (cycling ? 65 : 120);
  const gpsAccuracyAllowance = Math.min(
    150,
    Math.max(0, Number(currentPosition.accuracy || 0)) * 1.15
  );
  const effectiveOffRouteDistance = offRouteDistance + gpsAccuracyAllowance;
  const movementThreshold = walking ? 0.35 : (cycling ? 1.0 : 2.5);
  const rerouteCooldown = walking ? 20000 : (cycling ? 25000 : 35000);

  // Include GPS uncertainty so weak mobile fixes do not cause false reroutes.
  if (
    nearest.distanceM > effectiveOffRouteDistance &&
    speed > movementThreshold &&
    now - navLastRerouteAt > rerouteCooldown
  ){
    calculateNavigationRoute(true);
    return;
  }

  // Live traffic refresh is useful for driving; pedestrian routes don't need it.
  if (
    !walking && !cycling &&
    speed > 2.5 &&
    now - navLastTrafficRefreshAt > 180000
  ){
    navLastTrafficRefreshAt = now;
    calculateNavigationRoute(true);
  }

  // Arrival detection.
  const destinationDistance = haversineMeters(
    currentPosition.lat,
    currentPosition.lng,
    navDestination.lat,
    navDestination.lng
  );

  const arrivalThreshold = navigationMode === "pedestrian"
    ? 22
    : (navigationMode === "bicycle" ? 25 : 35);
  const arrivalAccuracyOk = Number(currentPosition.accuracy || 9999) <= 80;

  if (destinationDistance < arrivalThreshold && arrivalAccuracyOk){
    byId("navManeuverIcon").textContent = "✓";
    byId("navInstruction").textContent = t("arrived");
    byId("navInstructionDistance").textContent = "";
    byId("navDestinationName").textContent = navDestination.name;

    const arrivalKey = "arrival";
    if (
      !navInstructionAnnouncements.has(arrivalKey) &&
      voiceEnabledByUser &&
      proximitySettings.voice
    ){
      navInstructionAnnouncements.add(arrivalKey);
      speakNavigationMessage(t("arrived"));
    }
  }
}

function projectPointToRouteSegment(lat,lng,a,b,segmentIndex=0){
  if (
    !Array.isArray(a) || !Array.isArray(b) ||
    !Number.isFinite(Number(a[0])) || !Number.isFinite(Number(a[1])) ||
    !Number.isFinite(Number(b[0])) || !Number.isFinite(Number(b[1]))
  ){
    return null;
  }

  const originLatRad = Number(lat) * Math.PI / 180;
  const metersPerLatDegree = 111132;
  const metersPerLngDegree = Math.max(1,111320 * Math.cos(originLatRad));
  const ax = (Number(a[1]) - Number(lng)) * metersPerLngDegree;
  const ay = (Number(a[0]) - Number(lat)) * metersPerLatDegree;
  const bx = (Number(b[1]) - Number(lng)) * metersPerLngDegree;
  const by = (Number(b[0]) - Number(lat)) * metersPerLatDegree;
  const dx = bx - ax;
  const dy = by - ay;
  const lengthSquared = dx * dx + dy * dy;
  const t = lengthSquared > 0
    ? Math.max(0,Math.min(1,-(ax * dx + ay * dy) / lengthSquared))
    : 0;
  const projectedX = ax + dx * t;
  const projectedY = ay + dy * t;

  return {
    lat:Number(lat) + projectedY / metersPerLatDegree,
    lng:Number(lng) + projectedX / metersPerLngDegree,
    distanceM:Math.hypot(projectedX,projectedY),
    segmentIndex,
    t,
    bearing:bearingDegrees(Number(a[0]),Number(a[1]),Number(b[0]),Number(b[1]))
  };
}

function findNearestRouteProjection(points,lat,lng,startSegment=0,endSegment=null){
  if (!Array.isArray(points) || points.length < 2) return null;

  const segmentCount = points.length - 1;
  const start = Math.max(0,Math.min(segmentCount - 1,Number(startSegment) || 0));
  const end = Math.max(start + 1,Math.min(segmentCount,endSegment == null ? segmentCount : Number(endSegment)));
  let best = null;

  for (let i=start; i<end; i++){
    const candidate = projectPointToRouteSegment(lat,lng,points[i],points[i+1],i);
    if (candidate && (!best || candidate.distanceM < best.distanceM)){
      best = candidate;
    }
  }

  return best;
}

function nearestRouteProjection(lat,lng){
  if (!Array.isArray(navRoutePoints) || navRoutePoints.length < 2) return null;

  if (navLastProgressIndex > 0 && navRoutePoints.length > 350){
    const start = Math.max(0,navLastProgressIndex - 40);
    const end = Math.min(navRoutePoints.length - 1,navLastProgressIndex + 320);
    const local = findNearestRouteProjection(navRoutePoints,lat,lng,start,end);
    if (local && local.distanceM <= 500) return local;
  }

  return findNearestRouteProjection(navRoutePoints,lat,lng);
}

function nearestRoutePoint(lat,lng){
  const projection = nearestRouteProjection(lat,lng);
  if (!projection) return null;
  return {
    ...projection,
    index:projection.t >= 0.5
      ? projection.segmentIndex + 1
      : projection.segmentIndex
  };
}

function getNavigationDisplayPosition(position=currentPosition){
  if (!position) return null;

  const fallback = {
    ...position,
    snapped:false,
    snapDistanceM:null,
    routeSegmentIndex:null
  };

  if (
    !navigationActive ||
    !Array.isArray(navRoutePoints) ||
    navRoutePoints.length < 2 ||
    Number(position.accuracy || 9999) > 150
  ){
    return fallback;
  }

  const projection = nearestRouteProjection(position.lat,position.lng);
  if (!projection) return fallback;

  const snapLimit = routeSnapDistanceLimit(navigationMode,position.accuracy);
  if (projection.distanceM > snapLimit) return fallback;

  const speed = Math.max(0,Number(position.speed || 0));
  const gpsHeading = nullableFiniteNumber(position.heading);
  const headingDifference = gpsHeading == null
    ? 0
    : angleDifference(gpsHeading,projection.bearing);

  // Do not jump to a nearby parallel/opposite carriageway when the device has
  // a reliable direction of travel that conflicts with the route direction.
  if (speed >= 2.5 && gpsHeading != null && headingDifference > 100){
    return fallback;
  }

  const matchedHeading = speed >= 1.0 && (gpsHeading == null || headingDifference <= 75)
    ? projection.bearing
    : gpsHeading;

  return {
    ...position,
    lat:projection.lat,
    lng:projection.lng,
    heading:matchedHeading,
    headingSource:matchedHeading === projection.bearing ? "route" : position.headingSource,
    snapped:true,
    snapDistanceM:projection.distanceM,
    routeSegmentIndex:projection.segmentIndex
  };
}

function findNextInstructionIndex(progressIndex){
  if (navInstructions.length === 0) return -1;

  for (let i=0; i<navInstructions.length; i++){
    const instruction = navInstructions[i];
    if (Number(instruction.pointIndex || 0) >= progressIndex){
      return i;
    }
  }

  return navInstructions.length - 1;
}

function renderNavigationInstruction(instruction){
  if (!instruction) return;

  const distance = (
    instruction.lat != null &&
    instruction.lng != null
  )
    ? haversineMeters(
        currentPosition.lat,
        currentPosition.lng,
        Number(instruction.lat),
        Number(instruction.lng)
      )
    : 0;

  byId("navManeuverIcon").textContent =
    maneuverIcon(instruction.maneuver);

  byId("navInstruction").textContent =
    instruction.message || "Continue";

  byId("navInstructionDistance").textContent =
    distance > 0 ? formatDistance(distance) : "";

  const roadName = getInstructionRoadName(instruction);
  const nextRoad = byId("navNextRoad");
  if (nextRoad){
    nextRoad.textContent = roadName || "—";
  }

  byId("navDestinationName").textContent =
    navDestination?.name || t("destination");
}

function maneuverIcon(maneuver){
  const icons = {
    TURN_LEFT:"↰",
    SHARP_LEFT:"↶",
    BEAR_LEFT:"↖",
    KEEP_LEFT:"↖",
    TURN_RIGHT:"↱",
    SHARP_RIGHT:"↷",
    BEAR_RIGHT:"↗",
    KEEP_RIGHT:"↗",
    STRAIGHT:"↑",
    FOLLOW:"↑",
    ENTER_MOTORWAY:"⇧",
    ENTER_FREEWAY:"⇧",
    ENTER_HIGHWAY:"⇧",
    ENTRANCE_RAMP:"↗",
    TAKE_EXIT:"↗",
    MOTORWAY_EXIT_LEFT:"↖",
    MOTORWAY_EXIT_RIGHT:"↗",
    MAKE_UTURN:"↶",
    TRY_MAKE_UTURN:"↶",
    ROUNDABOUT_LEFT:"⟲",
    ROUNDABOUT_RIGHT:"⟳",
    ROUNDABOUT_CROSS:"⟳",
    ARRIVE:"✓",
    ARRIVE_LEFT:"✓",
    ARRIVE_RIGHT:"✓",
    DEPART:"↑"
  };
  return icons[maneuver] || "↑";
}


function getInstructionRoadName(instruction){
  if (!instruction) return "";

  if (instruction.street){
    return String(instruction.street);
  }

  if (Array.isArray(instruction.roadNumbers) && instruction.roadNumbers.length){
    return instruction.roadNumbers.join(" / ");
  }

  if (instruction.exitNumber){
    return `Exit ${instruction.exitNumber}`;
  }

  return "";
}

function getNavigationAudioContext(){
  if (navAudioContext) return navAudioContext;

  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return null;

  try{
    navAudioContext = new AudioCtx();
  }catch(_){
    return null;
  }

  return navAudioContext;
}

async function unlockNavigationAudio(){
  const ctx = getNavigationAudioContext();
  if (!ctx) return;

  try{
    if (ctx.state === "suspended"){
      await ctx.resume();
    }
  }catch(_){}
}

function playNavigationChime(kind="normal"){
  const ctx = getNavigationAudioContext();
  if (!ctx || ctx.state !== "running") return;

  const now = ctx.currentTime;
  const notes = kind === "urgent"
    ? [{f:880,t:0,d:.10},{f:1175,t:.13,d:.13}]
    : [{f:660,t:0,d:.10},{f:880,t:.13,d:.12}];

  for (const note of notes){
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(note.f, now + note.t);

    gain.gain.setValueAtTime(0.0001, now + note.t);
    gain.gain.exponentialRampToValueAtTime(0.12, now + note.t + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + note.t + note.d);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now + note.t);
    osc.stop(now + note.t + note.d + 0.03);
  }
}

function navigationVoiceMessage(instruction, threshold){
  const base = instruction?.message || "Continue";
  const road = getInstructionRoadName(instruction);

  // TomTom's localized instruction often already contains the road.
  // Only append it if the road name isn't already present.
  let message = base;
  if (
    road &&
    !String(base).toLowerCase().includes(String(road).toLowerCase())
  ){
    message = `${base}. ${t("nextRoad")}: ${road}.`;
  }

  if (threshold <= (navigationMode === "pedestrian" ? 25 : (navigationMode === "bicycle" ? 35 : 70))){
    return message;
  }

  return `${localizedInMeters(threshold)}, ${message}`;
}

function maybeSpeakTurnInstruction(instruction,index){
  if (
    !instruction ||
    !voiceEnabledByUser ||
    !proximitySettings.voice ||
    instruction.lat == null ||
    instruction.lng == null
  ){
    return;
  }

  const distance = haversineMeters(
    currentPosition.lat,
    currentPosition.lng,
    Number(instruction.lat),
    Number(instruction.lng)
  );

  let threshold = null;
  if (navigationMode === "pedestrian"){
    if (distance <= 25) threshold = 25;
    else if (distance <= 80) threshold = 80;
    else if (distance <= 200) threshold = 200;
  }else if (navigationMode === "bicycle"){
    if (distance <= 35) threshold = 35;
    else if (distance <= 120) threshold = 120;
    else if (distance <= 350) threshold = 350;
  }else{
    if (distance <= 70) threshold = 70;
    else if (distance <= 250) threshold = 250;
    else if (distance <= 700) threshold = 700;
  }

  if (threshold == null) return;

  const key = `${index}:${threshold}`;
  if (navInstructionAnnouncements.has(key)) return;

  navInstructionAnnouncements.add(key);

  // Chime before every new road-change/turn announcement.
  playNavigationChime(threshold <= (navigationMode === "pedestrian" ? 25 : (navigationMode === "bicycle" ? 35 : 70)) ? "urgent" : "normal");

  const message = navigationVoiceMessage(instruction,threshold);
  setTimeout(()=>{
    speakNavigationMessage(message);
  }, 330);
}

function refreshNavigationVoices(){
  if (!("speechSynthesis" in window)) return [];
  navSpeechVoices = window.speechSynthesis.getVoices() || [];
  return navSpeechVoices;
}

function chooseNavigationVoice(language){
  const voices = refreshNavigationVoices();
  if (!voices.length) return null;

  const lang = String(language || "en-GB").toLowerCase();
  const primary = lang.split("-")[0];

  const candidates = voices.filter(v=>{
    const vl = String(v.lang || "").toLowerCase();
    return vl === lang || vl.startsWith(primary + "-") || vl === primary;
  });

  const local = candidates.find(v=>v.localService);
  return local || candidates[0] || voices.find(v=>v.default) || voices[0] || null;
}

function speakNavigationMessage(message){
  if (
    !message ||
    !voiceEnabledByUser ||
    !proximitySettings.voice ||
    !("speechSynthesis" in window)
  ){
    return;
  }

  const u = new SpeechSynthesisUtterance(message);
  u.lang = userLanguage || "en-GB";
  u.rate = 0.94;
  u.pitch = 1.0;
  u.volume = 1.0;

  const preferred = chooseNavigationVoice(u.lang);
  if (preferred) u.voice = preferred;

  // Cancel stale instructions so the driver hears the newest command clearly.
  window.speechSynthesis.cancel();
  window.speechSynthesis.resume();
  window.speechSynthesis.speak(u);
}

if ("speechSynthesis" in window){
  refreshNavigationVoices();
  window.speechSynthesis.addEventListener?.("voiceschanged", refreshNavigationVoices);
}

function syncWalkingLiveViewInstruction(){
  const instruction = byId("navInstruction")?.textContent || "Continue";
  const distance = byId("navInstructionDistance")?.textContent || "";
  const road = byId("navNextRoad")?.textContent || "";
  const icon = byId("navManeuverIcon")?.textContent || "↑";

  const title = byId("liveViewInstruction");
  const meta = byId("liveViewInstructionMeta");
  const arrow = byId("liveViewArrow");

  if (title) title.textContent = instruction;
  if (meta){
    meta.textContent = [distance, road && road !== "—" ? road : ""].filter(Boolean).join(" • ");
  }
  if (arrow) arrow.textContent = icon;
}

async function openWalkingLiveView(){
  if (navigationMode !== "pedestrian"){
    setNavigationMode("pedestrian");
  }

  const sheet = byId("walkingLiveViewSheet");
  const video = byId("walkingLiveViewVideo");
  const errorBox = byId("walkingLiveViewError");
  if (!sheet || !video) return;

  sheet.classList.remove("hidden");
  syncWalkingLiveViewInstruction();

  if (errorBox){
    errorBox.textContent = "";
    errorBox.classList.add("hidden");
  }

  if (!navigator.mediaDevices?.getUserMedia){
    if (errorBox){
      errorBox.textContent = "Camera Live View is not supported by this browser.";
      errorBox.classList.remove("hidden");
    }
    return;
  }

  try{
    closeWalkingLiveView(false);
    sheet.classList.remove("hidden");

    walkingLiveViewStream = await navigator.mediaDevices.getUserMedia({
      video:{facingMode:{ideal:"environment"}},
      audio:false
    });
    video.srcObject = walkingLiveViewStream;
    await video.play().catch(()=>{});
  }catch(err){
    if (errorBox){
      errorBox.textContent = "Camera permission is needed for Walking Live View.";
      errorBox.classList.remove("hidden");
    }
  }
}

function closeWalkingLiveView(hide=true){
  if (walkingLiveViewStream){
    walkingLiveViewStream.getTracks().forEach(track=>track.stop());
    walkingLiveViewStream = null;
  }

  const video = byId("walkingLiveViewVideo");
  if (video) video.srcObject = null;

  if (hide){
    byId("walkingLiveViewSheet")?.classList.add("hidden");
  }
}



function rememberRecentDestination(destination){
  if (!destination) return;

  recentDestinations = [
    destination,
    ...recentDestinations.filter(x=>!sameDestination(x,destination))
  ].slice(0,6);

  saveStoredDestinations("roadpulse_recent", recentDestinations);
}

function toggleFavoriteSearchResult(event,index){
  event?.stopPropagation();
  const item = navSearchResults[index];
  if (!item) return;

  const destination = {
    name:item.name,
    address:item.address,
    lat:Number(item.lat),
    lng:Number(item.lng)
  };

  toggleFavoriteDestination(destination);
  renderDestinationResults();
}

function toggleFavoriteDestination(destination){
  const existingIndex =
    favoriteDestinations.findIndex(x=>sameDestination(x,destination));

  if (existingIndex >= 0){
    favoriteDestinations.splice(existingIndex,1);
  }else{
    favoriteDestinations.unshift(destination);
  }

  favoriteDestinations = favoriteDestinations.slice(0,10);
  saveStoredDestinations("roadpulse_favorites", favoriteDestinations);
  renderDestinationQuickList();
}

function saveCurrentDestination(){
  if (!navDestination) return;

  const saved =
    favoriteDestinations.some(x=>sameDestination(x,navDestination));

  toggleFavoriteDestination(navDestination);

  if (
    voiceEnabledByUser &&
    proximitySettings.voice
  ){
    speakNavigationMessage(
      saved
        ? "Destination removed from saved places."
        : "Destination saved."
    );
  }
}

function renderDestinationQuickList(){
  const box = byId("destinationQuickList");
  if (!box) return;

  const items = [];
  favoriteDestinations.slice(0,5).forEach(item=>{
    items.push({...item,_kind:"favorite"});
  });

  recentDestinations
    .filter(item=>!favoriteDestinations.some(x=>sameDestination(x,item)))
    .slice(0,5)
    .forEach(item=>{
      items.push({...item,_kind:"recent"});
    });

  if (items.length === 0){
    box.classList.add("hidden");
    return;
  }

  box.innerHTML = items.map((item,index)=>`
    <button
      class="quick-destination-chip ${item._kind === "favorite" ? "favorite" : ""}"
      onclick="chooseQuickDestination(${index})"
      title="${esc(item.address || item.name)}"
    >
      ${item._kind === "favorite" ? "★" : "↺"}
      ${esc(item.name)}
    </button>
  `).join("");

  box.dataset.items = JSON.stringify(items);
  box.classList.remove("hidden");
}

function chooseQuickDestination(index){
  unlockNavigationAudio();
  const box = byId("destinationQuickList");
  if (!box) return;

  let items = [];
  try{ items = JSON.parse(box.dataset.items || "[]"); }catch(_){}

  const item = items[index];
  if (!item) return;

  navDestination = {
    name:item.name,
    address:item.address,
    lat:Number(item.lat),
    lng:Number(item.lng)
  };

  const input = byId("destinationSearchInput");
  if (input) input.value = navDestination.name;

  box.classList.add("hidden");
  byId("clearDestinationBtn")?.classList.remove("hidden");
  rememberRecentDestination(navDestination);
  renderDestinationMarker();
  updateDestinationActionButton();
}

function enableRouteFollow(){
  navFollowMode = true;
  updateFollowButton();
  updateNavigationCamera(true);
}

function showRouteOverview(){
  stopNavigationHeadingUp(true);
  navFollowMode = false;
  updateFollowButton();

  if (navRouteLayer && map){
    try{
      map.fitBounds(navRouteLayer.getBounds(),{
        padding:[70,70],
        maxZoom:16
      });
    }catch(_){}
  }
}

function updateFollowButton(){
  const btn = byId("followRouteBtn");
  if (btn){
    btn.classList.toggle("active", navFollowMode);
    btn.textContent = navFollowMode ? `◎ ${t("follow")}` : `◎ ${t("followOff")}`;
  }

  const recenter = byId("mapRecenterBtn");
  if (recenter){
    recenter.classList.toggle("hidden", !navigationActive || navFollowMode);
  }

  updateRouteControlLabels();
}

async function requestNavigationWakeLock(){
  if (
    !navigationActive &&
    !navDestination
  ){
    return;
  }

  if (
    !("wakeLock" in navigator) ||
    document.visibilityState !== "visible"
  ){
    return;
  }

  try{
    if (!navWakeLock){
      navWakeLock = await navigator.wakeLock.request("screen");
      navWakeLock.addEventListener("release",()=>{
        navWakeLock = null;
      });
    }
  }catch(_){}
}

async function releaseNavigationWakeLock(){
  try{
    if (navWakeLock){
      await navWakeLock.release();
    }
  }catch(_){}
  navWakeLock = null;
}

function calculateRemainingRouteMeters(){
  if (
    !navRoutePoints ||
    navRoutePoints.length < 2
  ){
    return 0;
  }

  let total = 0;
  let start = Math.max(
    0,
    Math.min(navLastProgressIndex,navRoutePoints.length-1)
  );

  if (currentPosition){
    const projection = nearestRouteProjection(currentPosition.lat,currentPosition.lng);
    const projectedNextIndex = projection ? projection.segmentIndex + 1 : -1;

    if (
      projection &&
      projection.distanceM <= 500 &&
      projectedNextIndex >= start &&
      projectedNextIndex < navRoutePoints.length
    ){
      start = projectedNextIndex;
      const next = navRoutePoints[start];
      total += haversineMeters(
        projection.lat,
        projection.lng,
        next[0],
        next[1]
      );
    }else{
      const p = navRoutePoints[start];
      total += haversineMeters(
        currentPosition.lat,
        currentPosition.lng,
        p[0],
        p[1]
      );
    }
  }

  for (let i=start; i<navRoutePoints.length-1; i++){
    const a = navRoutePoints[i];
    const b = navRoutePoints[i+1];
    total += haversineMeters(a[0],a[1],b[0],b[1]);
  }

  return total;
}

function updateRemainingRouteSummary(){
  if (!navigationActive || !navBaseSummary) return;

  const remainingMeters = calculateRemainingRouteMeters();
  const totalMeters = Number(navBaseSummary.lengthMeters || 0);
  const totalSeconds = Number(navBaseSummary.travelTimeSeconds || 0);
  const totalDelay = Number(navBaseSummary.trafficDelaySeconds || 0);

  const ratio =
    totalMeters > 0
      ? Math.max(0,Math.min(1,remainingMeters/totalMeters))
      : 1;

  const remainingSeconds = Math.round(totalSeconds * ratio);
  const remainingDelay = Math.round(totalDelay * ratio);

  byId("routeDistance").textContent =
    formatRouteDistance(remainingMeters);

  byId("routeDuration").textContent =
    formatDuration(remainingSeconds);

  byId("routeDelay").textContent = (navigationMode === "pedestrian" || navigationMode === "bicycle")
    ? "—"
    : (remainingDelay > 30 ? `+${formatDuration(remainingDelay)}` : "None");

  const arrival = new Date(Date.now() + remainingSeconds*1000);
  byId("routeEta").textContent =
    arrival.toLocaleTimeString([],{
      hour:"2-digit",
      minute:"2-digit"
    });
}

function buildProximityTargets(data){
  const targets = [];

  (data.reports || []).forEach(item=>{
    if (item.lat == null || item.lng == null) return;

    // Camera reports are treated as camera alerts for compliance.
    if (item.type === "camera" && !cameraVoiceAlertsAllowed()) return;

    targets.push({
      id:`report:${item.id}`,
      type:item.type,
      lat:Number(item.lat),
      lng:Number(item.lng),
      location:item.location || "Verified community report",
      source:"community"
    });
  });

  if (cameraVoiceAlertsAllowed()){
    (data.cameras || []).forEach(item=>{
      if (item.lat == null || item.lng == null) return;
      targets.push({
        id:`camera:${item.id}`,
        type:"camera",
        lat:Number(item.lat),
        lng:Number(item.lng),
        location:item.location || "Camera",
        source:"camera"
      });
    });
  }

  return targets;
}

function cameraVoiceAlertsAllowed(){
  const country = String(proximitySettings.defaultCountry || "").toUpperCase();
  const mode = proximitySettings.cameraWarningMode;

  // Compliance safeguard: in Germany, country-compliance mode suppresses
  // automated camera proximity voice alerts.
  if (mode === "country_compliance" && country === "DE"){
    return false;
  }
  return true;
}

function haversineMeters(lat1,lng1,lat2,lng2){
  const R = 6371000;
  const rad = d => d * Math.PI / 180;
  const p1 = rad(lat1);
  const p2 = rad(lat2);
  const dp = rad(lat2-lat1);
  const dl = rad(lng2-lng1);
  const a =
    Math.sin(dp/2) ** 2 +
    Math.cos(p1) * Math.cos(p2) * Math.sin(dl/2) ** 2;
  return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

function bearingDegrees(lat1,lng1,lat2,lng2){
  const rad = d => d * Math.PI / 180;
  const deg = r => r * 180 / Math.PI;
  const p1 = rad(lat1);
  const p2 = rad(lat2);
  const dl = rad(lng2-lng1);
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1)*Math.sin(p2) -
            Math.sin(p1)*Math.cos(p2)*Math.cos(dl);
  return (deg(Math.atan2(y,x)) + 360) % 360;
}

function angleDifference(a,b){
  return Math.abs(((a - b + 540) % 360) - 180);
}

function targetIsAhead(target){
  const heading = currentPosition?.heading;
  const speed = currentPosition?.speed;

  // At low speed or when heading is unavailable, use radius-only detection.
  if (heading == null || heading < 0 || speed == null || speed < 4.2){
    return true;
  }

  const bearing = bearingDegrees(
    currentPosition.lat,
    currentPosition.lng,
    target.lat,
    target.lng
  );

  // Roughly the forward 180-degree field.
  return angleDifference(heading, bearing) <= 90;
}

function evaluateProximityAlerts(){
  const card = byId("proximityAlertCard");
  const nearbyBadge = byId("nearbyBadge");

  if (!card || !currentPosition || !proximitySettings.enabled){
    if (card) card.classList.add("hidden");
    if (nearbyBadge) nearbyBadge.textContent = "Nearby: waiting GPS";
    currentProximityTarget = null;
    return;
  }

  let nearest = null;
  const now = Date.now();

  for (const target of proximityTargets){
    const dismissed = dismissedUntil.get(target.id) || 0;
    if (dismissed > now) continue;

    const distanceM = haversineMeters(
      currentPosition.lat,
      currentPosition.lng,
      target.lat,
      target.lng
    );

    if (distanceM > proximitySettings.maxDistanceM) continue;

    // Only apply "ahead of vehicle" filtering when actually moving.
    if (!targetIsAhead(target)) continue;

    if (!nearest || distanceM < nearest.distanceM){
      nearest = {...target, distanceM};
    }
  }

  if (!nearest){
    card.classList.add("hidden");
    if (nearbyBadge){
      nearbyBadge.textContent =
        `Nearby: none < ${Math.round(proximitySettings.maxDistanceM)}m`;
      nearbyBadge.classList.remove("good", "camera-ahead");
    }
    currentProximityTarget = null;
    return;
  }

  if (nearbyBadge){
    if (nearest.type === "camera"){
      nearbyBadge.textContent =
        `📷 Camera ahead ${formatCameraCountdownDistance(nearest.distanceM)}`;
      nearbyBadge.classList.add("camera-ahead");
    }else{
      nearbyBadge.textContent =
        `Nearby: ${nearest.type} ${formatDistance(nearest.distanceM)}`;
      nearbyBadge.classList.remove("camera-ahead");
    }
    nearbyBadge.classList.add("good");
  }

  currentProximityTarget = nearest;
  renderProximityAlert(nearest);
  maybeSpeakProximityAlert(nearest);
}

function renderProximityAlert(target){
  const card = byId("proximityAlertCard");
  if (!card) return;

  const style = reportStyle[target.type] || {emoji:"⚠️"};

  byId("proximityAlertIcon").textContent = style.emoji || "⚠️";
  byId("proximityAlertTitle").textContent = alertTitleForType(target.type);
  byId("proximityAlertDistance").textContent = formatDistance(target.distanceM);
  byId("proximityAlertLocation").textContent =
    target.location || "Verified nearby report";

  card.classList.remove("hidden");
  card.classList.toggle(
    "urgent",
    target.distanceM <= proximitySettings.urgentDistanceM
  );
  card.classList.toggle("camera-countdown", target.type === "camera");
}

function alertTitleForType(type){
  return localizedAlertTitle(type);
}

function formatDistance(meters){
  if (meters < 1000){
    return `${Math.max(10, Math.round(meters/10)*10)} m`;
  }
  return `${(meters/1000).toFixed(1)} km`;
}

function formatCameraCountdownDistance(meters){
  const d = Math.max(0, Number(meters || 0));
  if (d <= 100) return "100 m";
  if (d <= 200) return "200 m";
  if (d <= 300) return "300 m";
  if (d <= 400) return "400 m";
  if (d <= 500) return "500 m";
  return formatDistance(d);
}

function cameraCountdownMessage(distance){
  return `${localizedAlertTitle("camera")} ${localizedInMeters(distance)}.`;
}

function maybeSpeakCameraCountdown(target){
  if (target.type !== "camera") return false;

  // Keep the existing country-compliance safeguard for voice warnings.
  // Visual countdown still appears even when voice is restricted.
  if (!cameraVoiceAlertsAllowed()) return true;

  const distance = Number(target.distanceM || 0);
  let state = cameraCountdownState.get(target.id);

  // Reset after moving well away so the sequence works again next time.
  if (!state || distance > 650){
    state = {announced:[], lastDistance:distance};
  }

  // If GPS jumps backwards substantially, allow thresholds to re-arm.
  if (state.lastDistance != null && distance > state.lastDistance + 180){
    state.announced = state.announced.filter(step => step > distance);
  }

  const crossed = CAMERA_COUNTDOWN_STEPS.find(step =>
    distance <= step && !state.announced.includes(step)
  );

  if (crossed){
    state.announced.push(crossed);
    lastAlertedAt.set(target.id, Date.now());
    speakNavigationMessage(cameraCountdownMessage(crossed));
  }

  state.lastDistance = distance;
  cameraCountdownState.set(target.id, state);
  return true;
}

function voiceMessageForTarget(target){
  const d = Math.max(50, Math.round(target.distanceM/50)*50);
  return `${localizedAlertTitle(target.type)} ${localizedInMeters(d)}.`;
}

function maybeSpeakProximityAlert(target){
  if (
    !voiceEnabledByUser ||
    !proximitySettings.voice ||
    !("speechSynthesis" in window)
  ){
    return;
  }

  // Cameras use exact 500/400/300/200/100 metre countdown announcements.
  if (target.type === "camera"){
    maybeSpeakCameraCountdown(target);
    return;
  }

  const now = Date.now();
  const previous = lastAlertedAt.get(target.id) || 0;
  const cooldownMs = proximitySettings.cooldownS * 1000;

  if (now - previous < cooldownMs){
    return;
  }

  lastAlertedAt.set(target.id, now);
  speakNavigationMessage(voiceMessageForTarget(target));
}

function toggleVoiceAlerts(){
  unlockNavigationAudio();
  voiceEnabledByUser = !voiceEnabledByUser;
  safeLocalSet(
    "roadpulse_voice",
    voiceEnabledByUser ? "on" : "off"
  );

  if ("speechSynthesis" in window){
    window.speechSynthesis.cancel();

    // A user click helps browsers unlock speech output.
    if (voiceEnabledByUser && proximitySettings.voice){
      const u = new SpeechSynthesisUtterance(t("voiceEnabled"));
      u.lang = userLanguage || "en-GB";
      u.rate = 1.0;
      window.speechSynthesis.speak(u);
    }
  }

  updateVoiceBadge();
}

function updateVoiceBadge(){
  const badge = byId("voiceBadge");
  if (!badge) return;

  const effectiveOn =
    voiceEnabledByUser &&
    proximitySettings.voice;

  badge.textContent =
    effectiveOn
      ? `🔊 ${t("voiceOn")}`
      : `🔇 ${t("voiceOff")}`;

  badge.classList.toggle("off", !effectiveOn);
}

function dismissCurrentAlert(){
  if (!currentProximityTarget) return;

  // Hide this alert for 10 minutes on this device.
  dismissedUntil.set(
    currentProximityTarget.id,
    Date.now() + 10 * 60 * 1000
  );

  byId("proximityAlertCard")?.classList.add("hidden");
  currentProximityTarget = null;
}

function openReportSheet(){
  const el = byId("reportSheet");
  el.classList.remove("hidden");
  byId("reportMsg").classList.add("hidden");
}

function closeReportSheet(){
  byId("reportSheet").classList.add("hidden");
}

async function submitReport(type){
  const msg = byId("reportMsg");
  if (!msg) return;
  msg.classList.add("hidden");

  if (!currentPosition){
    msg.textContent = "GPS location is not ready yet. Allow location access and try again.";
    msg.classList.remove("hidden","error");
    msg.classList.add("error");
    startGpsWatch();
    return;
  }

  if (Number(currentPosition.accuracy || 9999) > 250){
    msg.textContent = `GPS is still weak (±${Math.round(currentPosition.accuracy)}m). Wait for a better fix before reporting.`;
    msg.classList.remove("hidden");
    msg.classList.add("error");
    return;
  }

  try{
    const r = await fetch("/api/reports", {
      method:"POST", credentials:"include",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({
        type,
        lat:currentPosition.lat,
        lng:currentPosition.lng,
        location:"User GPS report"
      })
    });

    const data = await r.json().catch(()=>({}));
    if (!r.ok){
      msg.textContent = data.detail || "Could not submit report.";
      msg.classList.remove("hidden");
      msg.classList.add("error");
      return;
    }

    msg.textContent = `${type} report sent for admin/community verification.`;
    msg.classList.remove("hidden","error");
    setTimeout(closeReportSheet, 1400);
  }catch(err){
    console.error("RoadPulse report submit failed:", err);
    msg.textContent = "Network unavailable. Report was not sent.";
    msg.classList.remove("hidden");
    msg.classList.add("error");
  }
}

function esc(v){
  return String(v ?? "").replace(/[&<>"']/g,s=>({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"
  })[s]);
}

/* ---------------- Admin ---------------- */

async function adminLogin(){
  const r = await fetch("/api/admin/login", {
    method:"POST", credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({password:byId("adminPassword").value})
  });

  if (!r.ok){
    const msg = byId("adminLoginMsg");
    msg.textContent = "Admin login failed.";
    msg.classList.remove("hidden");
    msg.classList.add("error");
    return;
  }

  byId("adminPassword").value = "";
  await loadAdmin();
}

async function adminLogout(){
  await fetch("/api/admin/logout", {method:"POST",credentials:"include"});
  location.hash = "";
  showOnly("userAuthView");
  routeByHash();
}

async function changeAdminPassword(){
  const current = byId("adminCurrentPassword")?.value || "";
  const next = byId("adminNewPassword")?.value || "";
  const confirm = byId("adminConfirmPassword")?.value || "";
  const msg = byId("adminPasswordChangeMsg");

  if (!msg) return;

  msg.classList.add("hidden");
  msg.classList.remove("error");

  if (next.length < 4){
    msg.textContent = "New PIN / password must be at least 4 characters.";
    msg.classList.remove("hidden");
    msg.classList.add("error");
    return;
  }

  if (next !== confirm){
    msg.textContent = "New PIN / password confirmation does not match.";
    msg.classList.remove("hidden");
    msg.classList.add("error");
    return;
  }

  const r = await fetch("/api/admin/change-password", {
    method:"POST",
    credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({
      current_password:current,
      new_password:next,
      confirm_password:confirm
    })
  });

  let data = {};
  try{ data = await r.json(); }catch(_){}

  if (!r.ok){
    msg.textContent = data.detail || "Could not change Admin PIN / password.";
    msg.classList.remove("hidden");
    msg.classList.add("error");
    return;
  }

  ["adminCurrentPassword","adminNewPassword","adminConfirmPassword"].forEach(id=>{
    const el = byId(id);
    if (el) el.value = "";
  });

  msg.textContent = "Admin PIN / password changed successfully.";
  msg.classList.remove("hidden");
}

async function loadAdmin(){
  const r = await fetch("/api/admin/dashboard", {credentials:"include"});
  if (!r.ok){
    showOnly("adminLoginView");
    return;
  }
  adminData = await r.json();
  showOnly("adminView");
  renderAdmin();
}

function renderAdmin(){
  const c = adminData.counts;
  byId("statIncidents").textContent = c.live_incidents;
  byId("statPending").textContent = c.pending_reports;
  byId("statCameras").textContent = c.camera_count;
  byId("statUsers").textContent = c.active_users;
  renderSettings();
  renderReports();
  renderCameras();
  renderUsers();
}

const settingDescriptions = {
  voice_alerts:"Master switch for supported voice alerts.",
  background_driving_mode:"Native driving mode may keep location active while driving.",
  community_reports:"Accept community reports.",
  camera_layer:"Show camera data where permitted.",
  traffic_layer:"Show live traffic when a provider is connected.",
  hazard_layer:"Show hazards/roadworks.",
  admin_2fa_required:"Require owner second factor.",
  default_country:"Fallback jurisdiction.",
  camera_warning_mode:"Apply country-by-country camera rules.",
  app_name:"Public display name.",
  proximity_alerts:"Show nearby verified road alerts.",
  alert_distance_m:"Maximum proximity alert distance.",
  urgent_alert_distance_m:"Urgent warning distance.",
  alert_repeat_cooldown_s:"Repeat voice alert cooldown.",
  voice_language:"Fallback browser speech language."
};

function boolRow(k,v){
  return `<div class="setting-row">
    <div class="meta"><strong>${esc(k.replaceAll("_"," "))}</strong>
    <small>${esc(settingDescriptions[k]||"")}</small></div>
    <div class="switch ${v?"on":""}" onclick="updateSetting('${k}',${!v})"></div>
  </div>`;
}
function scalarRow(k,v){
  return `<div class="setting-row">
    <div class="meta"><strong>${esc(k.replaceAll("_"," "))}</strong>
    <small>${esc(settingDescriptions[k]||"")}</small></div>
    <input style="max-width:260px" value="${esc(v)}" onchange="updateSetting('${k}',this.value)">
  </div>`;
}
function renderSettings(){
  const s=adminData.settings;
  const q=["voice_alerts","background_driving_mode","community_reports","camera_layer","traffic_layer","hazard_layer","proximity_alerts"];
  byId("quickSettings").innerHTML=q.map(k=>typeof s[k]==="boolean"?boolRow(k,s[k]):scalarRow(k,s[k])).join("");
  byId("allSettings").innerHTML=Object.entries(s).map(([k,v])=>typeof v==="boolean"?boolRow(k,v):scalarRow(k,v)).join("");
}
async function updateSetting(k,v){
  const r=await fetch(`/api/admin/settings/${encodeURIComponent(k)}`,{
    method:"PUT",credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({value:v})
  });
  if(r.ok){adminData.settings[k]=v;renderSettings()}
}

function renderReports(){
  const rows=adminData.reports.map(r=>`<tr>
    <td>${esc(r.type)}</td>
    <td>${esc(r.location)}</td>
    <td>${esc(r.reported_by)}</td>
    <td>${r.lat != null ? Number(r.lat).toFixed(5) : "—"}</td>
    <td>${r.lng != null ? Number(r.lng).toFixed(5) : "—"}</td>
    <td><span class="status ${esc(r.status)}">${esc(r.status)}</span></td>
    <td class="row-actions">
      <button onclick="setReportStatus(${r.id},'verified')">Verify</button>
      <button onclick="setReportStatus(${r.id},'pending')">Pending</button>
      <button class="reject" onclick="setReportStatus(${r.id},'rejected')">Reject</button>
    </td>
  </tr>`).join("");

  byId("reportsTable").innerHTML=`<table>
    <thead><tr><th>Type</th><th>Location</th><th>Reporter</th><th>Lat</th><th>Lng</th><th>Status</th><th>Actions</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

async function setReportStatus(id,status){
  const r=await fetch(`/api/admin/reports/${id}/status`,{
    method:"PUT",credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({status})
  });
  if(r.ok)await loadAdmin();
}

function renderCameras(){
  const rows=adminData.cameras.map(c=>`<tr>
    <td>${esc(c.camera_type)}</td><td>${esc(c.location)}</td>
    <td>${esc(c.speed_limit??"—")}</td><td>${esc(c.confidence)}%</td>
    <td>${c.lat != null ? Number(c.lat).toFixed(5) : "—"}</td>
    <td>${c.lng != null ? Number(c.lng).toFixed(5) : "—"}</td>
    <td>${c.enabled?"Enabled":"Disabled"}</td>
    <td><button class="reject" onclick="deleteCamera(${c.id})">Delete</button></td>
  </tr>`).join("");

  byId("cameraTable").innerHTML=`<table>
    <thead><tr><th>Type</th><th>Location</th><th>Limit</th><th>Confidence</th><th>Lat</th><th>Lng</th><th>State</th><th></th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

async function addCamera(){
  const payload={
    camera_type:byId("cameraType").value,
    location:byId("cameraLocation").value,
    speed_limit:byId("cameraSpeed").value?Number(byId("cameraSpeed").value):null,
    confidence:Number(byId("cameraConfidence").value||50),
    lat:byId("cameraLat").value?Number(byId("cameraLat").value):null,
    lng:byId("cameraLng").value?Number(byId("cameraLng").value):null,
    enabled:true
  };

  const r=await fetch("/api/admin/cameras",{
    method:"POST",credentials:"include",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(payload)
  });

  if(r.ok){
    ["cameraLocation","cameraSpeed","cameraLat","cameraLng"].forEach(id=>byId(id).value="");
    await loadAdmin();
  }
}

async function deleteCamera(id){
  const r=await fetch(`/api/admin/cameras/${id}`,{
    method:"DELETE",credentials:"include"
  });
  if(r.ok)await loadAdmin();
}

function renderUsers(){
  const staffRows=(adminData.users||[]).map(u=>`<tr>
    <td>${esc(u.name)}</td><td>${esc(u.role)}</td><td>${u.active?"Active":"Disabled"}</td>
  </tr>`).join("");
  byId("usersTable").innerHTML=`<table>
    <thead><tr><th>Name</th><th>Role</th><th>Status</th></tr></thead>
    <tbody>${staffRows}</tbody>
  </table>`;

  const appRows=(adminData.app_users||[]).map(u=>`<tr>
    <td>${esc(u.name)}</td><td>${esc(u.email)}</td><td>${u.active?"Active":"Disabled"}</td>
  </tr>`).join("");
  byId("appUsersTable").innerHTML=`<table>
    <thead><tr><th>Name</th><th>Email</th><th>Status</th></tr></thead>
    <tbody>${appRows || '<tr><td colspan="3">No registered app users yet.</td></tr>'}</tbody>
  </table>`;
}

document.querySelectorAll(".nav").forEach(btn=>{
  btn.addEventListener("click",()=>{
    document.querySelectorAll(".nav").forEach(x=>x.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".tab").forEach(x=>x.classList.add("hidden"));
    byId(btn.dataset.tab+"Tab").classList.remove("hidden");
    byId("pageTitle").textContent=btn.textContent;
  });
});


/* Explicit browser globals for inline HTML handlers. */
window.userLogin = userLogin;
window.userRegister = userRegister;
window.userLogout = userLogout;
window.showAuthTab = showAuthTab;
window.adminLogin = adminLogin;
window.adminLogout = adminLogout;
window.changeAdminPassword = changeAdminPassword;
window.centerOnUser = centerOnUser;
window.refreshAllLiveData = refreshAllLiveData;
window.openReportSheet = openReportSheet;
window.closeReportSheet = closeReportSheet;
window.submitReport = submitReport;
window.toggleVoiceAlerts = toggleVoiceAlerts;
window.toggleTrafficLayer = toggleTrafficLayer;
window.focusDestinationSearch = focusDestinationSearch;
window.onDestinationSearchInput = onDestinationSearchInput;
window.onDestinationSearchKeydown = onDestinationSearchKeydown;
window.manualDestinationSearch = manualDestinationSearch;
window.clearDestinationSearch = clearDestinationSearch;
window.changeAppLanguage = changeAppLanguage;
window.setNavigationMode = setNavigationMode;
window.dismissCurrentAlert = dismissCurrentAlert;
window.stopNavigation = stopNavigation;
window.manualReroute = manualReroute;
window.enableRouteFollow = enableRouteFollow;
window.updateNavigationCamera = updateNavigationCamera;
window.showRouteOverview = showRouteOverview;
window.saveCurrentDestination = saveCurrentDestination;
window.resetMapBearing = resetMapBearing;
window.openWalkingLiveView = openWalkingLiveView;
window.closeWalkingLiveView = closeWalkingLiveView;

window.setReportStatus = setReportStatus;
window.updateSetting = updateSetting;
window.addCamera = addCamera;
window.deleteCamera = deleteCamera;
window.chooseDestinationResult = chooseDestinationResult;
window.toggleFavoriteSearchResult = toggleFavoriteSearchResult;
window.chooseQuickDestination = chooseQuickDestination;

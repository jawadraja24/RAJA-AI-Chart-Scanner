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

let voiceEnabledByUser =
  safeLocalGet("roadpulse_voice", "on") !== "off";

let lastAlertedAt = new Map();
let dismissedUntil = new Map();
let currentProximityTarget = null;
let proximityEvalTimer = null;

let navigationActive = false;
let navDestination = null;
let navRoute = null;
let navRouteLayer = null;
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

let favoriteDestinations =
  loadStoredDestinations("roadpulse_favorites");

let recentDestinations =
  loadStoredDestinations("roadpulse_recent");

let navAudioContext = null;
let navLastChimeKey = null;
let adminData = null;

const SUPPORTED_APP_LANGUAGES = [
  "en-GB","de-DE","it-IT","fr-FR","es-ES","nl-NL","pt-PT","pl-PL",
  "cs-CZ","da-DK","sv-SE","fi-FI","nb-NO","hu-HU","tr-TR","sk-SK",
  "sl-SI","lt-LT","el-GR","bg-BG","ru-RU","ar"
];

let userLanguage = "en-GB";

const UI_TRANSLATIONS = {
  "en-GB":{
    logout:"Log out",
    search:"Where do you want to go?",
    nextRoad:"Next road",
    destination:"Destination",
    voiceOn:"Voice ON",
    voiceOff:"Voice OFF",
    online:"Online",
    offline:"Offline",
    navigate:"Navigate",
    myGps:"My GPS",
    report:"Report",
    refresh:"Refresh",
    follow:"Following",
    followOff:"Follow",
    overview:"Overview",
    save:"Save",
    route:"Route",
    trafficDelay:"Traffic delay",
    distance:"Distance",
    drive:"Drive",
    eta:"ETA",
    arrived:"You have arrived",
    routeUpdated:"Route updated.",
    voiceEnabled:"Voice alerts enabled.",
    hazardAhead:"Hazard ahead",
    accidentAhead:"Accident ahead",
    roadworkAhead:"Roadwork ahead",
    trafficAhead:"Traffic ahead",
    policeAhead:"Police report ahead",
    roadAlertAhead:"Road alert ahead",
    inMeters:"in {n} meters"
  },

  "de-DE":{
    logout:"Abmelden",
    search:"Wohin möchtest du fahren?",
    nextRoad:"Nächste Straße",
    destination:"Ziel",
    voiceOn:"Stimme AN",
    voiceOff:"Stimme AUS",
    online:"Online",
    offline:"Offline",
    navigate:"Navigation",
    myGps:"Mein GPS",
    report:"Melden",
    refresh:"Aktualisieren",
    follow:"Folge Route",
    followOff:"Folgen",
    overview:"Übersicht",
    save:"Speichern",
    route:"Route",
    trafficDelay:"Verkehrsverzögerung",
    distance:"Entfernung",
    drive:"Fahrzeit",
    eta:"Ankunft",
    arrived:"Ziel erreicht",
    routeUpdated:"Route aktualisiert.",
    voiceEnabled:"Sprachhinweise aktiviert.",
    hazardAhead:"Gefahr voraus",
    accidentAhead:"Unfall voraus",
    roadworkAhead:"Baustelle voraus",
    trafficAhead:"Verkehr voraus",
    policeAhead:"Polizeimeldung voraus",
    roadAlertAhead:"Straßenhinweis voraus",
    inMeters:"in {n} Metern"
  },

  "it-IT":{
    logout:"Esci",
    search:"Dove vuoi andare?",
    nextRoad:"Prossima strada",
    destination:"Destinazione",
    voiceOn:"Voce ON",
    voiceOff:"Voce OFF",
    online:"Online",
    offline:"Offline",
    navigate:"Naviga",
    myGps:"Il mio GPS",
    report:"Segnala",
    refresh:"Aggiorna",
    follow:"Segui",
    followOff:"Segui",
    overview:"Panoramica",
    save:"Salva",
    route:"Percorso",
    trafficDelay:"Ritardo traffico",
    distance:"Distanza",
    drive:"Durata",
    eta:"Arrivo",
    arrived:"Sei arrivato",
    routeUpdated:"Percorso aggiornato.",
    voiceEnabled:"Avvisi vocali attivati.",
    hazardAhead:"Pericolo più avanti",
    accidentAhead:"Incidente più avanti",
    roadworkAhead:"Lavori stradali più avanti",
    trafficAhead:"Traffico più avanti",
    policeAhead:"Segnalazione polizia più avanti",
    roadAlertAhead:"Avviso stradale più avanti",
    inMeters:"tra {n} metri"
  },

  "fr-FR":{
    logout:"Déconnexion",
    search:"Où voulez-vous aller ?",
    nextRoad:"Prochaine route",
    destination:"Destination",
    voiceOn:"Voix ON",
    voiceOff:"Voix OFF",
    online:"En ligne",
    offline:"Hors ligne",
    navigate:"Naviguer",
    myGps:"Mon GPS",
    report:"Signaler",
    refresh:"Actualiser",
    follow:"Suivi",
    followOff:"Suivre",
    overview:"Aperçu",
    save:"Enregistrer",
    route:"Itinéraire",
    trafficDelay:"Retard trafic",
    distance:"Distance",
    drive:"Durée",
    eta:"Arrivée",
    arrived:"Vous êtes arrivé",
    routeUpdated:"Itinéraire mis à jour.",
    voiceEnabled:"Alertes vocales activées.",
    hazardAhead:"Danger devant",
    accidentAhead:"Accident devant",
    roadworkAhead:"Travaux devant",
    trafficAhead:"Trafic devant",
    policeAhead:"Signalement police devant",
    roadAlertAhead:"Alerte routière devant",
    inMeters:"dans {n} mètres"
  },

  "es-ES":{
    logout:"Salir",
    search:"¿A dónde quieres ir?",
    nextRoad:"Próxima vía",
    destination:"Destino",
    voiceOn:"Voz ON",
    voiceOff:"Voz OFF",
    online:"En línea",
    offline:"Sin conexión",
    navigate:"Navegar",
    myGps:"Mi GPS",
    report:"Reportar",
    refresh:"Actualizar",
    follow:"Siguiendo",
    followOff:"Seguir",
    overview:"Vista general",
    save:"Guardar",
    route:"Ruta",
    trafficDelay:"Retraso tráfico",
    distance:"Distancia",
    drive:"Duración",
    eta:"Llegada",
    arrived:"Has llegado",
    routeUpdated:"Ruta actualizada.",
    voiceEnabled:"Avisos de voz activados.",
    hazardAhead:"Peligro más adelante",
    accidentAhead:"Accidente más adelante",
    roadworkAhead:"Obras más adelante",
    trafficAhead:"Tráfico más adelante",
    policeAhead:"Aviso de policía más adelante",
    roadAlertAhead:"Aviso vial más adelante",
    inMeters:"en {n} metros"
  },

  "nl-NL":{
    logout:"Uitloggen",
    search:"Waar wil je naartoe?",
    nextRoad:"Volgende weg",
    destination:"Bestemming",
    voiceOn:"Stem AAN",
    voiceOff:"Stem UIT",
    online:"Online",
    offline:"Offline",
    navigate:"Navigeren",
    myGps:"Mijn GPS",
    report:"Melden",
    refresh:"Vernieuwen",
    follow:"Volgen",
    followOff:"Volgen",
    overview:"Overzicht",
    save:"Opslaan",
    route:"Route",
    trafficDelay:"Vertraging",
    distance:"Afstand",
    drive:"Rijtijd",
    eta:"Aankomst",
    arrived:"Je bent aangekomen",
    routeUpdated:"Route bijgewerkt.",
    voiceEnabled:"Spraakmeldingen ingeschakeld.",
    hazardAhead:"Gevaar verderop",
    accidentAhead:"Ongeval verderop",
    roadworkAhead:"Wegwerkzaamheden verderop",
    trafficAhead:"Verkeer verderop",
    policeAhead:"Politiemelding verderop",
    roadAlertAhead:"Wegmelding verderop",
    inMeters:"over {n} meter"
  },

  "pt-PT":{
    logout:"Sair",
    search:"Para onde quer ir?",
    nextRoad:"Próxima estrada",
    destination:"Destino",
    voiceOn:"Voz ON",
    voiceOff:"Voz OFF",
    online:"Online",
    offline:"Offline",
    navigate:"Navegar",
    myGps:"Meu GPS",
    report:"Reportar",
    refresh:"Atualizar",
    follow:"Seguindo",
    followOff:"Seguir",
    overview:"Visão geral",
    save:"Guardar",
    route:"Rota",
    trafficDelay:"Atraso no trânsito",
    distance:"Distância",
    drive:"Duração",
    eta:"Chegada",
    arrived:"Chegou ao destino",
    routeUpdated:"Rota atualizada.",
    voiceEnabled:"Alertas de voz ativados.",
    hazardAhead:"Perigo à frente",
    accidentAhead:"Acidente à frente",
    roadworkAhead:"Obras à frente",
    trafficAhead:"Trânsito à frente",
    policeAhead:"Alerta de polícia à frente",
    roadAlertAhead:"Alerta rodoviário à frente",
    inMeters:"em {n} metros"
  },

  "pl-PL":{
    logout:"Wyloguj",
    search:"Dokąd chcesz jechać?",
    nextRoad:"Następna droga",
    destination:"Cel",
    voiceOn:"Głos WŁ.",
    voiceOff:"Głos WYŁ.",
    online:"Online",
    offline:"Offline",
    navigate:"Nawiguj",
    myGps:"Mój GPS",
    report:"Zgłoś",
    refresh:"Odśwież",
    follow:"Prowadzenie",
    followOff:"Podążaj",
    overview:"Przegląd",
    save:"Zapisz",
    route:"Trasa",
    trafficDelay:"Opóźnienie",
    distance:"Dystans",
    drive:"Czas jazdy",
    eta:"Przyjazd",
    arrived:"Dotarłeś do celu",
    routeUpdated:"Trasa zaktualizowana.",
    voiceEnabled:"Wskazówki głosowe włączone.",
    hazardAhead:"Niebezpieczeństwo przed tobą",
    accidentAhead:"Wypadek przed tobą",
    roadworkAhead:"Roboty drogowe przed tobą",
    trafficAhead:"Korek przed tobą",
    policeAhead:"Zgłoszenie policji przed tobą",
    roadAlertAhead:"Ostrzeżenie drogowe",
    inMeters:"za {n} metrów"
  },

  "tr-TR":{
    logout:"Çıkış",
    search:"Nereye gitmek istiyorsun?",
    nextRoad:"Sonraki yol",
    destination:"Hedef",
    voiceOn:"Ses AÇIK",
    voiceOff:"Ses KAPALI",
    online:"Çevrimiçi",
    offline:"Çevrimdışı",
    navigate:"Navigasyon",
    myGps:"GPS'im",
    report:"Bildir",
    refresh:"Yenile",
    follow:"Takip",
    followOff:"Takip et",
    overview:"Genel görünüm",
    save:"Kaydet",
    route:"Rota",
    trafficDelay:"Trafik gecikmesi",
    distance:"Mesafe",
    drive:"Sürüş",
    eta:"Varış",
    arrived:"Hedefe ulaştınız",
    routeUpdated:"Rota güncellendi.",
    voiceEnabled:"Sesli uyarılar açıldı.",
    hazardAhead:"İleride tehlike",
    accidentAhead:"İleride kaza",
    roadworkAhead:"İleride yol çalışması",
    trafficAhead:"İleride trafik",
    policeAhead:"İleride polis bildirimi",
    roadAlertAhead:"İleride yol uyarısı",
    inMeters:"{n} metre sonra"
  }
};

function detectInitialLanguage(){
  const browser =
    (navigator.language || "en-GB")
      .toLowerCase();

  const exact =
    SUPPORTED_APP_LANGUAGES.find(
      x => x.toLowerCase() === browser
    );

  if (exact){
    return exact;
  }

  const prefix =
    browser.split("-")[0];

  const pref =
    SUPPORTED_APP_LANGUAGES.find(
      x =>
        x.toLowerCase().startsWith(prefix + "-") ||
        x.toLowerCase() === prefix
    );

  return pref || "en-GB";
}

function t(key){
  const dict =
    UI_TRANSLATIONS[userLanguage] ||
    UI_TRANSLATIONS["en-GB"];

  return (
    dict[key] ||
    UI_TRANSLATIONS["en-GB"][key] ||
    key
  );
}

function changeAppLanguage(language){
  if (
    !SUPPORTED_APP_LANGUAGES.includes(language)
  ){
    language = "en-GB";
  }

  userLanguage = language;

  safeLocalSet(
    "roadpulse_language",
    userLanguage
  );

  applyAppLanguage();

  if (
    navigationActive &&
    navDestination
  ){
    calculateNavigationRoute(true);

  }else{
    refreshMapData();
  }
}

function initializeLanguageSafe(){
  try{
    const stored =
      safeLocalGet(
        "roadpulse_language",
        ""
      );

    if (
      stored &&
      SUPPORTED_APP_LANGUAGES.includes(stored)
    ){
      userLanguage =
        stored;

    }else{
      userLanguage =
        detectInitialLanguage();
    }

  }catch(_){
    userLanguage =
      "en-GB";
  }
}

function applyAppLanguage(){
  const select =
    byId("appLanguageSelect");

  if (select){
    select.value =
      userLanguage;
  }

  document.documentElement.lang =
    userLanguage;

  document.documentElement.dir =
    userLanguage === "ar"
      ? "rtl"
      : "ltr";

  const logout =
    byId("logoutBtn");

  if (logout){
    logout.textContent =
      t("logout");
  }

  const search =
    byId("destinationSearchInput");

  if (search){
    search.placeholder =
      t("search");
  }

  const nextRoad =
    byId("nextRoadLabel");

  if (nextRoad){
    nextRoad.textContent =
      t("nextRoad");
  }

  const navDest =
    byId("navDestinationName");

  if (
    navDest &&
    !navigationActive
  ){
    navDest.textContent =
      t("destination");
  }

  updateVoiceBadge();
  updateNetworkBadge();
  updateBottomNavigationLabels();
  updateRouteControlLabels();
}

function updateBottomNavigationLabels(){
  const buttons =
    document.querySelectorAll(
      ".bottom-nav button span"
    );

  if (buttons.length >= 4){
    buttons[0].textContent =
      t("navigate");

    buttons[1].textContent =
      t("myGps");

    buttons[2].textContent =
      t("report");

    buttons[3].textContent =
      t("refresh");
  }
}

function updateRouteControlLabels(){
  const follow =
    byId("followRouteBtn");

  if (follow){
    follow.textContent =
      navFollowMode
        ? `◎ ${t("follow")}`
        : `◎ ${t("followOff")}`;
  }

  const summary =
    byId("routeSummaryCard");

  if (!summary){
    return;
  }

  const labels =
    summary.querySelectorAll(
      ":scope > div > span"
    );

  if (labels.length >= 4){
    labels[0].textContent =
      t("eta");

    labels[1].textContent =
      t("drive");

    labels[2].textContent =
      t("distance");

    labels[3].textContent =
      t("trafficDelay");
  }

  const controls =
    summary.querySelectorAll(
      ".route-control-btn"
    );

  if (controls.length >= 4){
    controls[1].textContent =
      `▱ ${t("overview")}`;

    controls[2].textContent =
      `☆ ${t("save")}`;

    controls[3].textContent =
      `↻ ${t("route")}`;
  }
}

function localizedInMeters(n){
  return t("inMeters")
    .replace(
      "{n}",
      String(n)
    );
}

function localizedAlertTitle(type){
  const keys = {
    accident:"accidentAhead",
    hazard:"hazardAhead",
    roadwork:"roadworkAhead",
    traffic:"trafficAhead",
    police:"policeAhead"
  };

  return t(
    keys[type] ||
    "roadAlertAhead"
  );
}

function loadStoredDestinations(key){
  try{
    const value =
      JSON.parse(
        safeLocalGet(
          key,
          "[]"
        ) ||
        "[]"
      );

    return Array.isArray(value)
      ? value.slice(0,12)
      : [];

  }catch(_){
    return [];
  }
}

function saveStoredDestinations(
  key,
  items
){
  try{
    safeLocalSet(
      key,
      JSON.stringify(
        items.slice(0,12)
      )
    );
  }catch(_){}
}

function sameDestination(a,b){
  if (!a || !b){
    return false;
  }

  return (
    Math.abs(
      Number(a.lat) -
      Number(b.lat)
    ) < 0.00001
    &&
    Math.abs(
      Number(a.lng) -
      Number(b.lng)
    ) < 0.00001
  );
}

const byId =
  id =>
    document.getElementById(id);

function showOnly(id){
  [
    "userAuthView",
    "userAppView",
    "adminLoginView",
    "adminView"
  ]
  .forEach(
    x => {
      const el =
        byId(x);

      if (el){
        el.classList.toggle(
          "hidden",
          x !== id
        );
      }
    }
  );
}

async function routeByHash(){
  const isAdmin =
    location.hash.toLowerCase()
    === "#admin";

  if (isAdmin){
    try{
      stopGpsWatch();
    }catch(_){}

    showOnly(
      "adminLoginView"
    );

    return;
  }

  try{
    const r =
      await fetch(
        "/api/auth/me",
        {
          credentials:"include"
        }
      );

    if (r.ok){
      const data =
        await r.json();

      currentUser =
        data.user;

      try{
        await openUserApp();

      }catch(err){
        console.error(
          "RoadPulse user app open error:",
          err
        );

        showOnly(
          "userAuthView"
        );
      }

      return;
    }

  }catch(err){
    console.error(
      "RoadPulse auth check error:",
      err
    );
  }

  try{
    stopGpsWatch();
  }catch(_){}

  showOnly(
    "userAuthView"
  );
}

window.addEventListener(
  "hashchange",
  routeByHash
);

window.addEventListener(
  "load",
  async () => {
    try{
      initializeLanguageSafe();
      applyAppLanguage();
      updateNetworkBadge();
      bindDestinationSearchControls();

    }catch(err){
      console.error(
        "RoadPulse UI init warning:",
        err
      );
    }

    try{
      await routeByHash();

    }catch(err){
      console.error(
        "RoadPulse route/auth boot error:",
        err
      );

      if (
        location.hash.toLowerCase()
        === "#admin"
      ){
        showOnly(
          "adminLoginView"
        );

      }else{
        showOnly(
          "userAuthView"
        );
      }
    }

    window.__ROADPULSE_BOOT_OK__ =
      true;

    console.log(
      "RoadPulse Web V1.1 safe boot loaded"
    );
  }
);

window.addEventListener(
  "online",
  updateNetworkBadge
);

window.addEventListener(
  "offline",
  updateNetworkBadge
);

document.addEventListener(
  "visibilitychange",
  () => {
    if (
      document.visibilityState === "visible" &&
      navigationActive
    ){
      requestNavigationWakeLock();
    }
  }
);

function updateNetworkBadge(){
  const badge =
    byId("networkBadge");

  if (!badge){
    return;
  }

  const online =
    navigator.onLine !== false;

  badge.textContent =
    online
      ? t("online")
      : t("offline");

  badge.classList.toggle(
    "offline",
    !online
  );
}

function showAuthTab(tab){
  byId("loginForm")
    .classList
    .toggle(
      "hidden",
      tab !== "login"
    );

  byId("registerForm")
    .classList
    .toggle(
      "hidden",
      tab !== "register"
    );

  byId("loginTabBtn")
    .classList
    .toggle(
      "active",
      tab === "login"
    );

  byId("registerTabBtn")
    .classList
    .toggle(
      "active",
      tab === "register"
    );

  setUserAuthMessage("");
}

function setUserAuthMessage(
  message,
  isError=false
){
  const el =
    byId("userAuthMsg");

  if (!message){
    el.classList.add(
      "hidden"
    );

    return;
  }

  el.textContent =
    message;

  el.classList.remove(
    "hidden"
  );

  el.classList.toggle(
    "error",
    isError
  );
}

async function userRegister(){
  setUserAuthMessage("");

  const payload = {
    name:
      byId("registerName")
        .value
        .trim(),

    email:
      byId("registerEmail")
        .value
        .trim(),

    password:
      byId("registerPassword")
        .value
  };

  const r =
    await fetch(
      "/api/auth/register",
      {
        method:"POST",
        credentials:"include",

        headers:{
          "Content-Type":
            "application/json"
        },

        body:
          JSON.stringify(
            payload
          )
      }
    );

  const data =
    await r.json()
      .catch(
        () => ({})
      );

  if (!r.ok){
    setUserAuthMessage(
      data.detail ||
      "Could not create account.",
      true
    );

    return;
  }

  currentUser =
    data.user;

  await openUserApp();
}

async function userLogin(){
  setUserAuthMessage("");

  const payload = {
    email:
      byId("loginEmail")
        .value
        .trim(),

    password:
      byId("loginPassword")
        .value
  };

  const r =
    await fetch(
      "/api/auth/login",
      {
        method:"POST",
        credentials:"include",

        headers:{
          "Content-Type":
            "application/json"
        },

        body:
          JSON.stringify(
            payload
          )
      }
    );

  const data =
    await r.json()
      .catch(
        () => ({})
      );

  if (!r.ok){
    setUserAuthMessage(
      data.detail ||
      "Login failed.",
      true
    );

    return;
  }

  currentUser =
    data.user;

  await openUserApp();
}

async function userLogout(){
  stopGpsWatch();
  stopNavigation(false);

  if (navSearchTimer){
    clearTimeout(
      navSearchTimer
    );

    navSearchTimer =
      null;
  }

  if (proximityEvalTimer){
    clearInterval(
      proximityEvalTimer
    );

    proximityEvalTimer =
      null;
  }

  if (
    map &&
    trafficFlowLayer &&
    map.hasLayer(
      trafficFlowLayer
    )
  ){
    map.removeLayer(
      trafficFlowLayer
    );
  }

  if (
    map &&
    trafficIncidentLayer &&
    map.hasLayer(
      trafficIncidentLayer
    )
  ){
    map.removeLayer(
      trafficIncidentLayer
    );
  }

  await fetch(
    "/api/auth/logout",
    {
      method:"POST",
      credentials:"include"
    }
  );

  currentUser =
    null;

  location.hash =
    "";

  showOnly(
    "userAuthView"
  );
}

async function openUserApp(){
  showOnly(
    "userAppView"
  );

  applyAppLanguage();
  bindDestinationSearchControls();

  byId("userGreeting")
    .textContent =
    currentUser
      ? `Hi ${currentUser.name}`
      : "Live map";

  ensureMap();

  await refreshMapData();

  startGpsWatch();

  setTimeout(
    () => {
      if (map){
        map.invalidateSize();
      }
    },
    50
  );

  if (!proximityEvalTimer){
    proximityEvalTimer =
      setInterval(
        () => {
          evaluateProximityAlerts();
        },
        2000
      );
  }
}

function ensureMap(){
  if (map){
    return;
  }

  map =
    L.map(
      "map",
      {
        zoomControl:true
      }
    )
    .setView(
      [
        53.5511,
        9.9937
      ],
      12
    );

  L.tileLayer(
    "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    {
      maxZoom:19,
      attribution:
        "&copy; OpenStreetMap contributors"
    }
  )
  .addTo(map);

  incidentLayer =
    L.layerGroup()
      .addTo(map);

  cameraLayer =
    L.layerGroup()
      .addTo(map);

  trafficFlowLayer =
    L.tileLayer(
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

  trafficIncidentLayer =
    L.tileLayer(
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
    trafficRefreshTimer =
      setInterval(
        () => {
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
        },
        60000
      );
  }

  map.on(
    "dragstart",
    () => {
      if (navigationActive){
        navFollowMode =
          false;

        updateFollowButton();
      }
    }
  );
}

function startGpsWatch(){
  if (!navigator.geolocation){
    setGpsBadge(
      "GPS not supported",
      false
    );

    return;
  }

  if (watchId !== null){
    return;
  }

  setGpsBadge(
    "Requesting GPS…",
    false
  );

  watchId =
    navigator.geolocation
      .watchPosition(
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
    speed: pos.coords.speed,
    heading: pos.coords.heading
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
    .bindPopup(
      "<strong>Your live GPS location</strong>"
    );
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
    )
    .addTo(map);
  }else{
    userAccuracyCircle.setLatLng(latlng);
    userAccuracyCircle.setRadius(
      currentPosition.accuracy
    );
  }

  if (!map.__centeredOnUser){
    map.setView(latlng,15);
    map.__centeredOnUser = true;
  }

  const speedKmh =
    currentPosition.speed != null &&
    currentPosition.speed >= 0
      ? Math.round(
          currentPosition.speed * 3.6
        )
      : null;

  setGpsBadge(
    `GPS live · ±${Math.round(currentPosition.accuracy)}m`,
    true
  );

  const speedBadge =
    byId("speedBadge");

  if (speedBadge){
    speedBadge.textContent =
      `${speedKmh ?? 0} km/h`;
  }

  evaluateProximityAlerts();
  updateNavigationProgress();

  if (
    navigationActive &&
    navFollowMode &&
    map
  ){
    map.setView(
      [
        currentPosition.lat,
        currentPosition.lng
      ],
      Math.max(
        map.getZoom(),
        16
      ),
      {
        animate:true
      }
    );
  }
}

function onGpsError(err){
  const messages = {
    1:"Location permission denied",
    2:"GPS position unavailable",
    3:"GPS request timed out"
  };

  setGpsBadge(
    messages[err.code] ||
    "GPS error",
    false
  );
}

function setGpsBadge(text,good){
  const el =
    byId("gpsBadge");

  if (!el){
    return;
  }

  el.textContent = text;

  el.classList.toggle(
    "good",
    !!good
  );

  el.classList.toggle(
    "warning",
    !good
  );
}

function centerOnUser(){
  if (navigationActive){
    navFollowMode = true;
    updateFollowButton();
  }

  if (
    map &&
    currentPosition
  ){
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

    setGpsBadge(
      "Waiting for GPS…",
      false
    );
  }
}

const reportStyle = {
  camera:{
    color:"#2d70d6",
    emoji:"📷"
  },

  police:{
    color:"#3159b8",
    emoji:"🚓"
  },

  accident:{
    color:"#d63b32",
    emoji:"🚗"
  },

  hazard:{
    color:"#e09b18",
    emoji:"⚠️"
  },

  roadwork:{
    color:"#d97818",
    emoji:"🚧"
  },

  traffic:{
    color:"#17a65b",
    emoji:"🚦"
  }
};

async function refreshMapData(){
  if (!map){
    return;
  }

  const r =
    await fetch(
      "/api/map-data",
      {
        credentials:"include"
      }
    );

  if (r.status === 401){
    await userLogout();
    return;
  }

  if (!r.ok){
    return;
  }

  const data =
    await r.json();

  incidentLayer.clearLayers();
  cameraLayer.clearLayers();

  data.reports.forEach(
    item => {
      const style =
        reportStyle[item.type] ||
        {
          color:"#666",
          emoji:"•"
        };

      const marker =
        L.circleMarker(
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
          ${style.emoji}
          ${esc(item.type)}
        </div>

        <div>
          ${esc(
            item.location ||
            "Reported location"
          )}
        </div>

        <div class="popup-meta">
          Community verified
        </div>
      `);

      marker.addTo(
        incidentLayer
      );
    }
  );

  data.cameras.forEach(
    item => {
      const marker =
        L.marker(
          [
            item.lat,
            item.lng
          ],
          {
            title:
              `Camera: ${item.location}`
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
          ${esc(limit)}
          · confidence
          ${esc(item.confidence)}%
        </div>
      `);

      marker.addTo(
        cameraLayer
      );
    }
  );

  const incidentBadge =
    byId("incidentBadge");

  if (incidentBadge){
    incidentBadge.textContent =
      `${data.reports.length} verified reports`;
  }

  proximitySettings = {
    enabled:
      data.settings
        .proximity_alerts !== false,

    voice:
      data.settings
        .voice_alerts !== false,

    maxDistanceM:
      Number(
        data.settings
          .alert_distance_m ||
        1200
      ),

    urgentDistanceM:
      Number(
        data.settings
          .urgent_alert_distance_m ||
        400
      ),

    cooldownS:
      Number(
        data.settings
          .alert_repeat_cooldown_s ||
        300
      ),

    language:
      data.settings
        .voice_language ||
      "en-GB",

    defaultCountry:
      data.settings
        .default_country ||
      "DE",

    cameraWarningMode:
      data.settings
        .camera_warning_mode ||
      "country_compliance"
  };

  proximityTargets =
    buildProximityTargets(data);

  updateVoiceBadge();
  evaluateProximityAlerts();

  trafficConfigured =
    !!data.settings
      .traffic_available;

  const adminTrafficEnabled =
    data.settings
      .traffic_layer !== false;

  applyTrafficLayerState(
    adminTrafficEnabled
  );
}

function applyTrafficLayerState(
  adminTrafficEnabled=true
){
  const badge =
    byId("trafficBadge");

  const legend =
    byId("trafficLegend");

  if (
    !badge ||
    !map
  ){
    return;
  }

  if (!trafficConfigured){
    if (
      trafficFlowLayer &&
      map.hasLayer(
        trafficFlowLayer
      )
    ){
      map.removeLayer(
        trafficFlowLayer
      );
    }

    if (
      trafficIncidentLayer &&
      map.hasLayer(
        trafficIncidentLayer
      )
    ){
      map.removeLayer(
        trafficIncidentLayer
      );
    }

    badge.textContent =
      "Traffic API not configured";

    badge.classList.remove(
      "on",
      "off"
    );

    badge.classList.add(
      "error"
    );

    if (legend){
      legend.classList.add(
        "hidden"
      );
    }

    return;
  }

  if (!adminTrafficEnabled){
    if (
      trafficFlowLayer &&
      map.hasLayer(
        trafficFlowLayer
      )
    ){
      map.removeLayer(
        trafficFlowLayer
      );
    }

    if (
      trafficIncidentLayer &&
      map.hasLayer(
        trafficIncidentLayer
      )
    ){
      map.removeLayer(
        trafficIncidentLayer
      );
    }

    badge.textContent =
      "Traffic disabled by admin";

    badge.classList.remove(
      "on",
      "error"
    );

    badge.classList.add(
      "off"
    );

    if (legend){
      legend.classList.add(
        "hidden"
      );
    }

    return;
  }

  if (trafficEnabledByUser){
    if (
      trafficFlowLayer &&
      !map.hasLayer(
        trafficFlowLayer
      )
    ){
      trafficFlowLayer.addTo(map);
    }

    if (
      trafficIncidentLayer &&
      !map.hasLayer(
        trafficIncidentLayer
      )
    ){
      trafficIncidentLayer.addTo(map);
    }

    badge.textContent =
      "Live Traffic ON";

    badge.classList.remove(
      "off",
      "error"
    );

    badge.classList.add(
      "on"
    );

    if (legend){
      legend.classList.remove(
        "hidden"
      );
    }
  }else{
    if (
      trafficFlowLayer &&
      map.hasLayer(
        trafficFlowLayer
      )
    ){
      map.removeLayer(
        trafficFlowLayer
      );
    }

    if (
      trafficIncidentLayer &&
      map.hasLayer(
        trafficIncidentLayer
      )
    ){
      map.removeLayer(
        trafficIncidentLayer
      );
    }

    badge.textContent =
      "Traffic OFF";

    badge.classList.remove(
      "on",
      "error"
    );

    badge.classList.add(
      "off"
    );

    if (legend){
      legend.classList.add(
        "hidden"
      );
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

function bindDestinationSearchControls(){
  const input =
    byId("destinationSearchInput");

  const goBtn =
    byId("destinationSearchGoBtn");

  if (
    !input ||
    input.dataset.roadpulseSearchBound === "1"
  ){
    return;
  }

  input.dataset.roadpulseSearchBound =
    "1";

  input.addEventListener(
    "input",
    onDestinationSearchInput
  );

  input.addEventListener(
    "keydown",
    onDestinationSearchKeydown
  );

  input.addEventListener(
    "focus",
    () => {
      if (!input.value.trim()){
        renderDestinationQuickList();
      }
    }
  );

  if (goBtn){
    goBtn.addEventListener(
      "click",
      manualDestinationSearch
    );
  }

  console.log(
    "RoadPulse destination search controls bound"
  );
}

async function manualDestinationSearch(){
  const input =
    byId("destinationSearchInput");

  if (!input){
    return;
  }

  const q =
    input.value.trim();

  if (q.length < 2){
    const box =
      byId("destinationResults");

    if (box){
      box.innerHTML =
        '<div class="destination-result"><div class="destination-result-icon">⌕</div><div><strong>Type at least 2 letters</strong><small>Example: Frankfurt Hbf</small></div></div>';

      box.classList.remove(
        "hidden"
      );
    }

    return;
  }

  if (navSearchTimer){
    clearTimeout(
      navSearchTimer
    );

    navSearchTimer =
      null;
  }

  await searchDestinations(q);
}

function focusDestinationSearch(){
  const input =
    byId("destinationSearchInput");

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
    byId("destinationResults")
      ?.classList
      .add("hidden");

    return;
  }

  if (event.key === "Enter"){
    event.preventDefault();

    if (
      navSearchResults.length > 0
    ){
      chooseDestinationResult(0);
    }else{
      manualDestinationSearch();
    }
  }
}

function onDestinationSearchInput(){
  const input =
    byId("destinationSearchInput");

  const clearBtn =
    byId("clearDestinationBtn");

  if (!input){
    return;
  }

  const q =
    input.value.trim();

  if (clearBtn){
    clearBtn.classList.toggle(
      "hidden",
      q.length === 0
    );
  }

  if (navSearchTimer){
    clearTimeout(
      navSearchTimer
    );
  }

  if (q.length < 2){
    navSearchResults = [];

    byId("destinationResults")
      ?.classList
      .add("hidden");

    renderDestinationQuickList();

    return;
  }

  byId("destinationQuickList")
    ?.classList
    .add("hidden");

  navSearchTimer =
    setTimeout(
      () => {
        searchDestinations(q);
      },
      320
    );
}

async function searchDestinations(q){
  const resultsBox =
    byId("destinationResults");

  if (!resultsBox){
    return;
  }

  resultsBox.innerHTML =
    `
      <div class="destination-result">

        <div class="destination-result-icon">
          …
        </div>

        <div>
          <strong>
            Searching
          </strong>

          <small>
            Finding destinations near you
          </small>
        </div>

      </div>
    `;

  resultsBox.classList.remove(
    "hidden"
  );

  const params =
    new URLSearchParams({
      q,
      limit:"6",
      language:
        userLanguage ||
        "en-GB"
    });

  if (currentPosition){
    params.set(
      "lat",
      currentPosition.lat
    );

    params.set(
      "lng",
      currentPosition.lng
    );
  }

  try{
    const r =
      await fetch(
        `/api/navigation/search?${params.toString()}`,
        {
          credentials:"include"
        }
      );

    const data =
      await r.json()
        .catch(
          () => ({})
        );

    if (!r.ok){
      throw new Error(
        data.detail ||
        "Search failed"
      );
    }

    navSearchResults =
      data.results || [];

    renderDestinationResults();

  }catch(err){
    navSearchResults = [];

    resultsBox.innerHTML =
      `
        <div class="destination-result">

          <div class="destination-result-icon">
            !
          </div>

          <div>
            <strong>
              Search unavailable
            </strong>

            <small>
              ${esc(
                err.message ||
                "Please try again"
              )}
            </small>
          </div>

        </div>
      `;
  }
}

function renderDestinationResults(){
  const box =
    byId("destinationResults");

  if (!box){
    return;
  }

  if (
    navSearchResults.length === 0
  ){
    box.innerHTML =
      `
        <div class="destination-result">

          <div class="destination-result-icon">
            ⌕
          </div>

          <div>
            <strong>
              No results
            </strong>

            <small>
              Try a street, city or place name
            </small>
          </div>

        </div>
      `;

    box.classList.remove(
      "hidden"
    );

    return;
  }

  box.innerHTML =
    navSearchResults
      .map(
        (item,index) => {
          const saved =
            favoriteDestinations
              .some(
                x =>
                  sameDestination(
                    x,
                    item
                  )
              );

          return `
            <div class="destination-result">

              <button
                class="destination-result-icon"
                onclick="chooseDestinationResult(${index})">
                ⌖
              </button>

              <button
                class="destination-result-main"
                onclick="chooseDestinationResult(${index})"
                style="
                  background:transparent;
                  color:inherit;
                  text-align:left;
                  padding:0;
                  border-radius:0
                ">

                <strong>
                  ${esc(item.name)}
                </strong>

                <small>
                  ${esc(item.address || "")}
                </small>

              </button>

              <button
                class="destination-result-save ${saved ? "saved" : ""}"
                onclick="toggleFavoriteSearchResult(event,${index})"
                title="Save destination">

                ${saved ? "★" : "☆"}

              </button>

            </div>
          `;
        }
      )
      .join("");

  box.classList.remove(
    "hidden"
  );
}

function chooseDestinationResult(index){
  unlockNavigationAudio();

  const item =
    navSearchResults[index];

  if (!item){
    return;
  }

  navDestination = {
    name:item.name,
    address:item.address,
    lat:Number(item.lat),
    lng:Number(item.lng)
  };

  const input =
    byId("destinationSearchInput");

  if (input){
    input.value =
      item.name;
  }

  byId("destinationResults")
    ?.classList
    .add("hidden");

  byId("destinationQuickList")
    ?.classList
    .add("hidden");

  byId("clearDestinationBtn")
    ?.classList
    .remove("hidden");

  rememberRecentDestination(
    navDestination
  );

  requestNavigationWakeLock();

  startNavigation();
}

function clearDestinationSearch(){
  const input =
    byId("destinationSearchInput");

  if (input){
    input.value = "";
  }

  navSearchResults = [];

  byId("destinationResults")
    ?.classList
    .add("hidden");

  byId("destinationQuickList")
    ?.classList
    .add("hidden");

  byId("clearDestinationBtn")
    ?.classList
    .add("hidden");

  if (navigationActive){
    stopNavigation();
  }
}

async function startNavigation(){
  if (!navDestination){
    focusDestinationSearch();
    return;
  }

  if (!currentPosition){
    setGpsBadge(
      "Waiting for GPS to start route…",
      false
    );

    startGpsWatch();
    return;
  }

  await calculateNavigationRoute(
    false
  );
}

async function calculateNavigationRoute(
  isReroute=false
){
  if (
    !currentPosition ||
    !navDestination ||
    navRequestInFlight
  ){
    return;
  }

  navRequestInFlight = true;

  const search =
    byId("destinationSearchInput");

  search
    ?.closest(".destination-search")
    ?.classList
    .add("navigation-loading");

  try{
    const r =
      await fetch(
        "/api/navigation/route",
        {
          method:"POST",
          credentials:"include",

          headers:{
            "Content-Type":
              "application/json"
          },

          body:
            JSON.stringify({
              origin_lat:
                currentPosition.lat,

              origin_lng:
                currentPosition.lng,

              destination_lat:
                navDestination.lat,

              destination_lng:
                navDestination.lng,

              destination_name:
                navDestination.name,

              language:
                userLanguage ||
                "en-GB"
            })
        }
      );

    const data =
      await r.json()
        .catch(
          () => ({})
        );

    if (!r.ok){
      throw new Error(
        data.detail ||
        "Could not calculate route"
      );
    }

    applyNavigationRoute(
      data,
      isReroute
    );

  }catch(err){
    const card =
      byId("navigationCard");

    if (card){
      card.classList.remove(
        "hidden"
      );

      byId("navManeuverIcon")
        .textContent = "!";

      byId("navInstruction")
        .textContent =
        "Route unavailable";

      byId("navInstructionDistance")
        .textContent = "";

      byId("navDestinationName")
        .textContent =
        err.message ||
        "Please try again";
    }

  }finally{
    navRequestInFlight = false;

    search
      ?.closest(".destination-search")
      ?.classList
      .remove("navigation-loading");
  }
}

function applyNavigationRoute(
  data,
  isReroute=false
){
  navRoute = data;

  navRoutePoints =
    data.points || [];

  navInstructions =
    data.instructions || [];

  navCurrentInstructionIndex = 0;
  navLastProgressIndex = 0;

  navInstructionAnnouncements.clear();

  navigationActive = true;
  navFollowMode = true;

  navBaseSummary =
    data.summary || {};

  navLastRerouteAt =
    Date.now();

  navLastTrafficRefreshAt =
    Date.now();

  document.body
    .classList
    .add(
      "navigation-active"
    );

  if (
    navRouteLayer &&
    map
  ){
    map.removeLayer(
      navRouteLayer
    );
  }

  navRouteLayer =
    L.polyline(
      navRoutePoints,
      {
        color:"#1769d2",
        weight:7,
        opacity:.88,
        lineJoin:"round"
      }
    )
    .addTo(map);

  if (!isReroute){
    try{
      map.fitBounds(
        navRouteLayer.getBounds(),
        {
          padding:[70,70],
          maxZoom:16
        }
      );
    }catch(_){}
  }

  byId("navigationCard")
    ?.classList
    .remove("hidden");

  byId("routeSummaryCard")
    ?.classList
    .remove("hidden");

  byId("destinationResults")
    ?.classList
    .add("hidden");

  byId("destinationQuickList")
    ?.classList
    .add("hidden");

  updateFollowButton();

  requestNavigationWakeLock();

  updateRouteSummary(
    data.summary || {}
  );

  updateNavigationProgress();

  if (
    isReroute &&
    voiceEnabledByUser &&
    proximitySettings.voice
  ){
    speakNavigationMessage(
      t("routeUpdated")
    );
  }
}

function updateRouteSummary(summary){
  byId("routeEta")
    .textContent =
    formatArrivalTime(
      summary.arrivalTime
    );

  byId("routeDuration")
    .textContent =
    formatDuration(
      summary.travelTimeSeconds ||
      0
    );

  byId("routeDistance")
    .textContent =
    formatRouteDistance(
      summary.lengthMeters ||
      0
    );

  const delay =
    Number(
      summary.trafficDelaySeconds ||
      0
    );

  byId("routeDelay")
    .textContent =
    delay > 30
      ? `+${formatDuration(delay)}`
      : "None";
}

function formatArrivalTime(value){
  if (!value){
    return "—";
  }

  const date =
    new Date(value);

  if (
    Number.isNaN(
      date.getTime()
    )
  ){
    return "—";
  }

  return date
    .toLocaleTimeString(
      [],
      {
        hour:"2-digit",
        minute:"2-digit"
      }
    );
}

function formatDuration(seconds){
  const mins =
    Math.max(
      0,
      Math.round(
        Number(
          seconds || 0
        ) / 60
      )
    );

  if (mins < 60){
    return `${mins} min`;
  }

  const h =
    Math.floor(
      mins / 60
    );

  const m =
    mins % 60;

  return m
    ? `${h}h ${m}m`
    : `${h}h`;
}

function formatRouteDistance(meters){
  const m =
    Number(
      meters || 0
    );

  if (m < 1000){
    return `${Math.round(m)} m`;
  }

  return `${
    (m / 1000)
      .toFixed(
        m < 10000
          ? 1
          : 0
      )
  } km`;
}

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
let voiceEnabledByUser = localStorage.getItem("roadpulse_voice") !== "off";
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
let favoriteDestinations = loadStoredDestinations("roadpulse_favorites");
let recentDestinations = loadStoredDestinations("roadpulse_recent");
let userLanguage = localStorage.getItem("roadpulse_language") || detectInitialLanguage();
let navAudioContext = null;
let navLastChimeKey = null;
let adminData = null;

const SUPPORTED_APP_LANGUAGES = [
  "en-GB","de-DE","it-IT","fr-FR","es-ES","nl-NL","pt-PT","pl-PL",
  "cs-CZ","da-DK","sv-SE","fi-FI","nb-NO","hu-HU","tr-TR","sk-SK",
  "sl-SI","lt-LT","el-GR","bg-BG","ru-RU","ar"
];

const UI_TRANSLATIONS = {
  "en-GB":{
    logout:"Log out", search:"Where do you want to go?", nextRoad:"Next road",
    destination:"Destination", voiceOn:"Voice ON", voiceOff:"Voice OFF",
    online:"Online", offline:"Offline", navigate:"Navigate", myGps:"My GPS",
    report:"Report", refresh:"Refresh", follow:"Following", followOff:"Follow",
    overview:"Overview", save:"Save", route:"Route", trafficDelay:"Traffic delay",
    distance:"Distance", drive:"Drive", eta:"ETA", arrived:"You have arrived",
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
    distance:"Entfernung", drive:"Fahrzeit", eta:"Ankunft", arrived:"Ziel erreicht",
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
    distance:"Distanza", drive:"Durata", eta:"Arrivo", arrived:"Sei arrivato",
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
    distance:"Distance", drive:"Durée", eta:"Arrivée", arrived:"Vous êtes arrivé",
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
    distance:"Distancia", drive:"Duración", eta:"Llegada", arrived:"Has llegado",
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
    distance:"Afstand", drive:"Rijtijd", eta:"Aankomst", arrived:"Je bent aangekomen",
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
    distance:"Distância", drive:"Duração", eta:"Chegada", arrived:"Chegou ao destino",
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
    distance:"Dystans", drive:"Czas jazdy", eta:"Przyjazd", arrived:"Dotarłeś do celu",
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
    distance:"Mesafe", drive:"Sürüş", eta:"Varış", arrived:"Hedefe ulaştınız",
    routeUpdated:"Rota güncellendi.", voiceEnabled:"Sesli uyarılar açıldı.",
    hazardAhead:"İleride tehlike", accidentAhead:"İleride kaza",
    roadworkAhead:"İleride yol çalışması", trafficAhead:"İleride trafik",
    policeAhead:"İleride polis bildirimi", roadAlertAhead:"İleride yol uyarısı",
    inMeters:"{n} metre sonra"
  }
};

function detectInitialLanguage(){
  const browser = (navigator.language || "en-GB").toLowerCase();

  const exact = SUPPORTED_APP_LANGUAGES.find(
    x => x.toLowerCase() === browser
  );

  if (exact) return exact;

  const prefix = browser.split("-")[0];

  const pref = SUPPORTED_APP_LANGUAGES.find(
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
  if (!SUPPORTED_APP_LANGUAGES.includes(language)){
    language = "en-GB";
  }

  userLanguage = language;

  localStorage.setItem(
    "roadpulse_language",
    userLanguage
  );

  applyAppLanguage();

  if (navigationActive && navDestination){
    calculateNavigationRoute(true);
  }else{
    refreshMapData();
  }
}

function applyAppLanguage(){
  const select = byId("appLanguageSelect");

  if (select){
    select.value = userLanguage;
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
    buttons[0].textContent = t("navigate");
    buttons[1].textContent = t("myGps");
    buttons[2].textContent = t("report");
    buttons[3].textContent = t("refresh");
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

  if (!summary) return;

  const labels =
    summary.querySelectorAll(
      ":scope > div > span"
    );

  if (labels.length >= 4){
    labels[0].textContent = t("eta");
    labels[1].textContent = t("drive");
    labels[2].textContent = t("distance");
    labels[3].textContent = t("trafficDelay");
  }

  const controls =
    summary.querySelectorAll(
      ".route-control-btn"
    );

  if (controls.length >= 4){
    controls[1].textContent = `▱ ${t("overview")}`;
    controls[2].textContent = `☆ ${t("save")}`;
    controls[3].textContent = `↻ ${t("route")}`;
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
        localStorage.getItem(key) ||
        "[]"
      );

    return Array.isArray(value)
      ? value.slice(0,12)
      : [];

  }catch(_){
    return [];
  }
}

function saveStoredDestinations(key,items){
  try{
    localStorage.setItem(
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
  ].forEach(x => {
    const el = byId(x);

    if (el){
      el.classList.toggle(
        "hidden",
        x !== id
      );
    }
  });
}

async function routeByHash(){
  if (
    location.hash.toLowerCase()
    === "#admin"
  ){
    stopGpsWatch();
    showOnly("adminLoginView");
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

      await openUserApp();

      return;
    }

  }catch(_){}

  stopGpsWatch();
  showOnly("userAuthView");
}

window.addEventListener(
  "hashchange",
  routeByHash
);

window.addEventListener(
  "load",
  () => {
    applyAppLanguage();
    updateNetworkBadge();
    routeByHash();
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

  if (!badge) return;

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
    el.classList.add("hidden");
    return;
  }

  el.textContent =
    message;

  el.classList.remove("hidden");

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
          JSON.stringify(payload)
      }
    );

  const data =
    await r.json()
      .catch(() => ({}));

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
          JSON.stringify(payload)
      }
    );

  const data =
    await r.json()
      .catch(() => ({}));

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

    navSearchTimer = null;
  }

  if (proximityEvalTimer){
    clearInterval(
      proximityEvalTimer
    );

    proximityEvalTimer = null;
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

  currentUser = null;
  location.hash = "";

  showOnly("userAuthView");
}

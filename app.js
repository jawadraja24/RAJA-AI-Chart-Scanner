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
  enabled: true,
  voice: true,
  maxDistanceM: 1200,
  urgentDistanceM: 400,
  cooldownS: 300,
  language: "en-GB",
  defaultCountry: "DE",
  cameraWarningMode: "country_compliance"
};

let voiceEnabledByUser =
  localStorage.getItem("roadpulse_voice") !== "off";

let lastAlertedAt = new Map();
let dismissedUntil = new Map();

let currentProximityTarget = null;
let proximityEvalTimer = null;

/* =========================
   NAVIGATION
========================= */

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

/* =========================
   SAVED PLACES
========================= */

let favoriteDestinations =
  loadStoredDestinations(
    "roadpulse_favorites"
  );

let recentDestinations =
  loadStoredDestinations(
    "roadpulse_recent"
  );

/* =========================
   AUDIO
========================= */

let navAudioContext = null;
let navLastChimeKey = null;

/* =========================
   ADMIN
========================= */

let adminData = null;

/* =========================
   SUPPORTED LANGUAGES
========================= */

/*
 IMPORTANT FIX:

 userLanguage MUST be created AFTER
 SUPPORTED_APP_LANGUAGES.

 Otherwise detectInitialLanguage()
 tries to access this const before
 JavaScript has initialized it and
 the whole app crashes.

 That was why Login and #admin
 were not responding.
*/

const SUPPORTED_APP_LANGUAGES = [
  "en-GB",
  "de-DE",
  "it-IT",
  "fr-FR",
  "es-ES",
  "nl-NL",
  "pt-PT",
  "pl-PL",
  "cs-CZ",
  "da-DK",
  "sv-SE",
  "fi-FI",
  "nb-NO",
  "hu-HU",
  "tr-TR",
  "sk-SK",
  "sl-SI",
  "lt-LT",
  "el-GR",
  "bg-BG",
  "ru-RU",
  "ar"
];

/*
 This line is now in the CORRECT place.
*/

let userLanguage =
  localStorage.getItem(
    "roadpulse_language"
  ) ||
  detectInitialLanguage();

/* =========================
   TRANSLATIONS
========================= */

const UI_TRANSLATIONS = {

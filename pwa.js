const ROADPULSE_PWA_BUILD = "webv25navfix1";
let roadPulseInstallPrompt = null;
let roadPulseSwReloading = false;

function roadPulseIsInstalled(){
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

function roadPulseIsIOS(){
  return (
    /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  );
}

function roadPulseIsAndroid(){
  return /android/i.test(navigator.userAgent);
}

function showPwaInstallToast(message){
  const toast = document.getElementById("pwaInstallToast");
  if (!toast) return;

  toast.textContent = message;
  toast.classList.remove("hidden");

  clearTimeout(window.__roadpulsePwaToastTimer);
  window.__roadpulsePwaToastTimer = setTimeout(()=>{
    toast.classList.add("hidden");
  }, 4500);
}

function openRoadPulseInstallHelp(kind){
  const sheet = document.getElementById("installHelpSheet");
  const title = document.getElementById("installHelpTitle");
  const body = document.getElementById("installHelpBody");
  if (!sheet || !title || !body) return;

  if (kind === "ios"){
    title.textContent = "Install RoadPulse on iPhone / iPad";
    body.innerHTML = `
      <p>Safari installs RoadPulse through the Home Screen menu.</p>
      <ol>
        <li>Tap the <strong>Share</strong> button in Safari.</li>
        <li>Choose <strong>Add to Home Screen</strong>.</li>
        <li>Tap <strong>Add</strong>.</li>
      </ol>
    `;
  }else if (kind === "android"){
    title.textContent = "Install RoadPulse on Android";
    body.innerHTML = `
      <p>Your browser has not exposed the direct install prompt yet.</p>
      <ol>
        <li>Open the browser menu <strong>⋮</strong>.</li>
        <li>Choose <strong>Install app</strong> or <strong>Add to Home screen</strong>.</li>
        <li>Confirm <strong>Install</strong>.</li>
      </ol>
    `;
  }else{
    title.textContent = "Install RoadPulse AI";
    body.innerHTML = `
      <p>Use your browser's app installation option.</p>
      <ol>
        <li>Open the browser menu.</li>
        <li>Choose <strong>Install RoadPulse AI</strong> / <strong>Install app</strong>.</li>
        <li>Confirm the installation.</li>
      </ol>
    `;
  }

  sheet.classList.remove("hidden");
}

function closeRoadPulseInstallHelp(){
  document.getElementById("installHelpSheet")?.classList.add("hidden");
}

function updateInstallButton(){
  const btn = document.getElementById("installAppBtn");
  if (!btn) return;

  if (roadPulseIsInstalled()){
    btn.disabled = true;
    btn.classList.add("installed");
    btn.innerHTML = '✓ <span class="install-label">Installed</span>';
    btn.title = "RoadPulse AI is installed";
    return;
  }

  btn.disabled = false;
  btn.classList.remove("installed");
  btn.innerHTML = '⬇ <span class="install-label">Install</span>';

  if (roadPulseIsIOS()){
    btn.title = "Install RoadPulse on iPhone / iPad";
  }else{
    btn.title = "Install RoadPulse AI";
  }
}

async function installRoadPulseApp(){
  if (roadPulseIsInstalled()){
    updateInstallButton();
    return;
  }

  if (roadPulseInstallPrompt){
    const promptEvent = roadPulseInstallPrompt;
    roadPulseInstallPrompt = null;

    try{
      await promptEvent.prompt();
      const choice = await promptEvent.userChoice;

      if (choice?.outcome === "accepted"){
        showPwaInstallToast("RoadPulse AI installation started.");
      }else{
        showPwaInstallToast("Installation cancelled.");
      }
    }catch(err){
      console.error("RoadPulse install prompt failed:", err);
      openRoadPulseInstallHelp(roadPulseIsAndroid() ? "android" : "other");
    }

    updateInstallButton();
    return;
  }

  if (roadPulseIsIOS()){
    openRoadPulseInstallHelp("ios");
    return;
  }

  openRoadPulseInstallHelp(roadPulseIsAndroid() ? "android" : "other");
}

window.addEventListener("beforeinstallprompt", event=>{
  event.preventDefault();
  roadPulseInstallPrompt = event;
  updateInstallButton();
});

window.addEventListener("appinstalled", ()=>{
  roadPulseInstallPrompt = null;
  updateInstallButton();
  closeRoadPulseInstallHelp();
  showPwaInstallToast("RoadPulse AI installed successfully.");
});

window.addEventListener("load", async ()=>{
  updateInstallButton();

  if (!("serviceWorker" in navigator)) return;

  // Only reload on controller replacement when this page was already controlled.
  // This makes a newly deployed app.js/styles.css take effect in installed PWAs.
  const hadController = !!navigator.serviceWorker.controller;
  navigator.serviceWorker.addEventListener("controllerchange", ()=>{
    if (!hadController || roadPulseSwReloading) return;
    roadPulseSwReloading = true;
    window.location.reload();
  });

  try{
    const registration = await navigator.serviceWorker.register(
      "/service-worker.js",
      {scope:"/", updateViaCache:"none"}
    );

    registration.update().catch(()=>{});
  }catch(err){
    console.error("RoadPulse service worker registration failed:", err);
    showPwaInstallToast("Install service could not start. Refresh and try again.");
  }
});

window.installRoadPulseApp = installRoadPulseApp;
window.closeRoadPulseInstallHelp = closeRoadPulseInstallHelp;

let roadPulseInstallPrompt = null;

function roadPulseIsInstalled(){
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

function roadPulseIsIOS(){
  return /iphone|ipad|ipod/i.test(navigator.userAgent);
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

function setInstallButtonState(){
  const btn = document.getElementById("installAppBtn");
  if (!btn) return;

  if (roadPulseIsInstalled()){
    btn.disabled = true;
    btn.classList.add("installed");
    btn.innerHTML = '✓ <span class="install-label">Installed</span>';
    btn.title = "RoadPulse AI is installed";
    return;
  }

  btn.classList.remove("installed");

  // iOS does not expose beforeinstallprompt.
  if (roadPulseIsIOS()){
    btn.disabled = false;
    btn.innerHTML = '⬇ <span class="install-label">Install</span>';
    btn.title = "Add RoadPulse AI to Home Screen";
    return;
  }

  // Chrome/Edge/Android: only enable when the browser has declared the PWA installable.
  if (roadPulseInstallPrompt){
    btn.disabled = false;
    btn.innerHTML = '⬇ <span class="install-label">Install</span>';
    btn.title = "Install RoadPulse AI";
  }else{
    btn.disabled = true;
    btn.innerHTML = '… <span class="install-label">Preparing</span>';
    btn.title = "Preparing install";
  }
}

async function installRoadPulseApp(){
  if (roadPulseIsInstalled()){
    setInstallButtonState();
    return;
  }

  if (roadPulseIsIOS()){
    showPwaInstallToast("iPhone/iPad: tap Share, then Add to Home Screen.");
    return;
  }

  if (!roadPulseInstallPrompt){
    // Button should normally be disabled in this state.
    showPwaInstallToast("Install is still preparing. Refresh once if this remains disabled.");
    setInstallButtonState();
    return;
  }

  const promptEvent = roadPulseInstallPrompt;
  roadPulseInstallPrompt = null;
  setInstallButtonState();

  try{
    // Must be called directly from the user's click.
    await promptEvent.prompt();
    const choice = await promptEvent.userChoice;

    if (choice && choice.outcome === "accepted"){
      showPwaInstallToast("RoadPulse AI installation started.");
    }else{
      showPwaInstallToast("Installation cancelled.");
    }
  }catch(err){
    console.error("RoadPulse install prompt failed:", err);
    showPwaInstallToast("Install prompt could not open. Refresh and try again.");
  }
}

window.addEventListener("beforeinstallprompt", event=>{
  event.preventDefault();
  roadPulseInstallPrompt = event;
  setInstallButtonState();
});

window.addEventListener("appinstalled", ()=>{
  roadPulseInstallPrompt = null;
  setInstallButtonState();
  showPwaInstallToast("RoadPulse AI installed successfully.");
});

window.addEventListener("load", ()=>{
  setInstallButtonState();

  if ("serviceWorker" in navigator){
    navigator.serviceWorker
      .register("/service-worker.js", {scope:"/"})
      .then(()=> {
        // Registration succeeded. beforeinstallprompt will enable the button
        // once the browser finishes its own installability checks.
      })
      .catch(err=>{
        console.error("RoadPulse service worker registration failed:", err);
        showPwaInstallToast("App install service could not start. Refresh and try again.");
      });
  }
});

window.installRoadPulseApp = installRoadPulseApp;

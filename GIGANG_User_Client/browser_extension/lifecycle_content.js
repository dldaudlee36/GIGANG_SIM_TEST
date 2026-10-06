(() => {
    let pausedUntil=0, busy=false;
    globalThis.GIGANGPaused=()=>performance.now()<pausedUntil;
    async function update() {
        if(busy)return;
        busy=true;
        const started=performance.now();
        try {
            const state=await chrome.runtime.sendMessage({type:'GIGANG_RUN_MODE'});
            // Expire from request start, so a delayed reply cannot extend stale STOP.
            pausedUntil=state?.paused ? started+1500 : 0;
            if(globalThis.GIGANGPaused())document.getElementById('gigang-image-guard')?.remove();
        } catch { pausedUntil=0; }
        finally {busy=false;}
    }
    void update();
    setInterval(update,750);
    document.addEventListener('visibilitychange',()=>void update());
})();

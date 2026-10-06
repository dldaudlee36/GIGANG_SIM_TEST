// Missing Agent/bridge is not a normal STOP. Only an explicit launcher mode pauses checks.
const GIGANGMode = (() => {
    async function paused() {
        try {
            const response=await fetch('http://127.0.0.1:8766/mode',{
                credentials:'omit',redirect:'error',cache:'no-store',signal:AbortSignal.timeout(1200)});
            const state=await response.json();
            return response.ok && state.service==='GIGANGLifecycle' && state.mode==='stopped';
        } catch { return false; }
    }
    chrome.runtime.onMessage.addListener((message,sender,respond)=>{
        if(sender.id!==chrome.runtime.id || message?.type!=='GIGANG_RUN_MODE') return false;
        paused().then(value=>respond({paused:value}),()=>respond({paused:false}));
        return true;
    });
    return {paused};
})();

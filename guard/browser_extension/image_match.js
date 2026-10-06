// Only salted DB cell hashes are retained, in extension session storage (30 minutes).
const ImageMatch = (() => {
    const TTL = 30 * 60 * 1000;
    const normalize = s => String(s).normalize('NFKC').toLowerCase().replace(/[^\p{L}\p{N}]/gu, '');
    const digest = async s => Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s))),
        b => b.toString(16).padStart(2,'0')).join('');
    const hash = (seed, value) => digest(seed + '\0image-cell\0' + value);
    const aiDomains = ['chatgpt.com','chat.openai.com','claude.ai','gemini.google.com','aistudio.google.com',
        'copilot.microsoft.com','perplexity.ai','grok.com','chat.deepseek.com'];
    const isAI = host => aiDomains.some(d => host === d || host.endsWith('.' + d));
    function validRows(rows, now=Date.now()) {
        return (rows || []).filter(r => r.observed <= now && now - r.observed < TTL);
    }
    async function snapshot(rows, seed, now=Date.now()) {
        if (!Array.isArray(rows) || rows.length > 500) throw new Error('INVALID_DB_SNAPSHOT');
        const out = [];
        for (const cells of rows) {
            if (!Array.isArray(cells) || cells.length > 30) throw new Error('INVALID_DB_SNAPSHOT');
            const tokens = [];
            for (const cell of cells) {
                if (typeof cell !== 'string' || cell.length > 256 || /[*●•]/.test(cell)) continue;
                const value = normalize(cell);
                if (value.length < 3 || value.length > 32 || /^(0+|검색결과없음|데이터없음)$/.test(value)) continue;
                const numeric = /^\d+$/.test(value);
                // Short IDs, dates, balances, names alone are insufficient evidence.
                if (numeric && value.length < 8) continue;
                tokens.push({hash:await hash(seed,value), length:value.length, strong:numeric && value.length >= 13});
            }
            const unique = [...new Map(tokens.map(t=>[t.hash,t])).values()];
            if (unique.length) out.push({tokens:unique,observed:now,trace_id:crypto.randomUUID(),timestamp:new Date(now).toISOString()});
        }
        return out;
    }
    async function match(lines, rows, seed, now=Date.now()) {
        rows = validRows(rows, now);
        if (!rows.length) return {status:'hold',error:'DB_BASELINE_MISSING'};
        if (!Array.isArray(lines) || lines.some(s=>typeof s !== 'string')) return {status:'hold',error:'INVALID_OCR'};
        const text = normalize(lines.join(' '));
        if (!text) return {status:'hold',error:'OCR_NO_TEXT'};
        if (text.length > 24000) return {status:'hold',error:'OCR_TEXT_TOO_LONG'};
        const byLength = new Map();
        for (const row of rows) for (const t of row.tokens) {
            if (!byLength.has(t.length)) byLength.set(t.length,new Set());
            byLength.get(t.length).add(t.hash);
        }
        if ([...byLength.keys()].reduce((n,l)=>n+Math.max(0,text.length-l+1),0)>250000)
            return {status:'hold',error:'MATCH_WORK_LIMIT'};
        const found = new Set();
        for (const [length,wanted] of byLength) {
            for (let start=0; start<=text.length-length; start+=128) {
                const jobs=[];
                for (let i=start;i<Math.min(start+128,text.length-length+1);i++) jobs.push(hash(seed,text.slice(i,i+length)));
                for (const value of await Promise.all(jobs)) if(wanted.has(value)) found.add(value);
            }
        }
        for (const row of rows) {
            const hits=row.tokens.filter(t=>found.has(t.hash));
            if (hits.some(t=>t.strong) || hits.length>=3) {
                return {status:'blocked',evidence:{source_trace_id:row.trace_id,source_kind:'DB_SCREEN_VIEW',
                    source_domain:'desktop-oli.tail2bbbea.ts.net',source_path:'/db',source_time:row.timestamp,
                    method:'windows_ocr_db_cells',age_seconds:Math.floor((now-row.observed)/1000),
                    candidate_count:1,matched_fields:hits.length}};
            }
        }
        return {status:'allow',matched_fields:0};
    }
    return {TTL,normalize,digest,hash,isAI,validRows,snapshot,match};
})();

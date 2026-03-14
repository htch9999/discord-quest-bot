/**
 * Live stats fetcher — polls /v1/stats/public every 30s
 */
(function () {
  const INTERVAL = 30000;

  function fmt(n) { return n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : n.toLocaleString(); }
  function uptime(s) { const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60); return d>0?`${d}d ${h}h ${m}m`:h>0?`${h}h ${m}m`:`${m}m`; }

  function updateHero(d) {
    const m = {'stat-users':d.total_users,'stat-quests':d.total_quests_completed,'stat-servers':d.guild_count,'stat-uptime':uptime(d.uptime_seconds)};
    for (const [id,v] of Object.entries(m)) { const e=document.getElementById(id); if(e) e.textContent=typeof v==='number'?fmt(v):v; }
  }

  function updateDash(d) {
    const m = {'dash-today':d.quests_today,'dash-week':d.quests_this_week,'dash-total':d.total_quests_completed,'dash-active':d.active_sessions,'dash-ping':d.bot_ping_ms>=0?d.bot_ping_ms+'ms':'N/A','dash-uptime':uptime(d.uptime_seconds)};
    for (const [id,v] of Object.entries(m)) { const e=document.getElementById(id); if(e){e.textContent=typeof v==='number'?fmt(v):v;e.classList.remove('skeleton');} }
    const bc=document.getElementById('quest-bars');
    if(bc&&d.quest_type_breakdown){bc.innerHTML='';for(const[type,pct]of Object.entries(d.quest_type_breakdown)){const i=document.createElement('div');i.className='bar-item';i.innerHTML=`<span class="bar-label">${type}</span><div class="bar-track"><div class="bar-fill" style="width:${pct*100}%"></div></div><span class="bar-value">${Math.round(pct*100)}%</span>`;bc.appendChild(i);}}
    const ts=document.getElementById('stats-timestamp');if(ts&&d.cached_at)ts.textContent=new Date(d.cached_at).toLocaleTimeString();
  }

  async function fetch_() {
    const API = window.API_BASE || '';
    try { const r=await fetch(`${API}/v1/stats/public`); if(!r.ok)return; const d=await r.json(); updateHero(d); updateDash(d); } catch(e){}
  }

  window.statsInit = function() { fetch_(); setInterval(fetch_, INTERVAL); };
})();

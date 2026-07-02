"""Generate the self-contained robustness-explorer HTML from the live non-price
study CSV. Re-run any time to refresh the baked-in data as more series score.

    PYTHONPATH=src python benchmarks/comparisons/make_robustness_page.py \
        [results.csv] [out.html]

Bakes, per scored series: the per-method scores (crps, logpdf) plus metadata the
page filters on — asset class, family, first letter, history length, grid mass
(repeat structure), volatility, tail (excess kurtosis), lag-1 autocorrelation,
volatility-clustering, weekly-lag autocorrelation, and sampling cadence. All
win-rate math happens client-side over the selected subset.
"""
import csv
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))  # benchmarks/
import fred
import fred_universe as fu

CAP = 6000  # match study.py's most-recent-N window


def _stats(changes):
    x = changes[-CAP:]
    n = len(x)
    if n < 20:
        return None
    mean = sum(x) / n
    var = sum((v - mean) ** 2 for v in x) / n
    sd = math.sqrt(var) or 1e-12
    # excess kurtosis (heavy tails)
    m4 = sum((v - mean) ** 4 for v in x) / n
    kurt = m4 / (var * var) - 3.0 if var > 0 else 0.0
    # grid mass: modal fraction of a single (rounded) change value -> lattice-ness
    from collections import Counter
    q = Counter(round(v, 12) for v in x)
    grid_mass = q.most_common(1)[0][1] / n

    def acf(series, lag):
        m = sum(series) / len(series)
        num = sum((series[i] - m) * (series[i + lag] - m) for i in range(len(series) - lag))
        den = sum((v - m) ** 2 for v in series) or 1e-12
        return num / den

    ac1 = acf(x, 1) if n > 2 else 0.0
    absx = [abs(v) for v in x]
    absac1 = acf(absx, 1) if n > 2 else 0.0
    seas5 = acf(x, 5) if n > 6 else 0.0
    return {
        "n": n, "vol": sd, "kurt": kurt, "gridMass": grid_mass,
        "ac1": ac1, "absac1": absac1, "seas5": seas5,
    }


def build(results_csv):
    rows = list(csv.DictReader(open(results_csv)))
    scored = sorted({r["series"] for r in rows})
    # titles
    uj = os.path.join(fred._CACHE, "universe_daily.json")
    titles = {s["id"]: s.get("title", "") for s in json.load(open(uj))} if os.path.exists(uj) else {}

    scores = {}
    for r in rows:
        try:
            lp = float(r["logpdf"]); cr = float(r["crps"])
        except (ValueError, KeyError):
            continue
        scores.setdefault(r["series"], {})[r["method"]] = {
            "logpdf": lp, "crps": cr, "n": int(float(r.get("n", 0) or 0)),
        }

    series = []
    for sid in scored:
        if "laplace" not in scores.get(sid, {}):
            continue  # need the reference
        levels = fred._load_levels(sid)
        ch = fred._to_changes(levels) if levels else []
        st = _stats(ch)
        if not st:
            continue
        title = titles.get(sid, "")
        # sampling cadence: mean gap in calendar days between observations
        gap = None
        if levels and len(levels) > 30:
            import datetime as _dt
            ds = []
            for d, _ in levels[-500:]:
                try:
                    ds.append(_dt.date.fromisoformat(d))
                except ValueError:
                    pass
            if len(ds) > 5:
                gaps = [(ds[i + 1] - ds[i]).days for i in range(len(ds) - 1)]
                gaps = [g for g in gaps if g > 0]
                gap = sum(gaps) / len(gaps) if gaps else None
        series.append({
            "id": sid,
            "title": title,
            "cls": fu.asset_class(title),
            "fam": fu.family(sid),
            "letter": sid[0].upper() if sid else "?",
            "histYears": round(st["n"] / 252.0, 1),
            **{k: round(v, 6) for k, v in st.items()},
            "gap": round(gap, 2) if gap else None,
        })

    methods = sorted({r["method"] for r in rows if r["method"] != "laplace"})
    return {"series": series, "scores": scores, "methods": methods}


PAGE = r"""<title>Non-price robustness explorer — skaters</title>
<meta name="description" content="Slice the non-price forecasting benchmark any way you like and watch laplace's win-rate hold.">
<style>
  :root{
    --ground:#0f1419; --panel:#161d26; --panel2:#1b232e; --line:#243040;
    --ink:#e6edf3; --muted:#8493a5; --faint:#5b6672;
    --accent:#5aa2ff; --win:#3fb950; --loss:#e5804a; --neutral:#4a5666;
    --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
    --sans:ui-sans-serif,-apple-system,"SF Pro Text","Segoe UI",Roboto,sans-serif;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
    font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
  .wrap{max-width:1180px;margin:0 auto;padding:20px 24px 64px}
  .topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;
    padding:10px 0 18px;font-family:var(--mono);font-size:12px;color:var(--muted)}
  .topbar a{color:var(--accent);text-decoration:none}
  .topbar a:hover{text-decoration:underline}
  .topbar .mid{color:var(--faint);letter-spacing:.08em;text-transform:uppercase}
  header{border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:24px}
  .eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.18em;text-transform:uppercase;
    color:var(--accent);margin:0 0 8px}
  h1{font-size:26px;font-weight:650;margin:0 0 6px;letter-spacing:-.01em;text-wrap:balance}
  .sub{color:var(--muted);max-width:66ch;margin:0}
  .layout{display:grid;grid-template-columns:300px 1fr;gap:24px;align-items:start}
  @media(max-width:820px){.layout{grid-template-columns:1fr}}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:10px}
  .rail{position:sticky;top:16px;padding:4px}
  .grp{padding:14px 16px;border-bottom:1px solid var(--line)}
  .grp:last-child{border-bottom:0}
  .grp h3{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;
    color:var(--muted);margin:0 0 10px;font-weight:600}
  label.mode{display:flex;align-items:center;gap:8px;padding:5px 0;cursor:pointer;font-size:14px}
  input[type=radio],input[type=checkbox]{accent-color:var(--accent);width:15px;height:15px;cursor:pointer}
  .chips{display:flex;flex-wrap:wrap;gap:5px}
  .chip{font-family:var(--mono);font-size:12px;padding:3px 8px;border:1px solid var(--line);
    border-radius:5px;background:var(--panel2);color:var(--muted);cursor:pointer;user-select:none}
  .chip.on{background:var(--accent);border-color:var(--accent);color:#06101f;font-weight:600}
  .letters .chip{padding:2px 6px;min-width:22px;text-align:center}
  input[type=text]{width:100%;background:var(--panel2);border:1px solid var(--line);border-radius:6px;
    color:var(--ink);padding:7px 9px;font-family:var(--mono);font-size:13px}
  input[type=text]:focus,button:focus-visible,.chip:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
  input[type=range]{width:100%;accent-color:var(--accent)}
  .rowflex{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
  .val{font-family:var(--mono);color:var(--ink);font-variant-numeric:tabular-nums}
  button{font-family:var(--sans);font-size:13px;font-weight:600;background:var(--accent);color:#06101f;
    border:0;border-radius:6px;padding:8px 12px;cursor:pointer;width:100%}
  button.ghost{background:var(--panel2);color:var(--muted);border:1px solid var(--line)}
  button:hover{filter:brightness(1.08)}
  /* results */
  .summary{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px}
  .stat{flex:1;min-width:150px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
  .stat .k{font-family:var(--mono);font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
  .stat .v{font-family:var(--mono);font-size:28px;font-variant-numeric:tabular-nums;margin-top:4px}
  .stat .v small{font-size:14px;color:var(--muted)}
  .metricbar{display:inline-flex;gap:2px;margin-left:8px;vertical-align:middle}
  .metricbar button{width:auto;padding:4px 10px;font-size:12px;background:var(--panel2);color:var(--muted);border:1px solid var(--line)}
  .metricbar button.on{background:var(--accent);color:#06101f;border-color:var(--accent)}
  table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
  th,td{padding:9px 8px;text-align:left;border-bottom:1px solid var(--line)}
  th{font-family:var(--mono);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--faint);font-weight:600}
  td.m{font-family:var(--mono);font-size:13px;white-space:nowrap}
  td.num{font-family:var(--mono);text-align:right;font-size:13px}
  .barcell{width:52%;min-width:220px}
  .track{position:relative;height:22px;background:var(--panel2);border-radius:4px;overflow:hidden}
  .mid{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--faint);z-index:3}
  .fill{position:absolute;top:0;bottom:0;border-radius:4px 0 0 4px;z-index:1;transition:width .25s,background .25s}
  .ci{position:absolute;top:50%;height:2px;background:rgba(230,237,243,.55);transform:translateY(-50%);z-index:2}
  .ci::before,.ci::after{content:"";position:absolute;top:-3px;height:8px;width:1.5px;background:rgba(230,237,243,.7)}
  .ci::before{left:0}.ci::after{right:0}
  .ratetag{position:absolute;right:6px;top:50%;transform:translateY(-50%);font-family:var(--mono);
    font-size:12px;font-weight:600;color:var(--ink);z-index:4;text-shadow:0 1px 2px rgba(0,0,0,.6)}
  .note{color:var(--muted);font-size:12.5px;margin-top:16px;line-height:1.6}
  .note code{font-family:var(--mono);color:var(--ink);background:var(--panel2);padding:1px 5px;border-radius:4px}
  .empty{color:var(--loss);font-family:var(--mono);font-size:13px;padding:18px 0}
  .legend{display:flex;gap:16px;font-size:12px;color:var(--muted);margin-bottom:10px;align-items:center;flex-wrap:wrap}
  .swatch{display:inline-block;width:11px;height:11px;border-radius:2px;vertical-align:middle;margin-right:5px}
</style>

<div class="wrap">
  <nav class="topbar">
    <a href="/">← skaters</a>
    <span class="mid">non-price robustness explorer</span>
    <a href="https://github.com/microprediction/skaters">GitHub</a>
  </nav>
  <header>
    <p class="eyebrow">skaters · non-price benchmark</p>
    <h1>How robust is the win? Slice it and see.</h1>
    <p class="sub">Every non-price FRED change-series scored so far, one-step-ahead, held-out. Pick any
      subset — sample it at random, balance by category, filter by keyword, seasonality, tails, whatever —
      and the per-series win-rate of <b>laplace</b> against each opponent recomputes live, with a bootstrap
      90% band. A robust edge stays high <em>and</em> tight no matter how you cut the data.</p>
  </header>

  <div class="layout">
    <aside class="panel rail">
      <div class="grp">
        <h3>Sampling mode</h3>
        <label class="mode"><input type="radio" name="mode" value="all" checked> Everything selected</label>
        <label class="mode"><input type="radio" name="mode" value="random"> Random sample</label>
        <label class="mode"><input type="radio" name="mode" value="balanced"> Category-balanced sample</label>
        <div id="randbox" style="display:none;margin-top:10px">
          <div class="rowflex"><span>size <span class="val" id="kval">20</span></span></div>
          <input type="range" id="ksize" min="5" max="200" value="20">
          <button class="ghost" id="resample" style="margin-top:8px">↻ Resample</button>
        </div>
      </div>
      <div class="grp">
        <h3>Category</h3>
        <div class="chips" id="cats"></div>
      </div>
      <div class="grp">
        <h3>Keyword in title</h3>
        <input type="text" id="kw" placeholder="e.g. treasury, spread, rate">
      </div>
      <div class="grp">
        <h3>First letter of series id</h3>
        <div class="chips letters" id="letters"></div>
      </div>
      <div class="grp">
        <h3>Structure filters</h3>
        <div id="buckets"></div>
      </div>
      <div class="grp">
        <button class="ghost" id="reset">Reset all filters</button>
      </div>
    </aside>

    <main>
      <div class="summary">
        <div class="stat"><div class="k">Series selected</div><div class="v" id="nsel">0<small id="ntot"></small></div></div>
        <div class="stat"><div class="k">laplace mean logpdf</div><div class="v" id="mll">–</div></div>
        <div class="stat"><div class="k">Opponents beaten (LL &gt;50%)</div><div class="v" id="nbeat">–</div></div>
      </div>

      <div class="legend">
        <span>metric
          <span class="metricbar">
            <button data-metric="logpdf" class="on">log-likelihood</button><button data-metric="crps">CRPS</button>
          </span>
        </span>
        <span><span class="swatch" style="background:var(--win)"></span>laplace wins &gt;50%</span>
        <span><span class="swatch" style="background:var(--loss)"></span>&lt;50%</span>
        <span>│ whisker = bootstrap 90% CI · vertical line = 50%</span>
      </div>

      <div class="panel" style="padding:6px 14px 10px">
        <table>
          <thead><tr>
            <th>Opponent</th><th class="barcell">laplace win-rate (per series)</th>
            <th class="num">rate</th><th class="num">N</th>
          </tr></thead>
          <tbody id="tbody"></tbody>
        </table>
        <div class="empty" id="empty" style="display:none">No series match this selection — loosen a filter.</div>
      </div>

      <p class="note" id="foot"></p>
    </main>
  </div>
</div>

<script>
const DATA = __DATA__;
const S = DATA.series, SC = DATA.scores, METHODS = DATA.methods;
const byId = Object.fromEntries(S.map(d=>[d.id,d]));
let metric = "logpdf";
let randomPick = null;  // cached id set for random/balanced modes

// ---- bucket definitions (terciles computed from the data) ----
function terciles(key){
  const vs = S.map(d=>d[key]).filter(v=>v!=null&&!isNaN(v)).sort((a,b)=>a-b);
  if(!vs.length) return [0,0];
  return [vs[Math.floor(vs.length/3)], vs[Math.floor(2*vs.length/3)]];
}
const BUCKETS = [
  {key:"vol",     label:"Volatility"},
  {key:"kurt",    label:"Tail weight (kurtosis)"},
  {key:"seas5",   label:"Weekly autocorr (lag-5)"},
  {key:"absac1",  label:"Vol clustering (|Δ| lag-1)"},
  {key:"gridMass",label:"Repeat / grid mass"},
  {key:"histYears",label:"History length"},
].map(b=>{const t=terciles(b.key);return {...b,lo:t[0],hi:t[1]}});
const bucketState = {}; // key -> Set of {low,mid,high}

// ---- build controls ----
const cats = [...new Set(S.map(d=>d.cls))].sort();
const catSel = new Set(cats);
const catBox = document.getElementById("cats");
cats.forEach(c=>{
  const el=document.createElement("span"); el.className="chip on"; el.textContent=c+" ("+S.filter(d=>d.cls===c).length+")";
  el.onclick=()=>{ if(catSel.has(c)){catSel.delete(c);el.classList.remove("on")}else{catSel.add(c);el.classList.add("on")} render(); };
  catBox.appendChild(el);
});
const letters=[...new Set(S.map(d=>d.letter))].sort();
const letSel=new Set();
const letBox=document.getElementById("letters");
letters.forEach(L=>{
  const el=document.createElement("span"); el.className="chip"; el.textContent=L;
  el.onclick=()=>{ if(letSel.has(L)){letSel.delete(L);el.classList.remove("on")}else{letSel.add(L);el.classList.add("on")} render(); };
  letBox.appendChild(el);
});
const bBox=document.getElementById("buckets");
BUCKETS.forEach(b=>{
  bucketState[b.key]=new Set();
  const row=document.createElement("div"); row.style.marginBottom="9px";
  const h=document.createElement("div"); h.style.cssText="font-size:12px;color:var(--muted);margin-bottom:4px"; h.textContent=b.label;
  const ch=document.createElement("div"); ch.className="chips";
  [["low","low"],["mid","mid"],["high","high"]].forEach(([k,lab])=>{
    const el=document.createElement("span"); el.className="chip"; el.textContent=lab;
    el.onclick=()=>{ const st=bucketState[b.key]; if(st.has(k)){st.delete(k);el.classList.remove("on")}else{st.add(k);el.classList.add("on")} render(); };
    ch.appendChild(el);
  });
  row.appendChild(h); row.appendChild(ch); bBox.appendChild(row);
});
function bucketOf(d,b){ if(d[b.key]==null) return null; return d[b.key]<=b.lo?"low":(d[b.key]<=b.hi?"mid":"high"); }

// ---- selection pipeline ----
function baseFiltered(){
  const kw=document.getElementById("kw").value.trim().toLowerCase();
  return S.filter(d=>{
    if(!catSel.has(d.cls)) return false;
    if(letSel.size && !letSel.has(d.letter)) return false;
    if(kw && !(d.title.toLowerCase().includes(kw)||d.id.toLowerCase().includes(kw))) return false;
    for(const b of BUCKETS){ const st=bucketState[b.key]; if(st.size){ const bk=bucketOf(d,b); if(!st.has(bk)) return false; } }
    return true;
  });
}
function mode(){ return document.querySelector('input[name=mode]:checked').value; }
function shuffle(a){ a=a.slice(); for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];} return a; }
function selection(){
  let pool=baseFiltered();
  const m=mode();
  if(m==="all") return pool;
  const k=+document.getElementById("ksize").value;
  if(m==="random"){
    if(!randomPick) randomPick=shuffle(pool.map(d=>d.id)).slice(0,k);
    const set=new Set(randomPick); return pool.filter(d=>set.has(d.id));
  }
  if(m==="balanced"){
    // equalize per category: draw k/|cats| from each present category
    if(!randomPick){
      const present=[...new Set(pool.map(d=>d.cls))];
      const per=Math.max(1,Math.floor(k/present.length)); const picked=[];
      present.forEach(c=>{ picked.push(...shuffle(pool.filter(d=>d.cls===c).map(d=>d.id)).slice(0,per)); });
      randomPick=picked;
    }
    const set=new Set(randomPick); return pool.filter(d=>set.has(d.id));
  }
  return pool;
}

// ---- scoring ----
function winForSubset(ids,method,met){
  let n=0,w=0;
  for(const id of ids){ const s=SC[id]; if(!s||!s.laplace||!s[method]) continue;
    const a=s.laplace[met], b=s[method][met]; if(a==null||b==null||isNaN(a)||isNaN(b)) continue;
    n++; if(met==="logpdf"){ if(a>b) w++; } else { if(a<b) w++; } }
  return {n, rate: n? w/n : null};
}
function bootstrapCI(ids,method,met,B=300){
  const valid=ids.filter(id=>{const s=SC[id];return s&&s.laplace&&s[method]&&s.laplace[met]!=null&&s[method][met]!=null;});
  if(valid.length<3) return null;
  const rates=[];
  for(let b=0;b<B;b++){ let w=0;
    for(let i=0;i<valid.length;i++){ const id=valid[Math.floor(Math.random()*valid.length)]; const s=SC[id];
      const A=s.laplace[met],Bv=s[method][met]; if(met==="logpdf"){if(A>Bv)w++}else{if(A<Bv)w++} }
    rates.push(w/valid.length); }
  rates.sort((a,b)=>a-b);
  return [rates[Math.floor(.05*B)], rates[Math.floor(.95*B)]];
}

// ---- render ----
function render(){
  const sel=selection(), ids=sel.map(d=>d.id);
  document.getElementById("nsel").firstChild.nodeValue=String(sel.length);
  document.getElementById("ntot").textContent=" / "+S.length;
  // laplace mean logpdf
  const lls=ids.map(id=>SC[id]&&SC[id].laplace&&SC[id].laplace.logpdf).filter(v=>v!=null&&!isNaN(v));
  document.getElementById("mll").innerHTML = lls.length? (lls.reduce((a,b)=>a+b,0)/lls.length).toFixed(3) : "–";

  const tb=document.getElementById("tbody"); tb.innerHTML="";
  const empty=document.getElementById("empty");
  if(!sel.length){ empty.style.display="block"; document.getElementById("nbeat").textContent="–"; document.getElementById("mll").textContent="–"; return; }
  empty.style.display="none";

  const results=METHODS.map(mth=>{ const wr=winForSubset(ids,mth,metric); return {mth,...wr,ci:bootstrapCI(ids,mth,metric)}; })
    .filter(r=>r.n>0).sort((a,b)=>b.rate-a.rate);
  let beaten=0;
  results.forEach(r=>{
    if(r.rate>=0.5) beaten++;
    const tr=document.createElement("tr");
    const win=r.rate>=0.5;
    const col=win?"var(--win)":"var(--loss)";
    const ci=r.ci?`<div class="ci" style="left:${(r.ci[0]*100).toFixed(1)}%;width:${((r.ci[1]-r.ci[0])*100).toFixed(1)}%"></div>`:"";
    tr.innerHTML=`<td class="m">${r.mth}</td>
      <td class="barcell"><div class="track">
        <div class="fill" style="width:${(r.rate*100).toFixed(1)}%;background:${col}"></div>
        <div class="mid"></div>${ci}
        <span class="ratetag">${(r.rate*100).toFixed(0)}%</span>
      </div></td>
      <td class="num" style="color:${col}">${(r.rate*100).toFixed(1)}%</td>
      <td class="num">${r.n}</td>`;
    tb.appendChild(tr);
  });
  document.getElementById("nbeat").innerHTML=beaten+"<small> / "+results.length+"</small>";
}

// ---- wiring ----
document.querySelectorAll('input[name=mode]').forEach(r=>r.addEventListener("change",()=>{
  document.getElementById("randbox").style.display = mode()==="all"?"none":"block";
  randomPick=null; render();
}));
document.getElementById("ksize").addEventListener("input",e=>{ document.getElementById("kval").textContent=e.target.value; randomPick=null; render(); });
document.getElementById("resample").addEventListener("click",()=>{ randomPick=null; render(); });
document.getElementById("kw").addEventListener("input",()=>{ randomPick=null; render(); });
document.querySelectorAll(".metricbar button").forEach(b=>b.addEventListener("click",()=>{
  metric=b.dataset.metric; document.querySelectorAll(".metricbar button").forEach(x=>x.classList.toggle("on",x===b)); render();
}));
document.getElementById("reset").addEventListener("click",()=>{
  cats.forEach(c=>catSel.add(c)); catBox.querySelectorAll(".chip").forEach(c=>c.classList.add("on"));
  letSel.clear(); letBox.querySelectorAll(".chip").forEach(c=>c.classList.remove("on"));
  Object.values(bucketState).forEach(s=>s.clear()); bBox.querySelectorAll(".chip").forEach(c=>c.classList.remove("on"));
  document.getElementById("kw").value=""; document.querySelector('input[value=all]').checked=true;
  document.getElementById("randbox").style.display="none"; randomPick=null; render();
});
document.getElementById("foot").innerHTML =
  `Baked from <code>__CSV__</code> · __NSER__ non-price series scored so far · win-rate = fraction of the selected series where `+
  `laplace's held-out score beats the opponent's (log-likelihood: higher wins; CRPS: lower wins). Price series `+
  `(equity/fx/commodity) are excluded by construction — laplace is not a price-series model. As more series `+
  `score, re-generate to widen the sample; bands tighten accordingly.`;
render();
</script>
"""


def main(argv):
    results = argv[0] if argv else os.path.join(_HERE, "_shared_R25_nonprice.csv")
    out = argv[1] if len(argv) > 1 else os.path.join(_HERE, "robustness.html")
    standalone = "--standalone" in argv
    data = build(results)
    html = (PAGE
            .replace("__DATA__", json.dumps(data, separators=(",", ":")))
            .replace("__CSV__", os.path.basename(results))
            .replace("__NSER__", str(len(data["series"]))))
    if standalone:
        # split the Artifact fragment at </style> into head + body, wrap as a full doc
        head, body = html.split("</style>", 1)
        html = ("<!doctype html>\n<html lang=\"en\">\n<head>\n"
                "<meta charset=\"utf-8\">\n"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
                "<link rel=\"icon\" href=\"/favicon.ico\">\n"
                + head + "</style>\n</head>\n<body>\n" + body + "\n</body>\n</html>\n")
    open(out, "w").write(html)
    print(f"[page] {len(data['series'])} series, {len(data['methods'])} opponents "
          f"({'standalone' if standalone else 'fragment'}) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

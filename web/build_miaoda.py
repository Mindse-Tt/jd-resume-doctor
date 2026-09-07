# -*- coding: utf-8 -*-
"""生成妙搭静态前端 dist/index.html。

能力体检那一层是纯文本正则，能在浏览器里跑；维度数据直接从
kb/role_profiles/*.yaml 生成，避免前端和引擎两套标准跑偏。

    python3 web/build_miaoda.py [role] [out_dir]
"""
import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.profile import CONCRETE, JARGON, REASONING, RIGOR  # noqa: E402


def collect(role: str) -> dict:
    prof = yaml.safe_load(
        open(os.path.join(ROOT, "kb", "role_profiles", f"{role}.yaml"), encoding="utf-8"))
    return {
        "role": prof["role"], "name": prof["name"], "version": prof.get("version", ""),
        "note": (prof.get("note") or "").strip(),
        "bands": prof["bands"],
        "dimensions": [{
            "id": d["id"], "name": d["name"], "weight": d["weight"],
            "why": (d.get("why") or "").strip(),
            "probe": d.get("probe", ""), "trap": d.get("trap", ""),
            "levels": d.get("levels", {}),
            "signals": d.get("signals", []),
        } for d in prof["dimensions"]],
        "patterns": {
            "reasoning": REASONING.pattern,
            "rigor": RIGOR.pattern,
            "jargon": JARGON.pattern,
            "concrete": CONCRETE.pattern,
        },
    }


HTML = r"""<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI 产品简历体检</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@500;600&display=swap">
<style>
:root{
  --paper:#F7F9FA;--card:#FFF;--sunk:#F1F5F7;--ink:#0E1519;--muted:#5E6E7A;--line:#DCE3E8;
  --acc:#005FA2;--acc-soft:#E9F1F8;--acc-line:#B7D2E6;
  --ok:#1B6E45;--ok-bg:#E6F3EB;--ok-line:#B6DCC6;
  --warn:#9A5B08;--warn-bg:#FAF0E1;--warn-line:#E6CFA6;
  --crit:#A32330;--crit-bg:#FBEAEC;--crit-line:#EBC0C5;
  --serif:"IBM Plex Serif","Songti SC",serif;
  --sans:"IBM Plex Sans","PingFang SC","Microsoft YaHei",sans-serif;
  --mono:"IBM Plex Mono","SF Mono",Menlo,monospace;
  --sh:0 1px 2px rgba(14,21,25,.05),0 8px 22px -14px rgba(14,21,25,.18);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#0D1317;--card:#151D23;--sunk:#111920;--ink:#E6EDF2;--muted:#93A3AF;--line:#25313A;
  --acc:#5CAFE6;--acc-soft:#132738;--acc-line:#28455C;
  --ok:#63C795;--ok-bg:#122619;--ok-line:#23472F;
  --warn:#DDA355;--warn-bg:#291F12;--warn-line:#4A3919;
  --crit:#EE7381;--crit-bg:#2C1418;--crit-line:#502228;
  --sh:0 1px 2px rgba(0,0,0,.4),0 10px 26px -16px rgba(0,0,0,.7);}}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:16px;line-height:1.7}
.page{max-width:940px;margin:0 auto;padding:0 20px 88px}
header{padding:56px 0 26px;border-bottom:1px solid var(--line);margin-bottom:32px}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--acc);margin:0 0 14px;display:flex;align-items:center;gap:10px}
.eyebrow::after{content:"";flex:1;height:1px;background:var(--acc-line)}
h1{font-family:var(--serif);font-weight:600;font-size:clamp(30px,5vw,44px);line-height:1.12;
  margin:0 0 10px;letter-spacing:-.02em}
.lede{font-size:17px;color:var(--muted);margin:0;max-width:660px}
h2{font-family:var(--serif);font-size:22px;font-weight:600;margin:44px 0 6px}
.sec-num{font-family:var(--mono);font-size:11px;color:var(--acc);letter-spacing:.12em;
  display:block;margin-bottom:10px}
.sub{color:var(--muted);font-size:15px;margin:0 0 18px;max-width:680px}
textarea{width:100%;min-height:250px;border:1px solid var(--line);border-radius:10px;
  padding:14px 16px;font:14px/1.75 var(--sans);background:var(--card);color:var(--ink);resize:vertical}
textarea:focus{outline:2px solid var(--acc);outline-offset:1px}
.row{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-top:12px}
button{font:600 15px var(--sans);border:0;border-radius:9px;padding:11px 22px;cursor:pointer;
  background:var(--acc);color:#fff}
button.ghost{background:transparent;color:var(--acc);border:1px solid var(--acc-line)}
button:disabled{opacity:.45;cursor:not-allowed}
.hint{color:var(--muted);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:18px 20px;
  box-shadow:var(--sh);margin-bottom:12px}
.hero{display:flex;gap:22px;align-items:center;flex-wrap:wrap}
.dial{width:110px;height:110px;border-radius:50%;flex:0 0 auto;display:grid;place-items:center;
  color:#fff;text-align:center;line-height:1.1}
.dial b{font-family:var(--mono);font-size:30px;display:block;font-weight:600}
.dial span{font-size:11px;opacity:.92}
.vd{font-size:19px;font-weight:700;margin-bottom:3px}
.ad{color:var(--muted);font-size:14.5px}
.tag{display:inline-block;padding:2px 9px;border-radius:5px;font-size:11.5px;font-weight:600;
  font-family:var(--mono);white-space:nowrap}
.dim{display:grid;grid-template-columns:4px 1fr auto;gap:0 13px;padding:14px 0;
  border-bottom:1px solid var(--line)}
.dim:last-child{border-bottom:0}
.dim .rail{grid-row:1/span 4;border-radius:2px}
.dim .nm{font-weight:650;font-size:15px}
.dim .w{font-family:var(--mono);font-size:11px;color:var(--muted);font-weight:400}
.dim .gap{grid-column:2/4;color:var(--muted);font-size:13.5px;margin-top:3px}
.dim .probe{grid-column:2/4;font-size:13.5px;margin-top:4px}
.dim .ev{grid-column:2/4;background:var(--sunk);border:1px dashed var(--line);border-radius:6px;
  padding:7px 10px;margin-top:6px;font-size:12.5px;color:var(--muted)}
.mets{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.met{background:var(--card);border:1px solid var(--line);border-radius:9px;padding:11px 13px}
.met i{font-style:normal;font-size:12px;color:var(--muted);display:block}
.met b{font-family:var(--mono);font-size:20px;font-variant-numeric:tabular-nums}
.warn{background:var(--warn-bg);border:1px solid var(--warn-line);border-radius:10px;
  padding:15px 17px;margin-bottom:12px}
.warn b{color:var(--warn);display:block;margin-bottom:4px}
.warn p{margin:0;font-size:14px;line-height:1.62}
.crit{background:var(--crit-bg);border-color:var(--crit-line)}
.crit b{color:var(--crit)}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:12.5px;color:var(--muted);
  border-top:1px solid var(--line);margin-top:10px;padding-top:11px}
.tbl{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:11px;
  box-shadow:var(--sh)}
table{width:100%;border-collapse:collapse;font-size:13.5px;min-width:560px}
th,td{text-align:left;padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:last-child td{border-bottom:0}
th{font-family:var(--mono);font-size:11px;letter-spacing:.06em;text-transform:uppercase;
  color:var(--muted);font-weight:500;background:var(--sunk)}
td.n{font-family:var(--mono);color:var(--acc);white-space:nowrap}
.note{background:var(--acc-soft);border:1px solid var(--acc-line);border-radius:10px;
  padding:16px 18px;font-size:14px;margin-top:20px}
.note b{display:block;margin-bottom:5px;color:var(--acc)}
footer{border-top:1px solid var(--line);margin-top:56px;padding-top:22px;color:var(--muted);
  font-size:12.5px;font-family:var(--mono);display:flex;gap:20px;flex-wrap:wrap}
[hidden]{display:none!important}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style></head>
<body><div class="page">

<header>
  <p class="eyebrow">AI 产品岗 · 能力模型 v__VER__</p>
  <h1>AI 产品简历体检</h1>
  <p class="lede">不看你写了多少字，看十个维度上各有没有拿得出手的证据——
    以及有没有说清「为什么这么设计」。这是面试官唯一真正在问的事。</p>
</header>

<section>
  <span class="sec-num">01 — 自检</span>
  <h2>把简历正文贴进来</h2>
  <p class="sub">全部在你自己的浏览器里算，不上传、不留存。一段一行，越具体越准。</p>
  <textarea id="ta" placeholder="从简历里复制「实习经历」「项目经历」部分的正文，粘贴到这里。&#10;每条要点单独一行效果最好。"></textarea>
  <div class="row">
    <button id="go">开始体检</button>
    <button id="demo" class="ghost">载入示例</button>
    <span class="hint" id="cnt">0 字</span>
  </div>
</section>

<section id="out" hidden>
  <span class="sec-num">02 — 结果</span>
  <h2 id="outTitle">体检结果</h2>
  <div id="flags"></div>
  <div class="card hero">
    <div class="dial" id="dial"><div><b>—</b><span>能力分</span></div></div>
    <div style="flex:1;min-width:240px">
      <div class="vd" id="label">—</div>
      <div class="ad" id="advice">—</div>
      <div class="ad" id="counts" style="margin-top:6px;font-size:13px"></div>
    </div>
  </div>
  <div class="mets" id="mets"></div>
  <div class="card" id="dims" style="margin-top:12px"></div>
</section>

<section>
  <span class="sec-num">03 — 判据</span>
  <h2>十个维度和面试官的那一刀</h2>
  <p class="sub">每个维度都必须配一句「面试官真会问的话」。
    想不出面试官会怎么问，这个维度就不该存在——这是模型不至于越写越水的唯一约束。</p>
  <div class="tbl"><table>
    <thead><tr><th>维度</th><th>权重</th><th>面试官会问</th></tr></thead>
    <tbody id="dimTable"></tbody>
  </table></div>
  <div class="legend">
    <span><b>L3</b> 同一句里既有证据，又讲了为什么</span>
    <span><b>L2</b> 有做过的证据，没写为什么</span>
    <span><b>L1</b> 只沾到边</span>
    <span><b>L0</b> 找不到证据</span>
  </div>
</section>

<section>
  <span class="sec-num">04 — 边界</span>
  <h2>这个网页版能做什么，不能做什么</h2>
  <div class="note">
    <b>能做</b>
    十个维度的证据召回与判级、术语堆砌识别、实质指标（行话密度 / 具体性 / 因果比例）。
    这些都是纯文本分析，所以能完整跑在浏览器里，你的简历不会离开这台设备。
  </div>
  <div class="note" style="margin-top:10px">
    <b>不能做</b>
    docx / PDF 解析、与具体 JD 的匹配度、逐句改写、FactGuard 防编造校验——
    这几项需要本地引擎。判级本身也还是靠正则召回，
    <b>用大白话写、不带行话的简历会被低估</b>，这种情况页面会提示你分数不作数。
  </div>
  <div class="note" style="margin-top:10px">
    <b>不会做</b>
    不替任何人编造经历。简历上写下的每个数字，你都要能讲清它的口径、基线和自己的贡献。
  </div>
</section>

<footer>
  <span>能力模型 v__VER__</span><span>纯前端运行</span><span>数据不出本机</span>
</footer>
</div>

<script id="PROFILE" type="application/json">__PROFILE__</script>
<script>
(function(){
  const P = JSON.parse(document.getElementById('PROFILE').textContent);
  const $ = s => document.querySelector(s);
  const LEVEL_SCORE = {L3:1.0, L2:0.55, L1:0.22, L0:0.0};
  const LV = {
    L3:['强证据','var(--ok)','var(--ok-bg)'],
    L2:['做了没说清','var(--warn)','var(--warn-bg)'],
    L1:['只沾到边','var(--warn)','var(--warn-bg)'],
    L0:['完全没有','var(--crit)','var(--crit-bg)']
  };
  const rx = p => new RegExp(p, 'i');
  const REASONING = rx(P.patterns.reasoning);
  const RIGOR     = rx(P.patterns.rigor);
  const JARGON    = new RegExp(P.patterns.jargon, 'gi');
  const CONCRETE  = rx(P.patterns.concrete);
  const DIMS = P.dimensions.map(d => Object.assign({}, d, {
    core: d.signals.slice(0,1).map(rx),
    depth: d.signals.slice(1).map(rx)
  }));

  const hit = (list, t) => list.reduce((n,r) => n + (r.test(t) ? 1 : 0), 0);

  function excerpt(text, res, width){
    let pos = -1;
    for (const r of res){ const m = text.match(r); if (m && m.index !== undefined)
      pos = pos < 0 ? m.index : Math.min(pos, m.index); }
    if (pos < 0 || text.length <= width) return text.slice(0, width);
    const start = Math.max(0, pos - Math.floor(width/3));
    const end = Math.min(text.length, start + width);
    return (start>0?'…':'') + text.slice(start,end) + (end<text.length?'…':'');
  }

  function split(text){
    return text.split(/\n+/).map(s => s.replace(/^[\s●•·\-–—*]+/,'').trim())
               .filter(s => s.length > 20);
  }

  function analyse(text){
    const bs = split(text);
    if (!bs.length) return null;

    const chars = bs.reduce((n,s)=>n+s.length,0);
    const jar = bs.reduce((n,s)=>n+((s.match(JARGON)||[]).length),0);
    const jd = jar / chars * 1000;
    const conc = bs.filter(s=>CONCRETE.test(s)).length / bs.length;
    const caus = bs.filter(s=>REASONING.test(s)).length / bs.length;
    const stuffing = jd / (conc*100 + 8);
    const stuffed = stuffing > 1.5 && caus < 0.15;

    const dims = DIMS.map(d => {
      const cands = [];
      for (const s of bs){
        if (hit(d.core, s) === 0) continue;
        cands.push({g: 1 + hit(d.depth, s), r: REASONING.test(s), q: RIGOR.test(s), s});
      }
      let level = 'L0', quote = '';
      if (cands.length){
        const strong = cands.filter(c=>c.g>=2 && (c.r||c.q))
                            .sort((a,b)=>b.g-a.g)[0];
        const best = cands.slice().sort((a,b)=>(b.g-a.g)||(b.r-a.r)||(b.q-a.q))[0];
        if (strong && cands.length >= 2) level = 'L3';
        else if (best.g >= 2 || cands.length >= 2) level = 'L2';
        else level = 'L1';
        quote = excerpt((strong||best).s, d.core, 120);
      }
      return {d, level, quote, n: cands.length};
    });

    if (stuffed) dims.forEach(x => { if (x.level==='L3'||x.level==='L2') x.level='L1'; });

    const total = dims.reduce((n,x)=>n + x.d.weight*LEVEL_SCORE[x.level], 0);
    const band = P.bands.find(b => total >= b.min_score) || P.bands[P.bands.length-1];
    const l0 = dims.filter(x=>x.level==='L0').length;
    const thin = jd < 8 && chars > 300 && l0 >= dims.length*0.6;

    return {dims, score: +(total*100).toFixed(1), band, stuffed, thin,
            met:{jd:+jd.toFixed(1), conc:+conc.toFixed(2), caus:+caus.toFixed(2),
                 stuffing:+stuffing.toFixed(2), n:bs.length},
            counts: ['L3','L2','L1','L0'].reduce((o,k)=>
              (o[k]=dims.filter(x=>x.level===k).length, o), {})};
  }

  function esc(s){ return String(s).replace(/[&<>"]/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

  function render(r){
    const c = r.counts;
    const color = r.stuffed || r.thin ? 'var(--crit)'
                : r.score >= 72 ? 'var(--ok)'
                : r.score >= 55 ? 'var(--warn)' : 'var(--crit)';
    $('#dial').style.background = color;
    $('#dial').innerHTML = '<div><b>'+Math.round(r.score)+'</b><span>能力分</span></div>';
    $('#label').textContent = r.stuffed ? '疑似术语堆砌，判定已封顶'
                            : r.thin ? '规则层判不了，分数不作数' : r.band.label;
    $('#advice').textContent = r.stuffed
      ? '术语都写到了，但没有一处具体对象或因果论述。面试官问第一个「具体怎么做的」就会穿。'
      : r.thin
      ? '这份简历几乎不用行业术语，规则召回不到证据。真实水平大概率高于这个分数，需要人工或语义层重判。'
      : r.band.advice;
    $('#counts').textContent = '强证据 '+c.L3+' 项 · 做了没说清 '+c.L2
      +' 项 · 只沾到边 '+c.L1+' 项 · 完全没有 '+c.L0+' 项';

    const f = [];
    if (r.stuffed) f.push('<div class="warn crit"><b>识别到术语堆砌</b><p>行话密度 '
      +r.met.jd+' 个/千字，但只有 '+Math.round(r.met.conc*100)
      +'% 的要点带具体对象或数字，因果论述 '+Math.round(r.met.caus*100)
      +'%。所有维度已封顶到 L1。</p></div>');
    if (r.thin) f.push('<div class="warn"><b>这份简历几乎不用行话</b><p>'
      +'规则层靠术语召回证据，抓不到用大白话讲清楚的人。'
      +'上面的分数不作数，请以人工判断为准——这是当前版本已知的短板。</p></div>');
    $('#flags').innerHTML = f.join('');

    $('#mets').innerHTML = [
      ['要点数', r.met.n], ['行话密度', r.met.jd + ' /千字'],
      ['具体性', Math.round(r.met.conc*100) + '%'],
      ['因果比例', Math.round(r.met.caus*100) + '%'],
      ['堆砌指数', r.met.stuffing]
    ].map(([k,v]) => '<div class="met"><i>'+k+'</i><b>'+v+'</b></div>').join('');

    $('#dims').innerHTML = r.dims.slice().sort((a,b)=>b.d.weight-a.d.weight).map(x => {
      const [txt,fg,bg] = LV[x.level];
      const gap = x.level==='L3' ? ''
        : x.level==='L0' ? '简历里完全没有这一项的证据'
        : x.level==='L1' ? '只沾到边，看不出体系。要么补细节，要么这项就别写'
        : '有做过的证据，但没写出「为什么这么设计」——而这正是面试官会追问的地方';
      return '<div class="dim"><div class="rail" style="background:'+fg+'"></div>'
        + '<div class="nm">'+esc(x.d.name)+'<span class="w">　权重 '+x.d.weight.toFixed(2)+'</span></div>'
        + '<div style="text-align:right"><span class="tag" style="color:'+fg+';background:'+bg+'">'
        + x.level+' '+txt+'</span></div>'
        + (gap ? '<div class="gap">'+esc(gap)+'</div>' : '')
        + (x.level!=='L3' ? '<div class="probe">面试官会问：'+esc(x.d.probe)+'</div>' : '')
        + (x.quote ? '<div class="ev">证据：'+esc(x.quote)+'</div>' : '')
        + '</div>';
    }).join('') + '<div class="legend">'
      + '<span>判级只看同一句里有没有同时出现证据和「为什么」</span>'
      + '<span>权重按面试中的区分度定</span></div>';

    $('#out').hidden = false;
    $('#out').scrollIntoView({behavior:'smooth', block:'start'});
  }

  const DEMO = [
    '产品定义与意图路由：新手不懂玩法即流失，图文攻略无法按人按局面给指导。将输入拆为闲聊、知识问答、阵容推荐、阵容教学四类分支并单独设计拒答策略；前置意图 Agent 做复杂度分级、多意图 query 拆分与改写，并把上一轮对话摘要注入 context 弥补基模多轮能力不足——复杂度分级不是为省算力，而是决定该不该用一句安慰句覆盖等待感。',
    '知识体系与检索策略：按知识生产、检索召回、结果重排三层搭建。知识库拆为公库（官方数值、策划文本人工释义、背景故事，以 QA 对组织）与私库（玩家背包内精灵的技能/等级/性格/天赋）——个性化瓶颈不在检索能力而在数据隔离，故「何时调私库」上提为策略决策、「如何调」封装为 tool；检索按 q/a/qa 分域并融合 tf-idf 与向量检索，对「A 技能打 B 精灵几倍伤害」这类问题走多轮检索。',
    '知识生产链路：策划给的文本模型看不懂省略（如「同上题方法」），因此要求先补成一问一答的完整形式再入库，虽然慢但入库后答错率明显下降；配合双 Agent 自动发现知识缺口触发更新，知识覆盖率由 40% 提升至 90%。',
    '盘面分析 Agent：为需结合玩家个人数据的 RAG 场景设计三级嵌套 Agent（意图识别 → Planner 规划 → 工具调用），按 search / 排序 / 比较三类定义 14 个 tool 的能力边界——tool 粒度过细会让 Planner 规划空间爆炸、过粗则单 tool 内部失控，最终按「一个 tool 只回答一类可验证的事实问题」切分。',
    '评测体系：0-1 阶段以 badcase 率 / 回答正确率为北极星，下拆 query 改写、意图路由、检索准确、阵容推荐、闲聊人设偏差（OOC）、回复模型六项过程指标——业务指标要等有量了才有统计意义，所以前期只用过程指标定位，业务指标进来后过程指标转为归因用。以 800 条人工标注 QA 集为基准，双人标注一致性 91%。',
    'badcase 归因：按「安全拦截 → 黑话替换 → 意图与改写 → 检索 → 知识本身 → 回复模型」六层定位责任模块；事实性错误由模型自动判定，理解性错误必须人工复核，因为后者要求评判者真的懂这个游戏怎么玩。自建评测平台替代人工看 Excel，评审效率提升约两倍。',
    '模型选型：线上没用最贵的模型。试了三个，贵的答得好一点但一次要等七八秒，玩家等不住就走了；便宜的 16B 在自建的 800 条评测集上错得不明显多，一次一秒多，而且已经吃过洛克的领域知识，所以线上用它，离线分析才用大模型。端到端语音响应由 8s 降至 3s。',
    '安全与人设：定义 AI 教练角色人设 prompt，明确拒答边界（黄赌毒、能力不支持的问题）；自建黑话库——脚本聚合社媒每周约 20w 条评论做词频统计得 3,000 候选词，经双 Agent 过滤压缩至 100-200 词后周会人工终审入库。黑话刻意选高准确率、容忍漏检，因为误替换会污染下游意图识别，而漏检只损失单个词的覆盖，这与舆情监测优先保召回的取舍相反。',
    '0-1 落地：作为部门首位 AI 产品实习生独立负责该产品线，端到端覆盖需求定义、Agent 架构设计、知识体系搭建与评测闭环；中间为了要不要保留「直接给答案」跟研发争过一次，最后按我的方案做了灰度，两周后数据支持保留但需加二次确认。'
  ].join('\n');

  $('#ta').addEventListener('input', e => {
    $('#cnt').textContent = e.target.value.length + ' 字';
  });
  $('#demo').addEventListener('click', () => {
    $('#ta').value = DEMO;
    $('#cnt').textContent = DEMO.length + ' 字';
  });
  $('#go').addEventListener('click', () => {
    const r = analyse($('#ta').value);
    if (!r){ alert('至少贴一条 20 字以上的要点'); return; }
    render(r);
  });

  $('#dimTable').innerHTML = P.dimensions.slice()
    .sort((a,b)=>b.weight-a.weight).map(d =>
      '<tr><td>'+esc(d.name)+'</td><td class="n">'+d.weight.toFixed(2)+'</td><td>'
      +esc(d.probe)+'</td></tr>').join('');
})();
</script>
</body></html>
"""


def build(role="ai_pm", out_dir=None):
    data = collect(role)
    out_dir = out_dir or os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    html = (HTML.replace("__PROFILE__", json.dumps(data, ensure_ascii=False))
                .replace("__VER__", data["version"] or "0"))
    path = os.path.join(out_dir, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"written: {path}  ({len(html)/1024:.1f} KB, {len(data['dimensions'])} 个维度)")
    return path


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "ai_pm",
          sys.argv[2] if len(sys.argv) > 2 else None)

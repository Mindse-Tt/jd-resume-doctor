# -*- coding: utf-8 -*-
"""本地网页版。零第三方依赖，只用标准库。

前端把文件读成 base64 走 JSON POST，服务端落盘后跑同一套引擎——
不引入 multipart 解析，也不引入 Web 框架。
"""
import base64
import json
import os
import re
import sys
import threading
from urllib.parse import quote, unquote
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RUNS = os.path.join(ROOT, "runs")
MAX_BYTES = 12 * 1024 * 1024
SAFE_NAME = re.compile(r"[^\w一-龥.\-]+")

PAGE = """<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>简历诊断 · 按 JD 体检</title><style>
:root{--ink:#151A20;--sub:#5A6672;--line:#E3E7EC;--bg:#F5F7F9;--acc:#005FA2}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:44px 20px 80px}
h1{font-size:27px;margin:0 0 6px}
.sub{color:var(--sub);margin-bottom:26px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:14px}
label{display:block;font-weight:650;margin-bottom:7px;font-size:14px}
.drop{border:2px dashed #C7D0D9;border-radius:11px;padding:34px 18px;text-align:center;
 color:var(--sub);cursor:pointer;transition:.15s;background:#FAFCFD}
.drop:hover,.drop.on{border-color:var(--acc);background:#F0F7FC;color:var(--acc)}
.drop b{color:var(--ink)}
textarea{width:100%;min-height:190px;border:1px solid var(--line);border-radius:9px;
 padding:11px 13px;font:14px/1.6 inherit;resize:vertical}
input[type=text]{width:100%;border:1px solid var(--line);border-radius:9px;padding:10px 13px;font:15px inherit}
button{background:var(--acc);color:#fff;border:0;border-radius:9px;padding:13px 26px;
 font-size:16px;font-weight:650;cursor:pointer;width:100%}
button:disabled{background:#9FB4C4;cursor:not-allowed}
.hint{color:var(--sub);font-size:13px;margin-top:8px}
.err{color:#B4232B;margin-top:10px;white-space:pre-wrap}
.note{background:#FFF9E8;border:1px solid #F0DFAE;border-radius:10px;padding:13px 15px;
 font-size:13.5px;color:#6B5312;margin-top:18px}
</style>
<div class="wrap">
<h1>简历诊断</h1>
<div class="sub">上传简历 + 粘贴 JD，看这一版投这个岗位卡在哪。全部本地处理，文件不出这台电脑。</div>

<div class="card">
  <label>1 · 简历文件</label>
  <div class="drop" id="drop"><b>点击选择</b>，或把文件拖进来<br>
    <span style="font-size:13px">支持 .docx / .pdf / .md（docx 诊断最完整）</span></div>
  <input type="file" id="file" accept=".docx,.pdf,.md,.txt" hidden>
  <div class="hint" id="fname"></div>
</div>

<div class="card">
  <label>2 · 目标岗位名（可选）</label>
  <input type="text" id="title" placeholder="例如：AI产品经理（游戏方向）">
</div>

<div class="card">
  <label>3 · JD 原文</label>
  <textarea id="jd" placeholder="把招聘页面上的「工作职责」和「任职要求」整段粘进来。&#10;不填也能跑，但只会给简历本身的问题，没有匹配度。"></textarea>
</div>

<button id="go" disabled>开始诊断</button>
<div class="err" id="err"></div>

<div class="note">这个工具只做表达优化和匹配诊断，<b>不会替你编造经历</b>。
报告里标黄的地方需要你填真实数据。简历上写的每个数字，你都要能讲清它的口径和你的贡献。</div>
</div>
<script>
const $=s=>document.querySelector(s);
let payload=null;
$('#drop').onclick=()=>$('#file').click();
['dragover','dragenter'].forEach(e=>$('#drop').addEventListener(e,ev=>{
  ev.preventDefault();$('#drop').classList.add('on')}));
['dragleave','drop'].forEach(e=>$('#drop').addEventListener(e,ev=>{
  ev.preventDefault();$('#drop').classList.remove('on')}));
$('#drop').addEventListener('drop',ev=>{if(ev.dataTransfer.files[0])load(ev.dataTransfer.files[0])});
$('#file').onchange=e=>{if(e.target.files[0])load(e.target.files[0])};
function load(f){
  if(f.size>12*1024*1024){$('#err').textContent='文件超过 12MB';return}
  const r=new FileReader();
  r.onload=()=>{payload={name:f.name,data:r.result.split(',')[1]};
    $('#fname').textContent='已选择：'+f.name;$('#go').disabled=false;$('#err').textContent=''};
  r.readAsDataURL(f);
}
$('#go').onclick=async()=>{
  if(!payload)return;
  $('#go').disabled=true;$('#go').textContent='诊断中…';$('#err').textContent='';
  try{
    const res=await fetch('/api/diagnose',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...payload,jd:$('#jd').value,title:$('#title').value})});
    const j=await res.json();
    if(j.ok){location.href=j.url}
    else{$('#err').textContent='诊断失败：'+j.error}
  }catch(e){$('#err').textContent='请求失败：'+e.message}
  $('#go').disabled=false;$('#go').textContent='开始诊断';
};
</script>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "JRD/1.0"

    def log_message(self, fmt, *args):
        print(f"  {self.address_string()} {fmt % args}")

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, PAGE)
        if self.path.startswith("/report/"):
            rel = unquote(self.path[len("/report/"):].split("?")[0])
            path = os.path.normpath(os.path.join(RUNS, rel))
            if not path.startswith(RUNS) or not os.path.isfile(path):
                return self._send(404, "报告不存在")
            with open(path, "rb") as f:
                return self._send(200, f.read())
        self._send(404, "Not Found")

    def do_POST(self):
        if self.path != "/api/diagnose":
            return self._send(404, "Not Found")
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n > MAX_BYTES * 2:
                raise ValueError("请求过大")
            req = json.loads(self.rfile.read(n))
            url = self._run(req)
            self._send(200, json.dumps({"ok": True, "url": url}),
                       "application/json; charset=utf-8")
        except Exception as e:
            self._send(200, json.dumps({"ok": False, "error": str(e)},
                                       ensure_ascii=False),
                       "application/json; charset=utf-8")

    def _run(self, req):
        from jrd import diagnose

        name = SAFE_NAME.sub("_", os.path.basename(req.get("name", "resume.docx")))
        if not name.lower().endswith((".docx", ".pdf", ".md", ".txt")):
            raise ValueError("只支持 docx / pdf / md / txt")
        raw = base64.b64decode(req["data"])
        if len(raw) > MAX_BYTES:
            raise ValueError("文件过大")

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out = os.path.join(RUNS, f"{stamp}_{os.path.splitext(name)[0]}")
        os.makedirs(out, exist_ok=True)
        src = os.path.join(out, name)
        with open(src, "wb") as f:
            f.write(raw)

        diagnose(src, req.get("jd", ""), req.get("title", ""), out)
        return "/report/" + quote(os.path.basename(out)) + "/diagnosis.html"


def serve(port=8899):
    os.makedirs(RUNS, exist_ok=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"\n  简历诊断已启动：{url}")
    print("  只监听本机，文件不出这台电脑。Ctrl+C 停止。\n")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n  已停止。")

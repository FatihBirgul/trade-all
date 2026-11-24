import { createServer } from "node:http";
import { spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { createChatGPT } from "@siwc/local";
import { windowsDpapiEncryption } from "./windows-dpapi.mjs";

const APP_NAME = "Trade AI GPT Bağlantı Testi";
const EXPECTED = "Token sharing works.";
const storageDir = join(process.env.APPDATA ?? process.cwd(), "Trade-AI-GPT-Baglanti-Testi");
await mkdir(storageDir, { recursive: true });

function openBrowser(url) {
  return new Promise((resolve, reject) => {
    const child = spawn("rundll32.exe", ["url.dll,FileProtocolHandler", url], { stdio: "ignore", windowsHide: true });
    child.once("error", reject);
    child.once("exit", (code) => code === 0 ? resolve() : reject(new Error("Varsayılan tarayıcı açılamadı.")));
  });
}

const chatgpt = createChatGPT({
  appName: APP_NAME,
  appId: "trade-ai-gpt-baglanti-testi",
  redirectPort: 0,
  storageDir,
  credentialEncryption: windowsDpapiEncryption,
  openBrowser,
  sendHostId: true,
});

let running = false;
let result = { stage: "Hazır", signIn: "Bekliyor", consent: "Bekliyor", message: "Bekliyor", response: "Bekliyor", detail: "Henüz OAuth bağlantısı başlatılmadı." };

const page = `<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${APP_NAME}</title>
<style>body{margin:0;background:#f7f7f8;color:#202123;font:16px system-ui,-apple-system,"Segoe UI",sans-serif}main{max-width:720px;margin:9vh auto;padding:32px;background:#fff;border:1px solid #e5e5e5;border-radius:16px;box-shadow:0 12px 35px #0000000d}h1{margin:0 0 8px;font-size:29px}p{line-height:1.55;color:#515158}button{border:0;border-radius:9px;background:#111;color:#fff;padding:13px 19px;font-weight:650;font-size:16px;cursor:pointer}button:disabled{opacity:.55;cursor:wait}dl{margin:28px 0 0;border-top:1px solid #eee}div.row{display:grid;grid-template-columns:150px 1fr;gap:12px;padding:13px 0;border-bottom:1px solid #eee}dt{font-weight:650}dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}.ok{color:#137333}.bad{color:#b3261e}.wait{color:#7a5800}.note{font-size:13px;margin-top:22px}</style>
<main><h1>Trade AI GPT Bağlantı Testi</h1><p>Bu ayrı yerel test, OpenAI’nin resmî <em>Sign in with ChatGPT</em> OAuth akışını başlatır. Devam edince sistem tarayıcınız açılır; hesap girişini ve “ChatGPT planını kullanma” iznini OpenAI sayfasında siz onaylarsınız. Şifre, çerez ve API anahtarı bu uygulamaya verilmez.</p><button id="go">ChatGPT ile giriş yap ve testi çalıştır</button><dl id="status"></dl><p class="note">İzin sonrası otomatik istek: <code>Reply with exactly: Token sharing works.</code><br>Kimlik bilgileri yalnızca Windows kullanıcı hesabınıza bağlı DPAPI ile şifreli biçimde <code>%APPDATA%\\Trade-AI-GPT-Baglanti-Testi</code> altında saklanır.</p></main>
<script>const labels={stage:'Durum',signIn:'Giriş',consent:'Kullanım izni',message:'Otomatik mesaj',response:'Yanıt kontrolü',detail:'Ayrıntı'};let busy=false;function klass(v){return /Başarılı|Doğrulandı|Gönderildi/.test(v)?'ok':/Hata|Reddedildi|Başarısız|Etkin değil/.test(v)?'bad':'wait'}async function refresh(){let s=await fetch('/api/status').then(r=>r.json());document.querySelector('#status').innerHTML=Object.entries(s).map(([k,v])=>'<div class="row"><dt>'+labels[k]+'</dt><dd class="'+klass(v)+'">'+String(v).replaceAll('&','&amp;').replaceAll('<','&lt;')+'</dd></div>').join('');document.querySelector('#go').disabled=busy}document.querySelector('#go').onclick=async()=>{busy=true;refresh();try{await fetch('/api/run',{method:'POST'})}finally{busy=false;refresh()}};refresh();</script></html>`;

function json(response, status = 200) { response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" }); response.end(JSON.stringify(result)); }
function errorText(error) { return error?.message ?? String(error); }

async function runTest() {
  if (running) return;
  running = true;
  result = { stage: "OAuth bağlantısı başlatılıyor", signIn: "Tarayıcıda bekleniyor", consent: "OpenAI izin ekranında bekleniyor", message: "İzin sonrası otomatik gönderilecek", response: "Bekliyor", detail: "Sistem tarayıcısında giriş ve izin verin." };
  try {
    const session = await chatgpt.signIn();
    result.signIn = session.status === "connected" ? "Başarılı — uygulamanın kendi OAuth oturumu doğrulandı" : `Başarısız — ${session.status}`;
    if (!session.sharing) {
      result.consent = "Etkin değil veya reddedildi — ChatGPT plan kullanım izni verilmedi";
      result.message = "Gönderilmedi";
      result.response = "Doğrulanmadı";
      result.stage = "Test tamamlanamadı";
      result.detail = "Kimlik girişi tek başına AI isteği yetkisi vermez. Yeniden girişte kullanım iznini onaylayın.";
      return;
    }
    result.consent = "Başarılı — chatgpt.tokens.use.direct izni doğrulandı";
    const models = await chatgpt.listModels();
    if (!models.length) throw new Error("Bu hesap için kullanılabilir model listesi boş döndü.");
    result.message = `Gönderildi — ${models[0].displayName} ile otomatik test isteği çalışıyor`;
    const reply = await chatgpt.streamResponse({ model: models[0].slug, input: `Reply with exactly: ${EXPECTED}` });
    const received = reply.text.trim();
    result.response = received === EXPECTED ? `Doğrulandı — tam yanıt: ${received}` : `Hata — beklenen “${EXPECTED}”, alınan “${received}”`;
    result.stage = received === EXPECTED ? "Test başarıyla tamamlandı" : "Yanıt alındı ancak eşleşmedi";
    result.detail = received === EXPECTED ? "Yeni uygulamanın OAuth bağlantısı, kullanım izni, otomatik mesajı ve tamamlanmış Responses akışı doğrulandı." : "Responses isteği tamamlandı; ancak model çıktısı bire bir beklenen metin değildi.";
  } catch (error) {
    const message = errorText(error);
    result.stage = "Test hata ile durdu";
    if (result.signIn.includes("bekleniyor")) result.signIn = `Hata — ${message}`;
    else if (result.consent.includes("bekleniyor")) result.consent = `Hata — ${message}`;
    else { result.message = result.message.includes("Gönderildi") ? `Hata — ${message}` : result.message; result.response = `Hata — ${message}`; }
    result.detail = "Gerçek hata uygulama günlüğüne yazılmadan, tanısal metin olarak gösterildi.";
  } finally { running = false; }
}

const server = createServer((request, response) => {
  if (request.method === "GET" && request.url === "/") { response.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" }); response.end(page); return; }
  if (request.method === "GET" && request.url === "/api/status") return json(response);
  if (request.method === "POST" && request.url === "/api/run") { void runTest(); return json(response, 202); }
  response.writeHead(404).end("Not found");
});
server.listen(0, "127.0.0.1", () => { const address = server.address(); const url = `http://127.0.0.1:${address.port}`; console.log(`${APP_NAME}: ${url}`); void openBrowser(url); });

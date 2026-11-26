// Her ekranın GERÇEK sunucu yanıtlarıyla (fixtures/) veri gösterdiğini kanıtlar ve görüntüsünü kaydeder.
// Çalıştırma: npm run export:web && node e2e/screens.cjs [ad süzgeci]
const { run, mock, pair, shot, fixture, assert } = require("./harness.cjs");

const text = (page, id) => page.getByTestId(id).innerText();

run([
  ["bağlantı: eşleşme formu, sonra Panel'e dönüş", async (page) => {
    await mock(page, "dry_idle");
    await page.goto(page.base + "/");
    await page.getByTestId("pair-card").waitFor(); // bağlantı yokken uygulama bu ekranla açılır
    await shot(page, "01-baglanti-form");
    await page.getByLabel("Sunucu adresi").fill("bot.test");
    await page.getByLabel("Eşleştirme kodu").fill("123456");
    await page.getByTestId("pair").click();
    await page.getByTestId("screen-panel").waitFor(); // eşleşme bitince Panel
    assert.equal(await page.getByTestId("pair-card").count(), 0);
  }],
  ["bağlantı: hatalı kod açık bir hata gösterir", async (page) => {
    await mock(page, "dry_idle", { "POST /pair": { status: 401, body: { detail: "kod geçersiz ya da süresi dolmuş" } } });
    await page.goto(page.base + "/");
    await page.getByLabel("Sunucu adresi").fill("bot.test");
    await page.getByLabel("Eşleştirme kodu").fill("000000");
    await page.getByTestId("pair").click();
    assert.match(await text(page, "pair-error"), /Kod geçersiz/);
    await shot(page, "02-baglanti-hata");
  }],
  ["panel: deneme modunda bugünkü üretim durumu", async (page) => {
    await mock(page, "dry_idle");
    await pair(page);
    const status = fixture("dry_idle", "status");
    assert.match(await text(page, "equity"), /10\.000,00 USD/);
    assert.match(await text(page, "mode-pill"), /DENEME MODU/);
    assert.match(await text(page, "bot-state"), /Deneme modu/);
    assert.equal(status.dry_run, true);
    const summary = fixture("dry_idle", "summary");
    assert.match(await text(page, "activity-card"), new RegExp(summary.scans + " tarama"));
    assert.match(await text(page, "activity-card"), new RegExp(summary.would_open + " işlem açardı"));
    await shot(page, "03-panel-deneme");
    assert.match(await text(page, "mode-card"), /Deneme modu açık/);
    await shot(page, "03b-panel-deneme-alt", "mode-card");
  }],
  ["panel: canlıda açık işlemler ve hafta/ay kâr-zararı", async (page) => {
    await mock(page, "live_active");
    await pair(page);
    assert.match(await text(page, "equity"), /10\.111,64 USD/);
    assert.match(await text(page, "mode-pill"), /CANLI/);
    assert.match(await text(page, "pnl-Bugün"), /\+111,64/);
    assert.match(await text(page, "pnl-Bu hafta"), /\+124,24/);
    assert.match(await text(page, "pnl-Bu ay"), /\+124,24/);
    assert.match(await text(page, "bot-card"), /1 bot işlemi/);
    assert.match(await text(page, "bot-card"), /1 elle işlem/);
    assert.match(await page.getByTestId("screen-panel").innerText(), /Bakiye 10\.124,24 USD · Serbest 10\.111,64 USD/);
    assert.match(await text(page, "pnl-caption"), /yalnızca kapanan işlemlerdir/);
    await shot(page, "04-panel-canli");
  }],
  ["panel: veri gelene kadar yükleniyor, gelmezse hata ve yeniden dene", async (page) => {
    await mock(page, "dry_idle", { "GET /status": "hang" });
    await page.goto(page.base + "/");
    await page.getByLabel("Sunucu adresi").fill("bot.test");
    await page.getByLabel("Eşleştirme kodu").fill("123456");
    await page.getByTestId("pair").click();
    await page.getByTestId("state-loading").waitFor();
    assert.match(await text(page, "state-loading"), /Sunucudan veri bekleniyor/);
    await shot(page, "05-panel-yukleniyor");
  }],
  ["panel: sunucu hata verirse hata durumu görünür", async (page) => {
    let fail = true;
    await mock(page, "dry_idle", { "GET /status": () => (fail ? { status: 500, body: { detail: "iç hata" } } : { body: fixture("dry_idle", "status") }) });
    await page.goto(page.base + "/");
    await page.getByLabel("Sunucu adresi").fill("bot.test");
    await page.getByLabel("Eşleştirme kodu").fill("123456");
    await page.getByTestId("pair").click();
    await page.getByTestId("state-error").waitFor();
    assert.match(await text(page, "state-error"), /Veri alınamadı/);
    await shot(page, "06-panel-hata");
    fail = false;
    await page.getByRole("button", { name: "Yeniden dene" }).click();
    await page.getByTestId("equity").waitFor();
  }],
  ["panel: durdur onay ister ve isteği gönderir", async (page) => {
    const calls = await mock(page, "live_active", { "POST /bot/stop": { body: { ...fixture("live_active", "status"), stopped: true } } });
    await pair(page);
    await page.getByTestId("stop").click();
    assert.match(await text(page, "confirm"), /Bot durdurulsun mu/);
    await shot(page, "07-panel-durdur-onay");
    await page.getByTestId("confirm-no").click();
    assert.equal(calls.filter((call) => call.method === "POST" && call.url === "/bot/stop").length, 0);
    await page.getByTestId("stop").click();
    await page.getByTestId("confirm-yes").click();
    await page.getByTestId("panel-notice").waitFor();
    assert.equal(calls.filter((call) => call.url === "/bot/stop").length, 1);
  }],
  ["panel: canlıya geçiş iki ayrı onay ister", async (page) => {
    const calls = await mock(page, "dry_idle", { "PUT /settings": (request) => ({ body: request.postDataJSON() }) });
    await pair(page);
    await page.getByTestId("go-live").click();
    assert.match(await text(page, "confirm"), /GERÇEK PARA/);
    await shot(page, "08-panel-canliya-gecis-onay");
    await page.getByTestId("confirm-yes").click();
    assert.match(await text(page, "confirm"), /Emin misiniz/);
    assert.equal(calls.filter((call) => call.method === "PUT").length, 0); // ikinci onaydan önce istek yok
    await page.getByTestId("confirm-no").click();
    assert.equal(calls.filter((call) => call.method === "PUT").length, 0);
  }],
  ["pozisyonlar: açık pozisyonlar gerçek alanlarla", async (page) => {
    await mock(page, "live_active");
    await pair(page);
    await page.getByTestId("tab-positions").click();
    const [bot, manual] = fixture("live_active", "positions").positions;
    const card = await text(page, "position-" + bot.position_id);
    assert.match(card, /XAUUSD/);
    assert.match(card, /0,62 lot/);
    assert.match(card, /2024,1/); // giriş
    assert.match(card, /2023,29/); // stop
    assert.match(card, /−12,40|-12,40/);
    assert.match(card, /Şimdi\s*2023,9/);
    assert.match(card, /Hedef\s*2026,54/); // hedef = Exness'teki kâr al emri (tp2)
    assert.match(card, /Ara hedef 2025,73/);
    assert.match(await text(page, "position-" + manual.position_id), /Elle/);
    assert.match(await text(page, "position-" + manual.position_id), /Hedef\s*2027,34/);
    await shot(page, "09-pozisyonlar");
  }],
  ["pozisyonlar: stop düzenleme yön denetimi ve kapatma onayı", async (page) => {
    const [bot] = fixture("live_active", "positions").positions;
    const calls = await mock(page, "live_active", {
      ["PATCH /positions/" + bot.position_id]: { body: { order: "o1", manage: true } },
      ["POST /positions/" + bot.position_id + "/close"]: { body: { order: "o2" } },
    });
    await pair(page);
    await page.getByTestId("tab-positions").click();
    await page.getByTestId("edit-" + bot.position_id).click();
    await page.getByLabel("Yeni stop (zarar durdur)").fill("2030");
    await page.getByTestId("save-" + bot.position_id).click();
    assert.match(await text(page, "position-" + bot.position_id), /altında olmalı/); // alışta stop fiyatın üstünde olamaz
    assert.equal(calls.filter((call) => call.method === "PATCH").length, 0);
    await shot(page, "10-pozisyon-duzenle");
    await page.getByLabel("Yeni stop (zarar durdur)").fill("2023,50");
    await page.getByTestId("save-" + bot.position_id).click();
    // Her seviye değişikliği eski → yeni değerleriyle onaylatılır.
    assert.match(await text(page, "confirm"), /Stop: 2023,29 → 2023,5/);
    assert.match(await text(page, "confirm"), /Anlık fiyat: 2023,9/);
    assert.equal(calls.filter((call) => call.method === "PATCH").length, 0);
    await page.getByTestId("confirm-yes").click();
    await page.getByText("Seviye değişikliği gönderildi.").waitFor();
    assert.deepEqual(calls.find((call) => call.method === "PATCH").body, { sl: 2023.5 });
    // Gönderilen değer kutuda kalmaz: sonraki düzenlemede eski stop yeniden gönderilemez.
    await page.getByTestId("edit-" + bot.position_id).click();
    assert.equal(await page.getByLabel("Yeni stop (zarar durdur)").inputValue(), "");
    await page.getByRole("button", { name: "Vazgeç" }).click();
    await page.getByTestId("close-" + bot.position_id).click();
    assert.match(await text(page, "confirm"), /Pozisyon kapatılsın mı/);
    await page.getByTestId("confirm-yes").click();
    await page.getByText("Kapama isteği gönderildi.").waitFor();
  }],
  ["pozisyonlar: boş durum (deneme modu)", async (page) => {
    await mock(page, "dry_idle");
    await pair(page);
    await page.getByTestId("tab-positions").click();
    assert.match(await text(page, "state-empty"), /Açık pozisyon yok/);
    await shot(page, "11-pozisyonlar-bos");
  }],
  ["elle işlem: sembol seçimi, önizleme ve onay", async (page) => {
    const preview = fixture("live_active", "trade_preview").body;
    const calls = await mock(page, "live_active", {
      "POST /trades/preview": { body: preview },
      "POST /trades": { body: { order: "o9", state: "FILLED", lots: preview.lots, sl: preview.sl, tp: preview.tp } },
    });
    await pair(page);
    await page.getByTestId("tab-positions").click();
    await page.getByTestId("new-trade").click();
    await page.getByTestId("symbol-card").waitFor();
    assert.equal(await page.getByTestId("symbol-EURUSD").count(), 0); // fiyatı olmayan sembol seçilemez
    await shot(page, "12-elle-islem-sembol");
    await page.getByTestId("symbol-" + preview.symbol).click();
    await page.getByLabel("Zarar durdurma mesafesi (zorunlu)").fill("4");
    await page.getByLabel("Kâr al mesafesi").fill("8");
    await page.getByTestId("preview").click();
    const card = await text(page, "preview-card");
    assert.match(card, new RegExp(preview.symbol + " AL"));
    assert.match(card, /En çok zarar/);
    await shot(page, "13-elle-islem-onizleme", "send");
    await page.getByTestId("send").click();
    assert.match(await text(page, "confirm"), /emri gönderilsin mi/);
    assert.match(await text(page, "confirm"), /GERÇEK hesapta/);
    await shot(page, "14-elle-islem-onay");
    assert.equal(calls.filter((call) => call.url === "/trades").length, 0);
    await page.getByTestId("confirm-yes").click();
    assert.match(await text(page, "manual-notice"), /Emir gönderildi/);
    const sent = calls.filter((call) => call.url === "/trades");
    assert.equal(sent.length, 1);
    assert.equal(sent[0].body.symbol, preview.symbol);
    assert.equal(sent[0].body.lots, preview.lots);
    assert.ok(sent[0].body.sl_distance > 0 && sent[0].body.client_id.length >= 8); // stopsuz emir yok, tek kimlik
  }],
  ["elle işlem: stop mesafesi olmadan önizleme bile istenmez", async (page) => {
    const calls = await mock(page, "live_active");
    await pair(page);
    await page.getByTestId("tab-positions").click();
    await page.getByTestId("new-trade").click();
    await page.getByTestId("symbol-XAUUSD").click();
    await page.getByTestId("preview").click();
    assert.match(await text(page, "manual-notice"), /Zarar durdurma mesafesi zorunludur/);
    assert.equal(calls.filter((call) => call.method === "POST" && call.url !== "/pair").length, 0);
  }],
  ["raporlar: kapanan işlemler, dönemler ve karne", async (page) => {
    await mock(page, "live_active");
    await pair(page);
    await page.getByTestId("tab-reports").click();
    assert.match(await text(page, "report-pnl"), /\+124,24 USD/);
    assert.match(await text(page, "report-totals"), /1 işlem/);
    assert.match(await text(page, "report-breakdown"), /Trend momentum/);
    assert.match(await text(page, "report-history"), /XAUUSD AL/);
    assert.match(await text(page, "report-shadow"), /Trend momentum/);
    await shot(page, "15-raporlar");
    await shot(page, "15b-raporlar-gecmis-ve-karne", "report-shadow");
    await page.getByRole("button", { name: "Hafta" }).click();
    await page.getByTestId("report-periods").getByText("2027-W02").waitFor(); // haftalık rapor yüklendi
  }],
  ["raporlar: işlem yokken boş durum, karne yine görünür", async (page) => {
    await mock(page, "dry_idle");
    await pair(page);
    await page.getByTestId("tab-reports").click();
    assert.match(await text(page, "state-empty"), /Henüz kapanmış işlem yok/);
    assert.match(await text(page, "report-shadow"), /EMA geri çekilme/);
    await shot(page, "16-raporlar-bos");
  }],
  ["raporlar: rapor alınamazsa hata durumu", async (page) => {
    await mock(page, "dry_idle", { "GET /reports": { status: 500, body: { detail: "iç hata" } } });
    await pair(page);
    await page.getByTestId("tab-reports").click();
    assert.match(await text(page, "state-error"), /Veri alınamadı/);
    await shot(page, "17-raporlar-hata");
  }],
  ["bildirimler: önemli olaylar ve tümü", async (page) => {
    await mock(page, "live_active");
    await pair(page);
    await page.getByTestId("tab-events").click();
    const events = fixture("live_active", "events").events;
    const opened = events.find((event) => event.kind === "trade_opened");
    assert.match(await text(page, "event-" + opened.id), /XAUUSD BUY/);
    assert.equal(await page.getByTestId("event-" + events.find((event) => event.kind === "scan").id).count(), 0);
    await shot(page, "18-bildirimler-onemli");
    await page.getByRole("button", { name: "Tümü" }).click();
    assert.match(await text(page, "event-" + events.find((event) => event.kind === "scan").id), /Tarama/);
    await shot(page, "19-bildirimler-tumu");
  }],
  ["bildirimler: deneme modunda önemli olay yoksa boş durum ve tümünü göster", async (page) => {
    await mock(page, "dry_idle");
    await pair(page);
    await page.getByTestId("tab-events").click();
    assert.match(await text(page, "state-empty"), /Önemli bir olay yok/);
    await shot(page, "20-bildirimler-bos");
    await page.getByTestId("show-all").click();
    assert.match(await text(page, "event-list"), /Tarama/);
  }],
  ["ayarlar: gerçek değerler, risk artışı uyarısı ve kayıt", async (page) => {
    const settings = fixture("dry_idle", "settings");
    const calls = await mock(page, "dry_idle", { "PUT /settings": (request) => ({ body: request.postDataJSON() }) });
    await pair(page);
    await page.getByTestId("tab-settings").click();
    await page.getByTestId("settings-risk").waitFor();
    assert.equal(await page.getByLabel("İşlem başı risk").inputValue(), String(settings.risk.risk_pct).replace(".", ","));
    assert.match(await text(page, "settings-symbols"), /4 \/ 4/);
    assert.match(await text(page, "settings-strategies"), /Sahte kırılım/);
    assert.match(await text(page, "settings-app"), /Trade Bot 1\.0\.0/);
    await shot(page, "21-ayarlar");
    await shot(page, "21b-ayarlar-korumalar-semboller", "settings-symbols");
    await shot(page, "21c-ayarlar-stratejiler", "settings-app");
    await page.getByLabel("İşlem başı risk").fill("1");
    await page.getByTestId("save-settings").click();
    assert.match(await text(page, "confirm"), /risk artıyor/);
    assert.match(await text(page, "confirm"), /0,5% → 1%/);
    await shot(page, "22-ayarlar-risk-onayi");
    await page.getByTestId("confirm-yes").click();
    assert.match(await text(page, "settings-notice"), /Ayarlar kaydedildi/);
    const put = calls.find((call) => call.method === "PUT");
    assert.equal(put.body.risk.risk_pct, 1);
    assert.equal(put.body.dry_run, true); // deneme/canlı kipi bu yoldan değişmez
  }],
  ["ayarlar: sınır dışı değer kaydedilmez", async (page) => {
    const calls = await mock(page, "dry_idle");
    await pair(page);
    await page.getByTestId("tab-settings").click();
    await page.getByLabel("İşlem başı risk").fill("5");
    await page.getByTestId("save-settings").click();
    await page.getByTestId("settings-notice").waitFor();
    assert.equal(calls.filter((call) => call.method === "PUT").length, 0);
  }],
  ["bağlantı ve tanı: bağlı durumu ve istek günlüğü", async (page) => {
    await mock(page, "live_active");
    await pair(page);
    await page.getByTestId("tab-settings").click();
    await page.getByTestId("open-connection-settings").click();
    assert.match(await text(page, "connected-card"), /bot\.test/);
    await shot(page, "23-baglanti-bagli");
    await page.getByRole("button", { name: "İstek günlüğü (tanı)" }).click();
    assert.match(await text(page, "request-log"), /GET \/status/);
    assert.match(await text(page, "request-log"), /200/);
    await shot(page, "24-tani");
  }],
  ["bağlantı iptal edilirse (401) veri silinir ve yeniden eşleştirme istenir", async (page) => {
    let revoked = false;
    await mock(page, "live_active", { "GET /status": () => (revoked ? { status: 401, body: { detail: "geçersiz ya da eksik token" } } : { body: fixture("live_active", "status") }) });
    await pair(page);
    await page.getByTestId("equity").waitFor();
    revoked = true;
    await page.getByTestId("open-connection").waitFor({ timeout: 15000 });
    assert.equal(await page.getByTestId("equity").count(), 0);
    await shot(page, "25-baglanti-iptal");
  }],
  ["panel: bu hafta ve bu ay kendi döneminden okunur, tüm zamanların toplamından değil", async (page) => {
    // Sunucunun `totals` alanı tüm zamanların toplamıdır (500); bu haftanın kovası 100, bu ayınki 50.
    const report = (period, rows) => ({ ...fixture("live_active", "reports_" + period), totals: { bot: { pnl: 500, trades: 9, wins: 5, win_rate: 0.55 }, manual: { pnl: 0, trades: 0, wins: 0, win_rate: null }, all: { pnl: 500, trades: 9, wins: 5, win_rate: 0.55 } }, periods: { bot: rows, manual: [], all: rows } });
    await mock(page, "live_active", { "GET /reports": (request, url) => ({ body: /period=week/.test(url) ? report("week", [{ period: "2027-W01", pnl: 400, trades: 7 }, { period: "2027-W02", pnl: 100, trades: 2 }]) : /period=month/.test(url) ? report("month", [{ period: "2026-12", pnl: 450, trades: 8 }, { period: "2027-01", pnl: 50, trades: 1 }]) : report("day", [{ period: "2027-01-15", pnl: 30, trades: 1 }]) }) });
    await pair(page);
    assert.match(await text(page, "pnl-Bu hafta"), /\+100,00/);
    assert.match(await text(page, "pnl-Bu ay"), /\+50,00/);
    assert.doesNotMatch(await page.getByTestId("screen-panel").innerText(), /500,00/);
    await page.getByTestId("tab-reports").click();
    assert.match(await text(page, "report-totals"), /tüm zamanlar/);
    assert.match(await text(page, "report-pnl"), /\+500,00 USD/);
  }],
  ["panel: son 24 saat kartı hem açılan hem açılırdı sayısını gösterir", async (page) => {
    await mock(page, "dry_idle", { "GET /health/summary": { body: { ...fixture("dry_idle", "summary"), dry_run: true, opened: 3, would_open: 2 } } });
    await pair(page);
    assert.match(await text(page, "activity-card"), /3 işlem açtı/);
    assert.match(await text(page, "activity-card"), /2 işlem açardı/);
  }],
  ["panel: canlıya geçiş iki onaydan sonra doğru isteği gönderir; hızlı çift dokunuş geçemez", async (page) => {
    const calls = await mock(page, "dry_idle", { "PUT /settings": (request) => ({ body: request.postDataJSON() }) });
    await pair(page);
    await page.getByTestId("go-live").click();
    await page.getByTestId("confirm").waitFor();
    // Pencere yeni açıldı: onay düğmesi kısa süre basılamaz (çift dokunuş iki onayı birden geçemesin).
    await page.getByTestId("confirm-yes").click({ force: true, clickCount: 2, timeout: 1000 }).catch(() => {});
    assert.match(await text(page, "confirm"), /GERÇEK PARA/); // hâlâ ilk onay
    assert.equal(calls.filter((call) => call.method === "PUT").length, 0);
    await page.getByTestId("confirm-yes").click();
    assert.match(await text(page, "confirm"), /Emin misiniz/);
    await page.getByTestId("confirm-yes").click({ force: true, timeout: 1000 }).catch(() => {});
    assert.equal(calls.filter((call) => call.method === "PUT").length, 0); // ikinci pencere de hemen basılamaz
    await page.getByTestId("confirm-yes").click();
    await page.getByTestId("panel-notice").waitFor();
    const put = calls.filter((call) => call.method === "PUT");
    assert.equal(put.length, 1);
    assert.equal(put[0].url, "/settings?confirm_live=true");
    assert.equal(put[0].body.dry_run, false);
  }],
  ["panel: kayıp sınırıyla durmuş botu devam ettirmek iki onay ister", async (page) => {
    const halted = { ...fixture("live_active", "status"), halted: true, halt_reason: "toplam kayıp sınırı (%25) aşıldı" };
    const calls = await mock(page, "live_active", { "GET /status": { body: halted }, "POST /bot/resume": { body: { ...halted, halted: false } } });
    await pair(page);
    assert.match(await text(page, "bot-state"), /Durdu: toplam kayıp sınırı/);
    await page.getByTestId("resume").click();
    assert.match(await text(page, "confirm"), /kayıp sınırı nedeniyle durdu/);
    await page.getByTestId("confirm-yes").click();
    assert.match(await text(page, "confirm"), /Kayıp sınırı koruması sıfırlanacak/);
    await page.getByTestId("confirm-no").click();
    assert.equal(calls.filter((call) => call.url === "/bot/resume").length, 0);
    await page.getByTestId("resume").click();
    await page.getByTestId("confirm-yes").click();
    await page.getByTestId("confirm-yes").click();
    await page.getByTestId("panel-notice").waitFor();
    assert.deepEqual(calls.find((call) => call.url === "/bot/resume").body, { confirm_halt: true });
  }],
  ["panel: hepsini kapat onaysız gönderilmez", async (page) => {
    const calls = await mock(page, "live_active", { "POST /bot/close-all": { body: { requested: 2, skipped: [], stopped: true } } });
    await pair(page);
    await page.getByTestId("close-all").click();
    assert.match(await text(page, "confirm"), /2 pozisyonun tamamı/);
    await page.getByTestId("confirm-no").click();
    assert.equal(calls.filter((call) => call.url === "/bot/close-all").length, 0);
    await page.getByTestId("close-all").click();
    await page.getByTestId("confirm-yes").click();
    await page.getByTestId("panel-notice").waitFor();
    assert.deepEqual(calls.find((call) => call.url === "/bot/close-all").body, { confirm: "CLOSE-ALL" });
  }],
  ["panel: bottan haber yoksa uyarı görünür ve canlıya geçiş kapanır", async (page) => {
    const status = fixture("dry_idle", "status");
    await mock(page, "dry_idle", { "GET /status": { body: { ...status, heartbeat_at: status.server_time - 1000 } } });
    await pair(page);
    assert.match(await text(page, "notice-stale"), /Bottan 5 dakikadır haber yok/);
    assert.match(await text(page, "bot-state"), /Bot yanıt vermiyor/);
    assert.equal(await page.getByTestId("go-live").getAttribute("aria-disabled"), "true");
    await shot(page, "26-panel-bot-yanit-vermiyor");
  }],
  ["pozisyonlar: stopu uzaklaştırmak ayrı uyarıyla onaylatılır", async (page) => {
    const [bot] = fixture("live_active", "positions").positions;
    const calls = await mock(page, "live_active", { ["PATCH /positions/" + bot.position_id]: { body: { order: "o1", manage: true } } });
    await pair(page);
    await page.getByTestId("tab-positions").click();
    await page.getByTestId("edit-" + bot.position_id).click();
    await page.getByLabel("Yeni stop (zarar durdur)").fill("2022");
    await page.getByTestId("save-" + bot.position_id).click();
    assert.match(await text(page, "confirm"), /stop uzaklaşıyor/);
    assert.match(await text(page, "confirm"), /Stop: 2023,29 → 2022/);
    await shot(page, "27-pozisyon-stop-uzaklasiyor");
    await page.getByTestId("confirm-no").click();
    assert.equal(calls.filter((call) => call.method === "PATCH").length, 0);
  }],
  ["pozisyonlar: kademeli stopu kapatmak onay ister", async (page) => {
    const [bot] = fixture("live_active", "positions").positions;
    const calls = await mock(page, "live_active", { ["PATCH /positions/" + bot.position_id]: { body: { order: null, manage: false } } });
    await pair(page);
    await page.getByTestId("tab-positions").click();
    await page.getByTestId("edit-" + bot.position_id).click();
    await page.getByTestId("position-" + bot.position_id).getByRole("switch", { name: "Kademeli stop" }).click();
    assert.match(await text(page, "confirm"), /Kademeli stop kapatılsın mı/);
    await page.getByTestId("confirm-no").click();
    assert.equal(calls.filter((call) => call.method === "PATCH").length, 0);
    await page.getByTestId("position-" + bot.position_id).getByRole("switch", { name: "Kademeli stop" }).click();
    await page.getByTestId("confirm-yes").click();
    await page.getByText("Kademeli stop kapatıldı").waitFor();
    assert.deepEqual(calls.find((call) => call.method === "PATCH").body, { manage: false });
  }],
  ["elle işlem: sonucu bilinmeyen emir formu kilitler, sonuç sorulmadan yenisi gönderilemez", async (page) => {
    const preview = fixture("live_active", "trade_preview").body;
    const calls = await mock(page, "live_active", { "POST /trades/preview": { body: preview }, "POST /trades": "abort" });
    await pair(page);
    await page.getByTestId("tab-positions").click();
    await page.getByTestId("new-trade").click();
    await page.getByTestId("symbol-" + preview.symbol).click();
    await page.getByLabel("Zarar durdurma mesafesi (zorunlu)").fill("4");
    await page.getByTestId("preview").click();
    await page.getByTestId("send").click();
    await page.getByTestId("confirm-yes").click();
    await page.getByTestId("pending-card").waitFor();
    assert.match(await text(page, "pending-card"), /Sonucu bilinmeyen bir emir var/);
    assert.equal(await page.getByTestId("preview").getAttribute("aria-disabled"), "true"); // kilitli
    await shot(page, "28-elle-islem-sonuc-belirsiz");
    const sent = calls.filter((call) => call.url === "/trades");
    assert.equal(sent.length, 1);
    // Ekrandan çıkıp dönmek kilidi kaldırmaz.
    await page.getByTestId("back").click();
    await page.getByTestId("new-trade").click();
    await page.getByTestId("pending-card").waitFor();
  }],
  ["elle işlem: bir dakikadan eski önizlemeyle emir gönderilmez", async (page) => {
    const preview = fixture("live_active", "trade_preview").body;
    await page.clock.install();
    const calls = await mock(page, "live_active", { "POST /trades/preview": { body: preview } });
    await pair(page);
    await page.getByTestId("tab-positions").click();
    await page.getByTestId("new-trade").click();
    await page.getByTestId("symbol-" + preview.symbol).click();
    await page.getByLabel("Zarar durdurma mesafesi (zorunlu)").fill("4");
    await page.getByTestId("preview").click();
    await page.getByTestId("preview-card").waitFor();
    await page.clock.fastForward(61000);
    await page.getByTestId("send").click();
    assert.match(await text(page, "manual-notice"), /Önizleme eskidi/);
    assert.equal(calls.filter((call) => call.url === "/trades").length, 0);
  }],
  ["ayarlar: stratejiyi canlıya almak onay ister; ret nedeni kartın içinde görünür", async (page) => {
    const strategies = fixture("dry_idle", "strategies");
    strategies.strategies = strategies.strategies.map((row) => (row.strategy_id === "fx_range_reversion_v6" ? { ...row, mode: "shadow" } : row));
    const calls = await mock(page, "dry_idle", { "GET /strategies": { body: strategies }, "POST /strategies/fx_range_reversion_v6/mode": { status: 409, body: { detail: "gölge karnesi yetersiz" } } });
    await pair(page);
    await page.getByTestId("tab-settings").click();
    await page.getByRole("button", { name: "Canlı fx_range_reversion_v6" }).click();
    assert.match(await text(page, "confirm"), /canlıya alınsın mı/);
    await page.getByTestId("confirm-no").click();
    assert.equal(calls.filter((call) => call.method === "POST" && /mode$/.test(call.url)).length, 0);
    await page.getByRole("button", { name: "Canlı fx_range_reversion_v6" }).click();
    await page.getByTestId("confirm-yes").click();
    const notice = page.getByTestId("strategy-notice");
    await notice.waitFor();
    assert.match(await notice.innerText(), /gölge karnesi yetersiz/);
    assert.deepEqual(calls.find((call) => /mode$/.test(call.url)).body, { mode: "live", confirm: true });
    const box = await notice.boundingBox();
    assert.ok(box && box.y >= 0 && box.y < 892, "ret nedeni ekranda görünür olmalı");
  }],
  ["raporlar: toplam, bot ve elle işlemlerin tamamıdır; düşüş değerleri doğru alandan gelir", async (page) => {
    const base = fixture("live_active", "reports_day");
    const body = { ...base, totals: { bot: { pnl: 100, trades: 4, wins: 3, win_rate: 0.75 }, manual: { pnl: 20, trades: 1, wins: 1, win_rate: 1 }, all: { pnl: 120, trades: 5, wins: 4, win_rate: 0.8 } }, max_drawdown: { bot: 5, manual: 0, all: 7 } };
    await mock(page, "live_active", { "GET /reports": { body } });
    await pair(page);
    await page.getByTestId("tab-reports").click();
    assert.match(await text(page, "report-pnl"), /\+120,00 USD/);
    assert.match(await text(page, "report-totals"), /5,00 USD \/ 7,00 USD/);
    assert.match(await text(page, "report-totals"), /%80 \(4\/5\)/);
  }],
]);

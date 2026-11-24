// Real API modules over a CA-verified local TLS socket; no real user credential.
const fs = require("node:fs"),
  https = require("node:https"),
  assert = require("node:assert/strict");
let stdin = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (x) => (stdin += x));
process.stdin.on("end", async () => {
  try {
    const config = JSON.parse(stdin),
      ca = fs.readFileSync(config.ca);
    const { createApi } = require(config.client + "/src/api/client.js");
    const { pairDevice, mobileSession } = require(
      config.client + "/src/api/gateway.js",
    );
    const { safeDecision } = require(config.client + "/src/domain/safety.js");
    const transport = (url, init = {}) =>
      new Promise((resolve, reject) => {
        const req = https.request(
          {
            hostname: "127.0.0.1",
            servername: new URL(url).hostname,
            path: new URL(url).pathname + new URL(url).search,
            agent: new https.Agent({ ca }),
            method: init.method || "GET",
            port: new URL(url).port || 8787,
            headers: { ...init.headers, Host: new URL(url).hostname },
            signal: init.signal,
            ca,
            lookup: (_hostname, options, callback) =>
              callback(
                null,
                options.all
                  ? [{ address: "127.0.0.1", family: 4 }]
                  : "127.0.0.1",
                4,
              ),
          },
          (res) => {
            let body = "";
            res.setEncoding("utf8");
            res.on("data", (s) => (body += s));
            res.on("end", () =>
              resolve({
                ok: res.statusCode >= 200 && res.statusCode < 300,
                status: res.statusCode,
                json: async () => JSON.parse(body),
              }),
            );
          },
        );
        req.on("error", reject);
        if (init.body) req.write(init.body);
        req.end();
      });
    const paired = await pairDevice(
      config.origin,
      config.code,
      config.deviceId,
      "TLS test Android",
      transport,
    );
    let connection = {
      origin: config.origin,
      session: paired.session,
      refresh: paired.refresh,
      deviceId: config.deviceId,
      renewalExpiresAt: paired.metadata.renewal_expires_at_ms,
      scopes: paired.metadata.scopes,
      accounts: paired.metadata.accounts,
    };
    const { renewConnection } = require(config.client + "/src/api/renewal.js");
    const crypto = require("node:crypto");
    let saved = connection,
      lostRenewalAck = false;
    const save = async (value) => {
      fs.writeFileSync(config.client + "/renewal.json", JSON.stringify(value), {
        mode: 0o600,
      });
      saved = value;
    };
    const lostRenewal = async (url, init) => {
      const response = await transport(url, init);
      if (!lostRenewalAck && url.endsWith("/gateway/refresh")) {
        lostRenewalAck = true;
        throw new Error("controlled lost renewal acknowledgement");
      }
      return response;
    };
    const random = async (prefix) =>
      prefix + crypto.randomBytes(32).toString("base64url");
    await assert.rejects(
      () => renewConnection(connection, save, random, lostRenewal),
      (e) => e.code === "RENEWAL_UNCERTAIN",
    );
    const reloaded = JSON.parse(
      fs.readFileSync(config.client + "/renewal.json", "utf8"),
    );
    connection = (await renewConnection(reloaded, save, random, transport))
      .config;
    await assert.rejects(
      () =>
        mobileSession(
          { origin: config.origin, session: paired.session },
          transport,
        ),
      (e) => e.status === 401,
    );
    assert(!saved.pendingRenewal);

    const metadata = await mobileSession(connection, transport);
    assert.deepEqual(metadata.accounts, ["AUTO", "MANUAL"]);
    const api = createApi(connection, transport);
    if (config.quotes) {
      const quotes = await api.quotes();
      assert.equal(quotes.stale, false);
      assert.equal(quotes.items.length, 3);
      assert(
        quotes.items.every(
          (q) => q.price === "123.45" && q.history.length === 24,
        ),
      );
    }
    const health = await api.health();
    assert.equal(health.real_execution, false);
    assert.equal(health.data_mode, "live");
    assert.equal(
      (await api.markets()).items.filter((x) => x.market === "crypto_spot")
        .length,
      3,
    );
    const body = {
      symbol: "BTCUSDT",
      timeframe: "1H",
      data_mode: "live",
      risk_portfolio: "MANUAL",
      auto_paper: true,
      idempotency_key: "https-client-integration",
    };
    let analysis;
    if (config.controlled) {
      const { snapshotMatches } = require(
        config.client + "/src/domain/snapshot.js",
      );
      for (const symbol of ["BTCUSDT", "ETHUSDT", "SOLUSDT"]) {
        const result = await api.analyze({
          ...body,
          symbol,
          timeframes: ["15m", "4H"],
          idempotency_key: "https-controlled-" + symbol,
        });
        assert.equal(result.provider, "controlled_test_input");
        assert.equal(result.auto_order_id, null);
        assert.equal(result.direction, "bullish");
        assert.equal(safeDecision(result), "bullish");
        assert.equal(Object.keys(result.strategy_setups).length, 4);
        assert(
          snapshotMatches(
            result,
            await api.candles(result.analysis_id, result.timeframe),
          ),
        );
        assert.deepEqual(await api.detail(result.analysis_id), result);
      }
    }
    analysis = await api.analyze(body);
    if (!config.controlled) {
      assert.equal(analysis.direction, "WAIT");
      assert.equal(safeDecision(analysis), "WAIT");
      assert.equal(analysis.levels, null);
    }
    if (config.follow) {
      const tracked = await api.follow(analysis.analysis_id);
      assert.equal(tracked.portfolio_id, "MANUAL");
      assert.equal(tracked.worker_running, false);
      assert.equal(
        (await api.follow(analysis.analysis_id)).tracking_id,
        tracked.tracking_id,
      );
      assert.equal((await api.follows()).length, 1);
      assert.equal(
        (await api.changeFollow(tracked.tracking_id, false)).enabled,
        false,
      );
      assert.equal(
        (await api.changeFollow(tracked.tracking_id, true)).enabled,
        true,
      );
    }
    const repeated = await api.analyze(body);
    assert.equal(repeated.analysis_id, analysis.analysis_id);
    assert.equal(
      (await api.detail(analysis.analysis_id)).analysis_id,
      analysis.analysis_id,
    );
    assert.equal((await api.analyses()).length, config.controlled ? 4 : 1);
    const portfolios = await api.portfolios();
    assert.deepEqual(
      portfolios.map((x) => x.portfolio_id),
      ["AUTO", "MANUAL"],
    );
    for (const account of ["AUTO", "MANUAL"]) {
      assert.deepEqual(await api.orders(account), []);
      assert.deepEqual(await api.positions(account), []);
      assert.deepEqual(await api.transactions(account), []);
    }
    if (config.controlled) {
      const { IntentJournal } = require(config.client + "/src/api/intent.js");
      const { paperOperations } = require(config.client + "/src/api/paper.js");
      const journalFile = config.client + "/paper-intent.json";
      const storage = {
        getItem: async () =>
          fs.existsSync(journalFile)
            ? fs.readFileSync(journalFile, "utf8")
            : null,
        setItem: async (_key, value) =>
          fs.writeFileSync(journalFile, value, { mode: 0o600 }),
        removeItem: async () => fs.unlinkSync(journalFile),
      };
      let lost = false;
      const lostAck = async (url, init) => {
        const result = await transport(url, init);
        if (!lost && init.method === "POST" && url.endsWith("/orders")) {
          lost = true;
          throw new Error("controlled lost acknowledgement after commit");
        }
        return result;
      };
      const paperApi = createApi(connection, lostAck, undefined, {
        paperWritesEnabled: true,
      });
      const context = {
        origin: config.origin,
        deviceId: config.deviceId,
        account: "MANUAL",
        enabled: true,
        scopes: metadata.scopes,
      };
      const operations = paperOperations(
        new IntentJournal(storage),
        paperApi,
        context,
      );
      await assert.rejects(
        () =>
          operations.execute(
            "/portfolios/MANUAL/orders",
            { analysis_id: analysis.analysis_id, quantity: "0.1" },
            "https-paper-original",
          ),
        (e) => e.uncertain,
      );
      assert.equal((await api.orders("MANUAL")).length, 1);
      const restarted = paperOperations(
        new IntentJournal(storage),
        paperApi,
        context,
      );
      const order = await restarted.recover();
      assert.equal(order.status, "pending");
      assert.equal((await api.orders("MANUAL")).length, 1);
      assert.equal(await restarted.pending(), null);
      await restarted.execute(
        "/portfolios/MANUAL/orders/" + order.order_id + "/cancel",
        {},
        "https-paper-cancel",
      );
      assert.equal((await api.orders("MANUAL"))[0].status, "cancelled");
      assert.deepEqual(await api.orders("AUTO"), []);
      await assert.rejects(
        () =>
          api.createOrder("MANUAL", {
            analysis_id: analysis.analysis_id,
            idempotency_key: "disabled-default-key",
          }),
        (e) => e.code === "PAPER_WRITES_DISABLED",
      );
      await api.watch({
        symbol: "ETHUSDT",
        timeframe: "15m",
        enabled: true,
        auto_paper: true,
      });
      assert.equal((await api.watches())[0].auto_paper, false);
      await api.pause(false);
      const tick = await api.tick();
      assert.equal(tick.status, "completed");
      assert.equal(tick.jobs.length, 1);
      assert.equal(
        (await api.detail(tick.jobs[0].analysis_id)).symbol,
        "ETHUSDT",
      );
      const pending = await api.notifications();
      assert.equal(pending[0].details.analysis_id, tick.jobs[0].analysis_id);
      assert.equal(pending[0].delivery_status, "pending");
      await api.watch({ symbol: "ETHUSDT", timeframe: "15m", enabled: false });
      assert.equal((await api.watches())[0].enabled, false);
      await api.pause(true);
    }
    await api.scanner();
    await api.jobs();
    await api.watches();
    await api.notifications();
    await api.performance();
    if (!config.controlled)
      await assert.rejects(
        () => api.tick(),
        (e) => e.status === 403,
      );
    await assert.rejects(
      () =>
        pairDevice(
          config.origin,
          config.code,
          config.deviceId,
          "Replay",
          transport,
        ),
      (e) => e.status === 401,
    );
    const wrong = createApi(
      { origin: config.origin, session: "wrong" },
      transport,
    );
    await assert.rejects(
      () => wrong.health(),
      (e) => e.code === "UNAUTHORIZED",
    );
    const off = createApi(
      { origin: config.offOrigin, session: paired.session },
      transport,
    );
    await assert.rejects(
      () => off.health(),
      (e) => e.code === "NETWORK",
    );
    console.log(
      config.controlled
        ? "PASS: Android API and persisted test journal → verified local TLS → gateway → real V2 engine with CONTROLLED SYNTHETIC test input only. Three market analyses, MTF, immutable snapshots, create/lost-ack/restart/same-key recovery/cancel, AUTO isolation, scanner watch/timeframe/pause/tick/jobs/outbox, default paper lock verified. This is NOT a live market or physical device test."
        : "PASS: Android production API → verified local HTTPS gateway → unmodified V2 backend (controlled provider unavailable, temporary database). Pairing/replay, auth, markets, WAIT/idempotency, history/detail, account reads, scanner read, notification pending, gateway-off tested.",
    );
  } catch (e) {
    console.error(e.message);
    process.exitCode = 1;
  }
});

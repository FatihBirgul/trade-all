/** Real compiled Android client over certificate-verified loopback HTTPS.
 * Test-only transport pins rc.example.test to 127.0.0.1; no TLS/auth/schema bypass.
 * The Python controller alone owns disposable databases and fixture authority.
 */
const { request } = require("node:https");
const { Buffer } = require("node:buffer");
const { readFileSync } = require("node:fs");
const { createInterface } = require("node:readline");
const { randomUUID, randomBytes } = require("node:crypto");
const assert = require("node:assert/strict");
const { join } = require("node:path");
const lines = createInterface({ input: process.stdin });
const iterator = lines[Symbol.asyncIterator]();
async function input() {
  const v = await iterator.next();
  if (v.done) throw Error("Controller closed");
  return JSON.parse(v.value);
}
async function control(name) {
  console.log(JSON.stringify({ control: name }));
  const r = await input();
  assert.equal(r.ok, true, r.error);
  return r;
}
async function main() {
  const cfg = await input();
  const root = process.argv[2];
  const { createApi } = require(join(root, "src/api/client.js"));
  const { pairDevice, mobileSession } = require(
    join(root, "src/api/gateway.js"),
  );
  const { renewConnection } = require(join(root, "src/api/renewal.js"));
  const ca = readFileSync(cfg.ca);
  let dropAck = false;
  const wire = [];
  const results = [];
  const transport = (url, options = {}) =>
    new Promise((resolve, reject) => {
      const u = new URL(url);
      assert.equal(u.origin, "https://rc.example.test");
      const req = request(
        {
          hostname: "127.0.0.1",
          port: cfg.port,
          servername: "rc.example.test",
          ca,
          rejectUnauthorized: true,
          path: u.pathname + u.search,
          method: options.method ?? "GET",
          headers: { ...options.headers, Host: "rc.example.test" },
          signal: options.signal,
        },
        (res) => {
          const chunks = [];
          let size = 0;
          res.on("data", (b) => {
            size += b.length;
            if (size > 2000000) req.destroy(Error("Response budget"));
            else chunks.push(b);
          });
          res.on("end", () => {
            wire.push({
              method: options.method ?? "GET",
              path: u.pathname,
              status: res.statusCode,
            });
            if (dropAck) {
              dropAck = false;
              reject(
                Error("Controlled lost acknowledgement after actual commit"),
              );
              return;
            }
            resolve(
              new Response(Buffer.concat(chunks), {
                status: res.statusCode,
                headers: res.headers,
              }),
            );
          });
        },
      );
      req.on("error", reject);
      if (options.body) req.write(options.body);
      req.end();
    });
  async function scenario(name, f) {
    try {
      await f();
      results.push({ scenario: name, status: "PASS" });
    } catch (e) {
      e.rc_scenario = name;
      throw e;
    }
  }
  const origin = "https://rc.example.test";
  const id = randomUUID();
  let paired = await pairDevice(
    origin,
    cfg.writer_code,
    id,
    "RC disposable client",
    transport,
  );
  let config = {
    origin,
    session: paired.session,
    refresh: paired.refresh,
    deviceId: id,
    renewalExpiresAt: paired.metadata.renewal_expires_at_ms,
    scopes: paired.metadata.scopes,
    accounts: paired.metadata.accounts,
  };
  let revoked = 0;
  let api = createApi(config, transport, () => revoked++, {
    profileScannerEnabled: true,
  });
  const reader = await pairDevice(
    origin,
    cfg.reader_code,
    randomUUID(),
    "RC read scoped client",
    transport,
  );
  const readApi = createApi(
    {
      origin,
      session: reader.session,
      scopes: reader.metadata.scopes,
      accounts: reader.metadata.accounts,
    },
    transport,
    () => revoked++,
  );
  let core, profile, bound, track;
  await scenario("pairing_scopes_tls_and_market_catalogue", async () => {
    const s = await mobileSession(config, transport);
    assert(!s.scopes.includes("paper:write"));
    assert(!s.scopes.includes("notifications:write"));
    assert.equal((await api.health()).real_execution, false);
    assert((await api.markets()).items.length > 0);
  });
  await scenario("analysis_saved_closed_snapshot_and_research", async () => {
    core = await api.analyze({
      data_mode: "live",
      timeframe: "1H",
      timeframes: ["4H"],
      risk_portfolio: "MANUAL",
      idempotency_key: "rc-core-analysis",
      auto_paper: false,
    });
    assert.equal(core.provider, "RC_CONTROLLED_FIXTURE");
    assert.equal(core.auto_order_id, null);
    assert.deepEqual(await api.detail(core.analysis_id), core);
    const candles = await api.candles(core.analysis_id);
    assert(
      candles.candles.every(
        (b) => b.is_final && b.close_time_ms <= core.created_at_ms,
      ),
    );
    assert.equal(core.technical_methods.research_context.status, "available");
    const cat = await api.researchCatalogue(core.analysis_id, "MANUAL");
    assert.equal(cat.source_record_id, candles.source_record_id);
    const body = {
      source_record_id: cat.source_record_id,
      symbol: cat.symbol,
      timeframe: cat.timeframe,
      anchor_ms: cat.anchors.at(-2).open_time_ms,
      parameters: { ema_period: 8 },
    };
    const research = await api.computeResearch(
      core.analysis_id,
      "MANUAL",
      body,
    );
    assert.equal(research.anchored_vwap.status, "available");
    assert.equal(research.trade_permission, false);
    assert.deepEqual(
      await api.computeResearch(core.analysis_id, "MANUAL", body),
      research,
    );
    await assert.rejects(
      api.computeResearch(core.analysis_id, "MANUAL", {
        ...body,
        parameters: { ema_period: 999 },
      }),
      (e) => e.status === 422,
    );
    assert.deepEqual(await api.detail(core.analysis_id), core);
  });
  await scenario(
    "older_backend_missing_research_requires_update_not_generic_outage",
    async () => {
      await control("legacy_research");
      await assert.rejects(
        api.researchCatalogue(core.analysis_id, "MANUAL"),
        (e) => e.code === "BACKEND_UPDATE_REQUIRED" && e.status === 404,
      );
      await control("modern_research");
    },
  );
  await scenario(
    "profile_create_revision_select_analysis_and_lost_ack_retry",
    async () => {
      profile = await api.saveProfile("MANUAL", {
        idempotency_key: "rc-profile-create",
      });
      const revision = await api.saveProfile(
        "MANUAL",
        { idempotency_key: "rc-profile-revise" },
        profile.profile_id,
      );
      assert.equal(revision.parent_id, profile.profile_id);
      const command = {
        data_mode: "live",
        timeframe: "1m",
        risk_portfolio: "MANUAL",
        profile_id: revision.profile_id,
        idempotency_key: "rc-profile-analysis",
        auto_paper: false,
      };
      dropAck = true;
      await assert.rejects(api.analyze(command), (e) => e.uncertain === true);
      bound = await api.analyze(command);
      assert.equal(
        bound.technical_methods.profile_control.profile_record_id,
        revision.profile_id,
      );
      assert.equal(
        (
          await api.evaluateProfile(
            "MANUAL",
            revision.profile_id,
            bound.analysis_id,
          )
        ).trade_permission,
        false,
      );
      assert.equal(
        (await api.analyses()).filter(
          (a) => a.analysis_id === bound.analysis_id,
        ).length,
        1,
      );
      await assert.rejects(
        readApi.saveProfile("MANUAL", {
          idempotency_key: "unauthorized-profile",
        }),
        (e) => e.code === "SCOPE_DENIED",
      );
      await assert.rejects(
        readApi.profile("AUTO", profile.profile_id),
        (e) => e.status === 403,
      );
      await assert.rejects(
        api.profile("MANUAL", "0".repeat(64)),
        (e) => e.status === 404,
      );
      profile = revision;
    },
  );
  await scenario(
    "scanner_follow_profile_binding_and_no_auto_orders",
    async () => {
      const p = await api.saveProfile("AUTO", {
        idempotency_key: "rc-watch-profile",
        selection: {
          bias_timeframe: "4H",
          setup_timeframe: "1H",
          trigger_timeframe: "15m",
        },
      });
      const w = await api.watch({
        symbol: "BTCUSDT",
        timeframe: "1H",
        profile_id: p.profile_id,
        auto_paper: false,
      });
      assert.equal(w.profile_id, p.profile_id);
      assert.equal(w.auto_paper, false);
      assert((await api.watches()).every((w) => !w.auto_paper));
      await api.scanner();
      track = await api.follow(bound.analysis_id);
      assert.equal(track.worker_running, false);
      assert.equal(
        (await api.detail(track.last_analysis_id)).technical_methods
          .profile_control.profile_record_id,
        profile.profile_id,
      );
      await api.saveProfile(
        "MANUAL",
        { idempotency_key: "rc-after-follow-revision" },
        profile.profile_id,
      );
      await api.setFollowPolicy(track.tracking_id, true);
      await api.pause(false);
      await api.tick();
      await api.jobs();
      const notifications = await api.notifications();
      assert(
        notifications.every(
          (n) =>
            n.delivery_status === "pending" &&
            n.delivery_service === "not_configured",
        ),
      );
    },
  );
  await scenario(
    "provider_outage_wait_recovery_and_follow_lifecycle",
    async () => {
      await control("outage");
      const a = await api.analyze({
        data_mode: "live",
        timeframe: "1H",
        risk_portfolio: "MANUAL",
        idempotency_key: "rc-outage-analysis",
      });
      assert.equal(a.direction, "WAIT");
      assert.equal(a.price, null);
      assert.equal(a.levels, null);
      assert.equal(a.reason, "provider_unavailable");
      await api.tick();
      await control("recover");
      await api.tick();
      const follows = await api.follows();
      assert.equal(
        (
          await api.detail(
            follows.find((t) => t.tracking_id === track.tracking_id)
              .last_analysis_id,
          )
        ).technical_methods.profile_control.profile_record_id,
        profile.profile_id,
      );
      const n = await api.notifications();
      assert(n.every((x) => x.delivery_status === "pending"));
      assert(n.some((x) => x.details.change_kind === "source_unavailable"));
      assert(n.some((x) => x.details.change_kind === "source_recovered"));
      const ids = n.map((x) => x.notification_id);
      assert.equal(new Set(ids).size, ids.length);
    },
  );
  let opportunityId;
  await scenario(
    "dual_scanner_explicit_grant_worker_and_saved_opportunities",
    async () => {
      assert(paired.metadata.scopes.includes("discovery:write"));
      const body = {
        idempotency_key: "rc9-scanner-config",
        enabled: true,
        discovery: true,
        favorites: ["BTCUSDT"],
        interval_seconds: 60,
      };
      dropAck = true;
      await assert.rejects(
        api.configureMarketScanner("MANUAL", body),
        (e) => e.uncertain,
      );
      const configured = await api.configureMarketScanner("MANUAL", body);
      assert.equal(configured.config.revision, 1);
      await assert.rejects(
        readApi.configureMarketScanner("MANUAL", body),
        (e) => e.code === "SCOPE_DENIED",
      );
      const worker = await control("discovery_worker");
      assert.equal(worker.worker_seen_active, true);
      const view = await readApi.marketScanner("MANUAL");
      assert.equal(view.runtime.worker_active, false);
      assert.equal(view.universe.symbols.length, 3);
      assert(view.runtime.backlog <= 1);
      const opportunities = await readApi.opportunities("MANUAL");
      const btc = opportunities.items.filter((o) => o.symbol === "BTCUSDT");
      assert.equal(btc.length, 1);
      opportunityId = btc[0].opportunity_id;
      assert.deepEqual(btc[0].modes, ["discovery", "favorites"]);
      assert.equal(btc[0].trade_permission, false);
      const detail = await readApi.opportunity("MANUAL", opportunityId);
      assert(detail.events.length > 0);
      assert.equal(
        (await readApi.detail(detail.opportunity.last_analysis_id))
          .auto_order_id,
        null,
      );
      await assert.rejects(
        readApi.opportunities("AUTO"),
        (e) => e.status === 403,
      );
    },
  );
  await scenario("opportunity_outage_recovery_dedup_and_chain", async () => {
    const before = await readApi.opportunity("MANUAL", opportunityId);
    const outage = await control("discovery_outage");
    assert.equal(outage.chain.status, "PASS");
    assert.equal(
      (await readApi.opportunity("MANUAL", opportunityId)).opportunity.state,
      "UNAVAILABLE",
    );
    const recovery = await control("discovery_recover");
    assert.equal(recovery.chain.status, "PASS");
    const after = await readApi.opportunity("MANUAL", opportunityId);
    assert.equal(after.opportunity.state, before.opportunity.state);
    assert(
      after.events.some(
        (e) => e.reason === "source_recovered_no_new_market_confirmation",
      ),
    );
    const count = after.events.length;
    await api.marketScannerTick("MANUAL");
    assert.equal(
      (await readApi.opportunity("MANUAL", opportunityId)).events.length,
      count,
    );
  });
  await scenario(
    "named_profile_timeframes_and_explicit_account_activation",
    async () => {
      const scoped = await api.saveProfile("MANUAL", {
        idempotency_key: "activation-mtf-profile",
        selection: {
          bias_timeframe: "4H",
          setup_timeframe: "1H",
          trigger_timeframe: "15m",
        },
      });
      const before = await readApi.marketScanner("MANUAL");
      const config = {
        idempotency_key: "activation-passive-save",
        expected_revision: before.config.revision,
        name: "Akşam kontrolü",
        runtime_mode: "selected_profile",
        enabled: false,
        discovery: false,
        favorites: ["BTCUSDT"],
        timeframe: "1H",
        profile_id: scoped.profile_id,
      };
      const saved = await api.configureMarketScanner("MANUAL", config);
      assert.equal(saved.config.enabled, false);
      assert.equal(saved.config.name, config.name);
      assert.equal(saved.config.timeframe, "1H");
      assert.equal(
        (await readApi.marketScanner("MANUAL")).runtime.worker_active,
        false,
      );
      const active = {
        ...config,
        idempotency_key: "activation-explicit-start",
        expected_revision: saved.config.revision,
        enabled: true,
      };
      await assert.rejects(
        api.configureMarketScanner("MANUAL", active),
        (e) => e.code === "DISCOVERY_ACTIVATION_BLOCKED" && e.status === 409,
      );
      await control("activation_runtime_start");
      assert.equal(
        (await readApi.marketScanner("MANUAL")).runtime.activation.state,
        "ready_to_activate",
      );
      const started = await api.configureMarketScanner("MANUAL", active);
      assert.equal(started.config.enabled, true);
      assert.deepEqual(
        await api.configureMarketScanner("MANUAL", active),
        started,
      );
      await control("activation_runtime_stop");
      assert.equal(
        (await readApi.marketScanner("MANUAL")).runtime.activation.state,
        "blocked",
      );
      await api.saveProfile(
        "MANUAL",
        {
          idempotency_key: "activation-new-revision",
          selection: scoped.selection,
        },
        scoped.profile_id,
      );
      assert.equal(
        (await readApi.marketScanner("MANUAL")).config.profile_id,
        scoped.profile_id,
      );
      const paused = await api.configureMarketScanner("MANUAL", {
        ...config,
        idempotency_key: "activation-explicit-pause",
        expected_revision: started.config.revision,
        runtime_mode: "off",
        enabled: false,
      });
      assert.equal(paused.config.enabled, false);
      assert.equal(
        (await readApi.marketScanner("MANUAL")).runtime.worker_active,
        false,
      );
    },
  );
  await scenario(
    "paper_isolation_equity_archive_pagination_and_independent_audit",
    async () => {
      await control("seed_observations");
      const end = cfg.now + 86400000;
      const accounts = await api.portfolios();
      assert.equal(accounts.length, 2);
      assert.equal((await readApi.portfolios()).length, 1);
      for (const account of ["AUTO", "MANUAL"]) {
        assert.equal((await api.orders(account)).length, 1);
        await api.positions(account);
        await api.transactions(account);
        const h = await api.equityHistory(account, 0, end);
        assert(h.points.length > 0);
        assert(h.points.every((p) => p.portfolio_id === account));
        const first = await api.equityWindow(account, 0, end);
        assert.equal(first.points.length, 200);
        assert(first.next_cursor);
        const next = await api.equityWindow(account, 0, end, first.next_cursor);
        assert(next.points.length > 0);
        assert(
          !first.points.some((p) =>
            next.points.some((q) => p.sequence === q.sequence),
          ),
        );
        assert.deepEqual(
          await api.equityWindow(account, 0, end, first.next_cursor),
          next,
        );
      }
      await api.performance();
      assert.equal((await control("audit")).status, "PASS");
    },
  );
  await scenario(
    "notification_authorization_and_closed_paper_permissions",
    async () => {
      const p = await api.notificationPreferences("MANUAL");
      assert.equal(p.push_status, "NOT_CONFIGURED");
      assert.equal(p.sender_running, false);
      const cmd = {
        idempotency_key: "rc-denied-preferences",
        expected_revision: p.revision,
        enabled: true,
        categories: { analysis: true },
      };
      await assert.rejects(
        api.setNotificationPreferences("MANUAL", cmd),
        (e) => e.code === "SCOPE_DENIED",
      );
      const raw = await transport(
        origin + "/api/v2/portfolios/MANUAL/notification-preferences",
        {
          method: "POST",
          headers: {
            Authorization: "Bearer " + config.session,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(cmd),
        },
      );
      assert.equal(raw.status, 403);
      await assert.rejects(
        api.createOrder("MANUAL", {
          analysis_id: core.analysis_id,
          idempotency_key: "rc-denied-order",
        }),
        (e) => e.code === "PAPER_WRITES_DISABLED",
      );
      const r = await transport(origin + "/api/v2/portfolios/MANUAL/orders", {
        method: "POST",
        headers: {
          Authorization: "Bearer " + config.session,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({}),
      });
      assert.equal(r.status, 403);
      const n = await readApi.notificationPreferences("MANUAL");
      assert.equal(n.revision, 0);
      assert.equal(revoked, 0);
    },
  );
  await scenario(
    "restart_preserves_snapshots_profiles_sessions_and_audit",
    async () => {
      await control("restart");
      assert.deepEqual(await api.detail(core.analysis_id), core);
      assert.equal(
        (await api.profile("MANUAL", profile.profile_id)).revision,
        2,
      );
      assert.equal(
        (
          await api.detail(
            (await api.follows()).find(
              (x) => x.tracking_id === track.tracking_id,
            ).last_analysis_id,
          )
        ).technical_methods.profile_control.profile_record_id,
        profile.profile_id,
      );
      assert.equal(
        (await readApi.opportunity("MANUAL", opportunityId)).opportunity
          .opportunity_id,
        opportunityId,
      );
      await mobileSession(config, transport);
      assert.equal((await control("audit")).status, "PASS");
    },
  );
  await scenario(
    "renewal_lost_ack_replays_same_committed_rotation_and_revocation",
    async () => {
      let saved = config;
      dropAck = true;
      const random = async (p) => p + randomBytes(32).toString("base64url");
      const save = async (v) => {
        saved = v;
      };
      await assert.rejects(
        renewConnection(config, save, random, transport),
        (e) => e.code === "RENEWAL_UNCERTAIN",
      );
      assert(saved.pendingRenewal);
      const old = api;
      const r = await renewConnection(saved, save, random, transport);
      config = r.config;
      assert(!config.pendingRenewal);
      await assert.rejects(old.health(), (e) => e.status === 401);
      assert.equal(revoked, 1);
      api = createApi(config, transport);
      await api.health();
      await control("revoke");
      await assert.rejects(api.health(), (e) => e.status === 401);
    },
  );
  // Use the independent read session after writer revocation.
  await scenario(
    "invalid_gateway_response_rejected_by_actual_android_validator",
    async () => {
      await control("malformed");
      await assert.rejects(
        readApi.health(),
        (e) => e.code === "INVALID_RESPONSE",
      );
    },
  );
  await scenario("backend_unavailable_is_not_fake_success", async () => {
    await control("backend_down");
    await assert.rejects(readApi.health(), (e) => e.status === 503);
    await control("backend_up");
    await readApi.health();
  });
  await scenario("real_https_timeout_and_disconnected_gateway", async () => {
    await control("slow");
    const start = Date.now();
    await assert.rejects(
      readApi.health(),
      (e) => e.code === "NETWORK" || e.code === "TIMEOUT",
    );
    assert(Date.now() - start >= 14000);
    await control("gateway_down");
    await assert.rejects(readApi.health());
  });
  api.dispose();
  readApi.dispose();
  lines.close();
  console.log(
    JSON.stringify({
      results,
      wire_requests: wire.length,
      wire_statuses: [...new Set(wire.map((x) => x.status))],
      transport:
        "real certificate-verified loopback HTTPS to production Gateway then production Backend ASGI",
      market_data:
        "controlled fixture; live wire contract only, never live market evidence",
      storage:
        "renewal save callback in-memory; physical SecureStore unverified",
    }),
  );
}
main().catch((e) => {
  console.log(
    JSON.stringify({
      failure: true,
      scenario: e.rc_scenario,
      error: e.code ?? e.name ?? "Error",
      message: String(e.message).slice(0, 180),
    }),
  );
  process.exitCode = 1;
  lines.close();
});

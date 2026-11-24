// Generated from the unchanged backend OpenAPI. Do not hand edit.
export interface components {
  schemas: {
    AnalysisResponse: {
      age_ms?: number | null;
      analysis_id: string;
      auto_order_id?: string | null;
      conflicting_evidence: {
        [key: string]: unknown;
      }[];
      contract_type: string;
      created_at_ms: number;
      data_mode: "live" | "fixture";
      direction: "bullish" | "bearish" | "WAIT";
      expires_at_ms: number;
      indicators: {
        [key: string]: unknown;
      };
      levels?: components["schemas"]["Levels"] | null;
      market: string;
      market_rules: {
        [key: string]: unknown;
      };
      mtf: {
        [key: string]: unknown;
      };
      price?: string | null;
      price_kind: string;
      price_time_ms?: number | null;
      provider: string;
      quality: {
        [key: string]: unknown;
      };
      quote_currency: string;
      reason: string;
      regime: {
        [key: string]: unknown;
      };
      risk: {
        [key: string]: unknown;
      };
      risk_portfolio: "AUTO" | "MANUAL";
      router: {
        [key: string]: unknown;
      };
      scenarios: {
        [key: string]: string;
      };
      strategy_setups?: {
        [key: string]: unknown;
      };
      supporting_evidence: {
        [key: string]: unknown;
      }[];
      symbol: string;
      technical_methods?: {
        [key: string]: unknown;
      };
      timeframe: string;
      timeframes: string[];
      venue: string;
      version: string;
      warnings: string[];
    };
    AnalyzeRequest: {
      auto_paper?: boolean;
      data_mode?: "live" | "fixture";
      fixture_case?:
        "trend" | "range" | "stale" | "unfinished" | "mixed" | "gap";
      idempotency_key: string;
      market?: "crypto_spot" | "forex_spot" | "gold_spot";
      profile_id?: string | null;
      risk_portfolio?: "AUTO" | "MANUAL";
      symbol?: "BTCUSDT" | "ETHUSDT" | "SOLUSDT" | "EURUSD" | "XAUUSD";
      timeframe?: "1m" | "5m" | "15m" | "1H" | "4H" | "1D";
      timeframes?: ("1m" | "5m" | "15m" | "1H" | "4H" | "1D")[];
    };
    CancelRequest: {
      idempotency_key: string;
    };
    ChartCandle: {
      close: string;
      close_time_ms: number;
      high: string;
      is_final: true;
      low: string;
      open: string;
      open_time_ms: number;
      volume: string;
    };
    ChartResponse: {
      analysis_id: string;
      as_of_ms: number;
      candles: components["schemas"]["ChartCandle"][];
      contract_type: "spot";
      data_mode: "live" | "fixture";
      price_kind: "last";
      provider: string;
      quote_currency: "USDT";
      snapshot_only?: true;
      source: string;
      source_record_id: string;
      symbol: string;
      timeframe: string;
      venue: string;
      volume_kind?: "real";
    };
    CloseRequest: {
      idempotency_key: string;
      quantity: number | string;
    };
    CloseResult: {
      close_request_id: string;
      created_at_ms: number;
      position_id: string;
      quantity: string;
      status: string;
    };
    DiscoveryReceipt: {
      config: {
        [key: string]: unknown;
      };
      data_mode: "fixture" | "live";
      portfolio_id: "AUTO" | "MANUAL";
    };
    DiscoveryTick: {
      data_mode: "fixture" | "live";
      jobs?: {
        [key: string]: unknown;
      }[];
      portfolio_id: "AUTO" | "MANUAL";
      provider_calls?: number;
      reason?: string | null;
      status: string;
      trade_permission?: false;
    };
    DiscoveryView: {
      config: {
        [key: string]: unknown;
      };
      data_mode: "fixture" | "live";
      jobs: {
        [key: string]: unknown;
      }[];
      portfolio_id: "AUTO" | "MANUAL";
      runtime: {
        [key: string]: unknown;
      };
      trade_permission?: false;
      universe: {
        [key: string]: unknown;
      };
      version?: string;
    };
    DiscoveryWrite: {
      discovery?: boolean;
      enabled?: boolean;
      expected_revision?: number;
      favorites?: ("BTCUSDT" | "ETHUSDT" | "SOLUSDT")[];
      idempotency_key: string;
      interval_seconds?: number;
      name?: string;
      notify_confirmed?: boolean;
      notify_early?: boolean;
      notify_expired?: boolean;
      notify_invalidated?: boolean;
      notify_unavailable?: boolean;
      profile_id?: string | null;
      runtime_mode?: "off" | "selected_profile" | "supported_markets" | null;
      timeframe?: "5m" | "15m" | "1H" | "4H" | "1D";
      ttl_seconds?: number;
    };
    EquityHistoryResponse: {
      audit_coverage: "domain_journal" | "checksum_only";
      coverage?: "forward_only";
      coverage_started_at_ms: number;
      data_mode: "fixture" | "live";
      has_more: boolean;
      note: string;
      period: "day" | "week" | "month";
      period_status: "complete" | "incomplete_budget_or_timestamp";
      period_totals: {
        [key: string]: unknown;
      }[];
      points: components["schemas"]["EquityPoint"][];
      portfolio_id: "AUTO" | "MANUAL";
    };
    EquityPoint: {
      ambiguous_positions: number;
      available_cash_quote: string;
      cash_quote: string;
      chart_eligible: boolean;
      closed_positions: number;
      data_mode: "fixture" | "live";
      drawdown_scope?: "observed_complete_snapshots_since_coverage";
      effective_at_ms: number;
      equity_quote: string | null;
      fees_quote: string;
      marks: {
        [key: string]: unknown;
      }[];
      maximum_drawdown_pct: string;
      maximum_drawdown_quote: string;
      open_positions: number;
      peak_equity_quote: string | null;
      pending_orders: number;
      portfolio_id: "AUTO" | "MANUAL";
      proof_coverage?: "domain_journal" | "checksum_only";
      quality_status: "complete" | "stale" | "incomplete";
      quote_currency?: "USDT";
      realized_pnl_quote: string;
      recorded_at_ms: number;
      reservations: {
        [key: string]: unknown;
      }[];
      reserved_cash_quote: string;
      schema_version?: 1;
      sequence: number;
      snapshot_id: string;
      source: {
        [key: string]: unknown;
      };
      spread_slippage_breakdown?: "not_separately_recorded";
      strategy_results: {
        [key: string]: unknown;
      }[];
      transaction_watermark: number;
      unrealized_pnl_quote: string | null;
    };
    EquityWindowResponse: {
      data_mode: "fixture" | "live";
      excluded_incomplete: number;
      has_more: boolean;
      next_cursor: string | null;
      note?: string;
      observations_scanned: number;
      ordering?: "account_sequence";
      points: components["schemas"]["EquityPoint"][];
      portfolio_id: "AUTO" | "MANUAL";
      request_cursor: string;
      sampling: "raw" | "minmax";
      status: "complete" | "incomplete_budget";
      watermark: number;
    };
    ErrorDetail: {
      code: string;
      message: string;
    };
    ErrorResponse: {
      error: components["schemas"]["ErrorDetail"];
    };
    EventResult: {
      close_time_ms: number;
      data_mode: string;
      event_id: string;
      market_event: {
        [key: string]: unknown;
      };
      processed: {
        [key: string]: unknown;
      }[];
    };
    FixtureEventRequest: {
      close: number | string;
      close_time_ms: number;
      high: number | string;
      is_final?: boolean;
      low: number | string;
      open: number | string;
      open_time_ms: number;
      symbol: "BTCUSDT" | "ETHUSDT" | "SOLUSDT";
      volume: number | string;
    };
    HealthResponse: {
      auth_required?: boolean;
      data_mode: string;
      provider: string;
      provider_status: string;
      real_execution?: false;
      status: string;
      storage: string;
      version: string;
    };
    IndicatorSettings: {
      adx_period?: number;
      atr_period?: number;
      bias_confirmation?: boolean;
      bias_timeframe?: string | null;
      bollinger_multiplier?: string;
      bollinger_period?: number;
      confirmation_filter?: string;
      donchian_period?: number;
      ema_period?: number;
      macd_fast?: number;
      macd_signal?: number;
      macd_slow?: number;
      rsi_period?: number;
      sma_period?: number;
      stochastic_period?: number;
      stochastic_smooth?: number;
      supertrend_multiplier?: string;
      supertrend_period?: number;
    };
    Levels: {
      entry_high: string;
      entry_low: string;
      invalidation: string;
      reward_risk: string;
      target_1: string;
      target_2: string;
      target_3?: string | null;
    };
    MarketQuote: {
      change_percent_24h: string;
      chart_status: "available" | "unavailable";
      history: components["schemas"]["QuotePoint"][];
      price: string;
      source_time_ms: number;
      symbol: "BTCUSDT" | "ETHUSDT" | "SOLUSDT";
    };
    MarketsResponse: {
      data_mode: string;
      items: {
        [key: string]: unknown;
      }[];
    };
    NoticeCategories: {
      analysis?: boolean;
      risk?: boolean;
      source?: boolean;
      system?: boolean;
    };
    NoticePreferences: {
      categories: components["schemas"]["NoticeCategories"];
      data_mode: "fixture" | "live";
      device_credentials_supported?: false;
      enabled: boolean;
      expires_at_ms: number | null;
      observed_at_ms: number;
      portfolio_id: "AUTO" | "MANUAL";
      push_status?: "NOT_CONFIGURED";
      recipient_id: string | null;
      recipient_status: "not_registered" | "active" | "revoked" | "expired";
      revision: number;
      scope?: "owned_logical_recipient_only";
      sender_running?: false;
      state_semantics?: "read_observation_or_immutable_command_receipt";
    };
    NoticePreferencesWrite: {
      categories?: components["schemas"]["NoticeCategories"];
      enabled: boolean;
      expected_revision: number;
      idempotency_key: string;
      recipient_action?: "keep" | "replace" | "revoke";
    };
    NotificationResponse: {
      created_at_ms: number;
      data_mode: "fixture" | "live";
      delivery_service: "not_configured";
      delivery_status: "pending";
      details: {
        [key: string]: unknown;
      };
      kind: "analysis" | "paper_event" | "scanner_error";
      notification_id: string;
    };
    OpportunityDetail: {
      data_mode: "fixture" | "live";
      events: {
        [key: string]: unknown;
      }[];
      opportunity: components["schemas"]["OpportunityRecord"];
      portfolio_id: "AUTO" | "MANUAL";
      trade_permission?: false;
    };
    OpportunityList: {
      data_mode: "fixture" | "live";
      items: components["schemas"]["OpportunityRecord"][];
      next_offset?: number | null;
      portfolio_id: "AUTO" | "MANUAL";
      trade_permission?: false;
    };
    OpportunityRecord: {
      direction: "bullish" | "bearish";
      evidence: {
        [key: string]: unknown;
      };
      expires_at_ms: number;
      first_known_ms: number;
      first_source_ms: number;
      initial_analysis_id: string;
      last_analysis_id: string;
      last_observed_ms: number;
      last_source_ms: number;
      last_valid_state: "EARLY" | "CONFIRMED";
      missing: string[];
      modes: ("favorites" | "discovery")[];
      opportunity_id: string;
      portfolio_id: "AUTO" | "MANUAL";
      profile_id: string | null;
      provider: string;
      reason: string;
      setup_fingerprint: string;
      source: string;
      source_record_ids: {
        [key: string]: unknown;
      };
      stale: boolean;
      state: "EARLY" | "CONFIRMED" | "INVALIDATED" | "EXPIRED" | "UNAVAILABLE";
      strategy_id: string;
      symbol: "BTCUSDT" | "ETHUSDT" | "SOLUSDT";
      timeframe: "5m" | "15m" | "1H" | "4H" | "1D";
      trade_permission?: false;
      venue: string;
    };
    OrderRequest: {
      analysis_id: string;
      idempotency_key: string;
      quantity?: number | string | null;
    };
    OrderResponse: {
      adverse_rate: string;
      analysis_id: string;
      created_at_ms: number;
      data_mode: string;
      execution_model: string;
      expires_at_ms: number;
      fee_rate: string;
      order_id: string;
      paper_only?: true;
      participation_fraction: string;
      portfolio_id: string;
      quantity: string;
      remaining_quantity: string;
      risk: {
        [key: string]: unknown;
      };
      status: string;
      symbol: string;
    };
    PauseRequest: {
      paused: boolean;
    };
    PerformanceResponse: {
      data_mode: string;
      note: string;
      paper_only?: true;
      portfolios: {
        [key: string]: unknown;
      }[];
    };
    PollRequest: {
      symbols?: ("BTCUSDT" | "ETHUSDT" | "SOLUSDT")[];
    };
    PortfolioResponse: {
      available_cash_quote: string;
      cash_quote: string;
      data_mode: string;
      equity_quote: string;
      open_positions: number;
      paper_only?: true;
      paused: boolean;
      pending_orders: number;
      portfolio_id: "AUTO" | "MANUAL";
      quote_currency: string;
      realized_loss_today_quote: string;
      realized_pnl_quote: string;
      reserved_cash_quote: string;
      seed_equity_quote: string;
      unrealized_pnl_quote: string;
    };
    PositionResponse: {
      ambiguity_seen?: boolean;
      average_entry: string;
      cost_basis_quote: string;
      data_mode: string;
      invalidation: string;
      mark_price: string;
      mark_time_ms: number;
      opened_at_ms: number;
      order_id: string;
      paper_only?: true;
      pending_closes?: {
        [key: string]: unknown;
      }[];
      portfolio_id: string;
      position_id: string;
      quantity: string;
      realized_pnl_quote: string;
      status: string;
      stop_triggered?: boolean;
      symbol: string;
      target_1: string;
      target_2: string;
      unrealized_pnl_quote: string;
    };
    ProfileEvaluation: {
      analysis_id: string;
      passes: boolean;
      portfolio_id: "AUTO" | "MANUAL";
      profile_id: string;
      reason: string;
      scope: string;
      trade_permission?: false;
    };
    ProfileEvaluationRequest: {
      analysis_id: string;
    };
    ProfileRecord: {
      content_id: string;
      created_at_ms: number;
      group_id: string;
      parent_id: string | null;
      portfolio_id: "AUTO" | "MANUAL";
      profile_id: string;
      revision: number;
      scope?: "restrict_existing_analysis_only";
      selection: components["schemas"]["ProfileSelection"];
      strategy_versions: {
        [key: string]: string;
      };
      trade_permission?: false;
    };
    ProfileSelection: {
      allowed_regimes?: string[];
      analysis_every_bars?: number;
      bias_timeframe?: string;
      minimum_confirmations?: number;
      required_methods?: string[];
      setup_timeframe?: string;
      strategy_ids?: string[];
      trigger_timeframe?: string;
    };
    ProfileWrite: {
      idempotency_key: string;
      selection?: components["schemas"]["ProfileSelection"];
    };
    QuotePoint: {
      price: string;
      time_ms: number;
    };
    QuotesResponse: {
      chart_timeframe?: "1H";
      data_mode?: "live";
      fetched_at_ms: number;
      items: components["schemas"]["MarketQuote"][];
      provider?: "binance_public_spot";
      provider_status: "available" | "unavailable";
      real_execution?: false;
      refresh_after_seconds?: 30;
      stale: boolean;
    };
    ResearchAnchor: {
      close_time_ms: number;
      open_time_ms: number;
    };
    ScannerJob: {
      analysis_id?: string | null;
      closed_bar_ms: number;
      job_id: string;
      reason?: string | null;
      started_at_ms?: number | null;
      status: "running" | "completed" | "failed" | "skipped_stale";
      symbol: string;
      timeframe: string;
    };
    ScannerState: {
      interval_seconds: number;
      last_error: string | null;
      last_tick_ms: number | null;
      lease_id: string | null;
      lease_until_ms: number;
      max_analyses_per_tick: number;
      paused: boolean;
    };
    SnapshotResearchRequest: {
      anchor_ms?: number | null;
      implementation_version?: "v2-snapshot-research-1";
      parameters?: components["schemas"]["IndicatorSettings"];
      schema_version?: 1;
      source_record_id: string;
      symbol: "BTCUSDT" | "ETHUSDT" | "SOLUSDT";
      timeframe: "1m" | "5m" | "15m" | "1H" | "4H" | "1D";
    };
    SnapshotResearchResponse: {
      analysis_id: string;
      anchored_vwap?: {
        [key: string]: unknown;
      };
      anchors?: components["schemas"]["ResearchAnchor"][];
      as_of_ms: number;
      configuration_id?: string | null;
      data_mode: "fixture" | "live";
      indicator_research?: {
        [key: string]: unknown;
      };
      limitations?: string[];
      parameter_id: string;
      parameter_version?: string;
      parameters: {
        [key: string]: unknown;
      };
      portfolio_id: "AUTO" | "MANUAL";
      reason?: string | null;
      schema_version?: 1;
      snapshot_only?: true;
      source: string;
      source_digest: string;
      source_record_id: string;
      status: "available" | "unavailable";
      symbol: string;
      timeframe: string;
      trade_permission?: false;
      version?: string;
      warmup_bars: number;
    };
    TickResponse: {
      jobs: components["schemas"]["ScannerJob"][];
      reason?: string | null;
      status: "paused" | "busy" | "completed" | "blocked";
    };
    TrackingChange: {
      enabled: boolean;
    };
    TrackingCreate: {
      analysis_id: string;
    };
    TrackingResponse: {
      data_mode: "fixture" | "live";
      enabled: boolean;
      last_analysis_id: string;
      last_checked_ms: number | null;
      last_direction: string;
      last_reason: string;
      notified_changes: number;
      origin_analysis_id: string;
      paper_only?: true;
      portfolio_id: "AUTO" | "MANUAL";
      status: "waiting" | "monitoring" | "waiting_data" | "paused" | "error";
      symbol: string;
      timeframe: string;
      tracking_id: string;
      worker_running: boolean;
    };
    TrackingSourcePolicy: {
      data_mode: "fixture" | "live";
      delivery_service?: "not_configured";
      notify_source_changes: boolean;
      portfolio_id: "AUTO" | "MANUAL";
      source_event_ttl_ms?: 900000;
      tracking_id: string;
    };
    TrackingSourcePolicyRequest: {
      notify_source_changes: boolean;
    };
    TransactionResponse: {
      cash_delta_quote: string;
      data_mode: string;
      event_id: string;
      fee_quote: string;
      kind: string;
      order_id: string;
      paper_only?: true;
      portfolio_id: string;
      position_id: string;
      price: string;
      quantity: string;
      realized_pnl_quote: string;
      time_ms: number;
      transaction_id: string;
    };
    WatchRequest: {
      auto_paper?: boolean;
      enabled?: boolean;
      profile_id?: string | null;
      symbol: "BTCUSDT" | "ETHUSDT" | "SOLUSDT";
      timeframe?: "5m" | "15m" | "1H" | "4H" | "1D";
    };
    WatchResponse: {
      auto_paper?: boolean;
      enabled?: boolean;
      profile_id?: string | null;
      symbol: "BTCUSDT" | "ETHUSDT" | "SOLUSDT";
      timeframe?: "5m" | "15m" | "1H" | "4H" | "1D";
      watch_id: string;
    };
  };
}

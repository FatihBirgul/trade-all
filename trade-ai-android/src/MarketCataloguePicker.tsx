import React, { useState } from "react";
import { TextInput } from "react-native";
import { useApp } from "./state";
import { useResource } from "./resource";
import { validTime } from "./domain/scannerHealth";
import { directionText } from "./domain/presentation";
import { useTheme } from "./theme";
import { Button, Choices, Label, Failure, Loading } from "./ui";
import {
  catalogueRows,
  findMarkets,
  marketType,
} from "./domain/marketCatalogue";
export function MarketCataloguePicker({
  favorites,
  disabled,
  onToggle,
  now,
}: {
  favorites: string[];
  now: number;
  disabled: boolean;
  onToggle: (symbol: string) => void;
}) {
  const app = useApp(),
    { colors } = useTheme();
  const [query, setQuery] = useState(""),
    [filter, setFilter] = useState("Hepsi");
  const key = [app.account, app.connectionKey, app.config.session].join("|");
  const q = useResource(
    async () => catalogueRows(await app.api.markets()),
    key + "|catalogue",
  );
  const history = useResource(
    () => app.api.analyses(),
    key + "|recent-analysis",
  );
  const rows = findMarkets(q.data ?? [], query, filter, favorites);
  function lastAnalysis(symbol: string) {
    const a = history.data
      ?.filter(
        (x) =>
          x.risk_portfolio === app.account &&
          x.data_mode === "live" &&
          x.symbol === symbol,
      )
      .sort((x, y) => y.created_at_ms - x.created_at_ms)[0];
    return a && validTime(a.created_at_ms)
      ? "Son 20 sunucu kaydında: " +
          directionText(a.direction) +
          " · " +
          new Date(a.created_at_ms).toISOString() +
          " · " +
          (history.stale || now >= a.expires_at_ms
            ? "geçmiş/eski kayıt"
            : "kaydedilmiş analiz; canlı fiyat değil")
      : "Son 20 kayıtta bu hesap için analiz bulunamadı veya geçmiş doğrulanamadı.";
  }
  return (
    <>
      <Label>Desteklenen piyasa kataloğu · favori kapsamı</Label>
      <TextInput
        accessibilityLabel="Parite ara"
        placeholder="BTC / ETH / SOL / XAU"
        placeholderTextColor={colors.muted}
        value={query}
        onChangeText={setQuery}
        maxLength={32}
        autoCapitalize="characters"
        autoCorrect={false}
        style={{
          color: colors.text,
          borderColor: colors.border,
          borderWidth: 1,
          borderRadius: 10,
          padding: 12,
        }}
      />
      <Choices
        values={["Hepsi", "Favoriler", "Spot", "Kullanılamayan"]}
        value={filter}
        onChange={setFilter}
      />
      <Label>
        Seçili favori: {favorites.length}. Favoriler önceliklidir; keşif ayrı
        moddur. Katalog, bütün dünya piyasaları veya canlı likidite ölçümü
        değildir.
      </Label>
      {q.loading ? (
        <Loading />
      ) : q.error ? (
        <Failure message={q.error} retry={q.reload} />
      ) : null}
      {!q.loading && !q.error && !rows.length ? (
        <Label>
          Arama/filtre için kayıt yok. Desteklenmeyen parite eklenmez.
        </Label>
      ) : null}
      {!q.loading && !q.error
        ? rows.slice(0, 30).map((r) => (
            <React.Fragment key={r.symbol}>
              <Button
                title={(favorites.includes(r.symbol) ? "✓ " : "+ ") + r.symbol}
                secondary
                disabled={
                  disabled || (!r.selectable && !favorites.includes(r.symbol))
                }
                onPress={() => onToggle(r.symbol)}
              />
              <Label muted>
                {marketType(r.market)} · {r.source} / {r.venue} ·{" "}
                {r.selectable ? "Yapılandırılmış kapsam" : "Kullanılamıyor"}.
                Kaynak: {r.sourceStatus}. Favori kaydı, canlı veri veya çalışan
                tarama kanıtı değildir.
              </Label>
              <Label muted>{lastAnalysis(r.symbol)}</Label>
            </React.Fragment>
          ))
        : null}
      {rows.length > 30 ? <Label>İlk 30 kayıt; aramayı daraltın.</Label> : null}
      {(q.loading || q.error) && favorites.length ? (
        <>
          <Label>
            Kayıtlı favoriler · katalog yeniden doğrulanamadı; yalnız çıkarma
            yapılabilir.
          </Label>
          {favorites.slice(0, 10).map((s) => (
            <Button
              key={s}
              title={"✓ " + s}
              secondary
              disabled={disabled}
              onPress={() => onToggle(s)}
            />
          ))}
        </>
      ) : null}
    </>
  );
}

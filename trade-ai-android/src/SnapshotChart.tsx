import React, { useEffect, useMemo, useRef, useState } from "react";
import { PanResponder, View, useWindowDimensions } from "react-native";
import { useTheme } from "./theme";
import { Button, Label } from "./ui";
import {
  chartBars,
  clampWindow,
  ema,
  panWindow,
  snapshotVwap,
  zoomWindow,
  type Snapshot,
  type Window,
} from "./domain/chart";
import type { components } from "./api/schema";
type Levels = components["schemas"]["Levels"];
const HEIGHT = 208;
const price = (v: number) =>
  v.toLocaleString("tr-TR", { maximumSignificantDigits: 7 });
// Axis ticks stay compact at accessibility font sizes; exact OHLC remains below.
const axisPrice = (v: number) =>
  Math.abs(v) < 0.01 || Math.abs(v) >= 1e6
    ? v.toExponential(2).replace(".", ",")
    : v.toLocaleString("tr-TR", {
        maximumSignificantDigits: 5,
        useGrouping: false,
      });
const time = (v: number) =>
  new Date(v).toLocaleString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
function Segment({
  x1,
  y1,
  x2,
  y2,
  color,
}: {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  color: string;
}) {
  const length = Math.hypot(x2 - x1, y2 - y1);
  return (
    <View
      pointerEvents="none"
      style={{
        position: "absolute",
        left: (x1 + x2) / 2 - length / 2,
        top: (y1 + y2) / 2,
        height: 1.5,
        width: length,
        backgroundColor: color,
        transform: [{ rotate: Math.atan2(y2 - y1, x2 - x1) + "rad" }],
      }}
    />
  );
}
export function SnapshotChart({
  snapshot,
  pro = false,
  levels,
}: {
  snapshot: Snapshot;
  pro?: boolean;
  levels?: Levels | null;
}) {
  const { colors } = useTheme();
  const { fontScale } = useWindowDimensions();
  const bars = useMemo(() => chartBars(snapshot), [snapshot]);
  const [width, setWidth] = useState(240);
  const [window, setWindow] = useState<Window>(() =>
    clampWindow(bars.length - 48, 48, bars.length),
  );
  const viewport = useMemo(
    () => clampWindow(window.start, window.count, bars.length),
    [window.start, window.count, bars.length],
  );
  const [selected, setSelected] = useState<number | null>(null);
  const [enabled, setEnabled] = useState<string[]>([]);
  const gesture = useRef({ window: viewport, distance: 0, anchor: 0.5 });
  const latest = useRef({ viewport, total: bars.length, width });
  useEffect(() => {
    latest.current = { viewport, total: bars.length, width };
  }, [viewport, bars.length, width]);
  // PanResponder registers handlers here; it invokes them only after a native touch event.
  const responder = useMemo(
    () =>
      // eslint-disable-next-line react-hooks/refs -- Handlers read refs only when native events fire.
      PanResponder.create({
        onStartShouldSetPanResponder: (e) => e.nativeEvent.touches.length === 2,
        onMoveShouldSetPanResponder: (e, g) =>
          e.nativeEvent.touches.length === 2 ||
          (Math.abs(g.dx) > 7 && Math.abs(g.dx) > Math.abs(g.dy) * 1.5),
        onPanResponderGrant: (e) => {
          const touches = e.nativeEvent.touches;
          const distance =
            touches.length === 2
              ? Math.hypot(
                  touches[0].pageX - touches[1].pageX,
                  touches[0].pageY - touches[1].pageY,
                )
              : 0;
          gesture.current = {
            window: latest.current.viewport,
            distance,
            anchor:
              touches.length === 2
                ? Math.max(
                    0,
                    Math.min(
                      1,
                      (touches[0].locationX + touches[1].locationX) /
                        2 /
                        latest.current.width,
                    ),
                  )
                : 0.5,
          };
        },
        onPanResponderMove: (e, g) => {
          const touches = e.nativeEvent.touches,
            base = gesture.current;
          if (touches.length === 2) {
            const distance = Math.hypot(
              touches[0].pageX - touches[1].pageX,
              touches[0].pageY - touches[1].pageY,
            );
            if (!base.distance) {
              gesture.current = {
                window: latest.current.viewport,
                distance,
                anchor: 0.5,
              };
              return;
            }
            const next = zoomWindow(
              base.window,
              distance / base.distance,
              latest.current.total,
              base.anchor,
            );
            setWindow((old) =>
              old.start === next.start && old.count === next.count ? old : next,
            );
          } else if (!base.distance) {
            const next = panWindow(
              base.window,
              g.dx,
              latest.current.width,
              latest.current.total,
            );
            setWindow((old) =>
              old.start === next.start && old.count === next.count ? old : next,
            );
          }
        },
        onPanResponderTerminationRequest: () => true,
      }),
    [],
  );
  const overlays = useMemo(
    () => ({
      EMA20: ema(bars, 20),
      EMA50: ema(bars, 50),
      VWAP: snapshotVwap(bars, snapshot.volume_kind === "real"),
    }),
    [bars, snapshot.volume_kind],
  );
  if (!bars.length)
    return (
      <Label>
        Mum verisi çizim için doğrulanamadı veya güvenli boyut sınırını aştı.
      </Label>
    );
  const visible = bars.slice(viewport.start, viewport.start + viewport.count);
  const active = pro ? enabled : [];
  const levelValues =
    levels && active.includes("Seviyeler")
      ? [
          ["Giriş alt", levels.entry_low],
          ["Giriş üst", levels.entry_high],
          ["Geçersizlik", levels.invalidation],
          ["TP1", levels.target_1],
          ["TP2", levels.target_2],
        ]
          .map(([name, value]) => ({ name, value: Number(value) }))
          .filter((l) => Number.isFinite(l.value) && l.value > 0)
      : [];
  const plotted = active.flatMap((key) =>
    key in overlays
      ? overlays[key as keyof typeof overlays]
          .slice(viewport.start, viewport.start + viewport.count)
          .filter((v): v is number => v !== null && Number.isFinite(v))
      : [],
  );
  const low = Math.min(
    ...visible.map((b) => b.low),
    ...plotted,
    ...levelValues.map((l) => l.value),
  );
  const high = Math.max(
    ...visible.map((b) => b.high),
    ...plotted,
    ...levelValues.map((l) => l.value),
  );
  const pad = (high - low || high * 0.001) * 0.08;
  const min = low - pad,
    max = high + pad;
  const y = (value: number) => ((max - value) / (max - min)) * HEIGHT;
  const step = width / viewport.count;
  const pickedIndex =
    selected === null
      ? viewport.start + viewport.count - 1
      : Math.max(
          viewport.start,
          Math.min(viewport.start + viewport.count - 1, selected),
        );
  const picked = bars[pickedIndex];
  function toggle(key: string) {
    setEnabled((old) =>
      old.includes(key) ? old.filter((k) => k !== key) : [...old, key],
    );
  }
  const tint = { EMA20: colors.gold, EMA50: colors.green, VWAP: colors.red };
  return (
    <View style={{ gap: 12 }}>
      <Label style={{ color: colors.gold, fontWeight: "700" }}>
        KAYITLI ANALİZ · CANLI GRAFİK DEĞİL
      </Label>
      <Label muted>
        {snapshot.symbol} · {snapshot.timeframe} · {time(snapshot.as_of_ms)}
      </Label>
      <View style={{ flexDirection: "row", gap: 6 }}>
        <View
          testID="snapshot-plot"
          accessibilityLabel={"Analize ait " + bars.length + " değişmez mum"}
          {...responder.panHandlers}
          onLayout={(e) => setWidth(Math.max(1, e.nativeEvent.layout.width))}
          onTouchEnd={(e) => {
            if (
              e.nativeEvent.touches.length === 0 &&
              e.nativeEvent.changedTouches.length === 1
            ) {
              const x = e.nativeEvent.changedTouches[0].locationX;
              setSelected(
                viewport.start +
                  Math.max(
                    0,
                    Math.min(viewport.count - 1, Math.floor(x / step)),
                  ),
              );
            }
          }}
          style={{
            flex: 1,
            minWidth: 0,
            height: HEIGHT + 2,
            backgroundColor: colors.bg,
            overflow: "hidden",
            borderRadius: 8,
          }}
        >
          {[0, 1, 2, 3].map((i) => (
            <View
              key={i}
              pointerEvents="none"
              style={{
                position: "absolute",
                top: (i * HEIGHT) / 3,
                left: 0,
                right: 0,
                borderTopWidth: 1,
                borderColor: colors.border,
              }}
            />
          ))}
          {visible.map((bar, i) => (
            <View
              key={bar.time}
              pointerEvents="none"
              testID="snapshot-candle"
              style={{
                position: "absolute",
                left: i * step,
                width: step,
                height: HEIGHT,
              }}
            >
              <View
                style={{
                  position: "absolute",
                  left: step / 2,
                  top: y(bar.high),
                  width: 1,
                  height: Math.max(1, y(bar.low) - y(bar.high)),
                  backgroundColor:
                    bar.close >= bar.open ? colors.green : colors.red,
                }}
              />
              <View
                style={{
                  position: "absolute",
                  left: step * 0.2,
                  width: Math.max(1, step * 0.6),
                  top: y(Math.max(bar.open, bar.close)),
                  height: Math.max(1, Math.abs(y(bar.open) - y(bar.close))),
                  backgroundColor:
                    bar.close >= bar.open ? colors.green : colors.red,
                }}
              />
            </View>
          ))}
          {(Object.keys(overlays) as (keyof typeof overlays)[])
            .filter((key) => active.includes(key))
            .map((key) => (
              <React.Fragment key={key}>
                {overlays[key]
                  .slice(viewport.start, viewport.start + viewport.count)
                  .map((value, i, series) =>
                    value !== null && i > 0 && series[i - 1] !== null ? (
                      <Segment
                        key={i}
                        x1={(i - 0.5) * step}
                        x2={(i + 0.5) * step}
                        y1={y(series[i - 1]!)}
                        y2={y(value)}
                        color={tint[key]}
                      />
                    ) : null,
                  )}
              </React.Fragment>
            ))}
          {levelValues.map((l) => (
            <View
              key={l.name}
              pointerEvents="none"
              style={{
                position: "absolute",
                left: 0,
                right: 0,
                top: y(l.value),
                borderTopWidth: 1,
                borderStyle: "dashed",
                borderColor: colors.gold,
              }}
            />
          ))}
          <View
            pointerEvents="none"
            style={{
              position: "absolute",
              top: 0,
              bottom: 0,
              left: (pickedIndex - viewport.start + 0.5) * step,
              borderLeftWidth: 1,
              borderColor: colors.muted,
            }}
          />
        </View>
        <View
          style={{
            width: Math.min(126, 76 * fontScale),
            justifyContent: "space-between",
            minHeight: HEIGHT,
          }}
        >
          {[0, 1, 2, 3].map((i) => (
            <Label
              key={i}
              muted
              style={{
                fontSize: 11,
                lineHeight: 16,
                textAlign: "right",
                fontVariant: ["tabular-nums"],
              }}
            >
              {axisPrice(max - ((max - min) * i) / 3)}
            </Label>
          ))}
        </View>
      </View>
      <View
        style={{
          flexDirection: "row",
          flexWrap: "wrap",
          justifyContent: "space-between",
          gap: 8,
        }}
      >
        <Label muted>{time(visible[0].time)}</Label>
        <Label muted>{time(visible[visible.length - 1].time)}</Label>
      </View>
      <Label>
        {time(picked.time)} · Açılış {price(picked.open)} · Yüksek{" "}
        {price(picked.high)} · Düşük {price(picked.low)} · Kapanış{" "}
        {price(picked.close)} USDT
      </Label>
      <Label muted>
        {viewport.start + 1}–{viewport.start + viewport.count} / {bars.length}{" "}
        mum · Yatay sürükle, iki parmakla yakınlaştır. Muma dokunarak fiyatını
        incele.
      </Label>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
        <Button
          title="Yakınlaştır"
          secondary
          disabled={viewport.count <= Math.min(12, bars.length)}
          onPress={() => setWindow(zoomWindow(viewport, 1.5, bars.length))}
        />
        <Button
          title="Uzaklaştır"
          secondary
          disabled={viewport.count >= Math.min(96, bars.length)}
          onPress={() => setWindow(zoomWindow(viewport, 1 / 1.5, bars.length))}
        />
        {pro ? (
          <Button
            title="Son mumlar"
            variant="ghost"
            onPress={() => {
              setWindow(clampWindow(bars.length - 48, 48, bars.length));
              setSelected(null);
            }}
          />
        ) : null}
      </View>
      {pro ? (
        <>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8 }}>
            {(Object.keys(overlays) as (keyof typeof overlays)[]).map((key) => (
              <Button
                key={key}
                title={key + (enabled.includes(key) ? " açık" : " kapalı")}
                secondary
                disabled={!overlays[key].some((v) => v !== null)}
                onPress={() => toggle(key)}
              />
            ))}
            {levels ? (
              <Button
                title={
                  enabled.includes("Seviyeler")
                    ? "Seviyeler açık"
                    : "Seviyeler kapalı"
                }
                secondary
                onPress={() => toggle("Seviyeler")}
              />
            ) : null}
          </View>
          <Label muted>
            EMA20: altın · EMA50: yeşil · VWAP: kırmızı. Çizgiler yalnız kayıtlı
            mumlardan hesaplanır; analiz kararını değiştirmez. EMA için yeterli
            mum gerekir. VWAP, gerçek hacimle kaydın ilk mumundan başlar; seans
            VWAP’ı değildir.
          </Label>
          {levelValues.map((l) => (
            <Label key={l.name}>
              {l.name} · {price(l.value)} USDT
            </Label>
          ))}
        </>
      ) : null}
    </View>
  );
}

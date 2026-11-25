import React from "react";
import { BotPage, Disconnected, StaleNotice } from "../../src/bot/BotPage";
import { PositionCard } from "../../src/bot/PositionCard";
import { useBot } from "../../src/bot/state";
import { Empty, Loading, ScreenHeader } from "../../src/ui";

export default function Positions() {
  const bot = useBot();
  const ready = bot.phase === "ready";
  return (
    <BotPage>
      <ScreenHeader
        title="Pozisyonlar"
        badge="TRADE BOT"
        subtitle={ready && bot.status ? bot.positions.length + " açık pozisyon" : undefined}
      />
      <Disconnected />
      {ready ? (
        <>
          <StaleNotice />
          {!bot.status && !bot.error ? (
            <Loading />
          ) : bot.positions.length === 0 ? (
            <Empty text="Açık pozisyon yok." />
          ) : (
            bot.positions.map((position) => (
              <PositionCard
                key={position.position_id}
                position={position}
                currency={bot.status?.currency}
                api={bot.api}
                onChanged={() => void bot.refresh()}
              />
            ))
          )}
        </>
      ) : null}
    </BotPage>
  );
}

import React from "react";
import { BotPage } from "../../src/bot/BotPage";
import { Empty, ScreenHeader } from "../../src/ui";

export default function Screen() {
  return (
    <BotPage>
      <ScreenHeader title="Pozisyonlar" badge="TRADE BOT" />
      <Empty text="Bu ekran hazırlanıyor." />
    </BotPage>
  );
}

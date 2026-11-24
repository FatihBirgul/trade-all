import React from "react";
import brandIcon from "../assets/brand/icon.png";
import { Image, View } from "react-native";
import { Heading, Label } from "./ui";
export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <View style={{ flexDirection: "row", gap: 12, alignItems: "center" }}>
      <Image
        source={brandIcon}
        accessibilityLabel="TRADE AI geometrik T simgesi"
        style={{
          width: compact ? 36 : 48,
          height: compact ? 36 : 48,
          borderRadius: 10,
        }}
      />
      <View>
        <Heading>TRADE AI</Heading>
        <Label muted>
          {compact
            ? "Kişisel piyasa analizi"
            : "Gözlem · strateji · kontrollü risk"}
        </Label>
      </View>
    </View>
  );
}

// Tasarım yönü önizlemesi (örnek veriyle). Yön seçilince bu klasör ve src/design kaldırılacak.
import React from "react";
import { Text } from "react-native";
import { useLocalSearchParams } from "expo-router";
import * as A from "../../../src/design/A";
import * as B from "../../../src/design/B";
import * as C from "../../../src/design/C";

const DIRECTIONS = { a: A, b: B, c: C } as const;

export default function Preview() {
  const { yon, ekran } = useLocalSearchParams<{ yon: string; ekran: string }>();
  const direction = DIRECTIONS[yon as keyof typeof DIRECTIONS];
  if (!direction) return <Text>Bilinmeyen yön</Text>;
  return ekran === "pozisyonlar" ? <direction.Positions /> : <direction.Panel />;
}

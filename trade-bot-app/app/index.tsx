import React from "react";
import { Text, View } from "react-native";
import { Link } from "expo-router";

// Geçici giriş ekranı: tasarım yönü seçilene kadar yalnızca önizlemelere bağlantı verir.
export default function Index() {
  return (
    <View style={{ flex: 1, padding: 24, gap: 12, justifyContent: "center" }}>
      <Text style={{ fontSize: 22, fontWeight: "800" }}>Trade Bot — tasarım yönleri</Text>
      {["a", "b", "c"].flatMap((yon) =>
        ["panel", "pozisyonlar"].map((ekran) => (
          <Link key={yon + ekran} href={`/tasarim/${yon}/${ekran}`} style={{ fontSize: 17, color: "#2457F5" }}>
            Yön {yon.toUpperCase()} · {ekran}
          </Link>
        )),
      )}
    </View>
  );
}

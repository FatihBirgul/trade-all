import { useEffect, useRef } from "react";
import { router } from "expo-router";
import { useBot } from "./state";

// Bot ile bağlantı yoksa (ilk kurulum ya da anahtar iptal edilmiş) uygulama açılışta bir kez bağlantı
// ekranını açar. Yalnızca bir kez: kullanıcı geri dönerse yeniden zorlanmaz.
export function useConnectOnStart() {
  const { phase } = useBot();
  const done = useRef(false);
  useEffect(() => {
    if (done.current || phase === "loading") return;
    done.current = true;
    if (phase !== "ready") router.push("/connection");
  }, [phase]);
}

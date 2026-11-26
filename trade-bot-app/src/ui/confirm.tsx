import React, { createContext, useCallback, useContext, useEffect, useRef, useState, type PropsWithChildren } from "react";
import { Modal, Pressable, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Button, IconBubble, T } from "./kit";
import { c } from "./theme";

// Uygulamanın kendi onay penceresi (Alert yerine): her platformda aynı görünür ve testlerde tıklanabilir.
export type ConfirmOptions = { title: string; message: string; confirm: string; cancel?: string; danger?: boolean };
type Ask = (options: ConfirmOptions) => Promise<boolean>;

// Pencere açıldıktan sonra onay düğmesi bu süre boyunca basılamaz. Art arda gelen iki onayın düğmeleri aynı
// yerde durur; bu bekleme olmasa hızlı bir çift dokunuş iki onayı birden geçerdi.
export const ARM_MS = 700;

const Context = createContext<Ask | null>(null);

export function ConfirmProvider({ children }: PropsWithChildren) {
  const insets = useSafeAreaInsets();
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const [armed, setArmed] = useState(false);
  const resolver = useRef<((value: boolean) => void) | null>(null);
  const ask = useCallback<Ask>((next) => {
    resolver.current?.(false); // açık bir soru varsa "vazgeç" sayılır
    setArmed(false);
    setOptions({ ...next }); // yeni nesne: aynı metinle ikinci soru da bekleme süresini yeniden başlatır
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);
  useEffect(() => {
    if (!options) return;
    const timer = setTimeout(() => setArmed(true), ARM_MS);
    return () => clearTimeout(timer);
  }, [options]);
  const answer = (value: boolean) => {
    if (value && !armed) return;
    const resolve = resolver.current;
    resolver.current = null;
    setOptions(null);
    setArmed(false);
    resolve?.(value);
  };
  return (
    <Context.Provider value={ask}>
      {children}
      <Modal visible={options !== null} transparent animationType="fade" onRequestClose={() => answer(false)}>
        <View style={{ flex: 1, justifyContent: "flex-end" }}>
          <Pressable accessibilityLabel="Vazgeç" onPress={() => answer(false)} style={{ position: "absolute", top: 0, bottom: 0, left: 0, right: 0, backgroundColor: "rgba(22,24,58,0.55)" }} />
          {options ? (
            <View testID="confirm" accessibilityViewIsModal style={{ backgroundColor: c.card, borderTopLeftRadius: 32, borderTopRightRadius: 32, padding: 22, paddingBottom: 22 + Math.max(12, insets.bottom), gap: 14 }}>
              <IconBubble icon={options.danger ? "alert" : "help"} color={options.danger ? c.down : c.hero} bg={options.danger ? c.downSoft : c.tint} size={54} />
              <T weight="900" size={21}>{options.title}</T>
              <T size={15} style={{ color: c.text }}>{options.message}</T>
              <Button testID="confirm-yes" title={options.confirm} kind={options.danger ? "danger" : "primary"} disabled={!armed} onPress={() => answer(true)} />
              <Button testID="confirm-no" title={options.cancel ?? "Vazgeç"} kind="ghost" onPress={() => answer(false)} />
            </View>
          ) : null}
        </View>
      </Modal>
    </Context.Provider>
  );
}

export function useConfirm(): Ask {
  const ask = useContext(Context);
  if (!ask) throw new Error("useConfirm, ConfirmProvider içinde kullanılmalı");
  return ask;
}

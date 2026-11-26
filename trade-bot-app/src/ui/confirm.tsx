import React, { createContext, useCallback, useContext, useRef, useState, type PropsWithChildren } from "react";
import { Modal, Pressable } from "react-native";
import { Button, IconBubble, T } from "./kit";
import { c } from "./theme";

// Uygulamanın kendi onay penceresi (Alert yerine): her platformda aynı görünür ve testlerde tıklanabilir.
export type ConfirmOptions = { title: string; message: string; confirm: string; cancel?: string; danger?: boolean };
type Ask = (options: ConfirmOptions) => Promise<boolean>;

const Context = createContext<Ask | null>(null);

export function ConfirmProvider({ children }: PropsWithChildren) {
  const [options, setOptions] = useState<ConfirmOptions | null>(null);
  const resolver = useRef<((value: boolean) => void) | null>(null);
  const ask = useCallback<Ask>((next) => {
    resolver.current?.(false); // açık bir soru varsa "vazgeç" sayılır
    setOptions(next);
    return new Promise<boolean>((resolve) => {
      resolver.current = resolve;
    });
  }, []);
  const answer = (value: boolean) => {
    const resolve = resolver.current;
    resolver.current = null;
    setOptions(null);
    resolve?.(value);
  };
  return (
    <Context.Provider value={ask}>
      {children}
      <Modal visible={options !== null} transparent animationType="fade" onRequestClose={() => answer(false)}>
        <Pressable accessibilityLabel="Vazgeç" onPress={() => answer(false)} style={{ flex: 1, backgroundColor: "rgba(22,24,58,0.55)", justifyContent: "flex-end" }}>
          {options ? (
            <Pressable testID="confirm" onPress={() => {}} style={{ backgroundColor: c.card, borderTopLeftRadius: 32, borderTopRightRadius: 32, padding: 22, paddingBottom: 30, gap: 14 }}>
              <IconBubble icon={options.danger ? "alert" : "help"} color={options.danger ? c.down : c.hero} bg={options.danger ? c.downSoft : c.tint} size={54} />
              <T weight="900" size={21}>{options.title}</T>
              <T size={15} style={{ color: c.text }}>{options.message}</T>
              <Button testID="confirm-yes" title={options.confirm} kind={options.danger ? "danger" : "primary"} onPress={() => answer(true)} />
              <Button testID="confirm-no" title={options.cancel ?? "Vazgeç"} kind="ghost" onPress={() => answer(false)} />
            </Pressable>
          ) : null}
        </Pressable>
      </Modal>
    </Context.Provider>
  );
}

export function useConfirm(): Ask {
  const ask = useContext(Context);
  if (!ask) throw new Error("useConfirm, ConfirmProvider içinde kullanılmalı");
  return ask;
}

import { BrandMark } from "../../src/BrandMark";
import { router } from "expo-router";
import React, { useState } from "react";
import { connectionPresentation } from "../../src/domain/connection";
import Constants from "expo-constants";
import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import { pairDevice } from "../../src/api/gateway";
import { gatewayOrigin } from "../../src/domain/safety";
import { Platform, TextInput } from "react-native";
import { useApp } from "../../src/state";
import { useTheme } from "../../src/theme";
import { userErrorText } from "../../src/domain/presentation";
import {
  ScreenHeader,
  Button,
  Card,
  Choices,
  Heading,
  Label,
  Page,
  Row,
  Disclosure,
} from "../../src/ui";
export default function Settings() {
  const app = useApp();
  const theme = useTheme();
  const [originDraft, setOriginDraft] = useState<string | null>(null);
  const origin = originDraft ?? app.config.origin;
  const [session, setSession] = useState("");
  const [code, setCode] = useState("");
  const [deviceName, setDeviceName] = useState("Android telefonum");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  async function connect() {
    setBusy(true);
    setMessage("");
    try {
      const normalized = gatewayOrigin(origin);
      let candidate = session || app.config.session;
      let credentials =
        normalized === app.config.origin
          ? { ...app.config }
          : { origin: normalized, session: "" };
      if (normalized !== app.config.origin && !code.trim())
        throw new Error(
          "Yeni gateway adresi için yeniden eşleştirme kodu girin.",
        );
      if (code.trim()) {
        let deviceId =
          Platform.OS === "web"
            ? null
            : await SecureStore.getItemAsync("mobile_device_id");
        if (!deviceId) {
          deviceId = Crypto.randomUUID();
          if (Platform.OS !== "web")
            await SecureStore.setItemAsync("mobile_device_id", deviceId);
        }
        const result = await pairDevice(normalized, code, deviceId, deviceName);
        candidate = result.session;
        credentials = {
          origin: normalized,
          session: candidate,
          refresh: result.refresh,
          deviceId,
          renewalExpiresAt: result.metadata.renewal_expires_at_ms,
          scopes: result.metadata.scopes,
          accounts: result.metadata.accounts,
        };
        setSession(candidate);
        setCode("");
      }
      if (!candidate)
        throw new Error("Bilgisayarda yeni eşleştirme kodu oluşturup girin.");
      const h = await app.configure({
        ...credentials,
        origin: normalized,
        session: candidate,
      });
      setSession("");
      setMessage(
        "Bağlantı testi başarılı. Bu sonuç sürekli bağlantı garantisi değildir. Sağlayıcı: " +
          h.provider_status +
          " · Depolama: " +
          h.storage,
      );
    } catch (e) {
      setMessage(userErrorText(e, "Bağlantı kurulamadı."));
    } finally {
      setBusy(false);
    }
  }
  async function disconnect() {
    setBusy(true);
    setMessage("");
    setSession("");
    setCode("");
    setOriginDraft("");
    try {
      await app.disconnect();
      setMessage("Oturum silindi. DEMO moduna dönüldü.");
    } catch {
      setMessage(
        "DEMO moduna dönüldü; cihazdaki oturum kaydı silinemedi. Silmeyi yeniden deneyin.",
      );
    } finally {
      setBusy(false);
    }
  }
  const input = {
    color: theme.colors.text,
    backgroundColor: theme.colors.soft,
    borderColor: theme.colors.border,
    borderWidth: 1,
    borderRadius: 12,
    padding: 12,
    minHeight: 48,
  };
  return (
    <Page mode={app.mode} connection={app}>
      <BrandMark compact />
      <ScreenHeader title="Ayarlar" badge="TERCİHLER VE BAĞLANTI" />
      <Card>
        <Heading>Kullanım modu</Heading>
        <Choices
          values={["BASİT", "PRO"] as const}
          value={app.uiMode === "pro" ? "PRO" : "BASİT"}
          onChange={async (value) => {
            try {
              await app.setUiMode(value === "PRO" ? "pro" : "basic");
            } catch {
              setMessage("Görünüm seçimi kaydedilemedi. Yeniden deneyin.");
            }
          }}
        />
        <Label muted>
          Basit: fiyat, kısa sonuç ve portföy özeti. Pro: MTF ayarları, geçmiş,
          karşılaştırma ve tarayıcı kontrolleri. Bu seçim analiz motorunu ve
          kararlarını değiştirmez.
        </Label>
      </Card>
      <Card>
        <Heading>Görünüm</Heading>
        <Button
          title={theme.isDark ? "Açık temaya geç" : "Koyu temaya geç"}
          secondary
          onPress={theme.toggle}
        />
      </Card>
      <Card>
        <Heading>Veri modu</Heading>
        <Choices
          values={["DEMO", "CANLI"] as const}
          value={app.mode === "demo" ? "DEMO" : "CANLI"}
          onChange={(v) => app.setMode(v === "DEMO" ? "demo" : "live")}
          disabledValues={app.gatewayVerified ? [] : ["CANLI"]}
        />
        <Label muted>
          DEMO yerel örnek veridir. CANLI, HTTPS gateway ve mobil oturumla
          başarılı bağlantı testi yapılana kadar kilitlidir. Tüm işlemler
          sanaldır.
        </Label>
      </Card>
      <Card>
        <Heading>Gateway bağlantısı ve oturum</Heading>
        <Label>{connectionPresentation(app).title}</Label>
        <Label muted>{connectionPresentation(app).detail}</Label>
        <Label muted>
          Bilgisayarda gateway’i başlatın ve 120 saniyelik tek kullanımlık
          eşleştirme kodu oluşturun. Backend gizli tokenı telefona girilmez.
          Kayıtlı mobil oturum varsa kod girmeden yeniden doğrulayabilirsiniz.
        </Label>
        <TextInput
          accessibilityLabel="HTTPS gateway adresi"
          placeholder="https://gateway.example.com"
          placeholderTextColor={theme.colors.muted}
          autoCapitalize="none"
          autoCorrect={false}
          editable={!busy}
          keyboardType="url"
          value={origin}
          onChangeText={setOriginDraft}
          style={input}
        />
        <TextInput
          accessibilityLabel="Tek kullanımlık eşleştirme kodu"
          placeholder="Bilgisayardaki eşleştirme kodu"
          placeholderTextColor={theme.colors.muted}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          editable={!busy}
          value={code}
          onChangeText={setCode}
          style={input}
        />
        <TextInput
          accessibilityLabel="Cihaz adı"
          value={deviceName}
          onChangeText={setDeviceName}
          maxLength={60}
          editable={!busy}
          style={input}
        />
        {app.sessionInfo ? (
          <Label muted>
            Oturum sonu:{" "}
            {new Date(app.sessionInfo.expires_at_ms).toLocaleString("tr-TR")} ·
            İzinli hesaplar: {app.sessionInfo.accounts.join(", ")}
          </Label>
        ) : null}
        <Label muted>
          {app.renewing
            ? "Güvenli oturum yenileniyor…"
            : app.config.refresh
              ? "Cihaza özel yenileme etkin · " +
                new Date(app.config.renewalExpiresAt!).toLocaleString("tr-TR") +
                " tarihine kadar. PC açık ve erişilebilir olmalı."
              : "Yenileme yetkisi yok. Güncel gateway ile bir kez yeniden eşleştirin."}
        </Label>
        <Button
          title="Oturumu yenile / yeniden bağlan"
          secondary
          disabled={busy || app.renewing || !app.config.session}
          onPress={async () => {
            setBusy(true);
            try {
              await app.reconnect();
              setMessage("Oturum ve backend bağlantısı doğrulandı.");
            } catch (error) {
              setMessage(userErrorText(error));
            } finally {
              setBusy(false);
            }
          }}
        />
        <Button
          title={
            busy ? "Bağlantı test ediliyor…" : "Bağlantıyı test et ve kaydet"
          }
          disabled={busy}
          onPress={connect}
        />
        <Label muted>
          Telefonun ağ durumu bu sürümde ayrıca ölçülmez. Genel bağlantı hatası,
          internetinizin kapalı olduğu anlamına gelmez.
        </Label>
        {app.lastVerifiedAt ? (
          <Label muted>
            Son başarılı doğrulama:{" "}
            {new Date(app.lastVerifiedAt).toLocaleString("tr-TR")}
          </Label>
        ) : null}
        <Row
          name="Bağlantı testi"
          value={
            app.gatewayVerified
              ? "Bu oturumda doğrulandı"
              : "Doğrulanmadı · CANLI kilitli"
          }
        />
        <Button
          title="Mobil oturumu sil"
          secondary
          disabled={busy}
          onPress={disconnect}
        />
        {message && message !== app.connectionError ? (
          <Label>{message}</Label>
        ) : null}
      </Card>
      <Card>
        <Heading>Tarama ve bildirimler</Heading>
        <Button
          title="Tarayıcı ayarlarını aç"
          secondary
          onPress={() => router.push("/market-discovery")}
        />
        <Button
          title="Bildirim tercihleri ve geçmişi"
          secondary
          onPress={() => router.push("/notifications")}
        />
        <Label muted>
          Bu ekranları açmak worker veya push göndericisi başlatmaz.
        </Label>
      </Card>
      <Card>
        <Disclosure title="Sürüm ve güvenlik bilgileri">
          <Heading>TRADE AI</Heading>
          <Row
            name="Sürüm"
            value={
              (Constants.nativeAppVersion ||
                Constants.expoConfig?.version ||
                "Bilinmiyor") +
              " · " +
              (Constants.nativeBuildVersion ||
                String(Constants.expoConfig?.android?.versionCode || "—"))
            }
          />
          <Row name="İşlem türü" value="Yalnız sanal" />
          <Label muted>
            Analizler başarı olasılığı veya kârlılık garantisi değildir. Push
            bildirim teslimatı yapılandırılmadı.
          </Label>
        </Disclosure>
      </Card>
    </Page>
  );
}

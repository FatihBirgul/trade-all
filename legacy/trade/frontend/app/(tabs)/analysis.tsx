import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import * as ImageManipulator from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import { useRouter } from "expo-router";
import React, { useState } from "react";
import { Linking, Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Api } from "@/src/api/client";
import { AssetPickerModal } from "@/src/components/AssetPickerModal";
import { Card, Disclaimer, PrimaryButton, SectionTitle, Segmented } from "@/src/components/common";
import { useMarket } from "@/src/context/MarketContext";
import { colors, fonts, logoUrl, radius, spacing, type } from "@/src/theme";

export default function AnalysisScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { selectedSymbol, setSelectedSymbol, assets, timeframes, defaultTimeframe } = useMarket();

  const [symbol, setSymbol] = useState(selectedSymbol);
  const [timeframe, setTimeframe] = useState(defaultTimeframe);
  const [imageUri, setImageUri] = useState<string | null>(null);
  const [imageB64, setImageB64] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [permModal, setPermModal] = useState<null | string>(null);
  const [error, setError] = useState<string | null>(null);

  const asset = assets.find((a) => a.symbol === symbol);

  const processImage = async (uri: string) => {
    const manipulated = await ImageManipulator.manipulateAsync(
      uri,
      [{ resize: { width: 1080 } }],
      { compress: 0.6, format: ImageManipulator.SaveFormat.JPEG, base64: true }
    );
    setImageUri(manipulated.uri);
    setImageB64(manipulated.base64 || null);
  };

  const takePhoto = async () => {
    const perm = await ImagePicker.getCameraPermissionsAsync();
    let status = perm.status;
    if (status !== "granted") {
      if (!perm.canAskAgain) {
        setPermModal("camera");
        return;
      }
      const req = await ImagePicker.requestCameraPermissionsAsync();
      status = req.status;
      if (status !== "granted") {
        if (!req.canAskAgain) setPermModal("camera");
        return;
      }
    }
    const res = await ImagePicker.launchCameraAsync({ quality: 0.7, base64: false });
    if (!res.canceled && res.assets?.[0]) await processImage(res.assets[0].uri);
  };

  const pickGallery = async () => {
    const perm = await ImagePicker.getMediaLibraryPermissionsAsync();
    let status = perm.status;
    if (status !== "granted") {
      if (!perm.canAskAgain) {
        setPermModal("photos");
        return;
      }
      const req = await ImagePicker.requestMediaLibraryPermissionsAsync();
      status = req.status;
      if (status !== "granted") {
        if (!req.canAskAgain) setPermModal("photos");
        return;
      }
    }
    const res = await ImagePicker.launchImageLibraryAsync({ quality: 0.7, base64: false });
    if (!res.canceled && res.assets?.[0]) await processImage(res.assets[0].uri);
  };

  const runAnalysis = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const result: any = await Api.createAnalysis({
        symbol,
        timeframe,
        image_base64: imageB64 || undefined,
      });
      setSelectedSymbol(symbol);
      router.replace(`/result/${result.id}`);
    } catch (e: any) {
      setError(e.message || "Analysis failed. Please try again.");
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>AI Analysis</Text>
        <Text style={styles.subtitle}>Upload a chart or analyze live data</Text>
      </View>

      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 140 }}
        showsVerticalScrollIndicator={false}
      >
        {/* Chart upload zone */}
        <SectionTitle title="Chart Image (optional)" />
        {imageUri ? (
          <View style={styles.previewWrap} testID="analysis-image-preview">
            <Image source={{ uri: imageUri }} style={styles.preview} contentFit="cover" />
            <Pressable
              style={styles.removeBtn}
              onPress={() => {
                setImageUri(null);
                setImageB64(null);
              }}
              testID="analysis-remove-image"
            >
              <Ionicons name="close" size={16} color={colors.onSurface} />
            </Pressable>
          </View>
        ) : (
          <View style={styles.uploadZone} testID="analysis-upload-zone">
            <Ionicons name="image-outline" size={34} color={colors.onSurfaceTertiary} />
            <Text style={styles.uploadText}>Add a chart screenshot for vision analysis</Text>
            <View style={styles.uploadBtns}>
              <Pressable style={styles.uploadBtn} onPress={takePhoto} testID="analysis-take-photo">
                <Ionicons name="camera" size={18} color={colors.brand} />
                <Text style={styles.uploadBtnText}>Camera</Text>
              </Pressable>
              <Pressable style={styles.uploadBtn} onPress={pickGallery} testID="analysis-pick-gallery">
                <Ionicons name="images" size={18} color={colors.brand} />
                <Text style={styles.uploadBtnText}>Gallery</Text>
              </Pressable>
            </View>
          </View>
        )}

        {/* Asset */}
        <View style={{ marginTop: spacing.xl }}>
          <SectionTitle title="Asset" />
          <Pressable style={styles.selectRow} onPress={() => setPickerOpen(true)} testID="analysis-asset-select">
            <Image source={{ uri: logoUrl(asset?.base || "BTC") }} style={styles.selectLogo} contentFit="contain" />
            <View style={{ flex: 1 }}>
              <Text style={styles.selectName}>{asset?.base}/{asset?.quote}</Text>
              <Text style={styles.selectSub}>{asset?.name}</Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.onSurfaceTertiary} />
          </Pressable>
        </View>

        {/* Timeframe */}
        <View style={{ marginTop: spacing.xl }}>
          <SectionTitle title="Timeframe" />
          <Segmented options={timeframes} value={timeframe} onChange={setTimeframe} testIDPrefix="analysis-tf" />
        </View>

        <Card style={{ marginTop: spacing.xl, flexDirection: "row", gap: spacing.sm }}>
          <Ionicons name="information-circle-outline" size={18} color={colors.onSurfaceTertiary} />
          <Text style={styles.infoText}>
            Live market data is combined with deterministic technical analysis. Image analysis alone is never treated as
            a trading conclusion.
          </Text>
        </Card>

        {error && (
          <View style={styles.errorBox} testID="analysis-error">
            <Ionicons name="alert-circle" size={16} color={colors.error} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}

        <View style={{ marginTop: spacing.lg }}>
          <Disclaimer compact />
        </View>
      </ScrollView>

      {/* Sticky CTA */}
      <View style={[styles.footer, { paddingBottom: insets.bottom + spacing.md }]}>
        <PrimaryButton
          label={imageB64 ? "ANALYZE CHART" : "ANALYZE LIVE DATA"}
          icon="flash"
          loading={analyzing}
          onPress={runAnalysis}
          testID="analysis-run-btn"
        />
      </View>

      {/* Analyzing overlay */}
      {analyzing && (
        <View style={styles.overlay} testID="analysis-overlay">
          <View style={styles.overlayCard}>
            <Ionicons name="pulse" size={30} color={colors.brand} />
            <Text style={styles.overlayTitle}>Analyzing {asset?.base}</Text>
            <Text style={styles.overlaySub}>
              Fetching live data · computing indicators · detecting patterns · AI reasoning…
            </Text>
          </View>
        </View>
      )}

      <AssetPickerModal
        visible={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={setSymbol}
        selected={symbol}
      />

      {/* Permission blocked modal */}
      <Modal visible={!!permModal} transparent animationType="fade" onRequestClose={() => setPermModal(null)}>
        <View style={styles.permBackdrop}>
          <View style={styles.permCard}>
            <Ionicons name="lock-closed" size={28} color={colors.brand} />
            <Text style={styles.permTitle}>
              {permModal === "camera" ? "Camera access needed" : "Photo access needed"}
            </Text>
            <Text style={styles.permText}>
              Enable {permModal === "camera" ? "camera" : "photos"} access in Settings to add a chart image. You can
              still analyze live data without it.
            </Text>
            <PrimaryButton
              label="OPEN SETTINGS"
              onPress={() => {
                setPermModal(null);
                Linking.openSettings();
              }}
              testID="perm-open-settings"
            />
            <Pressable onPress={() => setPermModal(null)} style={{ marginTop: spacing.md }} testID="perm-dismiss">
              <Text style={styles.permDismiss}>Not now</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.surface },
  header: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: { color: colors.onSurface, fontFamily: fonts.displayBold, fontSize: type["2xl"], letterSpacing: 0.5 },
  subtitle: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm },
  uploadZone: {
    borderWidth: 1.5,
    borderColor: colors.borderStrong,
    borderStyle: "dashed",
    borderRadius: radius.md,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
  },
  uploadText: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.base, textAlign: "center" },
  uploadBtns: { flexDirection: "row", gap: spacing.md, marginTop: spacing.xs },
  uploadBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceTertiary,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
  },
  uploadBtnText: { color: colors.onSurface, fontFamily: fonts.bodySemi, fontSize: type.base },
  previewWrap: { borderRadius: radius.md, overflow: "hidden", borderWidth: 1, borderColor: colors.border },
  preview: { width: "100%", height: 200 },
  removeBtn: {
    position: "absolute",
    top: spacing.sm,
    right: spacing.sm,
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: "#000000CC",
    alignItems: "center",
    justifyContent: "center",
  },
  selectRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  selectLogo: { width: 36, height: 36 },
  selectName: { color: colors.onSurface, fontFamily: fonts.displaySemi, fontSize: type.lg },
  selectSub: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm },
  infoText: { flex: 1, color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.sm, lineHeight: 18 },
  errorBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.lg },
  errorText: { color: colors.error, fontFamily: fonts.bodyMedium, fontSize: type.base, flex: 1 },
  footer: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  overlay: { ...StyleSheet.absoluteFillObject, backgroundColor: "#000000E6", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  overlayCard: { alignItems: "center", gap: spacing.md },
  overlayTitle: { color: colors.onSurface, fontFamily: fonts.displayBold, fontSize: type.xl },
  overlaySub: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.base, textAlign: "center", lineHeight: 20 },
  permBackdrop: { flex: 1, backgroundColor: "#000000CC", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  permCard: {
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.lg,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.md,
    width: "100%",
    borderWidth: 1,
    borderColor: colors.border,
  },
  permTitle: { color: colors.onSurface, fontFamily: fonts.displaySemi, fontSize: type.xl },
  permText: { color: colors.onSurfaceTertiary, fontFamily: fonts.body, fontSize: type.base, textAlign: "center", lineHeight: 20, marginBottom: spacing.sm },
  permDismiss: { color: colors.onSurfaceTertiary, fontFamily: fonts.bodyMedium, fontSize: type.base },
});

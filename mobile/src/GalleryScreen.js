import * as ImagePicker from "expo-image-picker";
import { useState } from "react";
import { Image, ScrollView, Text } from "react-native";
import { Button, Prediction, s } from "./ui";

export default function GalleryScreen({ api }) {
  const [asset, setAsset] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function pick() {
    setError("");
    const picked = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      base64: true,
      exif: true,
      quality: 0.8,
      // iPhone photos are HEIC; "compatible" gives us a JPEG that the server can read.
      preferredAssetRepresentationMode: ImagePicker.UIImagePickerPreferredAssetRepresentationMode.Compatible,
    });
    if (picked.canceled) return;

    const a = picked.assets[0];
    setAsset(a);
    setResult(null);
    setBusy(true);
    try {
      const r = await api.predict(a.base64, {
        source: "gallery",
        filename: a.fileName ?? null,
        mimeType: a.mimeType ?? "image/jpeg",
        sizeBytes: a.fileSize ?? null,
        width: a.width,
        height: a.height,
        takenAt: a.exif?.DateTimeOriginal ?? a.exif?.["{Exif}"]?.DateTimeOriginal ?? null,
        cameraModel: a.exif?.Model ?? a.exif?.["{TIFF}"]?.Model ?? null,
        capturedAt: new Date().toISOString(),
      });
      setResult(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 12 }}>
      <Button title="Choose from gallery" onPress={pick} disabled={busy} style={{ alignSelf: "flex-start" }} />
      {asset && (
        <Image
          source={{ uri: asset.uri }}
          style={{ width: "100%", aspectRatio: asset.width / asset.height, marginTop: 12, backgroundColor: "#eee" }}
          resizeMode="contain"
        />
      )}
      <Text style={s.heading}>Result</Text>
      {busy && <Text style={s.muted}>Classifying...</Text>}
      {result && (
        <>
          <Prediction result={result} />
          <Text style={s.muted}>Saved to history.</Text>
        </>
      )}
      {!asset && !busy && <Text style={s.muted}>Choose a photo of a cat or a dog.</Text>}
      {!!error && <Text style={s.error}>{error}</Text>}
    </ScrollView>
  );
}

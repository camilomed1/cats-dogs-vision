import { CameraView, useCameraPermissions } from "expo-camera";
import { useEffect, useRef, useState } from "react";
import { ScrollView, Text, View } from "react-native";
import { Button, Prediction, s } from "./ui";

const LIVE_PAUSE_MS = 300;

export default function CameraScreen({ api }) {
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef(null);
  const [ready, setReady] = useState(false);
  const [facing, setFacing] = useState("back");
  const [live, setLive] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [info, setInfo] = useState("");
  const [error, setError] = useState("");

  // Live mode: take a small, silent photo -> predict without storing -> repeat.
  useEffect(() => {
    if (!live || !ready) return;
    let cancelled = false;
    (async () => {
      while (!cancelled) {
        const start = Date.now();
        try {
          const pic = await cameraRef.current.takePictureAsync({ quality: 0.3, base64: true, shutterSound: false });
          if (cancelled) break;
          const r = await api.predict(pic.base64, { source: "camera", mode: "live", facing }, false);
          if (!cancelled) {
            setResult(r);
            setInfo(`Live: ${Date.now() - start} ms per prediction. Photos are not saved.`);
            setError("");
          }
        } catch (e) {
          if (!cancelled) setError(e.message);
          await new Promise((r) => setTimeout(r, 1000));
        }
        await new Promise((r) => setTimeout(r, LIVE_PAUSE_MS));
      }
    })();
    return () => { cancelled = true; };
  }, [live, ready, facing, api]);

  async function takePhoto() {
    if (!ready || busy) return;
    setBusy(true);
    setLive(false);
    setError("");
    try {
      const pic = await cameraRef.current.takePictureAsync({ quality: 0.8, base64: true });
      const now = new Date();
      const r = await api.predict(pic.base64, {
        source: "camera",
        mode: "photo",
        filename: `iphone_${now.toISOString().replace(/[:.]/g, "-")}.jpg`,
        mimeType: "image/jpeg",
        width: pic.width,
        height: pic.height,
        facing,
        capturedAt: now.toISOString(),
      });
      setResult(r);
      setInfo("Saved to history.");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!permission) return <View />;
  if (!permission.granted) {
    return (
      <View style={{ padding: 16 }}>
        <Text style={s.text}>The app needs camera access to take photos.</Text>
        <Button title="Allow camera" onPress={requestPermission} style={{ marginTop: 10, alignSelf: "flex-start" }} />
        {!permission.canAskAgain && (
          <Text style={s.muted}>Permission was denied. Enable it in Settings &gt; Expo Go &gt; Camera.</Text>
        )}
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 12 }}>
      <CameraView
        ref={cameraRef}
        style={{ width: "100%", aspectRatio: 3 / 4, backgroundColor: "#222" }}
        facing={facing}
        animateShutter={!live}
        onCameraReady={() => setReady(true)}
      />
      <View style={[s.row, { marginTop: 10 }]}>
        <Button title={busy ? "Saving..." : "Take photo and save"} onPress={takePhoto} disabled={!ready || busy} />
        <Button title={live ? "Stop live" : "Start live"} onPress={() => setLive((v) => !v)} disabled={!ready} />
        <Button title="Flip" onPress={() => setFacing((f) => (f === "back" ? "front" : "back"))} />
      </View>

      <Text style={s.heading}>Result</Text>
      {result ? <Prediction result={result} /> : <Text style={s.muted}>Take a photo, or start live prediction.</Text>}
      {!!info && <Text style={s.muted}>{info}</Text>}
      {!!error && <Text style={s.error}>{error}</Text>}
    </ScrollView>
  );
}

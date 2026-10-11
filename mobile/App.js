import { StatusBar } from "expo-status-bar";
import { useEffect, useMemo, useState } from "react";
import { Text, TextInput, View } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import { createApi, defaultServerUrl } from "./src/api";
import CameraScreen from "./src/CameraScreen";
import GalleryScreen from "./src/GalleryScreen";
import HistoryScreen from "./src/HistoryScreen";
import { Button, s } from "./src/ui";

const TABS = [
  { id: "camera", title: "Camera", Screen: CameraScreen },
  { id: "gallery", title: "Gallery", Screen: GalleryScreen },
  { id: "history", title: "History", Screen: HistoryScreen },
];

export default function App() {
  const [server, setServer] = useState(defaultServerUrl());
  const [draft, setDraft] = useState(null); // non-null while editing the server address
  const [health, setHealth] = useState(null);
  const [tab, setTab] = useState("camera");
  const api = useMemo(() => createApi(server), [server]);

  useEffect(() => {
    let active = true;
    const check = () =>
      api.health()
        .then((h) => active && setHealth(h))
        .catch(() => active && setHealth({ status: "down" }));
    setHealth(null);
    check();
    const id = setInterval(check, 10000);
    return () => { active = false; clearInterval(id); };
  }, [api]);

  const online = health?.status === "ok";
  const Screen = TABS.find((t) => t.id === tab).Screen;

  return (
    <SafeAreaProvider>
      <SafeAreaView style={{ flex: 1, backgroundColor: "#fff" }} edges={["top", "left", "right"]}>
        <StatusBar style="dark" />
        <View style={{ paddingHorizontal: 12, paddingTop: 8, paddingBottom: 8, borderBottomWidth: 1, borderColor: "#ccc" }}>
          <Text style={{ fontSize: 20, fontWeight: "bold", color: "#222" }}>Cats vs Dogs Classifier</Text>

          {draft === null ? (
            <View style={{ flexDirection: "row", alignItems: "center", marginTop: 4, gap: 8 }}>
              <Text style={[s.muted, { flex: 1 }]} numberOfLines={1}>
                Server: {server} (
                <Text style={{ color: online ? "green" : health ? "#c00" : "#666" }}>
                  {health === null ? "connecting..." : online ? "online" : "offline"}
                </Text>
                )
              </Text>
              <Button title="Change" onPress={() => setDraft(server)} style={{ paddingVertical: 3 }} />
            </View>
          ) : (
            <View style={{ flexDirection: "row", alignItems: "center", marginTop: 6, gap: 6 }}>
              <TextInput
                value={draft}
                onChangeText={setDraft}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
                style={{ flex: 1, borderWidth: 1, borderColor: "#999", paddingHorizontal: 8, paddingVertical: 5, fontSize: 14 }}
              />
              <Button title="Save" onPress={() => { setServer(draft.trim().replace(/\/+$/, "")); setDraft(null); }} />
              <Button title="Cancel" onPress={() => setDraft(null)} />
            </View>
          )}

          <View style={[s.row, { marginTop: 10 }]}>
            {TABS.map((t) => (
              <Button key={t.id} title={t.title} active={tab === t.id} onPress={() => setTab(t.id)} />
            ))}
          </View>
        </View>

        <View style={{ flex: 1 }}>
          <Screen api={api} />
        </View>
      </SafeAreaView>
    </SafeAreaProvider>
  );
}

import { useCallback, useEffect, useState } from "react";
import { Alert, FlatList, Image, Modal, Platform, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Button, Prediction, s } from "./ui";

const FILTERS = [
  { id: "", title: "All" },
  { id: "cat", title: "Cats" },
  { id: "dog", title: "Dogs" },
  { id: "uncertain", title: "Uncertain" },
];

export default function HistoryScreen({ api }) {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await api.history(50));
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => { load(); }, [load]);

  function confirmDelete(item) {
    Alert.alert("Delete", "Delete this prediction and its image from MongoDB?", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete",
        style: "destructive",
        onPress: async () => {
          try {
            await api.deletePrediction(item.id);
            setItems((prev) => prev.filter((i) => i.id !== item.id));
            setSelected(null);
          } catch (e) {
            Alert.alert("Delete", e.message);
          }
        },
      },
    ]);
  }

  const shown = filter ? items.filter((i) => i.label === filter) : items;
  const count = (l) => items.filter((i) => i.label === l).length;

  return (
    <View style={{ flex: 1 }}>
      <View style={{ padding: 12, paddingBottom: 6 }}>
        <View style={s.row}>
          {FILTERS.map((f) => (
            <Button key={f.id} title={f.title} active={filter === f.id} onPress={() => setFilter(f.id)} />
          ))}
        </View>
        <Text style={[s.muted, { marginTop: 8 }]}>
          Cats: {count("cat")} | Dogs: {count("dog")} | Uncertain: {count("uncertain")}. Pull down to refresh.
        </Text>
        {!!error && <Text style={s.error}>{error}</Text>}
      </View>

      <FlatList
        data={shown}
        keyExtractor={(i) => i.id}
        numColumns={2}
        contentContainerStyle={{ paddingHorizontal: 8, paddingBottom: 24 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        ListEmptyComponent={!loading && <Text style={[s.muted, { padding: 8 }]}>No predictions yet.</Text>}
        renderItem={({ item }) => (
          <Pressable style={{ width: "50%", padding: 4 }} onPress={() => setSelected(item)}>
            <View style={{ borderWidth: 1, borderColor: "#ccc" }}>
              <Image source={{ uri: api.imageUrl(item.imageUrl) }} style={{ width: "100%", aspectRatio: 4 / 3, backgroundColor: "#eee" }} />
              <View style={{ padding: 6 }}>
                <Prediction result={item} compact />
                <Text style={s.muted}>
                  {item.metadata.client} / {item.metadata.source || "?"}
                  {"\n"}
                  {new Date(item.createdAt).toLocaleString()}
                </Text>
              </View>
            </View>
          </Pressable>
        )}
      />

      <Modal visible={!!selected} animationType="slide" onRequestClose={() => setSelected(null)}>
        {selected && (
          <SafeAreaView style={{ flex: 1, backgroundColor: "#fff" }}>
            <ScrollView contentContainerStyle={{ padding: 12 }}>
              <Image
                source={{ uri: api.imageUrl(selected.imageUrl) }}
                style={{ width: "100%", aspectRatio: 1, backgroundColor: "#eee" }}
                resizeMode="contain"
              />
              <View style={{ marginTop: 10 }}>
                <Prediction result={selected} />
              </View>
              <Text style={s.heading}>Metadata (sent by the client)</Text>
              <Text style={mono}>{JSON.stringify(selected.metadata, null, 2)}</Text>
              <Text style={s.heading}>Stored image (GridFS)</Text>
              <Text style={mono}>{JSON.stringify({ imageId: selected.imageId, ...selected.image }, null, 2)}</Text>
              <View style={[s.row, { marginTop: 12 }]}>
                <Button title="Delete" onPress={() => confirmDelete(selected)} />
                <Button title="Close" onPress={() => setSelected(null)} />
              </View>
            </ScrollView>
          </SafeAreaView>
        )}
      </Modal>
    </View>
  );
}

const mono = {
  fontFamily: Platform.select({ ios: "Menlo", default: "monospace" }),
  fontSize: 12,
  color: "#222",
  backgroundColor: "#f5f5f5",
  borderWidth: 1,
  borderColor: "#ddd",
  padding: 8,
};

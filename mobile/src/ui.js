import { Pressable, StyleSheet, Text, View } from "react-native";

const NAMES = { cat: "Cat", dog: "Dog", uncertain: "Uncertain" };

export const formatResult = (r) => `${NAMES[r.label]} (${(r.confidence * 100).toFixed(1)}%)`;

/** Plain gray button, like the web and desktop clients. */
export function Button({ title, onPress, disabled, active, style }) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [s.button, active && s.buttonActive, pressed && !active && s.buttonPressed, style]}
    >
      <Text style={[s.buttonText, active && s.buttonTextActive, disabled && s.buttonTextDisabled]}>{title}</Text>
    </Pressable>
  );
}

export function Prediction({ result, compact = false }) {
  return (
    <View>
      <Text style={compact ? s.resultSmall : s.result}>{formatResult(result)}</Text>
      <View style={s.bar}>
        <View style={[s.barFill, { width: `${result.confidence * 100}%` }]} />
      </View>
      {result.label === "uncertain" && !compact && (
        <Text style={s.muted}>
          Best guess: {result.predictedClass}, but confidence is below {(result.threshold * 100).toFixed(0)}%. It may not
          be a cat or a dog.
        </Text>
      )}
    </View>
  );
}

export const s = StyleSheet.create({
  button: {
    borderWidth: 1,
    borderColor: "#999",
    borderRadius: 3,
    backgroundColor: "#f2f2f2",
    paddingVertical: 8,
    paddingHorizontal: 12,
    alignItems: "center",
  },
  buttonPressed: { backgroundColor: "#e4e4e4" },
  buttonActive: { backgroundColor: "#333", borderColor: "#333" },
  buttonText: { fontSize: 15, color: "#222" },
  buttonTextActive: { color: "#fff" },
  buttonTextDisabled: { color: "#888" },
  result: { fontSize: 18, fontWeight: "bold", color: "#222" },
  resultSmall: { fontSize: 14, fontWeight: "bold", color: "#222" },
  bar: { height: 6, backgroundColor: "#ddd", marginTop: 4, marginBottom: 6 },
  barFill: { height: "100%", backgroundColor: "#444" },
  text: { fontSize: 15, color: "#222" },
  muted: { fontSize: 13, color: "#666", marginTop: 2 },
  error: { fontSize: 14, color: "#c00", marginTop: 6 },
  row: { flexDirection: "row", gap: 6, flexWrap: "wrap" },
  heading: { fontSize: 15, fontWeight: "bold", color: "#222", marginTop: 12, marginBottom: 6 },
});

const EMOJI = { cat: "🐱", dog: "🐶", uncertain: "❓" };

/** Label + confidence bar for a prediction returned by the API. */
export default function Prediction({ result, compact = false }) {
  const { label, confidence, predictedClass } = result;
  return (
    <div className={`prediction ${label} ${compact ? "compact" : ""}`}>
      <div className="prediction-label">
        <span>{EMOJI[label]} {label === "uncertain" ? "Not sure" : label}</span>
        <span className="prediction-conf">{(confidence * 100).toFixed(1)}%</span>
      </div>
      <div className="bar">
        <div className="bar-fill" style={{ width: `${confidence * 100}%` }} />
      </div>
      {label === "uncertain" && !compact && (
        <p className="hint">
          Best guess: {predictedClass}, but confidence is below {(result.threshold * 100).toFixed(0)}%. It may not be a cat or a dog.
        </p>
      )}
    </div>
  );
}

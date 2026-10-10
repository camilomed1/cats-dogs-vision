const NAMES = { cat: "Cat", dog: "Dog", uncertain: "Uncertain" };

/** Label + confidence for a prediction returned by the API. */
export default function Prediction({ result, compact = false }) {
  const { label, confidence, predictedClass } = result;
  return (
    <div className="prediction">
      <div>
        <b>{NAMES[label]}</b> ({(confidence * 100).toFixed(1)}%)
      </div>
      <div className="bar">
        <div className="bar-fill" style={{ width: `${confidence * 100}%` }} />
      </div>
      {label === "uncertain" && !compact && (
        <p className="small">
          Best guess: {predictedClass}, but confidence is below {(result.threshold * 100).toFixed(0)}%. It may not be a cat or a dog.
        </p>
      )}
    </div>
  );
}

/** Reads a File as a base64 string (without the "data:...;base64," prefix) plus a preview URL. */
export function readFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const dataUrl = reader.result;
      const img = new Image();
      img.onload = () =>
        resolve({
          base64: dataUrl.slice(dataUrl.indexOf(",") + 1),
          previewUrl: dataUrl,
          width: img.naturalWidth,
          height: img.naturalHeight,
        });
      img.onerror = () => reject(new Error("The browser cannot open this image"));
      img.src = dataUrl;
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

/** Grabs the current video frame as a JPEG base64 string. */
export function captureFrame(video, canvas, quality = 0.85) {
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  const dataUrl = canvas.toDataURL("image/jpeg", quality);
  return { base64: dataUrl.slice(dataUrl.indexOf(",") + 1), previewUrl: dataUrl };
}

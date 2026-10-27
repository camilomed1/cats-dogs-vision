# Cats vs Dogs Vision

University computer-vision project: a cats vs dogs image classifier built with **TensorFlow/Keras**, served by a **Flask** API and used from three clients.

```
                ┌──────────────────────────┐
                │ Keras model (.keras)      │  trained in Google Colab
                └────────────┬─────────────┘
                ┌────────────▼─────────────┐      ┌──────────────────────┐
                │ Flask REST API (JSON)     │─────▶│ MongoDB + GridFS      │
                └──┬──────────┬──────────┬─┘      │ images + metadata     │
                   │          │          │        └──────────────────────┘
          Mobile (Expo)   Web (React)   Desktop (PySide6)
          camera/gallery  files/webcam  webcam/files
```

## Structure

| Folder | Description | Status |
|---|---|---|
| `training/` | Colab notebook: baseline CNN vs MobileNetV2 transfer learning | ✅ |
| `backend/` | Flask API, base64 + metadata in, prediction out, images stored in GridFS | ✅ |
| `web/` | React (Vite) client: file upload + live webcam | ✅ |
| `desktop/` | Python PySide6 client: webcam (live) + files | ✅ |
| `mobile/` | React Native (Expo) client: camera + gallery | ✅ |

## API contract

`POST /api/predict`
```json
{
  "image": "<base64 string>",
  "metadata": {
    "client": "mobile | web | desktop",
    "source": "camera | gallery | file | webcam",
    "filename": "photo.jpg",
    "mimeType": "image/jpeg",
    "width": 1080,
    "height": 1920,
    "capturedAt": "2026-10-09T15:30:00Z"
  },
  "store": true
}
```
Response:
```json
{ "id": "...", "label": "dog", "confidence": 0.97, "probabilities": { "cat": 0.03, "dog": 0.97 } }
```
`label` is `"uncertain"` when confidence is below the threshold. Live-mode frames are sent with `"store": false` so they are not saved.

## 1. Training: comparison of 5 pretrained models

`training/cats_vs_dogs_training.ipynb`:

1. Removes corrupted images and **balances the classes** (same number of cats and dogs).
2. Splits the data **70% train / 15% validation / 15% test** and saves the splits as CSV files.
3. Trains a **baseline CNN from scratch** and **5 pretrained ImageNet models** with transfer learning + fine-tuning:
   ResNet50, DenseNet121, MobileNetV2, EfficientNetB0 and Xception.
4. Uses callbacks: `ModelCheckpoint`, `EarlyStopping`, `ReduceLROnPlateau`, `CSVLogger`.
5. Compares all models on the test set: accuracy, precision, recall, specificity, F1, AUC, confusion matrices,
   ROC curves, size and inference time.
6. Runs **5-fold cross-validation** on the best model (chosen by validation F1).
7. Exports the best model with its normalization built in, so the backend works with any of the 5 architectures.

How to run:
1. Open the notebook in [Google Colab](https://colab.research.google.com/) (File → Upload notebook).
2. `Runtime → Change runtime type → T4 GPU`, then `Runtime → Run all`, and allow Google Drive access.
3. It takes about 2 hours. Progress is saved to `MyDrive/cats_dogs_vision/` after every model and every fold,
   so if Colab disconnects, run all again and it continues where it stopped.
4. At the end it downloads `cats_dogs_export.zip`. Replace the contents of `training/export/` with it.

### Results

Balanced dataset: 11,669 images per class. Split: 16,336 train / 3,500 validation / 3,502 test.
The best model is chosen by **validation F1**; the table shows the **test set** results.

| Model | Type | Params (M) | Accuracy | Precision | Recall | Specificity | F1 | AUC | CPU inference* |
|---|---|---|---|---|---|---|---|---|---|
| **EfficientNetB0** (selected) | pretrained | 4.05 | **99.09%** | 99.09% | 99.09% | 99.09% | 99.09% | 0.9997 | 29 ms |
| DenseNet121 | pretrained | 7.04 | 99.29% | 99.31% | 99.26% | 99.31% | 99.29% | 0.9998 | 63 ms |
| Xception | pretrained | 20.86 | 99.03% | 99.03% | 99.03% | 99.03% | 99.03% | 0.9994 | 50 ms |
| ResNet50 | pretrained | 23.59 | 99.03% | 98.97% | 99.09% | 98.97% | 99.03% | 0.9995 | 40 ms |
| MobileNetV2 | pretrained | 2.26 | 98.74% | 98.30% | 99.20% | 98.29% | 98.75% | 0.9993 | 13 ms |
| Baseline CNN | from scratch | 0.39 | 88.12% | 87.69% | 88.69% | 87.55% | 88.19% | 0.9542 | 5 ms |

\* One image on the backend PC's CPU with a compiled graph (`tf.function`), measured outside the notebook.

**5-fold cross-validation of EfficientNetB0** (train + validation data): accuracy **99.09% ± 0.20%**,
F1 99.09% ± 0.20%, AUC 0.9992 ± 0.0006. The low deviation shows the result does not depend on the split.

DenseNet121 scored slightly higher on the test set (+0.2%, 7 more images right), but the model is chosen with the
validation set only; picking it by test score would make the test result optimistic.

![Test metrics](training/export/figures/metrics_comparison.png)
![Training curves](training/export/figures/training_curves.png)
![Confusion matrices](training/export/figures/confusion_matrices.png)
![ROC curves](training/export/figures/roc_curves_zoom.png)
![K-fold](training/export/figures/kfold.png)

## 2. Backend (Flask + MongoDB)

Requires MongoDB running locally (`mongodb://localhost:27017`).

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python app.py
```

The API listens on `http://0.0.0.0:5000`. Other devices on the same Wi-Fi (the phone) reach it at `http://<your-PC-IP>:5000`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Server, database and model status |
| POST | `/api/predict` | Classify a base64 image (stores it in GridFS unless `"store": false`) |
| GET | `/api/history?limit=20&client=web` | Latest stored predictions |
| GET | `/api/predictions/<id>` | One prediction |
| DELETE | `/api/predictions/<id>` | Delete a prediction and its image |
| GET | `/api/images/<imageId>` | Original image bytes from GridFS |

MongoDB layout (database `cats_dogs_vision`):
- `images.files` / `images.chunks`: GridFS bucket with the original image bytes plus the client metadata.
- `predictions`: one document per stored prediction (`metadata`, `image` info such as size and sha256, `prediction`, `createdAt`, `imageFileId`).

## 3. Web client (React + Vite)

```bash
cd web
npm install
npm run dev
```

Open http://localhost:5173 (the backend must be running). Vite forwards `/api/*` to `http://localhost:5000`.

- **Upload**: drag and drop or pick one or more images. Each one is converted to base64 and sent with its metadata (filename, type, size, dimensions, last modified).
- **Webcam**: *live prediction* classifies a frame about 3 times per second without saving it (`store: false`). *Snapshot & save* classifies one frame and stores it in MongoDB.
- **History**: gallery of stored predictions from every client, with filters by client and label, a details view (metadata + GridFS info) and delete.

## 4. Desktop client (Python + PySide6 + OpenCV)

```powershell
cd desktop
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

Optional: `.venv\Scripts\python main.py http://<server-ip>:5000` to use a backend on another machine (default `http://127.0.0.1:5000`).

- **Upload**: "Choose images..." or drag and drop files into the window.
- **Webcam**: pick the camera, *Start live prediction* (result drawn on the video, frames not stored) or *Snapshot and save*.
- **History**: same data as the web client; double-click an image for metadata and GridFS details, or to delete it.

All network calls run in background threads, so the window never freezes while waiting for the server.

> Use `127.0.0.1` instead of `localhost` on Windows: `localhost` tries IPv6 first and adds about 2 s to every request.

## 5. Mobile client (React Native + Expo)

Requirements: the **Expo Go** app on the phone, and the phone on the **same Wi-Fi** as the PC running the backend.

```powershell
cd mobile
npm install
npx expo start
```

Scan the QR code with the iPhone camera, which opens it in Expo Go. The app automatically uses the PC's IP for the API (`http://<PC-IP>:5000`); the address can be changed with the "Change" button in the header.

- **Camera**: *Take photo and save* stores the photo; *Start live* classifies a silent low-quality photo about once per second without storing it; *Flip* switches cameras.
- **Gallery**: pick a photo from the library (HEIC photos are converted to JPEG). Metadata includes EXIF date and camera model when available.
- **History**: same data as the other clients, label filters, pull to refresh, tap for details and delete.

### Backend tests

Tests use the real model and a throwaway `cats_dogs_vision_test` database:
```bash
cd backend
.venv\Scripts\python -m pytest -q
```

# Demo checklist

## The night before
- [ ] Run a full rehearsal at home without the lab camera: double-click `start_demo.bat` with the test video:
      `start_demo.bat -Camera video` (or `-Camera webcam`). Check that all windows start and the web opens.
- [ ] Phone: Expo Go installed and signed in (`npx expo login` was already done on the PC).
- [ ] Have a few cat and dog photos on the phone, to show them to the camera.
- [ ] Laptop charged. MongoDB Compass installed (to show the database).

## In the lab
1. Connect the laptop to the **same network as the camera** (the camera is at `192.168.210.6`, so the laptop
   should get an address like `192.168.210.x`).
2. Double-click **`start_demo.bat`**. It opens: `1 Backend`, `2 Web`, `3 Camera station`, `4 Virtual ESP32`,
   `5 Mobile (Expo)`, `6 Desktop app`, and the browser at http://localhost:5173 after about 12 seconds.
3. Look at window **3 Camera station**: it first runs the camera check.
   - `OK, the camera answers on the network` and then `OK: <width>x<height>, about N fps` means everything is fine.
   - If it fails, see the table below.
4. Scan the QR code in window **5** with the iPhone camera.

The lab camera address and account are in `camera_station/.env` (`CAMERA_URL=rtsp://...@192.168.210.6:554/stream1`).
That file is not uploaded to GitHub. To check only the camera: `cd camera_station` then `.venv\Scripts\python check_camera.py`.

## If something fails

| Problem | What you see | Fix |
|---|---|---|
| Laptop not on the camera's network | Check: `Network ... FAILED (timed out)` | Connect to the lab Wi-Fi/cable where the camera is. Compare the first numbers of "This PC" and the camera IP |
| Camera IP changed | Same as above | Find the IP in the Tapo app (camera > settings > device info) and edit `CAMERA_URL` in `camera_station/.env` |
| Wrong camera account or path | `camera answers` but `Video ... FAILED` | Check user/password (Tapo app > Advanced settings > Camera account). Try `/stream2` instead of `/stream1` |
| Video slow or choppy | Low fps in the IP Camera tab | Use `/stream2` (lower quality, lighter) in `CAMERA_URL` |
| Lab camera not available at all | | Close all windows and run `start_demo.bat -Camera webcam` (or `-Camera video`) |
| MQTT blocked by the university network | Backend: `MQTT disconnected`; ESP32 window never says `Connected` | Close all windows and run `start_demo.bat -WebSockets` (uses port 8083 instead of 1883) |
| Phone cannot reach the laptop | App header says `offline` | University Wi-Fi often blocks device-to-device traffic. Turn on Windows **Mobile hotspot** (Settings > Network & internet), connect the iPhone to it, close all windows and run `start_demo.bat -Hotspot`. The laptop stays on the lab network for the camera. Allow Python/Node if Windows Firewall asks |
| `MongoDB is not running` warning | Predictions are not saved | Start the MongoDB service (services.msc > MongoDB > Start) |

Options can be combined, e.g. `start_demo.bat -WebSockets -Hotspot`.

## Suggested order (about 10 minutes)

1. **Training** (open `training/cats_vs_dogs_training.ipynb` on GitHub or the README results):
   balanced classes, 70/15/15 split, baseline from scratch vs 5 pretrained models, metrics (accuracy, precision,
   recall, specificity, F1, AUC), confusion matrices, ROC, 5-fold cross-validation. EfficientNetB0 chosen by
   **validation** F1 (99.09% test accuracy, 99.09% +- 0.20% in k-fold).
2. **Architecture**: one Flask backend + MongoDB/GridFS, every client sends **base64 + metadata** as JSON.
3. **Web** (http://localhost:5173): Upload, Webcam, **IP Camera** (lab Tapo live with the label drawn on it), History
   (click an image to show the metadata and the GridFS info).
4. **Mobile** (iPhone): Camera (photo + live), Gallery, History.
5. **Desktop app**: opens with `start_demo.bat` (window "Cats vs Dogs"); skip it with `-NoDesktop`.
6. **IP camera + MQTT + ESP32**: show a cat/dog photo to the Tapo, hold it 2 s: the station saves an *event* and window
   **4 Virtual ESP32** prints `... LED ON`. Then press **Enter** in window 4: the camera saves a *remote* snapshot.
   Uploading a photo from the web or phone also reaches the ESP32 (it reacts to every client).
7. **Database**: MongoDB Compass > `cats_dogs_vision`: `predictions`, `images.files`, `images.chunks` (GridFS).

Talking points: separation of concerns in the backend, transfer learning vs from scratch, why the model is chosen
with validation and not test, MQTT publish/subscribe (broker, topics, retained messages, Last Will), and why the
ESP32 does not run the model (0.4 MB RAM vs a 17 MB model).

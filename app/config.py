import os

FIREBASE_CREDENTIALS = "credentials/firebase-key.json"

FIREBASE_CREDENTIALS_JSON = os.getenv("FIREBASE_CREDENTIALS_JSON")

FIREBASE_DATABASE_URL = os.getenv(
    "FIREBASE_DATABASE_URL",
    "https://somnix-cfdb1-default-rtdb.firebaseio.com/"
)

CAMERA_URL = 1

TIEMPO_OJOS_CERRADOS = 2.5
TIEMPO_ENTRE_ALERTAS = 4
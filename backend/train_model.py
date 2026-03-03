import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import joblib

# CSV laden
df = pd.read_csv("umzug_daten.csv")

# Eingabedaten (Features)
X = df[["qm", "kartons", "fahrstuhl", "stockwerk", "distanz_meter",
        "schraenke", "waschmaschine", "fernseher", "montage"]]

# Zielvariable (Preis)
y = df["preis_eur"]

# Training / Test Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Modell erstellen
model = RandomForestRegressor(
    n_estimators=300,
    random_state=42
)

# Trainieren
model.fit(X_train, y_train)

# Testen
y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
print(f"MAE: {mae:.2f} €")

# Modell speichern
joblib.dump(model, "umzug_preis_model.pkl")
print("Modell gespeichert: umzug_preis_model.pkl")

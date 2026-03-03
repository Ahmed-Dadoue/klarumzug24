# generate_data.py
import pandas as pd
import random

def berechne_preis(qm, kartons, fahrstuhl, stockwerk, distanz, schraenke,
                   waschmaschine, fernseher, montage):
    basis = qm * 3
    karton_kosten = kartons * 2
    schrank = schraenke * 15
    wasch = waschmaschine * 10
    tv = fernseher * 5

    preis = basis + karton_kosten + schrank + wasch + tv

    if fahrstuhl == 0:
        preis *= 1.2  # 20% Aufschlag
    if distanz > 20:
        preis += 15
    if montage == 1:
        preis += 40

    # kleine Zufallsschwankung
    preis += random.randint(-20, 20)

    return round(preis, 2)

daten = []

for _ in range(300):
    qm = random.randint(30, 120)
    kartons = random.randint(5, 50)
    fahrstuhl = random.randint(0, 1)
    stockwerk = random.randint(0, 5)
    distanz = random.randint(5, 40)
    schraenke = random.randint(0, 5)
    waschmaschine = random.randint(0, 2)
    fernseher = random.randint(0, 3)
    montage = random.randint(0, 1)

    preis = berechne_preis(qm, kartons, fahrstuhl, stockwerk, distanz,
                           schraenke, waschmaschine, fernseher, montage)

    daten.append({
        "qm": qm,
        "kartons": kartons,
        "fahrstuhl": fahrstuhl,
        "stockwerk": stockwerk,
        "distanz_meter": distanz,
        "schraenke": schraenke,
        "waschmaschine": waschmaschine,
        "fernseher": fernseher,
        "montage": montage,
        "preis_eur": preis
    })

df = pd.DataFrame(daten)
df.to_csv("umzug_daten.csv", index=False)
print("umzug_daten.csv erstellt.")

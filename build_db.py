import sqlite3
from pathlib import Path
import pandas as pd

DATA_FOLDER = Path("data")      # folder with your CSV files
DB_PATH = "ecommerce.db"        # the database this script creates

conn = sqlite3.connect(DB_PATH)

for csv_file in DATA_FOLDER.glob("*.csv"):
    # Shorter table names: "olist_orders_dataset.csv" -> "orders"
    table = csv_file.stem.replace("olist_", "").replace("_dataset", "")
    df = pd.read_csv(csv_file)
    df.to_sql(table, conn, if_exists="replace", index=False)
    print(f"Loaded {table}: {len(df):,} rows")

conn.close()
print(f"\nDone! Created {DB_PATH}")
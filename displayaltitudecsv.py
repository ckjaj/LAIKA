import pandas as pd

# Path to your CSV
CSV_PATH = "xxx.csv"  # change this

# Load CSV
df = pd.read_csv(CSV_PATH)

# Parse timestamp
df["timestamp_iso"] = pd.to_datetime(df["timestamp_iso"])

# Set timestamp as index (nice for time-series)
df = df.set_index("timestamp_iso")

# Display first few rows
print(df.head())

# Optional: show dataframe info
print("\n--- DataFrame info ---")
print(df.info())

# Optional: basic stats
print("\n--- Summary stats ---")
print(df.describe())

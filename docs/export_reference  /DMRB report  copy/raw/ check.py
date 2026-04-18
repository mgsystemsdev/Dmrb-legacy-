import pandas as pd

df = pd.read_excel("DMRB_raw.xlsx")

df.columns = df.columns.str.strip()
print(df["Unit"].value_counts().to_string())

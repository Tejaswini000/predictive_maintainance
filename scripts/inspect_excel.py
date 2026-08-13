import pandas as pd
from pathlib import Path
path = Path('data/machines.xlsx')
df = pd.read_excel(path, sheet_name=0, engine='openpyxl')
print(df.columns.tolist())
print(df[['Machine ID','Machine Name','Purchase Date']].head().to_string(index=False))

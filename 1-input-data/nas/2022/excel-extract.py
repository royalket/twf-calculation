import pandas as pd
import os

# Config
xlsx_file = "nas-2022.xlsx"  # Change this
output_dir = "csv_output"     # Folder for CSVs

# Create output directory if needed
os.makedirs(output_dir, exist_ok=True)

# Read all sheets and export each
xl_file = pd.ExcelFile(xlsx_file)

for sheet_name in xl_file.sheet_names:
    df = pd.read_excel(xl_file, sheet_name=sheet_name)
    
    # Clean sheet name for filename (remove special chars)
    safe_name = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in sheet_name)
    csv_path = os.path.join(output_dir, f"{safe_name}.csv")
    
    df.to_csv(csv_path, index=False)
    print(f"✓ Exported: {sheet_name} → {csv_path}")

print(f"\nDone! {len(xl_file.sheet_names)} sheets exported to '{output_dir}/'")

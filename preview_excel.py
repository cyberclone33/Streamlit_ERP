import pandas as pd
import sys

def preview_excel(file_path, rows=100):
    try:
        # Get list of sheet names
        xl = pd.ExcelFile(file_path)
        sheet_names = xl.sheet_names
        print(f"Excel file has {len(sheet_names)} sheets: {sheet_names}")
        
        # Read the first sheet (or all if needed)
        df = pd.read_excel(file_path, sheet_name=0, nrows=rows)
        
        # Print basic info
        print(f"\nDataFrame shape: {df.shape} (rows, columns)")
        print("\nColumn names:")
        for col in df.columns:
            print(f"  - {col}")
        
        print("\nFirst 5 rows preview:")
        print(df.head().to_string())
        
        print("\nData types:")
        print(df.dtypes)
        
        # Basic statistics for numeric columns
        print("\nBasic statistics for numeric columns:")
        print(df.describe().to_string())
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        preview_excel(file_path)
    else:
        print("Please provide an Excel file path")
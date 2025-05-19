# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit-based ERP dashboard application that visualizes sales and inventory data. It processes Excel files containing sales transactions and product inventory information, provides data visualization, and allows users to analyze business performance metrics.

## Application Architecture

The application consists of several key modules:

- **sales.py**: Main dashboard for sales data analysis 
  - Contains optimized data processing with vectorized operations
  - Implements parallel file loading for multi-month analysis
  - Uses caching strategies to improve performance

- **bc_products.py**: Inventory management dashboard
  - Displays product inventory data
  - Can be integrated with sales data for stock level analysis

- **integrated_module.py**: Combined dashboard with multiple data sources
  - Integrates sales data with inventory information
  - Displays monthly sales breakdown for each product
  - Shows consolidated view with period-by-period comparison

- **fixed_sales_dashboard.py**: Alternative dashboard implementation with comparison features

## Key Optimizations

The application includes several performance optimizations:

1. **Vectorized Operations**: Pandas operations are optimized to use vectorized functions instead of row-by-row processing

2. **Parallel Processing**: Concurrent ThreadPoolExecutor for loading multiple files simultaneously 

3. **Advanced Caching**: Strategic caching with appropriate TTL values for different operations

4. **Memory Management**: Datatype optimization to reduce memory usage for large datasets

5. **Efficient Aggregations**: Optimized groupby operations with pre-filtering

6. **Monthly Sales Tracking**: Period-by-period sales breakdown for better trend analysis

## Running the Application

To run the application:

```bash
# Activate the virtual environment
source venv/bin/activate

# Run the Streamlit app
python -m streamlit run sales.py
```

## Alternative Entry Points

```bash
# Run inventory dashboard only
python -m streamlit run bc_products.py

# Run integrated dashboard
python -m streamlit run integrated_module.py

# Run fixed sales dashboard
python -m streamlit run fixed_sales_dashboard.py
```

## Feature Details

### Monthly Sales Breakdown

The integrated dashboard includes the ability to view sales data on a month-by-month basis:

- **Sales Summary Table**: Shows total sales quantities and values across all selected periods
- **Monthly Columns**: Individual columns for each selected month showing:
  - Sales quantity for that specific month
  - Sales revenue for that specific month
- **BC Products Integration**: The BC products table shows both total sales figures and monthly breakdowns
- **Sorting Options**: Tables can be sorted by any month's sales data for comparison

### Filter and Selection Features

- Products can be filtered by various attributes including category, vendor, and stock availability
- Multiple sales periods can be selected for comprehensive analysis
- Display columns can be customized to show only relevant data

## Known Issues and Solutions

### Pandas Boolean Operations

**Issue**: The error "'bool' object has no attribute 'any'" occurs when pandas returns a scalar boolean instead of a Series with boolean values.

**Cause**: When working with pandas Series and operations like `.str.contains()` or comparison operations, if the Series contains only a single value or if the operation results in a scalar result, pandas might return a simple boolean instead of a Series of booleans. Calling `.any()` on a scalar boolean causes the error.

**Solution**: Always check the type of the result before calling `.any()` method:

```python
# Problematic code:
mask = df['column'].str.contains('pattern')
if mask.any():  # Error if mask is a scalar boolean
    # Process data

# Fixed code:
mask = df['column'].str.contains('pattern')
if isinstance(mask, pd.Series) and mask.any():
    # Process Series case
elif isinstance(mask, bool) and mask:
    # Process scalar boolean case
```

**Affected parts**:
- `batch_convert_tw_dates()` function in sales.py
- Date parsing operations with `.str.contains()`
- Mask operations with `.shape[1] == 3`

### Return Value Consistency

When modifying function return values, ensure all calling code is updated to handle the new return signature. For example, the `run_sales_analysis()` function returns 3 values but some code expected only 2, causing the error "too many values to unpack (expected 2)".


## Sales Data Structure (銷貨單毛利分析表)

  - Each sales order (銷貨單號) spans multiple rows with order info only in first row
  - Subsequent product rows have NaN values in order fields
  - Numbers with commas represent thousands (for sorting: 999 < 1,000)
  - File contains 39 columns with mixed data types

  Column Definitions with Data Types:
  - 銷貨單號 (Sales Order Number): float64
  - 訂單單號 (Order Number): float64
  - 銷貨日期 (Sales Date): object (string)
  - 客戶代號 (Customer Code): object (string)
  - 客戶名稱 (Customer Name): object (string)
  - 部門代號 (Department Code): float64
  - 部門名稱 (Department Name): float64
  - 發票號碼 (Invoice Number): object (string)
  - 未稅小計 (Subtotal pre-tax): object (string with commas)
  - 營業稅 (Sales Tax): object (string with commas)
  - 折讓金額 (Discount Amount): float64
  - 稅前折價 (Pre-tax Discount): float64
  - 總計金額 (Total Amount): object (string with commas)
  - 實收總額 (Actual Receipt): object (string with commas)
  - 成本總額 (Total Cost): object (string with commas)
  - 毛利 (Gross Profit): float64
  - 毛利率 (Gross Margin): object (string)
  - 產品代號 (Product Code): object (string)
  - 產品名稱 (Product Name): object (string)
  - 倉別代號 (Warehouse Code): object (string)
  - 倉別名稱 (Warehouse Name): object (string)
  - 數量 (Quantity): int64
  - 單位 (Unit): object (string)
  - 單價 (Unit Price): object (string with commas)
  - 小計 (Subtotal): object (string with commas)
  - 成本總值 (Total Cost Value): object (string with commas)
  - 產品毛利 (Product Profit): float64
  - 產品毛利率 (Product Margin): float64
  - 銷售單價1 (Sales Unit Price 1): object (string)
  - 精準成本 (Precise Cost): object (string with commas)
  - 精準毛利 (Precise Profit): float64
  - 單位管銷成本 (Unit Mgt/Sales Cost): int64
  - 管銷成本合計 (Total Mgt/Sales Cost): int64
  - _銷貨日期 (Sales Date Filter): object (string)
  - _客戶代號 (Customer Code Filter): object (string)
  - _客戶條件 (Customer Condition): object (string)
  - _部門代號 (Department Code Filter): object (string)
  - _業務代號 (Business Code Filter): object (string)
  - _業務條件 (Business Condition): object (string)

⏺ BC Products Excel Structure:

  Key Information:
  - File contains product inventory data with 28 columns
  - Contains product codes, names, quantities, pricing, and categorization

  Column Definitions with Data Types:
  - 產品代號 (Product Code): object (string)
  - 產品名稱 (Product Name): object (string)
  - 數量 (Quantity): int64
  - 倉庫 (Warehouse): object (string)
  - 單位 (Unit): object (string)
  - 成本單價 (Cost Unit Price): object (string)
  - 成本總價 (Total Cost Price): object (string)
  - 安全存量 (Safety Stock): float64
  - 廠商代號 (Vendor Code): object (string)
  - 廠商簡稱 (Vendor Short Name): object (string)
  - 最後出貨日 (Last Shipping Date): object (string)
  - 最後進貨日 (Last Restocking Date): object (string)
  - 銷售單價1 (Sales Unit Price 1): object (string)
  - 銷售單價2 (Sales Unit Price 2): object (string)
  - 銷售單價3 (Sales Unit Price 3): float64
  - 銷售單價4 (Sales Unit Price 4): float64
  - 最低售價 (Minimum Selling Price): float64
  - 數量為零自動下架 (Auto-Removal when Quantity is Zero): int64
  - 持續上架 (Continue Listing): int64 (boolean: 0/1)
  - 停止上架 (Stop Listing): int64 (boolean: 0/1)
  - 大類名稱 (Main Category): object (string)
  - 中類名稱 (Middle Category): object (string)
  - 小類名稱 (Small Category): object (string)
  - 備註 (Remarks): float64
  - EAN13碼 (EAN13 Code): float64
  - CO128碼 (CO128 Code): object (string)
  - 建議售價 (Suggested Retail Price): object (string)
  - 毛利率 (Profit Margin): object (string)
# 銷貨單與BC產品資料整合模組 - Sales and BC Products Integrated Module
import streamlit as st
import pandas as pd
import os
import importlib
import sales
import bc_products
import plotly.express as px
from datetime import datetime
import locale
import numpy as np
import shutil

# Set locale for proper number formatting
try:
    locale.setlocale(locale.LC_ALL, 'zh_TW.UTF-8')  # For Taiwan locale
except:
    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')  # Fallback to US locale
    except:
        pass  # Keep default locale if unable to set

# Set page configuration only when run as standalone (not imported)
if __name__ == "__main__":
    st.set_page_config(
        page_title="銷貨單與BC產品資料整合",
        page_icon="🔄",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

# Function to get files sorted by modification time
def get_sorted_files(directory, file_extension=".xlsx"):
    """Get files from directory sorted by modification time (newest first)"""
    if not os.path.exists(directory):
        return []
    
    # Get files with their modification times
    files_with_time = [(f, os.path.getmtime(os.path.join(directory, f))) 
                      for f in os.listdir(directory) if f.endswith(file_extension)]
    
    # Sort by modification time, newest first
    files_with_time.sort(key=lambda x: x[1], reverse=True)
    
    # Return sorted filenames
    return [f[0] for f in files_with_time]

# Function to get all available files (both active and uploads)
def get_all_available_files(main_dir, uploads_dir, file_extension=".xlsx"):
    """Get all available files from both main and uploads directories"""
    main_files = get_sorted_files(main_dir, file_extension)
    uploads_files = get_sorted_files(uploads_dir, file_extension)
    
    # Create a set of main files to check for duplicates
    main_files_set = set(main_files)
    
    # Add upload files that aren't already in main directory
    all_files = main_files.copy()
    for f in uploads_files:
        if f not in main_files_set:
            all_files.append(f)
    
    return all_files, main_files, uploads_files

# Main function for the integrated module
def run_integrated_analysis():
    # Initialize session states for file selection
    if 'integrated_sales_periods' not in st.session_state:
        st.session_state.integrated_sales_periods = []
    if 'integrated_bc_file' not in st.session_state:
        st.session_state.integrated_bc_file = None
    if 'show_upload_history' not in st.session_state:
        st.session_state.show_upload_history = False
    
    # Title with refresh button
    title_col, refresh_col = st.columns([5, 1])
    with title_col:
        st.title("銷貨單與BC產品資料整合分析")
    with refresh_col:
        if st.button("🔄 重新整理", key="refresh_integrated", help="重新整理檔案清單與資料"):
            # Clear cached data
            sales.load_data.clear() if hasattr(sales.load_data, 'clear') else None
            bc_products.load_data.clear() if hasattr(bc_products.load_data, 'clear') else None
            st.rerun()
    
    # Get directories for both data types
    sales_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales data")
    sales_uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads/sales")
    bc_products_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bc  products")
    bc_uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads/bc_products")
    
    # Toggle for showing upload history
    show_uploads = st.checkbox("顯示上傳歷史檔案", 
                               value=st.session_state.show_upload_history,
                               help="選擇是否包含上傳歷史中的檔案")
    st.session_state.show_upload_history = show_uploads
    
    # Sales data section
    st.header("銷貨單毛利分析資料選擇")
    
    # Get all sales files
    if show_uploads:
        all_sales_files, active_sales_files, upload_sales_files = get_all_available_files(sales_data_dir, sales_uploads_dir)
        
        # Show counts of files
        st.info(f"共有 {len(active_sales_files)} 個使用中檔案 + {len(upload_sales_files)} 個上傳歷史檔案")
        
        # Mark files from upload history
        display_options = {}
        for file in all_sales_files:
            label = sales.extract_date_from_filename(file)
            
            # Add indicator if file is from upload history
            if file not in active_sales_files:
                label = f"{label} [上傳歷史]"
                
                # Add button to activate file
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.text(file)
                with col2:
                    if st.button("啟用此檔案", key=f"activate_{file}"):
                        try:
                            # Copy from uploads to active directory
                            shutil.copy(
                                os.path.join(sales_uploads_dir, file),
                                os.path.join(sales_data_dir, file)
                            )
                            st.success(f"已啟用 {file}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"無法啟用檔案: {e}")
            
            display_options[label] = file
    else:
        # Only use active files
        active_sales_files = get_sorted_files(sales_data_dir)
        display_options = {sales.extract_date_from_filename(file): file for file in active_sales_files}
    
    # Get the sorted keys
    sorted_keys = sorted(display_options.keys())
    
    # Determine default selection based on session state
    default_periods = []
    if st.session_state.integrated_sales_periods:
        # Use stored selections if they exist
        for period in st.session_state.integrated_sales_periods:
            if period in sorted_keys:
                default_periods.append(period)
    
    # If no stored options or they're invalid, default to first item
    if not default_periods and sorted_keys:
        default_periods = [sorted_keys[0]]
    
    # Using multi-month selection
    selected_periods = st.multiselect(
        "選擇多個報表期間 (按住Ctrl或⌘鍵可多選)",
        options=sorted_keys,
        default=default_periods
    )
    
    # Save to session state
    st.session_state.integrated_sales_periods = selected_periods
    
    # Check if any periods are selected
    if not selected_periods:
        st.warning("請至少選擇一個報表期間")
        sales_df = None
        period_display = None
    else:
        # Load data from multiple months, keeping track of which month each record belongs to
        dfs = []
        monthly_dfs = {}  # Dictionary to store each month's dataframe
        
        for period in selected_periods:
            file = display_options.get(period)
            
            # Determine the correct directory for this file
            if show_uploads and file not in active_sales_files:
                # File is from upload history
                file_path = os.path.join(sales_uploads_dir, file)
            else:
                # File is from active directory
                file_path = os.path.join(sales_data_dir, file)
            
            # Load the dataframe for this period
            period_df = sales.load_data(file_path)
            
            # Add a period identifier column
            period_df['_period'] = period
            
            # Store in our collection
            dfs.append(period_df)
            monthly_dfs[period] = period_df
        
        # Store the monthly dataframes in session state for later use
        st.session_state.monthly_sales_dfs = monthly_dfs
        st.session_state.selected_periods = selected_periods
        
        # Combine all dataframes
        sales_df = pd.concat(dfs, ignore_index=True)
        
        # Display combined periods
        period_display = f"合併報表 ({', '.join(selected_periods)})"
        
        # Show selected period
        st.subheader(f"期間: {period_display}")
    
    # BC Products data section
    st.header("BC產品全部資料選擇")
    
    # Get BC products data with uploads if requested
    try:
        if show_uploads:
            all_bc_files, active_bc_files, upload_bc_files = get_all_available_files(bc_products_dir, bc_uploads_dir)
            
            # Show counts of files
            st.info(f"共有 {len(active_bc_files)} 個使用中檔案 + {len(upload_bc_files)} 個上傳歷史檔案")
            
            # Mark files from upload history
            display_bc_options = []
            for file in all_bc_files:
                # Add indicator if file is from upload history
                if file not in active_bc_files:
                    # Add button to activate file
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.text(f"{file} [上傳歷史]")
                    with col2:
                        if st.button("啟用此檔案", key=f"activate_bc_{file}"):
                            try:
                                # Copy from uploads to active directory
                                shutil.copy(
                                    os.path.join(bc_uploads_dir, file),
                                    os.path.join(bc_products_dir, file)
                                )
                                st.success(f"已啟用 {file}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"無法啟用檔案: {e}")
                
                display_bc_options.append(file)
        else:
            # Only use active files
            display_bc_options = get_sorted_files(bc_products_dir)
        
        if not display_bc_options:
            st.error("沒有找到產品資料檔案")
            bc_df = None
            file_date_formatted = None
        else:
            # Determine default selection
            default_index = 0
            if st.session_state.integrated_bc_file in display_bc_options:
                default_index = display_bc_options.index(st.session_state.integrated_bc_file)
            
            selected_file = st.selectbox(
                "選擇產品資料檔案:", 
                display_bc_options,
                index=default_index
            )
            
            # Save to session state
            st.session_state.integrated_bc_file = selected_file
            
            # Determine correct directory
            if show_uploads and selected_file not in active_bc_files:
                file_path = os.path.join(bc_uploads_dir, selected_file)
            else:
                file_path = os.path.join(bc_products_dir, selected_file)
            
            # Add file modification time
            file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            st.info(f"檔案更新時間: {file_mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Load data
            bc_df = bc_products.load_data(file_path)
            
            # Extract file date for display
            try:
                file_date = selected_file.split('_')[-1].replace('.xlsx', '')
                # Make sure the date format is valid
                if len(file_date) >= 8:  # At least YYYYMMDD format
                    file_date_formatted = f"{file_date[:4]}/{file_date[4:6]}/{file_date[6:8]}"
                else:
                    # If date is not in expected format, use file modification time
                    file_date_formatted = file_mod_time.strftime("%Y/%m/%d")
            except:
                # Fallback to modification time if parsing fails
                file_date_formatted = file_mod_time.strftime("%Y/%m/%d")
    except Exception as e:
        st.error(f"讀取BC產品資料錯誤: {e}")
        bc_df = None
        file_date_formatted = None
    
    return sales_df, period_display, bc_df, file_date_formatted

# Function to display integrated dashboard
def display_integrated_dashboard(sales_df, period_display, bc_df, file_date):
    # Add refresh button to refresh cache
    refresh_col1, refresh_col2 = st.columns([4, 1])
    with refresh_col1:
        st.markdown("### 資料狀態:")
    with refresh_col2:
        if st.button("🔄 重新載入資料", key="refresh_data", help="清除資料快取並重新載入"):
            # Clear caches
            sales.load_data.clear() if hasattr(sales.load_data, 'clear') else None
            bc_products.load_data.clear() if hasattr(bc_products.load_data, 'clear') else None
            st.rerun()
    
    # Show data status with modification time information
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        if sales_df is not None:
            st.success(f"✅ 銷貨單資料已載入: {period_display}")
            if st.session_state.show_upload_history:
                st.info("✓ 上傳歷史檔案可用")
            if hasattr(st.session_state, 'integrated_sales_periods'):
                st.info(f"選擇報表: {', '.join(st.session_state.integrated_sales_periods)}")
        else:
            st.error("❌ 銷貨單資料未載入")
    
    with col2:
        if bc_df is not None:
            st.success(f"✅ BC產品資料已載入: {file_date}")
            if hasattr(st.session_state, 'integrated_bc_file'):
                st.info(f"檔案: {st.session_state.integrated_bc_file}")
        else:
            st.error("❌ BC產品資料未載入")
    
    # Add checkbox to toggle upload history
    change_col1, change_col2 = st.columns(2)
    with change_col1:
        if st.button("更改銷貨單資料選擇"):
            # Move back to the top of the page
            st.session_state._is_uploading = True
            st.experimental_set_query_params(section="sales_data")
            st.rerun()
    
    with change_col2:
        if st.button("更改BC產品資料選擇"):
            # Move back to the top of the page
            st.session_state._is_uploading = True
            st.experimental_set_query_params(section="bc_data")
            st.rerun()
            
    st.markdown("---")
    
    # Only proceed if we have valid data
    if sales_df is None:
        st.warning("請先選擇銷貨單資料")
        return
    
    # Display product summary table from sales data (reusing code from sales.py)
    st.header("銷貨單產品彙總表")

    # Add product code filter for sales data
    product_code_filter = st.text_input("輸入產品代號進行篩選 (留空顯示全部):", "")

    # Make a copy of the dataframe to clean numeric columns first
    df_products = sales_df.copy()

    # Fill in order information using the function from sales module
    sales_df_filled = sales.fill_order_info(sales_df)

    # Create a filtered version of the raw data if product code is provided
    if product_code_filter:
        # 使用填充後的DataFrame進行篩選，確保顯示完整訂單資訊
        df_filtered_raw = sales_df_filled[sales_df_filled['產品代號'].str.contains(product_code_filter, case=False, na=False)]

        if df_filtered_raw.empty:
            st.warning(f"沒有找到包含 '{product_code_filter}' 的產品代號")
        else:
            st.success(f"找到 {len(df_filtered_raw)} 筆包含 '{product_code_filter}' 的交易記錄")

            # 添加說明
            st.info("注意: 同一訂單中的所有產品行已自動填充訂單資訊，以確保顯示完整資料。")

            # Show the filtered raw data with filled order information
            with st.expander("查看篩選後的原始交易記錄 (已填充訂單資訊)", expanded=True):
                st.dataframe(df_filtered_raw, use_container_width=True)

    # Ensure numeric columns are properly converted to numeric before aggregation
    numeric_cols = ['數量', '小計', '成本總值']
    for col in numeric_cols:
        if col in df_products.columns:
            if df_products[col].dtype == 'object':
                df_products[col] = df_products[col].astype(str).str.replace(',', '')
                df_products[col] = pd.to_numeric(df_products[col], errors='coerce')
    
    # Separate handling for unit price
    if '單價' in df_products.columns:
        if df_products['單價'].dtype == 'object':
            df_products['單價'] = df_products['單價'].astype(str).str.replace(',', '')
            df_products['單價'] = pd.to_numeric(df_products['單價'], errors='coerce')
    
    # Apply filter to products data if needed
    if product_code_filter:
        df_products_filtered = df_products[df_products['產品代號'].str.contains(product_code_filter, case=False, na=False)]
    else:
        df_products_filtered = df_products.copy()

    # Now do the aggregation on filtered data with better error handling
    # First create a dict of aggregation functions for columns that exist
    agg_dict = {}
    if '產品名稱' in df_products_filtered.columns:
        agg_dict['產品名稱'] = 'first'  # Take the first product name
    
    if '數量' in df_products_filtered.columns:
        agg_dict['數量'] = 'sum'        # Sum quantities
    
    if '單位' in df_products_filtered.columns:
        agg_dict['單位'] = 'first'      # Take the first unit
    
    if '單價' in df_products_filtered.columns:
        agg_dict['單價'] = 'mean'       # Average price
    
    if '小計' in df_products_filtered.columns:
        agg_dict['小計'] = 'sum'        # Sum subtotals
    
    if '成本總值' in df_products_filtered.columns:
        agg_dict['成本總值'] = 'sum'     # Sum cost values
    
    # Only proceed if we have some columns to aggregate
    if agg_dict and '產品代號' in df_products_filtered.columns:
        # Do the aggregation
        product_summary = df_products_filtered.groupby(['產品代號'], as_index=False).agg(agg_dict)
        
        # Sort by 小計 in descending order if it exists
        if '小計' in product_summary.columns:
            product_summary = product_summary.sort_values(by='小計', ascending=False)
        
        # Calculate 單價（數量）= 小計 / 數量 safely
        # Initialize the column with float type to avoid dtype incompatibility
        product_summary['單價（數量）'] = 0.0  # Default value as float
        if '數量' in product_summary.columns and '小計' in product_summary.columns:
            # Use vectorized operations with safety checks
            mask = product_summary['數量'] > 0
            if isinstance(mask, pd.Series) and mask.any():
                # Calculate the division result as float
                result = (
                    product_summary.loc[mask, '小計'] / product_summary.loc[mask, '數量']
                ).astype('float64')  # Explicitly convert to float64
                # Assign the result to the column
                product_summary.loc[mask, '單價（數量）'] = result
        
        # Add monthly breakdowns if we have multiple periods selected
        if hasattr(st.session_state, 'monthly_sales_dfs') and len(st.session_state.monthly_sales_dfs) > 0:
            monthly_dfs = st.session_state.monthly_sales_dfs
            selected_periods = st.session_state.selected_periods
            
            # Process each month's data separately
            for period in selected_periods:
                if period in monthly_dfs:
                    period_df = monthly_dfs[period]
                    
                    # Create a copy and ensure numeric columns are properly converted
                    period_products = period_df.copy()
                    for col in numeric_cols:
                        if col in period_products.columns:
                            if period_products[col].dtype == 'object':
                                period_products[col] = period_products[col].astype(str).str.replace(',', '')
                                period_products[col] = pd.to_numeric(period_products[col], errors='coerce')
                    
                    # Also handle unit price for this period
                    if '單價' in period_products.columns and period_products['單價'].dtype == 'object':
                        period_products['單價'] = period_products['單價'].astype(str).str.replace(',', '')
                        period_products['單價'] = pd.to_numeric(period_products['單價'], errors='coerce')
                    
                    # Apply product code filter if needed
                    if product_code_filter:
                        period_products = period_products[
                            period_products['產品代號'].str.contains(product_code_filter, case=False, na=False)
                        ]
                    
                    # Create period-specific aggregation
                    period_agg = {}
                    if '數量' in period_products.columns:
                        period_agg['數量'] = 'sum'
                    if '小計' in period_products.columns:
                        period_agg['小計'] = 'sum'
                    
                    # Only proceed if we have data to aggregate
                    if period_agg and '產品代號' in period_products.columns:
                        try:
                            # Create period summary
                            period_summary = period_products.groupby(['產品代號'], as_index=False).agg(period_agg)
                            
                            # Rename columns to include period
                            if '數量' in period_summary.columns:
                                period_summary.rename(columns={'數量': f'{period} 銷售數量'}, inplace=True)
                            if '小計' in period_summary.columns:
                                period_summary.rename(columns={'小計': f'{period} 銷售小計'}, inplace=True)
                            
                            # Merge with main product summary
                            product_summary = pd.merge(
                                product_summary, 
                                period_summary, 
                                on='產品代號', 
                                how='left'
                            )
                            
                            # Fill NaN values with 0
                            if f'{period} 銷售數量' in product_summary.columns:
                                product_summary[f'{period} 銷售數量'].fillna(0, inplace=True)
                            if f'{period} 銷售小計' in product_summary.columns:
                                product_summary[f'{period} 銷售小計'].fillna(0, inplace=True)
                        except Exception as e:
                            st.warning(f"處理 {period} 期間的銷售數據時發生錯誤: {e}")
    else:
        # Create an empty DataFrame with expected columns if aggregation isn't possible
        product_summary = pd.DataFrame(columns=['產品代號', '產品名稱', '數量', '單位', '單價', '小計', '成本總值', '單價（數量）'])

    # Add inventory column (庫存) if we have BC products data
    if bc_df is not None and '產品代號' in bc_df.columns and '數量' in bc_df.columns:
        # Create a simple mapping of product code to inventory quantity
        inventory_map = {}
        # Ensure 數量 is numeric in BC data
        if bc_df['數量'].dtype == 'object':
            bc_df['數量'] = pd.to_numeric(bc_df['數量'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        inventory_map = dict(zip(bc_df['產品代號'], bc_df['數量']))

        # Map inventory data to product summary
        # Ensure proper type conversion to avoid incompatible dtype warning
        # First convert to float, then to int to handle any non-integer values
        product_summary['庫存'] = product_summary['產品代號'].map(inventory_map).fillna(0).astype(float).astype(int)

        # Prepare a list of all monthly columns
        monthly_columns = []
        if hasattr(st.session_state, 'selected_periods'):
            for period in st.session_state.selected_periods:
                if f'{period} 銷售數量' in product_summary.columns:
                    monthly_columns.append(f'{period} 銷售數量')
                if f'{period} 銷售小計' in product_summary.columns:
                    monthly_columns.append(f'{period} 銷售小計')
        
        # 準備顯示的欄位列表 (including inventory and monthly data)
        display_columns = ['產品代號', '產品名稱', '數量', '庫存', '單位', '單價', '單價（數量）', '小計', '成本總值'] + monthly_columns

        # Display the table with numeric sorting (with inventory)
        # Filter display columns to only include those that exist in the dataframe
        valid_columns = [col for col in display_columns if col in product_summary.columns]
        
        if valid_columns:
            st.dataframe(
                product_summary[valid_columns],
                use_container_width=True,
                column_config={
                    "產品代號": st.column_config.TextColumn("產品代號"),
                    "產品名稱": st.column_config.TextColumn("產品名稱"),
                    "數量": st.column_config.NumberColumn("銷售總數量", format="%.0f"),
                    "庫存": st.column_config.NumberColumn("庫存數量", format="%.0f", help="目前庫存數量 (來自BC產品資料)"),
                    "單位": st.column_config.TextColumn("單位"),
                    "單價": st.column_config.NumberColumn(
                        "單價 (平均)",
                        format="%.2f",
                        help="由所有交易單價加總後取平均"
                    ),
                    "單價（數量）": st.column_config.NumberColumn(
                        "單價 (數量)",
                        format="%.2f",
                        help="由小計總和除以總數量計算"
                    ),
                    "小計": st.column_config.NumberColumn(
                        "小計 (總和) ↓",
                        format="%.2f",
                        help="預設由高到低排序"
                    ),
                    "成本總值": st.column_config.NumberColumn(
                        "成本總值 (總和)",
                        format="%.2f",
                        help="點擊可以按數值大小排序"
                    ),
                    **{f"{period} 銷售數量": st.column_config.NumberColumn(
                        f"{period} 銷售數量",
                        format="%.0f",
                        help=f"{period} 期間的銷售數量"
                      ) for period in st.session_state.get('selected_periods', []) if f"{period} 銷售數量" in product_summary.columns},
                    **{f"{period} 銷售小計": st.column_config.NumberColumn(
                        f"{period} 銷售小計",
                        format="%.2f",
                        help=f"{period} 期間的銷售小計"
                      ) for period in st.session_state.get('selected_periods', []) if f"{period} 銷售小計" in product_summary.columns}
                },
                hide_index=True
            )
        else:
            st.error("無法顯示產品彙總表：產品資料欄位不完整")
    else:
        # 準備顯示的欄位列表 (without inventory)
        display_columns = ['產品代號', '產品名稱', '數量', '單位', '單價', '單價（數量）', '小計', '成本總值']

        # Display the table with numeric sorting (without inventory)
        # Filter display columns to only include those that exist in the dataframe
        valid_columns = [col for col in display_columns if col in product_summary.columns]
        
        if valid_columns:
            st.dataframe(
                product_summary[valid_columns],
                use_container_width=True,
                column_config={
                    "產品代號": st.column_config.TextColumn("產品代號"),
                    "產品名稱": st.column_config.TextColumn("產品名稱"),
                    "數量": st.column_config.NumberColumn("數量", format="%.0f"),
                    "單位": st.column_config.TextColumn("單位"),
                    "單價": st.column_config.NumberColumn(
                        "單價 (平均)",
                        format="%.2f",
                        help="由所有交易單價加總後取平均"
                    ),
                    "單價（數量）": st.column_config.NumberColumn(
                        "單價 (數量)",
                        format="%.2f",
                        help="由小計總和除以總數量計算"
                    ),
                    "小計": st.column_config.NumberColumn(
                        "小計 (總和) ↓",
                        format="%.2f",
                        help="預設由高到低排序"
                    ),
                    "成本總值": st.column_config.NumberColumn(
                        "成本總值 (總和)",
                        format="%.2f",
                        help="點擊可以按數值大小排序"
                    )
                },
                hide_index=True
            )
        else:
            st.error("無法顯示產品彙總表：產品資料欄位不完整")
    
    
    # Only show BC products data if available
    if bc_df is not None:
        st.markdown("---")
        st.header("BC產品資料")
        
        # Filter options for BC products data
        st.subheader("BC產品篩選選項")
        
        # Create 3 columns for filter widgets
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        
        with filter_col1:
            # Filter by category
            if '大類名稱' in bc_df.columns and not bc_df['大類名稱'].isna().all():
                all_categories = sorted(bc_df['大類名稱'].dropna().unique().tolist())
                selected_categories = st.multiselect(
                    "選擇產品大類:",
                    options=["全部"] + all_categories,
                    default=["全部"]
                )
                
                if "全部" not in selected_categories:
                    bc_df = bc_df[bc_df['大類名稱'].isin(selected_categories)]
        
        with filter_col2:
            # Filter by vendor
            if '廠商簡稱' in bc_df.columns and not bc_df['廠商簡稱'].isna().all():
                all_vendors = sorted(bc_df['廠商簡稱'].dropna().unique().tolist())
                selected_vendors = st.multiselect(
                    "選擇供應商:",
                    options=["全部"] + all_vendors,
                    default=["全部"]
                )
                
                if "全部" not in selected_vendors:
                    bc_df = bc_df[bc_df['廠商簡稱'].isin(selected_vendors)]
        
        with filter_col3:
            # Filter by stock availability
            stock_options = ["全部", "有庫存", "庫存不足", "無庫存"]
            selected_stock = st.radio("庫存狀態:", stock_options)
            
            if selected_stock == "有庫存":
                bc_df = bc_df[bc_df['數量'] > 0]
            elif selected_stock == "庫存不足":
                bc_df = bc_df[(bc_df['數量'] > 0) & (bc_df['數量'] < bc_df['安全存量'])]
            elif selected_stock == "無庫存":
                bc_df = bc_df[bc_df['數量'] <= 0]
        
        # Display BC products detail table
        st.subheader("BC產品明細表")
        
        # Prepare monthly columns for BC products table
        monthly_bc_columns = []
        if hasattr(st.session_state, 'selected_periods') and hasattr(st.session_state, 'monthly_sales_dfs'):
            # First, process each month's data to create a mapping of product codes to monthly sales data
            for period in st.session_state.selected_periods:
                if period in st.session_state.monthly_sales_dfs:
                    period_df = st.session_state.monthly_sales_dfs[period]
                    
                    # Process numeric columns
                    period_products = period_df.copy()
                    numeric_cols = ['數量', '小計']
                    for col in numeric_cols:
                        if col in period_products.columns:
                            if period_products[col].dtype == 'object':
                                period_products[col] = period_products[col].astype(str).str.replace(',', '')
                                period_products[col] = pd.to_numeric(period_products[col], errors='coerce')
                    
                    # Create period-specific aggregation
                    if '產品代號' in period_products.columns:
                        try:
                            # Group by product code and aggregate
                            period_agg = {}
                            if '數量' in period_products.columns:
                                period_agg['數量'] = 'sum'
                            if '小計' in period_products.columns:
                                period_agg['小計'] = 'sum'
                            
                            if period_agg:
                                period_summary = period_products.groupby(['產品代號'], as_index=False).agg(period_agg)
                                
                                # Create column names for this period
                                qty_col = f'{period} 銷售數量'
                                rev_col = f'{period} 銷售小計'
                                
                                # Add these columns to the BC dataframe
                                if '數量' in period_summary.columns:
                                    bc_df[qty_col] = bc_df['產品代號'].map(
                                        dict(zip(period_summary['產品代號'], period_summary['數量']))
                                    ).fillna(0)
                                    monthly_bc_columns.append(qty_col)
                                
                                if '小計' in period_summary.columns:
                                    bc_df[rev_col] = bc_df['產品代號'].map(
                                        dict(zip(period_summary['產品代號'], period_summary['小計']))
                                    ).fillna(0)
                                    monthly_bc_columns.append(rev_col)
                        except Exception as e:
                            st.warning(f"處理BC表格的 {period} 期間銷售數據時發生錯誤: {e}")
        
        # Merge sales data with BC product data
        if sales_df is not None and '產品代號' in sales_df.columns:
            # Create sales summary if it doesn't exist yet
            if 'product_summary' not in locals():
                # Ensure numeric columns are properly converted to numeric before aggregation
                df_products = sales_df.copy()
                numeric_cols = ['數量', '小計', '成本總值']
                for col in numeric_cols:
                    if col in df_products.columns:
                        if df_products[col].dtype == 'object':
                            df_products[col] = df_products[col].astype(str).str.replace(',', '')
                            df_products[col] = pd.to_numeric(df_products[col], errors='coerce')
                
                # Separate handling for unit price
                if '單價' in df_products.columns:
                    if df_products['單價'].dtype == 'object':
                        df_products['單價'] = df_products['單價'].astype(str).str.replace(',', '')
                        df_products['單價'] = pd.to_numeric(df_products['單價'], errors='coerce')
                
                # Create aggregation dictionary
                agg_dict = {}
                if '產品名稱' in df_products.columns:
                    agg_dict['產品名稱'] = 'first'  # Take the first product name
                if '數量' in df_products.columns:
                    agg_dict['數量'] = 'sum'        # Sum quantities
                if '單位' in df_products.columns:
                    agg_dict['單位'] = 'first'      # Take the first unit
                if '單價' in df_products.columns:
                    agg_dict['單價'] = 'mean'       # Average price
                if '小計' in df_products.columns:
                    agg_dict['小計'] = 'sum'        # Sum subtotals
                if '成本總值' in df_products.columns:
                    agg_dict['成本總值'] = 'sum'     # Sum cost values
                
                # Create product summary
                if agg_dict and '產品代號' in df_products.columns:
                    product_summary = df_products.groupby(['產品代號'], as_index=False).agg(agg_dict)
                    
                    # Calculate 單價（數量）= 小計 / 數量 safely
                    product_summary['單價（數量）'] = 0.0  # Default value as float
                    if '數量' in product_summary.columns and '小計' in product_summary.columns:
                        mask = product_summary['數量'] > 0
                        if isinstance(mask, pd.Series) and mask.any():
                            result = (product_summary.loc[mask, '小計'] / product_summary.loc[mask, '數量']).astype('float64')
                            product_summary.loc[mask, '單價（數量）'] = result
            
            # Create a copy of BC dataframe to add sales data (if not already done)
            enhanced_bc_df = bc_df.copy()
            
            # Add sales columns if they don't exist
            if 'product_summary' in locals() and not product_summary.empty:
                # Create a mapping of product codes to sales data
                sales_data_map = {}
                for _, row in product_summary.iterrows():
                    product_code = row['產品代號']
                    sales_data = {
                        '銷售數量': row.get('數量', 0),
                        '銷售單價': row.get('單價（數量）', 0),
                        '銷售小計': row.get('小計', 0)
                    }
                    sales_data_map[product_code] = sales_data
                
                # Add sales columns to BC data
                enhanced_bc_df['銷售數量'] = enhanced_bc_df['產品代號'].map(lambda x: sales_data_map.get(x, {}).get('銷售數量', 0))
                enhanced_bc_df['銷售單價'] = enhanced_bc_df['產品代號'].map(lambda x: sales_data_map.get(x, {}).get('銷售單價', 0))
                enhanced_bc_df['銷售小計'] = enhanced_bc_df['產品代號'].map(lambda x: sales_data_map.get(x, {}).get('銷售小計', 0))
            else:
                # If no sales data exists, add empty columns
                enhanced_bc_df['銷售數量'] = 0
                enhanced_bc_df['銷售單價'] = 0
                enhanced_bc_df['銷售小計'] = 0
            
            # Use the enhanced dataframe instead of the original
            bc_df = enhanced_bc_df
        
        # Allow user to select display columns
        all_columns = bc_df.columns.tolist()
        default_columns = ['產品代號', '產品名稱', '數量', '銷售數量', '單位', '成本單價', '銷售單價', '成本總價', '銷售小計'] + monthly_bc_columns + ['安全存量', '廠商簡稱', '大類名稱', '中類名稱']
        selected_columns = st.multiselect(
            "選擇顯示欄位:",
            options=all_columns,
            default=[col for col in default_columns if col in all_columns]
        )
        
        if not selected_columns:
            selected_columns = default_columns
        
        # Sort options with added sales columns
        sort_options = {
            "產品代號": "產品代號",
            "產品名稱": "產品名稱",
            "庫存數量 (高到低)": "數量",
            "庫存數量 (低到高)": "數量_asc",
            "成本單價 (高到低)": "成本單價",
            "成本單價 (低到高)": "成本單價_asc",
            "成本總價 (高到低)": "成本總價",
            "成本總價 (低到高)": "成本總價_asc",
            "銷售數量 (高到低)": "銷售數量",
            "銷售數量 (低到高)": "銷售數量_asc",
            "銷售小計 (高到低)": "銷售小計",
            "銷售小計 (低到高)": "銷售小計_asc"
        }
        
        # Add monthly columns to sort options
        for col in monthly_bc_columns:
            if '銷售數量' in col:
                sort_options[f"{col} (高到低)"] = col
                sort_options[f"{col} (低到高)"] = f"{col}_asc"
            elif '銷售小計' in col:
                sort_options[f"{col} (高到低)"] = col
                sort_options[f"{col} (低到高)"] = f"{col}_asc"
        
        sort_choice = st.selectbox("排序方式:", list(sort_options.keys()), index=0)
        sort_column = sort_options[sort_choice]
        
        # Handle ascending/descending
        if "_asc" in sort_column:
            sort_column = sort_column.replace("_asc", "")
            ascending = True
        else:
            ascending = False
        
        # Sort and display the table with column configuration
        if sort_column in bc_df.columns:
            sorted_df = bc_df.sort_values(by=sort_column, ascending=ascending)
            st.dataframe(
                sorted_df[selected_columns], 
                use_container_width=True,
                column_config={
                    "產品代號": st.column_config.TextColumn("產品代號"),
                    "產品名稱": st.column_config.TextColumn("產品名稱"),
                    "數量": st.column_config.NumberColumn("庫存數量", format="%.0f"),
                    "銷售數量": st.column_config.NumberColumn("銷售總數量", format="%.0f", help="來自銷貨單的銷售數量總和"),
                    "單位": st.column_config.TextColumn("單位"),
                    "成本單價": st.column_config.NumberColumn("成本單價", format="%.2f"),
                    "銷售單價": st.column_config.NumberColumn("銷售單價", format="%.2f", help="銷售小計除以銷售數量"),
                    "成本總價": st.column_config.NumberColumn("成本總價", format="%.2f"),
                    "銷售小計": st.column_config.NumberColumn("銷售總額", format="%.2f", help="來自銷貨單的銷售小計總和"),
                    "安全存量": st.column_config.NumberColumn("安全存量", format="%.0f"),
                    "廠商簡稱": st.column_config.TextColumn("廠商簡稱"),
                    "大類名稱": st.column_config.TextColumn("大類名稱"),
                    "中類名稱": st.column_config.TextColumn("中類名稱"),
                    **{col: st.column_config.NumberColumn(
                        col,
                        format="%.0f" if '數量' in col else "%.2f",
                        help=f"{col.split(' ')[0]} 期間的{'銷售數量' if '數量' in col else '銷售金額'}"
                      ) for col in monthly_bc_columns}
                },
                hide_index=True
            )
        else:
            st.dataframe(
                bc_df[selected_columns], 
                use_container_width=True,
                column_config={
                    "產品代號": st.column_config.TextColumn("產品代號"),
                    "產品名稱": st.column_config.TextColumn("產品名稱"),
                    "數量": st.column_config.NumberColumn("庫存數量", format="%.0f"),
                    "銷售數量": st.column_config.NumberColumn("銷售總數量", format="%.0f", help="來自銷貨單的銷售數量總和"),
                    "單位": st.column_config.TextColumn("單位"),
                    "成本單價": st.column_config.NumberColumn("成本單價", format="%.2f"),
                    "銷售單價": st.column_config.NumberColumn("銷售單價", format="%.2f", help="銷售小計除以銷售數量"),
                    "成本總價": st.column_config.NumberColumn("成本總價", format="%.2f"),
                    "銷售小計": st.column_config.NumberColumn("銷售總額", format="%.2f", help="來自銷貨單的銷售小計總和"),
                    "安全存量": st.column_config.NumberColumn("安全存量", format="%.0f"),
                    "廠商簡稱": st.column_config.TextColumn("廠商簡稱"),
                    "大類名稱": st.column_config.TextColumn("大類名稱"),
                    "中類名稱": st.column_config.TextColumn("中類名稱"),
                    **{col: st.column_config.NumberColumn(
                        col,
                        format="%.0f" if '數量' in col else "%.2f",
                        help=f"{col.split(' ')[0]} 期間的{'銷售數量' if '數量' in col else '銷售金額'}"
                      ) for col in monthly_bc_columns}
                },
                hide_index=True
            )

# Run the module when executed directly
if __name__ == "__main__":
    sales_df, period_display, bc_df, file_date = run_integrated_analysis()
    display_integrated_dashboard(sales_df, period_display, bc_df, file_date)
# 銷貨單毛利分析模組 - Sales Invoice Profit Analysis Module
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import os
from datetime import datetime
import locale
import numpy as np

# Set pandas option to opt-in to future behavior for downcasting
pd.set_option('future.no_silent_downcasting', True)

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
        page_title="ERP Sales Dashboard",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

# Function to load and preprocess data
@st.cache_data(ttl=3600, max_entries=10)  # Cache data for an hour with capacity for 10 different files
def load_data(file_path):
    # Add spinner to indicate data loading
    with st.spinner('正在載入銷貨單資料，請稍候...'):
        # Read the Excel file
        df = pd.read_excel(file_path)
        
        # OPTIMIZED: Convert all numeric columns in fewer operations
        numeric_cols = ['未稅小計', '營業稅', '總計金額', '實收總額', '成本總額', '小計', '成本總值', 
                      '毛利', '毛利率', '產品毛利', '產品毛利率', '精準毛利', '數量', '單價']
        
        # Filter columns that exist and need conversion (only object dtype)
        cols_to_convert = [col for col in numeric_cols 
                         if col in df.columns and df[col].dtype == 'object']
        
        # Process all columns in a batch for better performance
        if cols_to_convert:
            # Create a function to process a single column - only define once
            def convert_numeric_col(series):
                return pd.to_numeric(
                    series.astype(str).replace('', '0').str.replace(',', ''), 
                    errors='coerce'
                )
            
            # Apply the function to all columns that need conversion
            df[cols_to_convert] = df[cols_to_convert].apply(convert_numeric_col)
        
        # Optimize: Convert date columns more efficiently
        if '銷貨日期' in df.columns:
            # Create an improved vectorized function for Taiwanese calendar format conversion
            def batch_convert_tw_dates(date_series):
                # Print debug information about the input
                if st.session_state.get('debug_mode', False):
                    print(f"Converting dates, sample values: {date_series.head().tolist()}")
                    print(f"Date series dtype: {date_series.dtype}")
                
                # Initialize result series with NaT values
                result = pd.Series([pd.NaT] * len(date_series), index=date_series.index)
                
                # Handle empty series
                if len(date_series) == 0:
                    return result
                
                # Convert to string and handle NaN values
                date_strs = date_series.fillna('').astype(str)
                date_strs = date_strs.replace('nan', '')
                
                # Try multiple date formats in order of likelihood
                # 1. Direct datetime parsing for standard formats
                try:
                    # Try flexible date parsing first
                    temp_dates = pd.to_datetime(date_series, errors='coerce')
                    # Only update where we got valid dates
                    valid_mask = ~temp_dates.isna()
                    if valid_mask.any():
                        result[valid_mask] = temp_dates[valid_mask]
                except:
                    # Ignore errors and continue with other methods
                    pass
                
                # 2. Process Taiwan date format (ROC calendar) - format: YYY.MM.DD
                mask_tw = date_strs.str.contains('\.', regex=True) & ~date_strs.str.contains('nan')
                if isinstance(mask_tw, pd.Series) and mask_tw.any():
                    try:
                        tw_dates = date_strs[mask_tw].str.split('.', expand=True)
                        if tw_dates.shape[1] >= 3:  # Ensure we have 3 components
                            # Convert year, month, day to integers
                            years = pd.to_numeric(tw_dates[0], errors='coerce') + 1911  # ROC to CE
                            months = pd.to_numeric(tw_dates[1], errors='coerce')
                            days = pd.to_numeric(tw_dates[2], errors='coerce')
                            
                            # Create datetime objects
                            dates = pd.to_datetime({
                                'year': years,
                                'month': months,
                                'day': days
                            }, errors='coerce')
                            
                            # Only update result where parsing succeeded
                            valid_dates_mask = ~dates.isna()
                            if valid_dates_mask.any():
                                result[mask_tw.index[mask_tw][valid_dates_mask]] = dates[valid_dates_mask]
                    except Exception as e:
                        if st.session_state.get('debug_mode', False):
                            print(f"Error parsing Taiwan dates: {e}")
                
                # 3. Check for dash format (YYYY-MM-DD)
                mask_dash = date_strs.str.contains('-') & result.isna()
                if isinstance(mask_dash, pd.Series) and mask_dash.any():
                    try:
                        dash_dates = pd.to_datetime(date_strs[mask_dash], format='%Y-%m-%d', errors='coerce')
                        valid_mask = ~dash_dates.isna()
                        if valid_mask.any():
                            result[mask_dash.index[mask_dash][valid_mask]] = dash_dates[valid_mask]
                    except Exception as e:
                        if st.session_state.get('debug_mode', False):
                            print(f"Error parsing dash dates: {e}")
                
                # 4. Check for slash format (YYYY/MM/DD)
                mask_slash = date_strs.str.contains('/') & result.isna()
                if isinstance(mask_slash, pd.Series) and mask_slash.any():
                    try:
                        slash_dates = pd.to_datetime(date_strs[mask_slash], format='%Y/%m/%d', errors='coerce')
                        valid_mask = ~slash_dates.isna()
                        if valid_mask.any():
                            result[mask_slash.index[mask_slash][valid_mask]] = slash_dates[valid_mask]
                    except Exception as e:
                        if st.session_state.get('debug_mode', False):
                            print(f"Error parsing slash dates: {e}")
                
                # 5. Try other common formats for remaining NaT values
                mask_remaining = result.isna() & (date_strs != '') & (~date_strs.isna())
                if isinstance(mask_remaining, pd.Series) and mask_remaining.any():
                    remaining_strs = date_strs[mask_remaining]
                    
                    # Try formats like DD/MM/YYYY, MM/DD/YYYY, etc.
                    formats_to_try = ['%d/%m/%Y', '%m/%d/%Y', '%Y%m%d']
                    for fmt in formats_to_try:
                        try:
                            parsed_dates = pd.to_datetime(remaining_strs, format=fmt, errors='coerce')
                            valid_mask = ~parsed_dates.isna()
                            if valid_mask.any():
                                result[mask_remaining.index[mask_remaining][valid_mask]] = parsed_dates[valid_mask]
                        except Exception as e:
                            # Continue to next format
                            pass
                
                # Report conversion stats in debug mode
                if st.session_state.get('debug_mode', False):
                    success_rate = (~result.isna()).mean() * 100
                    print(f"Date conversion success rate: {success_rate:.2f}%")
                    if success_rate < 50:
                        print("Warning: Less than 50% of dates were successfully parsed.")
                        print(f"Sample of unparsed dates: {date_strs[result.isna()].head(5).tolist()}")
                
                return result
            
            # Convert dates using optimized function
            df['銷貨日期_dt'] = batch_convert_tw_dates(df['銷貨日期'])
            
        # Optimize memory usage
        # Identify candidate columns for memory optimization
        memory_usage_before = df.memory_usage(deep=True).sum() / (1024 * 1024)  # MB
        
        # Optimize numeric columns that use more memory than needed
        for col in df.select_dtypes(include=['int64', 'float64']).columns:
            # Convert int64 to smaller types if possible
            if pd.api.types.is_integer_dtype(df[col].dtype):
                c_min = df[col].min()
                c_max = df[col].max()
                
                # If all values are null/NA, skip this column
                if pd.isna(c_min) or pd.isna(c_max):
                    continue
                
                # Check if int8 is sufficient
                if c_min >= -128 and c_max <= 127:
                    df[col] = df[col].astype('int8')
                # Check if int16 is sufficient
                elif c_min >= -32768 and c_max <= 32767:
                    df[col] = df[col].astype('int16')
                # Check if int32 is sufficient
                elif c_min >= -2147483648 and c_max <= 2147483647:
                    df[col] = df[col].astype('int32')
            
            # For float columns with no NaN values, check if we can use more efficient types
            elif pd.api.types.is_float_dtype(df[col].dtype) and not df[col].isna().any():
                # If all values are integers, convert to integer type
                if (df[col] == df[col].astype('int64')).all():
                    c_min = df[col].min()
                    c_max = df[col].max()
                    
                    # Check if int8 is sufficient
                    if c_min >= -128 and c_max <= 127:
                        df[col] = df[col].astype('int8')
                    # Check if int16 is sufficient
                    elif c_min >= -32768 and c_max <= 32767:
                        df[col] = df[col].astype('int16')
                    # Check if int32 is sufficient
                    elif c_min >= -2147483648 and c_max <= 2147483647:
                        df[col] = df[col].astype('int32')
                    else:
                        df[col] = df[col].astype('int64')
                # If need to keep as float, try float32 if precision allows
                elif df[col].min() >= np.finfo('float32').min and df[col].max() <= np.finfo('float32').max:
                    df[col] = df[col].astype('float32')
        
        memory_usage_after = df.memory_usage(deep=True).sum() / (1024 * 1024)  # MB
        memory_reduction = memory_usage_before - memory_usage_after
        
        # Only print in development/debug mode
        if st.session_state.get('debug_mode', False) and memory_reduction > 0.1:  # If saved more than 0.1 MB
            print(f"Memory optimization: {memory_usage_before:.2f} MB → {memory_usage_after:.2f} MB (saved {memory_reduction:.2f} MB)")
            
        # Return the optimized dataframe
        return df

# Function to fill order information by forward filling
def fill_order_info(df):
    """
    Fill order related information using forward fill method
    This ensures each product row has complete order information
    
    Completely rewritten using vectorized operations for maximum performance
    """
    # Create a copy to avoid modifying original data
    df_filled = df.copy()
    
    # Order related columns to fill
    order_columns = ['銷貨單號', '訂單單號', '銷貨日期', '客戶代號', '客戶名稱', '部門代號', '部門名稱', 
                   '發票號碼', '未稅小計', '營業稅', '折讓金額', '稅前折價', '總計金額', '實收總額', 
                   '成本總額', '毛利', '毛利率']
    
    # Only include columns that exist in the dataframe
    available_columns = [col for col in order_columns if col in df_filled.columns]
    
    # Store original dtypes to ensure we preserve them
    original_dtypes = {col: df_filled[col].dtype for col in available_columns}
    
    # Check if we have unique sales order identifiers
    if '銷貨單號' in df_filled.columns:
        # Create a mask for rows where 銷貨單號 is not null
        valid_order_mask = ~df_filled['銷貨單號'].isna()
        
        # Create a group identifier based on valid order numbers
        # This creates a new group whenever a non-null 銷貨單號 appears
        group_id = valid_order_mask.cumsum()
        
        # For each column that needs filling, process separately
        for col in available_columns:
            # For each group, forward fill the values
            # Use groupby + transform to apply the ffill operation to each group
            # This is much faster than looping through rows
            df_filled[col] = df_filled.groupby(group_id)[col].transform(
                lambda grp: grp.ffill()
            )
    else:
        # If no sales order column, simply forward fill each column separately
        for col in available_columns:
            df_filled[col] = df_filled[col].ffill()
    
    # Preserve original data types with vectorized conversion
    for col in available_columns:
        try:
            # Try to convert back to original dtype in one operation
            df_filled[col] = df_filled[col].astype(original_dtypes[col])
        except:
            # If conversion fails, apply appropriate vectorized conversion
            if pd.api.types.is_numeric_dtype(original_dtypes[col]):
                df_filled[col] = pd.to_numeric(df_filled[col], errors='coerce')
            elif pd.api.types.is_datetime64_dtype(original_dtypes[col]):
                df_filled[col] = pd.to_datetime(df_filled[col], errors='coerce')
    
    return df_filled

# Function to extract month and year from filename
def extract_date_from_filename(filename):
    # Example format: 銷貨單毛利分析表_20250101_20250131.xlsx
    try:
        parts = filename.split('_')
        if len(parts) >= 3:
            start_date = parts[1]
            year = start_date[:4]
            month = start_date[4:6]
            return f"{year}-{month}"
    except:
        pass
    return filename

# Main function for the sales analysis module
def run_sales_analysis():
    # Initialize a session state for tracking processing status and performance metrics
    if 'processing_sales' not in st.session_state:
        st.session_state.processing_sales = False
    if 'sales_last_loaded' not in st.session_state:
        st.session_state.sales_last_loaded = None
    if 'performance_metrics' not in st.session_state:
        st.session_state.performance_metrics = {
            'loading_time': {},  # Track loading times by file
            'processing_time': {},  # Track processing times by operation
            'cache_hits': 0,    # Count of cache hits
            'total_operations': 0  # Total operations performed
        }
    if 'analysis_type' not in st.session_state:
        st.session_state.analysis_type = "單月報表"  # Default analysis type
    
    # Get list of Excel files in the sales data directory
    sales_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales data")
    
    # Get files sorted by modification time (newest first)
    def get_sorted_files(directory):
        if not os.path.exists(directory):
            return []
        
        # Get files with their modification times
        files_with_time = [(f, os.path.getmtime(os.path.join(directory, f))) 
                          for f in os.listdir(directory) if f.endswith('.xlsx')]
        
        # Sort by modification time, newest first
        files_with_time.sort(key=lambda x: x[1], reverse=True)
        
        # Return just the filenames
        return [f[0] for f in files_with_time]
    
    # Get sorted files for better user experience
    excel_files = get_sorted_files(sales_data_dir)
    
    if not excel_files:
        st.error("找不到銷貨單資料，請檢查 'sales data' 目錄")
        return None, None

    # Create file selection with nice labels
    file_options = {extract_date_from_filename(file): file for file in excel_files}

    # Create a horizontal file selector at the top of the page
    title_col, refresh_col = st.columns([5, 1])
    with title_col:
        st.title("銷貨單毛利分析表 Dashboard")
    with refresh_col:
        if st.button("🔄 重新整理", key="refresh_sales", help="清除快取並重新載入資料"):
            # Clear cache to force reload
            load_data.clear()
            st.rerun()

    # Add a radio button to choose between single month or multiple months
    # Use numeric value to avoid string comparison issues
    analysis_options = ["單月報表", "多月合併報表"]
    
    # Default to first option (single month)
    default_idx = 0
    if 'analysis_type_idx' in st.session_state:
        if st.session_state.analysis_type_idx < len(analysis_options):
            default_idx = st.session_state.analysis_type_idx
    
    # Create the radio button with numeric index
    selected_idx = st.radio(
        "選擇分析方式",
        options=range(len(analysis_options)),
        format_func=lambda i: analysis_options[i],
        horizontal=True,
        index=default_idx
    )
    
    # Get the string value based on index
    analysis_type = analysis_options[selected_idx]
    
    # Store both the index and value in session state
    st.session_state.analysis_type_idx = selected_idx
    st.session_state.analysis_type = analysis_type
    
    # Debug print
    print(f"Selected analysis type: {analysis_type} (index {selected_idx})")

    # Show processing indicator based on session state
    if st.session_state.processing_sales:
        st.info("處理中，請稍候...")
        progress_bar = st.progress(0)
    else:
        progress_bar = None
    
    # Track timing for optimization feedback
    start_time = datetime.now()

    if analysis_type == "單月報表":
        selected_period = st.selectbox(
            "選擇報表期間",
            options=list(file_options.keys())
        )

        selected_file = file_options.get(selected_period)
        file_path = os.path.join(sales_data_dir, selected_file)

        # Set processing flag
        st.session_state.processing_sales = True
        
        # Load data for single month
        df = load_data(file_path)
        period_display = selected_period
        
        # Update last loaded time
        st.session_state.sales_last_loaded = {
            'file': selected_file,
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    else:  # Multiple months
        selected_periods = st.multiselect(
            "選擇多個報表期間 (按住Ctrl或⌘鍵可多選)",
            options=list(file_options.keys()),
            default=[list(file_options.keys())[0]]  # Default to first month
        )

        # Check if any periods are selected
        if not selected_periods:
            st.warning("請至少選擇一個報表期間")
            st.stop()

        # Set processing flag
        st.session_state.processing_sales = True
        
        # Prepare file paths for loading with period information
        file_paths = []
        period_info = {}  # Map file paths to period labels
        
        for period in selected_periods:
            file = file_options.get(period)
            file_path = os.path.join(sales_data_dir, file)
            file_paths.append(file_path)
            # Store period info for each file path
            period_info[file_path] = period
        
        total_files = len(file_paths)
        
        # IMPROVED: Use concurrent processing for parallel file loading
        import concurrent.futures
        from functools import partial
        
        # Initialize progress counter
        if progress_bar:
            progress_counter = 0
            
            # Create a callback function to update progress after each file
            def update_progress(future, total):
                nonlocal progress_counter
                progress_counter += 1
                progress_bar.progress(progress_counter/total)
        
        # Load files in parallel with ThreadPoolExecutor and add month info
        dfs = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, total_files)) as executor:
            # Submit all file loading tasks 
            future_to_file = {executor.submit(load_data, path): path for path in file_paths}
            
            # Process results as they complete
            if progress_bar:
                # Add a progress callback when each future completes
                for future in concurrent.futures.as_completed(future_to_file):
                    file_path = future_to_file[future]
                    # Get result from future
                    df_result = future.result()
                    
                    # Add period information column to each dataframe
                    month_info = period_info.get(file_path, '')
                    df_result['month_info'] = month_info
                    
                    dfs.append(df_result)
                    # Update progress
                    update_progress(future, total_files)
            else:
                # Without progress tracking, just get the results
                for future in concurrent.futures.as_completed(future_to_file):
                    file_path = future_to_file[future]
                    df_result = future.result()
                    
                    # Add period information column to each dataframe
                    month_info = period_info.get(file_path, '')
                    df_result['month_info'] = month_info
                    
                    dfs.append(df_result)
        
        # Combine all dataframes with optimized concat
        df = pd.concat(dfs, ignore_index=True, sort=False)
        
        # Explicitly clean up to free memory
        del dfs
        
        # Display combined periods
        period_display = f"合併報表 ({', '.join(selected_periods)})"
        
        # Update last loaded time
        st.session_state.sales_last_loaded = {
            'files': [file_options.get(period) for period in selected_periods],
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # Reset processing flag
    st.session_state.processing_sales = False
    
    # Complete progress
    if progress_bar:
        progress_bar.progress(1.0)
    
    # IMPROVED: Enhanced performance metrics tracking and display
    processing_time = (datetime.now() - start_time).total_seconds()
    
    # Record the processing time in session state
    operation_name = "single_file_load" if analysis_type == "單月報表" else f"multi_file_load_{len(selected_periods)}"
    st.session_state.performance_metrics['processing_time'][operation_name] = processing_time
    st.session_state.performance_metrics['total_operations'] += 1
    
    # Display processing time with more context
    if processing_time > 1:  # Show all timing info
        st.info(f"資料處理完成 (耗時: {processing_time:.2f} 秒)")
        
        # Add expandable section with detailed performance metrics
        with st.expander("🚀 性能指標與優化資訊", expanded=False):
            st.markdown("### 性能優化指標")
            
            # Show current operation timing
            st.markdown(f"**當前操作時間:** {processing_time:.2f} 秒")
            
            # Display cache status
            is_cached = hasattr(load_data, 'get_cache_info') and load_data.get_cache_info().hits > 0
            cache_status = "✅ 使用快取" if is_cached else "❌ 未使用快取 (首次載入)"
            st.markdown(f"**快取狀態:** {cache_status}")
            
            # Display optimization tips
            st.markdown("### 優化提示")
            
            if analysis_type == "多月合併報表" and len(selected_periods) > 2:
                st.markdown("- ✅ 多檔案並行處理：已啟用")
                st.markdown(f"- ℹ️ 並行處理了 {len(selected_periods)} 個檔案")
            
            if processing_time > 5:
                st.markdown("**⚠️ 優化建議:**")
                st.markdown("- 考慮減少選擇的時間範圍以提高處理速度")
                st.markdown("- 避免載入不必要的資料")
            else:
                st.markdown("**✅ 效能良好:**")
                st.markdown("- 資料處理速度在預期範圍內")
                
            # Show technical details for developers
            st.markdown("### 技術細節")
            st.markdown("- 使用了向量化操作進行資料轉換")
            st.markdown("- 並行處理用於多檔案載入")
            st.markdown("- 使用聚合快取減少重複計算")
            st.markdown("- 動態記憶體最佳化以減少資源使用")

    # Show selected period
    st.subheader(f"期間: {period_display}")
    
    # If we have last loaded info, show it
    if st.session_state.sales_last_loaded:
        with st.expander("資料載入詳情", expanded=False):
            st.info(f"最後載入時間: {st.session_state.sales_last_loaded['time']}")
            if 'file' in st.session_state.sales_last_loaded:
                st.text(f"檔案: {st.session_state.sales_last_loaded['file']}")
            elif 'files' in st.session_state.sales_last_loaded:
                st.text(f"檔案: {', '.join(st.session_state.sales_last_loaded['files'])}")

    return df, period_display, analysis_type

# Cache key generator to handle dataframe inputs
def _get_df_hash(df):
    return pd.util.hash_pandas_object(df).sum()

# Add caching for expensive aggregation operations
@st.cache_data(ttl=1800, show_spinner=False)  # Cache for 30 minutes
def aggregate_sales_metrics(df):
    """Perform expensive aggregation operations on sales data and cache the results"""
    metrics = {
        # Summary metrics
        'total_sales': df['總計金額'].sum(),
        'total_profit': df['毛利'].sum(),
        'total_orders': df['銷貨單號'].nunique(),
        
        # Daily sales (if date exists)
        'has_date': '銷貨日期_dt' in df.columns,
    }
    
    # Daily sales trend
    if metrics['has_date']:
        # Filter out NaT values
        valid_dates = df.dropna(subset=['銷貨日期_dt'])
        metrics['has_valid_dates'] = not valid_dates.empty
        
        if metrics['has_valid_dates']:
            # Group by date and sum the sales
            metrics['daily_sales'] = valid_dates.groupby(valid_dates['銷貨日期_dt'].dt.date)['總計金額'].sum().reset_index()
            metrics['daily_sales'].columns = ['Date', 'Sales']
    
    # Customer analysis
    metrics['customer_sales'] = df.groupby('客戶名稱')['總計金額'].sum().reset_index()
    metrics['top_customers'] = metrics['customer_sales'].sort_values('總計金額', ascending=False).head(10)
    
    # Product analysis
    metrics['product_sales'] = df.groupby('產品名稱')['總計金額'].sum().reset_index()
    metrics['top_products'] = metrics['product_sales'].sort_values('總計金額', ascending=False).head(10)
    
    # Products by profit margin
    product_margin = df.groupby('產品名稱').agg({
        '總計金額': 'sum',
        '毛利': 'sum'
    }).reset_index()
    
    # Calculate profit margin percentage
    product_margin['毛利率'] = product_margin.apply(
        lambda x: (x['毛利'] / x['總計金額'] * 100) if x['總計金額'] > 0 else 0,
        axis=1
    )
    
    # Filter out rows with zero or negative total sales and get top 10
    metrics['top_margin_products'] = product_margin[product_margin['總計金額'] > 0].sort_values('毛利率', ascending=False).head(10)
    
    return metrics

# Function to display sales analysis dashboard
def display_sales_dashboard(df, period_display):
    # OPTIMIZED: Use cached aggregation functions for expensive operations
    # Get all metrics at once from the cache
    with st.spinner("計算摘要指標中..."):
        metrics = aggregate_sales_metrics(df)
    
    # Summary metrics in a row
    col1, col2, col3, col4 = st.columns(4)

    # Use pre-calculated metrics from cache
    total_sales = metrics['total_sales']
    total_profit = metrics['total_profit'] 
    total_orders = metrics['total_orders']
    
    # Display metrics
    col1.metric("總銷售額", f"{total_sales:,.0f} NTD")
    col2.metric("總毛利", f"{total_profit:,.0f} NTD")
    
    # Calculate average profit margin
    avg_profit_margin = (total_profit / total_sales * 100) if total_sales and total_sales > 0 else 0
    col3.metric("平均毛利率", f"{avg_profit_margin:.2f}%")
    col4.metric("訂單數量", f"{total_orders}")

    # Create two columns for charts
    chart1, chart2 = st.columns(2)

    with chart1:
        st.subheader("每日銷售趨勢")
        
        # Use cached date data
        if metrics['has_date']:
            # Attempt to calculate daily sales directly if needed
            if not metrics.get('has_valid_dates', False) and '銷貨日期' in df.columns:
                try:
                    # Try to parse dates directly
                    if '銷貨日期_dt' not in df.columns:
                        # Add a datetime column if it doesn't exist
                        df['parsed_date'] = pd.to_datetime(df['銷貨日期'], errors='coerce')
                        valid_dates = df.dropna(subset=['parsed_date'])
                    else:
                        valid_dates = df.dropna(subset=['銷貨日期_dt'])
                        valid_dates['parsed_date'] = valid_dates['銷貨日期_dt']
                    
                    if not valid_dates.empty:
                        # Group by date and sum the sales
                        daily_sales = valid_dates.groupby(valid_dates['parsed_date'].dt.date)['總計金額'].sum().reset_index()
                        daily_sales.columns = ['Date', 'Sales']
                        metrics['daily_sales'] = daily_sales
                        metrics['has_valid_dates'] = True
                except Exception as e:
                    if st.session_state.get('debug_mode', False):
                        st.error(f"Error calculating daily sales: {e}")
            
            # Now check if we have valid dates
            if metrics.get('has_valid_dates', False):
                # Use pre-calculated daily sales from cache
                daily_sales = metrics['daily_sales']
                
                if not daily_sales.empty:
                    # Plot with Plotly
                    fig = px.line(daily_sales, x='Date', y='Sales',
                                title='Daily Sales Trend',
                                labels={'Sales': 'Sales (NTD)', 'Date': 'Date'})
                    fig.update_layout(
                        xaxis_title="日期",
                        yaxis_title="銷售額 (NTD)"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Also display a rolling 7-day average if we have enough data
                    if len(daily_sales) > 7:
                        # Sort by date
                        daily_sales = daily_sales.sort_values('Date')
                        # Add 7-day rolling average
                        daily_sales['7-Day Average'] = daily_sales['Sales'].rolling(window=7).mean()
                        
                        fig_rolling = px.line(daily_sales, x='Date', y=['Sales', '7-Day Average'],
                                    title='Daily Sales with 7-Day Rolling Average',
                                    labels={'value': 'Sales (NTD)', 'Date': 'Date', 'variable': 'Metric'})
                        fig_rolling.update_layout(
                            xaxis_title="日期",
                            yaxis_title="銷售額 (NTD)",
                            legend_title="指標"
                        )
                        st.plotly_chart(fig_rolling, use_container_width=True)
                else:
                    st.write("無法顯示日銷售趨勢：日銷售數據為空")
            else:
                st.write("無法顯示日銷售趨勢：沒有有效的日期數據")
                
                # Add a help message with some example date formats
                with st.expander("日期格式幫助"):
                    st.markdown('''
                    ### 支援的日期格式例子：
                    - 國曆格式: 112.01.15 (民國112年1月15日)
                    - 西元格式: 2025-01-15 (西元YYYY-MM-DD)
                    - 西元格式: 2025/01/15 (西元YYYY/MM/DD)
                    
                    若數據中的日期欄位使用其他格式，請聯絡系統管理員以獲得支援。
                    ''')
        else:
            st.write("無法顯示日銷售趨勢：日期欄位無法解析")

    with chart2:
        st.subheader("top 10客戶")
        # Use pre-calculated customer data from cache
        customer_sales = metrics['top_customers']

        # Plot with Plotly
        fig = px.bar(customer_sales, x='客戶名稱', y='總計金額',
                     title='Top 10 Customers by Sales',
                     labels={'總計金額': 'Sales (NTD)', '客戶名稱': 'Customer'})
        st.plotly_chart(fig, use_container_width=True)

    # Product analysis
    st.subheader("產品分析")
    col1, col2 = st.columns(2)

    with col1:
        # Use pre-calculated product data from cache
        product_sales = metrics['top_products']

        fig = px.bar(product_sales, x='總計金額', y='產品名稱', orientation='h',
                     title='Top 10 Products by Sales',
                     labels={'總計金額': 'Sales (NTD)', '產品名稱': 'Product'})
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Use pre-calculated profit margin data from cache
        product_margin = metrics['top_margin_products']

        fig = px.bar(product_margin, x='毛利率', y='產品名稱', orientation='h',
                     title='Top 10 Products by Profit Margin (%)',
                     labels={'毛利率': 'Profit Margin (%)', '產品名稱': 'Product'})
        st.plotly_chart(fig, use_container_width=True)

    # Raw data section (expandable)
    with st.expander("查看原始數據"):
        st.dataframe(df)

    # Product summary table
    # Add chart showing daily sales by product category if available
    if 'daily_sales' in metrics and len(metrics['daily_sales']) > 0:
        st.subheader("每日銷售細分分析")
        # Check if we can create a product category grouping
        if '大類名稱' in df.columns and not df['大類名稱'].isna().all():
            try:
                # Create a daily sales by category dataframe
                daily_by_category = df.dropna(subset=['銷貨日期_dt', '大類名稱']).groupby(
                    [df['銷貨日期_dt'].dt.date, '大類名稱']
                )['總計金額'].sum().reset_index()
                daily_by_category.columns = ['Date', 'Category', 'Sales']
                
                # Plot with Plotly
                fig = px.line(daily_by_category, x='Date', y='Sales', color='Category',
                          title='Daily Sales by Product Category',
                          labels={'Sales': 'Sales (NTD)', 'Date': 'Date'})
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                if st.session_state.get('debug_mode', False):
                    st.error(f"Error creating category chart: {e}")
    
    st.subheader("產品彙總表")

    # Load BC products data for inventory if available
    try:
        bc_products_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bc  products")
        bc_excel_files = [f for f in os.listdir(bc_products_dir) if f.endswith('.xlsx')]

        # Default to use the latest BC products file
        if bc_excel_files:
            latest_bc_file = bc_excel_files[-1]  # Assuming sorted by name
            bc_file_path = os.path.join(bc_products_dir, latest_bc_file)

            # Check if bc_products module is available for loading data
            try:
                import bc_products
                bc_df = bc_products.load_data(bc_file_path)
                has_inventory_data = True

                # Create a simple mapping of product code to inventory quantity
                inventory_map = {}
                if not bc_df.empty and '產品代號' in bc_df.columns and '數量' in bc_df.columns:
                    inventory_map = dict(zip(bc_df['產品代號'], bc_df['數量']))
            except:
                # Fallback to basic Excel loading if module import fails
                try:
                    bc_df = pd.read_excel(bc_file_path)
                    has_inventory_data = True

                    # Create a simple mapping of product code to inventory quantity
                    inventory_map = {}
                    if not bc_df.empty and '產品代號' in bc_df.columns and '數量' in bc_df.columns:
                        # Ensure 數量 is numeric
                        bc_df['數量'] = pd.to_numeric(bc_df['數量'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                        inventory_map = dict(zip(bc_df['產品代號'], bc_df['數量']))
                except:
                    has_inventory_data = False
                    inventory_map = {}
        else:
            has_inventory_data = False
            inventory_map = {}
    except:
        has_inventory_data = False
        inventory_map = {}

    # Add product code filter
    product_code_filter = st.text_input("輸入產品代號進行篩選 (留空顯示全部):", "")

    # Make a copy of the dataframe to clean numeric columns first
    df_products = df.copy()

    # Fill in order information for better filtering
    df_filled = fill_order_info(df)

    # Create a filtered version of the raw data if product code is provided
    if product_code_filter:
        # 使用填充後的DataFrame進行篩選，確保顯示完整訂單資訊
        df_filtered_raw = df_filled[df_filled['產品代號'].str.contains(product_code_filter, case=False, na=False)]

        if df_filtered_raw.empty:
            st.warning(f"沒有找到包含 '{product_code_filter}' 的產品代號")
        else:
            st.success(f"找到 {len(df_filtered_raw)} 筆包含 '{product_code_filter}' 的交易記錄")

            # 添加說明
            st.info("注意: 同一訂單中的所有產品行已自動填充訂單資訊，以確保顯示完整資料。")

            # Show the filtered raw data with filled order information
            with st.expander("查看篩選後的原始交易記錄 (已填充訂單資訊)", expanded=True):
                st.dataframe(df_filtered_raw, use_container_width=True)
    else:
        df_filtered_raw = df.copy()

    # OPTIMIZED: Process numeric columns with batch operations
    # Define all numeric columns that need preprocessing
    numeric_cols = ['數量', '小計', '成本總值', '單價', '未稅小計', '營業稅', '總計金額', '實收總額', '成本總額', '毛利', '毛利率', '產品毛利', '產品毛利率', '精準毛利']
    
    # Create a mask of columns that exist in dataframe and are object type
    columns_to_process = [col for col in numeric_cols if col in df_products.columns and df_products[col].dtype == 'object']
    
    if columns_to_process:
        # Process all numeric columns in one vectorized operation
        for col in columns_to_process:
            # 1. Convert to string to handle mixed types
            # 2. Replace empty strings with '0'
            # 3. Remove commas in a single operation
            # 4. Convert to numeric all at once
            df_products[col] = pd.to_numeric(
                df_products[col].astype(str).replace('', '0').str.replace(',', ''), 
                errors='coerce'
            )

    # Apply filter to products data if needed
    if product_code_filter:
        df_products_filtered = df_products[df_products['產品代號'].str.contains(product_code_filter, case=False, na=False)]
    else:
        df_products_filtered = df_products.copy()

    # OPTIMIZED: Cache product summary data for better performance
    @st.cache_data(ttl=1800, show_spinner=False)
    def get_product_summary(df, product_filter=None, analysis_type="單月報表"):
        """
        Generate product summary with optimized groupby operations.
        Uses pre-filtering and efficient calculation methods.
        For multi-month analysis, also calculates metrics by month.
        """
        try:
            # Create a working copy
            df_work = df.copy()
            
            # Apply filter if provided
            if product_filter:
                df_work = df_work[df_work['產品代號'].str.contains(product_filter, case=False, na=False)]
                
            # Only keep necessary columns for aggregation
            agg_cols = ['產品代號', '產品名稱', '數量', '單位', '單價', '小計', '成本總值']
            
            # Add month_info for multi-month analysis
            is_multi_month = False
            if analysis_type == "多月合併報表" and 'month_info' in df_work.columns:
                is_multi_month = True
                agg_cols.append('month_info')
            
            # Filter for columns that actually exist in the dataframe
            required_cols = [col for col in agg_cols if col in df_work.columns]
            
            # Make sure we have at least the product code column
            if '產品代號' not in required_cols:
                # If we don't have the minimum required columns, return an empty dataframe
                return pd.DataFrame(columns=['產品代號', '產品名稱', '數量', '單位', '單價', '單價（數量）', '小計', '成本總值'])
            
            # Select only the columns we need
            df_work = df_work[required_cols]
            
            # Create a dictionary of aggregation functions only for columns that exist
            agg_dict = {}
            if '產品名稱' in required_cols:
                agg_dict['產品名稱'] = 'first'  # Take the first product name
            
            if '數量' in required_cols:
                agg_dict['數量'] = 'sum'        # Sum quantities
            
            if '單位' in required_cols:
                agg_dict['單位'] = 'first'      # Take the first unit
            
            if '小計' in required_cols:
                agg_dict['小計'] = 'sum'        # Sum subtotals
            
            if '成本總值' in required_cols:
                agg_dict['成本總值'] = 'sum'      # Sum cost values
            
            # Add 單價 only if it exists
            if '單價' in required_cols:
                agg_dict['單價'] = 'mean'
            
            # Do the aggregation with optimized groupby
            # - Create grouped object once
            # - Apply all aggregations at once
            product_summary = df_work.groupby(['產品代號'], as_index=False).agg(agg_dict)
            
            # Sort by 小計 in descending order (highest to lowest) if it exists
            if '小計' in product_summary.columns:
                product_summary = product_summary.sort_values(by='小計', ascending=False)
            
            # Calculate 單價（數量）= 小計 / 數量 using vectorized operations
            # This is much faster than apply + lambda
            # Use float type for the calculation results
            product_summary['單價（數量）'] = 0.0  # Default value as float
            if '數量' in product_summary.columns and '小計' in product_summary.columns:
                mask = product_summary['數量'] > 0
                if isinstance(mask, pd.Series) and mask.any():
                    # Calculate the result and ensure it's stored as float64
                    result = (
                        product_summary.loc[mask, '小計'] / product_summary.loc[mask, '數量']
                    ).astype('float64')  # Explicitly convert to float64
                    # Assign the result to the column
                    product_summary.loc[mask, '單價（數量）'] = result
            
            # For multi-month analysis, calculate monthly metrics
            if is_multi_month and 'month_info' in df_work.columns:
                # Get unique months
                months = df_work['month_info'].unique()
                
                # Create separate monthly aggregations
                for month in months:
                    # Filter data for this month
                    month_df = df_work[df_work['month_info'] == month]
                    
                    # Skip if empty
                    if month_df.empty:
                        continue
                    
                    # Make sure required columns exist
                    if '數量' not in month_df.columns or '小計' not in month_df.columns:
                        continue
                    
                    # Aggregate by product for this month
                    month_agg = month_df.groupby(['產品代號']).agg({
                        '數量': 'sum',
                        '小計': 'sum'
                    }).reset_index()
                    
                    # Rename columns to include month info
                    month_agg.rename(columns={
                        '數量': f'{month} 數量',
                        '小計': f'{month} 小計'
                    }, inplace=True)
                    
                    # Merge with main product summary on 產品代號
                    product_summary = product_summary.merge(
                        month_agg,
                        on='產品代號',
                        how='left'
                    )
                    
                    # Fill any NaN values with 0
                    product_summary[f'{month} 數量'] = product_summary[f'{month} 數量'].fillna(0)
                    product_summary[f'{month} 小計'] = product_summary[f'{month} 小計'].fillna(0)
            
            return product_summary
        except Exception as e:
            # If anything goes wrong, return an empty DataFrame with expected columns
            # to avoid errors when displaying the table
            return pd.DataFrame(columns=['產品代號', '產品名稱', '數量', '單位', '單價', '單價（數量）', '小計', '成本總值'])
    
    # Get optimized product summary
    # Check if we have the index value (more reliable than string)
    is_multi_month = False
    if 'analysis_type_idx' in st.session_state:
        # Index 1 corresponds to multi-month mode
        is_multi_month = (st.session_state.analysis_type_idx == 1)
    
    # Or fall back to string if needed
    elif 'analysis_type' in st.session_state:
        is_multi_month = (st.session_state.analysis_type == "多月合併報表")
    
    # Get product summary with analysis_type parameter
    # We've improved the function to handle errors internally
    # Use a string literal for analysis_type based on our calculated is_multi_month value
    product_summary = get_product_summary(
        df_products_filtered, 
        product_filter=product_code_filter if product_code_filter else None,
        analysis_type="多月合併報表" if is_multi_month else "單月報表"
    )

    # Add inventory column (庫存) if we have BC products data
    if has_inventory_data:
        # Map inventory data to product summary
        # Ensure proper type conversion to avoid incompatible dtype warning
        # First convert to float, then to int to handle any non-integer values
        product_summary['庫存'] = product_summary['產品代號'].map(inventory_map).fillna(0).astype(float).astype(int)

    # Prepare the basic columns (with or without inventory)
    if has_inventory_data:
        base_columns = ['產品代號', '產品名稱', '數量', '庫存', '單位', '單價', '單價（數量）', '小計', '成本總值']
    else:
        base_columns = ['產品代號', '產品名稱', '數量', '單位', '單價', '單價（數量）', '小計', '成本總值']
    
    # Prepare the display columns - include month columns if in multi-month mode
    # Use the index approach which is more reliable
    is_multi_month_mode = False
    if 'analysis_type_idx' in st.session_state:
        is_multi_month_mode = (st.session_state.analysis_type_idx == 1)
    elif 'analysis_type' in st.session_state:
        is_multi_month_mode = (st.session_state.analysis_type == "多月合併報表")
    
    # Only process month columns if in multi-month mode
    if is_multi_month_mode:
        # Find all month columns
        month_cols = []
        for col in product_summary.columns:
            if isinstance(col, str) and (' 數量' in col or ' 小計' in col):
                month_cols.append(col)
        
        # Sort month columns by month label to maintain chronological order
        month_cols.sort()
        
        if month_cols:  # Only modify if we found month columns
            # Add month columns after the base columns but before 小計 and 成本總值
            # Get the position of 小計 in the base_columns
            subtotal_pos = base_columns.index('小計')
            
            # Insert month columns before 小計
            display_columns = base_columns[:subtotal_pos] + month_cols + base_columns[subtotal_pos:]
        else:
            # If no month columns found, use base columns
            display_columns = base_columns
    else:
        # Just use the base columns for single month view
        display_columns = base_columns

    # Create the column configuration
    column_config = {
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
    }
    
    # Add inventory column to config if available
    if has_inventory_data:
        column_config["庫存"] = st.column_config.NumberColumn(
            "庫存", 
            format="%.0f", 
            help="目前庫存數量 (來自最新BC產品資料)"
        )
    
    # Add configurations for month columns if in multi-month mode
    month_cols = []  # Always initialize month_cols
    
    # Use the index approach which is more reliable
    is_multi_month_mode = False
    if 'analysis_type_idx' in st.session_state:
        is_multi_month_mode = (st.session_state.analysis_type_idx == 1)
    elif 'analysis_type' in st.session_state:
        is_multi_month_mode = (st.session_state.analysis_type == "多月合併報表")
    
    # Only attempt to find month columns if we're in multi-month mode
    if is_multi_month_mode:
        # Find month-specific columns safely
        for col in product_summary.columns:
            try:
                # Extra careful string check
                col_str = str(col)
                if ' 數量' in col_str or ' 小計' in col_str:
                    month_cols.append(col)
            except:
                # Skip any problematic columns
                continue
        
        # Sort month columns if we found any
        if len(month_cols) > 0:
            month_cols.sort()
    
    # Only process month columns if we have any
    if len(month_cols) > 0:
        for col in month_cols:
            if ' 數量' in col:
                month_label = col.replace(' 數量', '')
                column_config[col] = st.column_config.NumberColumn(
                    f"{month_label} 數量",
                    format="%.0f",
                    help=f"{month_label}期間的銷售數量"
                )
            elif ' 小計' in col:
                month_label = col.replace(' 小計', '')
                column_config[col] = st.column_config.NumberColumn(
                    f"{month_label} 小計",
                    format="%.2f",
                    help=f"{month_label}期間的銷售金額"
                )

    # Filter display columns to only include those that exist in the product_summary DataFrame
    valid_columns = [col for col in display_columns if col in product_summary.columns]
    
    # If we have valid columns, display the dataframe; otherwise show an error
    if valid_columns:
        st.dataframe(
            product_summary[valid_columns],
            use_container_width=True,
            column_config=column_config,
            hide_index=True
        )
    else:
        st.error("無法顯示產品彙總表：缺少必要的欄位")

# Execute if this file is run directly
if __name__ == "__main__":
    df, period_display, analysis_type = run_sales_analysis()
    display_sales_dashboard(df, period_display)
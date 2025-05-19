# BC產品全部資料模組 - BC Products Data Module
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import numpy as np
import locale
from datetime import datetime

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
        page_title="BC產品全部資料",
        page_icon="📦",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

# Function to load and preprocess data
@st.cache_data(show_spinner=False, ttl=60)  # Set a TTL of 60 seconds to refresh automatically
def load_data(file_path):
    try:
        df = pd.read_excel(file_path)

        # 添加調試資訊 (only in development mode)
        if st.session_state.get('debug_mode', False):
            print(f"BC檔案原始列名: {df.columns.tolist()}")
            print(f"數量欄位原始資料類型: {df['數量'].dtype}")

            # 先檢查非零庫存數量
            try:
                original_non_zero = (pd.to_numeric(df['數量'], errors='coerce') > 0).sum()
                print(f"原始檔案中非零庫存產品數量: {original_non_zero}")
            except:
                print("無法計算原始非零庫存產品數量")

        # Process numeric columns with commas
        numeric_columns = ['數量', '成本單價', '成本總價', '安全存量', '銷售單價1', '銷售單價2', '建議售價']
        for col in numeric_columns:
            if col in df.columns:
                # Always convert to string first, then to numeric to handle various formats
                df[col] = df[col].astype(str).str.replace(',', '')
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

                # For the 數量 column, print some diagnostic info if in debug mode
                if col == '數量' and st.session_state.get('debug_mode', False):
                    print(f"數量欄位轉換後資料類型: {df[col].dtype}")
                    print(f"數量統計資訊: 最小值={df[col].min()}, 最大值={df[col].max()}, 平均值={df[col].mean()}")
                    non_zero_values = df[df[col] > 0][col].head(10).tolist()
                    print(f"前10個非零數量值: {non_zero_values}")

                # Ensure 數量 is always an integer
                df[col] = df[col].astype(int)

        # Process percent columns
        if '毛利率' in df.columns:
            # Filter out non-numeric values like '***.**'
            df['毛利率'] = df['毛利率'].astype(str).replace('\\*\\*\\*\\.\\*\\*', np.nan, regex=True)
            df['毛利率'] = pd.to_numeric(df['毛利率'], errors='coerce')

        # Print debug information if in debug mode
        if '數量' in df.columns and st.session_state.get('debug_mode', False):
            non_zero_count = (df['數量'] > 0).sum()
            print(f"載入了 {len(df)} 項產品，其中 {non_zero_count} 項有庫存")

            # 顯示前10個非零庫存產品
            if non_zero_count > 0:
                non_zero_df = df[df['數量'] > 0].head(10)
                print("非零庫存產品示例:")
                for _, row in non_zero_df.iterrows():
                    print(f"產品代號: {row['產品代號']}, 名稱: {row['產品名稱']}, 數量: {row['數量']}")

        return df
    except Exception as e:
        st.error(f"資料載入錯誤: {e}")
        if st.session_state.get('debug_mode', False):
            print(f"資料載入錯誤詳情: {e}")
        return pd.DataFrame()

# Helper function to get sorted files from a directory
def get_sorted_files(directory):
    """Get files sorted by modification time (newest first)"""
    if not os.path.exists(directory):
        return []
    
    # Get files with their modification times
    files_with_time = [(f, os.path.getmtime(os.path.join(directory, f))) 
                      for f in os.listdir(directory) if f.endswith('.xlsx')]
    
    # Sort by modification time, newest first
    files_with_time.sort(key=lambda x: x[1], reverse=True)
    
    # Return just the filenames
    return [f[0] for f in files_with_time]

# Function to extract date from filename
def extract_date_from_filename(filename):
    """Extract date information from filename for nicer display"""
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

# Function to clear the data cache
def clear_data_cache():
    """Clear the st.cache_data cache to force data reload"""
    load_data.clear()
    st.success("資料快取已清除，將重新載入最新資料")

# Main function for the BC Products module
def run_bc_products_analysis():
    # Initialize session state for selected file
    if 'bc_selected_file' not in st.session_state:
        st.session_state.bc_selected_file = None
    
    # Get path to BC products file
    bc_products_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bc  products")
    
    # Get sorted files (newest first)
    excel_files = get_sorted_files(bc_products_dir)
    
    if not excel_files:
        st.error("沒有找到產品資料檔案")
        return None, None
    
    # Sidebar header
    st.sidebar.header("資料選項")
    
    # Add refresh button in sidebar
    refresh_col1, refresh_col2 = st.sidebar.columns([3, 1])
    with refresh_col1:
        st.write("更新資料:")
    with refresh_col2:
        if st.button("🔄", key="refresh_bc_data", help="重新整理資料和檔案清單"):
            # Clear cache to force data reload
            clear_data_cache()
            # Reset selected file to trigger reload
            st.session_state.bc_selected_file = None
            st.rerun()
    
    # File selection with most recent first
    # If there's no previously selected file or it's not in the list, default to first (most recent)
    default_index = 0
    if st.session_state.bc_selected_file in excel_files:
        default_index = excel_files.index(st.session_state.bc_selected_file)
    
    selected_file = st.sidebar.selectbox(
        "選擇產品資料檔案:", 
        excel_files,
        index=default_index,
        key="bc_file_selector"
    )
    
    # Update session state
    st.session_state.bc_selected_file = selected_file
    
    # Add file details
    file_path = os.path.join(bc_products_dir, selected_file)
    file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
    file_mod_time_str = file_mod_time.strftime("%Y-%m-%d %H:%M:%S")
    
    st.sidebar.info(f"檔案更新時間: {file_mod_time_str}")
    
    # Load data with caching (will automatically refresh after TTL)
    df = load_data(file_path)
    
    if df.empty:
        st.error(f"無法載入資料: {file_path}")
        return None, None
    
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
    
    # Return the dataframe for dashboard display
    return df, file_date_formatted

# Function to display BC Products dashboard
def display_bc_products_dashboard(df, file_date):
    # Create title with refresh button
    title_col, refresh_col = st.columns([5, 1])
    with title_col:
        st.title(f"BC產品全部資料 - {file_date}")
    with refresh_col:
        if st.button("🔄 重新整理", key="refresh_dashboard", help="清除快取並重新載入最新資料"):
            clear_data_cache()
            st.rerun()
            
    # Add filter options in sidebar
    st.sidebar.header("篩選選項")
    
    # Filter by category
    if '大類名稱' in df.columns and not df['大類名稱'].isna().all():
        all_categories = sorted(df['大類名稱'].dropna().unique().tolist())
        selected_categories = st.sidebar.multiselect(
            "選擇產品大類:",
            options=["全部"] + all_categories,
            default=["全部"]
        )
        
        if "全部" not in selected_categories:
            df = df[df['大類名稱'].isin(selected_categories)]
    
    # Filter by subcategory if available
    if '中類名稱' in df.columns and not df['中類名稱'].isna().all():
        all_subcategories = sorted(df['中類名稱'].dropna().unique().tolist())
        selected_subcategories = st.sidebar.multiselect(
            "選擇產品中類:",
            options=["全部"] + all_subcategories,
            default=["全部"]
        )
        
        if "全部" not in selected_subcategories:
            df = df[df['中類名稱'].isin(selected_subcategories)]
    
    # Filter by vendor
    if '廠商簡稱' in df.columns and not df['廠商簡稱'].isna().all():
        all_vendors = sorted(df['廠商簡稱'].dropna().unique().tolist())
        selected_vendors = st.sidebar.multiselect(
            "選擇供應商:",
            options=["全部"] + all_vendors,
            default=["全部"]
        )
        
        if "全部" not in selected_vendors:
            df = df[df['廠商簡稱'].isin(selected_vendors)]
    
    # Filter by stock availability
    stock_options = ["全部", "有庫存", "庫存不足", "無庫存", "有庫存但無銷售"]
    selected_stock = st.sidebar.radio("庫存狀態:", stock_options)
    
    if selected_stock == "有庫存":
        df = df[df['數量'] > 0]
    elif selected_stock == "庫存不足":
        df = df[(df['數量'] > 0) & (df['數量'] < df['安全存量'])]
    elif selected_stock == "無庫存":
        df = df[df['數量'] <= 0]
    elif selected_stock == "有庫存但無銷售":
        # 載入銷貨單資料以檢查銷售情況
        try:
            # 取得銷貨單資料目錄
            sales_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales data")
            
            # 檢查目錄是否存在
            if not os.path.exists(sales_data_dir):
                st.warning("無法找到銷貨單資料目錄")
                return df
            
            # 獲取排序後的檔案（最新的在前面）
            sales_files = get_sorted_files(sales_data_dir)
            
            if not sales_files:
                st.warning("無法找到銷貨單資料檔案")
                return df
            
            # 建立銷售文件選擇器的UI
            st.subheader("銷售資料選擇")
            
            # 建立檔案選項字典，用於更友好的顯示名稱
            file_options = {extract_date_from_filename(file): file for file in sales_files}
            
            # 選擇單個或多個銷售資料文件
            analysis_mode = st.radio(
                "選擇分析模式:",
                ["使用最新銷售資料", "選擇單個銷售期間", "選擇多個銷售期間"],
                index=0,
                horizontal=True
            )
            
            with st.spinner("正在分析銷售資料..."):
                # 根據選擇的模式決定要載入的銷售資料
                if analysis_mode == "使用最新銷售資料":
                    # 使用最新的銷售檔案
                    selected_files = [sales_files[0]]
                    st.info(f"使用最新銷售資料: {extract_date_from_filename(sales_files[0])}")
                    
                elif analysis_mode == "選擇單個銷售期間":
                    # 單個文件選擇
                    selected_period = st.selectbox(
                        "選擇銷售資料期間:",
                        options=list(file_options.keys())
                    )
                    selected_files = [file_options[selected_period]]
                    st.info(f"已選擇 {selected_period} 期間的銷售資料")
                    
                else:  # 選擇多個銷售期間
                    # 多選文件
                    selected_periods = st.multiselect(
                        "選擇多個銷售期間 (按住Ctrl或⌘鍵可多選):",
                        options=list(file_options.keys()),
                        default=[list(file_options.keys())[0]]  # 預設選擇第一個
                    )
                    
                    if not selected_periods:
                        st.warning("請至少選擇一個銷售期間")
                        return df
                    
                    selected_files = [file_options[period] for period in selected_periods]
                    st.info(f"已選擇 {len(selected_files)} 個期間的銷售資料")
                
                # 載入所有選定的銷售數據並合併
                sold_product_codes = set()
                
                # 如果選擇了多個檔案且數量大於1，顯示處理進度條
                if len(selected_files) > 1:
                    progress_bar = st.progress(0)
                else:
                    progress_bar = None
                
                # 並行處理多個檔案以提高效能
                if len(selected_files) > 1:
                    # 使用 ThreadPoolExecutor 實現並行載入
                    import concurrent.futures
                    
                    # 設定進度計數器
                    if progress_bar:
                        progress_counter = 0
                        total_files = len(selected_files)
                        
                        # 創建回調函數以更新進度
                        def update_progress():
                            nonlocal progress_counter
                            progress_counter += 1
                            progress_bar.progress(progress_counter/total_files)
                    
                    # 定義單個檔案處理函數
                    def process_single_file(file_name):
                        try:
                            file_path = os.path.join(sales_data_dir, file_name)
                            
                            # 嘗試使用銷售模組進行載入
                            try:
                                import sales
                                file_df = sales.load_data(file_path)
                            except Exception:
                                # 直接讀取 Excel 作為備用方案
                                file_df = pd.read_excel(file_path)
                            
                            # 從該檔案中提取產品代號
                            if '產品代號' in file_df.columns:
                                return set(file_df['產品代號'].dropna().unique())
                            return set()
                            
                        except Exception as e:
                            st.warning(f"處理檔案 {file_name} 時出錯: {str(e)}")
                            return set()
                    
                    # 並行處理所有檔案
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(selected_files))) as executor:
                        # 提交所有檔案處理任務
                        future_results = [executor.submit(process_single_file, file) for file in selected_files]
                        
                        # 收集所有結果
                        for future in concurrent.futures.as_completed(future_results):
                            # 合併產品代號集合
                            sold_product_codes.update(future.result())
                            
                            # 更新進度（如果有進度條）
                            if progress_bar:
                                update_progress()
                        
                else:
                    # 只有一個檔案，直接處理
                    file_path = os.path.join(sales_data_dir, selected_files[0])
                    
                    # 載入檔案
                    try:
                        import sales
                        sales_df = sales.load_data(file_path)
                    except Exception:
                        sales_df = pd.read_excel(file_path)
                    
                    # 確保產品代號欄位存在
                    if '產品代號' in sales_df.columns:
                        sold_product_codes = set(sales_df['產品代號'].dropna().unique())
                    else:
                        st.warning("銷貨單資料中找不到產品代號欄位")
                        return df
                
                # 完成進度（如果有進度條）
                if progress_bar:
                    progress_bar.progress(1.0)
                
                # 篩選出有庫存但無銷售的產品
                df_filtered = df[(df['數量'] > 0) & (~df['產品代號'].isin(sold_product_codes))]
                
                # 顯示找到的產品數量
                st.success(f"找到 {len(df_filtered)} 項有庫存但無銷售的產品")
                
                # 分析結果指標
                with st.expander("分析結果統計", expanded=True):
                    # 計算統計指標
                    total_inventory_value = (df_filtered['數量'] * df_filtered['成本單價']).sum()
                    avg_stock_days = 0  # 這需要更多數據才能計算
                    
                    # 顯示統計信息
                    cols = st.columns(3)
                    cols[0].metric("有庫存但無銷售產品數", f"{len(df_filtered)}")
                    cols[1].metric("佔總產品比例", f"{len(df_filtered)/len(df)*100:.1f}%")
                    cols[2].metric("庫存價值總計", f"${total_inventory_value:,.2f}")
                
                # 顯示高庫存價值且無銷售的產品詳細清單
                st.subheader("無銷售產品清單 (依成本總價排序)")
                
                # 計算成本總價 (數量 * 成本單價)
                df_filtered['成本總價_計算'] = df_filtered['數量'] * df_filtered['成本單價']
                
                # 依成本總價排序（高到低）
                sorted_df = df_filtered.sort_values(by='成本總價_計算', ascending=False)
                
                # 定義要顯示的欄位
                display_columns = ['產品代號', '產品名稱', '數量', '單位', '成本單價', '成本總價_計算']
                
                # 加入可選欄位（如果存在）
                optional_columns = ['廠商簡稱', '大類名稱', '中類名稱', '最後進貨日']
                for col in optional_columns:
                    if col in sorted_df.columns:
                        display_columns.append(col)
                
                # 設定欄位配置
                column_config = {
                    "產品代號": st.column_config.TextColumn("產品代號", width="medium"),
                    "產品名稱": st.column_config.TextColumn("產品名稱", width="large"),
                    "數量": st.column_config.NumberColumn("數量", format="%d"),
                    "單位": st.column_config.TextColumn("單位", width="small"),
                    "成本單價": st.column_config.NumberColumn("成本單價", format="%.2f"),
                    "成本總價_計算": st.column_config.NumberColumn(
                        "成本總價 ↓", 
                        format="%.2f",
                        help="依此欄位由高到低排序，找出最多資金積壓的庫存"
                    )
                }
                
                # 加入可選欄位的配置
                if '廠商簡稱' in display_columns:
                    column_config['廠商簡稱'] = st.column_config.TextColumn("廠商簡稱")
                if '大類名稱' in display_columns:
                    column_config['大類名稱'] = st.column_config.TextColumn("大類名稱")
                if '中類名稱' in display_columns:
                    column_config['中類名稱'] = st.column_config.TextColumn("中類名稱")
                if '最後進貨日' in display_columns:
                    column_config['最後進貨日'] = st.column_config.DateColumn("最後進貨日")
                
                # 顯示排序後的資料表
                st.dataframe(
                    sorted_df[display_columns], 
                    use_container_width=True,
                    column_config=column_config,
                    hide_index=True
                )
                
                # 新增下載CSV功能
                csv = sorted_df[display_columns].to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="下載CSV檔案",
                    data=csv,
                    file_name=f"無銷售產品清單_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    help="下載無銷售產品清單為CSV檔案，可在Excel中開啟"
                )
                
                # 提供建議
                with st.expander("📊 庫存優化建議", expanded=False):
                    st.markdown("""
                    ### 針對無銷售產品的建議
                    
                    1. **高價值庫存檢視**：優先關注成本總價最高的項目，這些項目佔用最多資金
                    2. **清倉促銷**：考慮對長期無銷售的產品進行清倉處理或特價促銷
                    3. **供應商協商**：與供應商協商退貨或換貨可能性
                    4. **調整訂貨策略**：針對無銷售產品調整未來訂貨量
                    5. **定期檢視**：建立定期檢視機制，追蹤庫存積壓情況
                    
                    > 注意：此分析基於所選銷售時段內的資料，建議定期使用不同時間範圍進行評估
                    """)
                
                # 更新過濾後的數據框
                df = df_filtered
                
        except Exception as e:
            st.error(f"分析銷售資料時出錯: {e}")
            # 發生錯誤時回傳原始資料
            return df
    
    # Dashboard layout
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("總產品數", f"{len(df):,}")
    
    with col2:
        total_stock = df['數量'].sum()
        st.metric("總庫存數量", f"{total_stock:,.0f}")
    
    with col3:
        total_inventory_value = (df['數量'] * df['成本單價']).sum()
        st.metric("總庫存價值", f"${total_inventory_value:,.2f}")
    
    with col4:
        low_stock_count = sum((df['數量'] > 0) & (df['數量'] < df['安全存量']))
        st.metric("庫存不足商品數", f"{low_stock_count:,}")
    
    # Add charts
    st.subheader("產品分析")
    
    # Chart tabs
    chart_tab1, chart_tab2, chart_tab3 = st.tabs(["類別分佈", "供應商分佈", "產品明細"])
    
    with chart_tab1:
        if '大類名稱' in df.columns:
            category_counts = df.groupby('大類名稱').size().reset_index(name='數量')
            category_counts = category_counts.sort_values('數量', ascending=False)
            
            fig = px.bar(
                category_counts, 
                x='大類名稱', 
                y='數量',
                title="各產品類別數量統計",
                color='數量',
                color_continuous_scale=px.colors.sequential.Blues
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with chart_tab2:
        if '廠商簡稱' in df.columns:
            vendor_counts = df.groupby('廠商簡稱').size().reset_index(name='產品數量')
            vendor_counts = vendor_counts.sort_values('產品數量', ascending=False).head(20)
            
            fig = px.bar(
                vendor_counts, 
                x='廠商簡稱', 
                y='產品數量',
                title="前20大供應商產品數量",
                color='產品數量',
                color_continuous_scale=px.colors.sequential.Greens
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
    
    with chart_tab3:
        # Product details table with sorting
        st.subheader("產品明細表")
        
        # Check if we should add sales data
        add_sales_data = st.checkbox("加入銷售資料", value=True, help="加入銷貨單產品的銷售數量、單價和小計")
        
        # Enhanced dataframe with sales data if requested
        enhanced_df = df.copy()
        
        if add_sales_data:
            # Get sales data to integrate with product data
            try:
                # 取得銷貨單資料目錄
                sales_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sales data")
                
                # 檢查目錄是否存在
                if not os.path.exists(sales_data_dir):
                    st.warning("無法找到銷貨單資料目錄")
                else:
                    # 獲取排序後的檔案（最新的在前面）
                    sales_files = get_sorted_files(sales_data_dir)
                    
                    if not sales_files:
                        st.warning("無法找到銷貨單資料檔案")
                    else:
                        # 建立檔案選項字典，用於更友好的顯示名稱
                        file_options = {extract_date_from_filename(file): file for file in sales_files}
                        
                        # 選擇單個或多個銷售資料檔案
                        analysis_mode = st.radio(
                            "選擇銷售資料範圍:",
                            ["使用最新銷售資料", "選擇單個銷售期間", "選擇多個銷售期間"],
                            index=0,
                            horizontal=True
                        )
                        
                        with st.spinner("正在載入銷售資料..."): 
                            # 根據選擇的模式決定要載入的銷售資料
                            if analysis_mode == "使用最新銷售資料":
                                # 使用最新的銷售檔案
                                selected_files = [sales_files[0]]
                                st.info(f"使用最新銷售資料: {extract_date_from_filename(sales_files[0])}")
                                
                            elif analysis_mode == "選擇單個銷售期間":
                                # 單個檔案選擇
                                selected_period = st.selectbox(
                                    "選擇銷售資料期間:",
                                    options=list(file_options.keys())
                                )
                                selected_files = [file_options[selected_period]]
                                st.info(f"已選擇 {selected_period} 期間的銷售資料")
                                
                            else:  # 選擇多個銷售期間
                                # 多選檔案
                                selected_periods = st.multiselect(
                                    "選擇多個銷售期間 (按住Ctrl或⌘鍵可多選):",
                                    options=list(file_options.keys()),
                                    default=[list(file_options.keys())[0]]  # 預設選擇第一個
                                )
                                
                                if not selected_periods:
                                    st.warning("請至少選擇一個銷售期間")
                                else:
                                    selected_files = [file_options[period] for period in selected_periods]
                                    st.info(f"已選擇 {len(selected_files)} 個期間的銷售資料")
                            
                            # 載入所有選定的銷售數據並合併
                            sales_dfs = []
                            
                            # 如果選擇了多個檔案且數量大於1，顯示處理進度條
                            if len(selected_files) > 1:
                                progress_bar = st.progress(0)
                                progress_counter = 0
                                total_files = len(selected_files)
                            else:
                                progress_bar = None
                            
                            # 載入所有選定的檔案
                            for i, file in enumerate(selected_files):
                                try:
                                    file_path = os.path.join(sales_data_dir, file)
                                    
                                    # 嘗試使用銷售模組進行載入
                                    try:
                                        import sales
                                        file_df = sales.load_data(file_path)
                                    except Exception:
                                        # 直接讀取 Excel 作為備用方案
                                        file_df = pd.read_excel(file_path)
                                    
                                    sales_dfs.append(file_df)
                                    
                                    # 更新進度條（如果有）
                                    if progress_bar:
                                        progress_counter += 1
                                        progress_bar.progress(progress_counter/total_files)
                                        
                                except Exception as e:
                                    st.warning(f"處理檔案 {file} 時出錯: {str(e)}")
                            
                            # 完成進度（如果有進度條）
                            if progress_bar:
                                progress_bar.progress(1.0)
                            
                            # 合併所有銷售資料
                            if sales_dfs:
                                combined_sales_df = pd.concat(sales_dfs, ignore_index=True)
                                
                                # 轉換數值欄位
                                numeric_cols = ['數量', '小計', '成本總值']
                                for col in numeric_cols:
                                    if col in combined_sales_df.columns:
                                        if combined_sales_df[col].dtype == 'object':
                                            combined_sales_df[col] = combined_sales_df[col].astype(str).str.replace(',', '')
                                            combined_sales_df[col] = pd.to_numeric(combined_sales_df[col], errors='coerce')
                                
                                # 轉換單價欄位
                                if '單價' in combined_sales_df.columns:
                                    if combined_sales_df['單價'].dtype == 'object':
                                        combined_sales_df['單價'] = combined_sales_df['單價'].astype(str).str.replace(',', '')
                                        combined_sales_df['單價'] = pd.to_numeric(combined_sales_df['單價'], errors='coerce')
                                
                                # 建立產品銷售摘要
                                agg_dict = {}
                                if '產品名稱' in combined_sales_df.columns:
                                    agg_dict['產品名稱'] = 'first'  # 取第一個產品名稱
                                if '數量' in combined_sales_df.columns:
                                    agg_dict['數量'] = 'sum'        # 合計數量
                                if '單位' in combined_sales_df.columns:
                                    agg_dict['單位'] = 'first'      # 取第一個單位
                                if '單價' in combined_sales_df.columns:
                                    agg_dict['單價'] = 'mean'       # 平均單價
                                if '小計' in combined_sales_df.columns:
                                    agg_dict['小計'] = 'sum'        # 合計小計
                                if '成本總值' in combined_sales_df.columns:
                                    agg_dict['成本總值'] = 'sum'     # 合計成本總值
                                
                                # 只有在產品代號欄位存在且有聚合內容時進行分組
                                if '產品代號' in combined_sales_df.columns and agg_dict:
                                    product_summary = combined_sales_df.groupby(['產品代號'], as_index=False).agg(agg_dict)
                                    
                                    # 安全計算單價（數量）= 小計 / 數量
                                    product_summary['單價（數量）'] = 0.0
                                    if '數量' in product_summary.columns and '小計' in product_summary.columns:
                                        mask = product_summary['數量'] > 0
                                        if isinstance(mask, pd.Series) and mask.any():
                                            result = (product_summary.loc[mask, '小計'] / product_summary.loc[mask, '數量']).astype('float64')
                                            product_summary.loc[mask, '單價（數量）'] = result
                                    
                                    # 將銷售資料映射到產品資料
                                    sales_data_map = {}
                                    for _, row in product_summary.iterrows():
                                        product_code = row['產品代號']
                                        sales_data = {
                                            '銷售數量': row.get('數量', 0),
                                            '銷售單價': row.get('單價（數量）', 0),
                                            '銷售小計': row.get('小計', 0)
                                        }
                                        sales_data_map[product_code] = sales_data
                                    
                                    # 將銷售資料添加到產品資料中
                                    enhanced_df['銷售數量'] = enhanced_df['產品代號'].map(lambda x: sales_data_map.get(x, {}).get('銷售數量', 0))
                                    enhanced_df['銷售單價'] = enhanced_df['產品代號'].map(lambda x: sales_data_map.get(x, {}).get('銷售單價', 0))
                                    enhanced_df['銷售小計'] = enhanced_df['產品代號'].map(lambda x: sales_data_map.get(x, {}).get('銷售小計', 0))
                                    
                                    # 顯示統計信息
                                    sales_count = (enhanced_df['銷售數量'] > 0).sum()
                                    st.success(f"找到 {sales_count} 項有銷售記錄的產品")
                                else:
                                    st.warning("銷貨單資料中找不到產品代號欄位或資料不完整")
                            else:
                                st.warning("未能載入任何銷售資料")
                                # 添加空的銷售欄位
                                enhanced_df['銷售數量'] = 0
                                enhanced_df['銷售單價'] = 0
                                enhanced_df['銷售小計'] = 0
            except Exception as e:
                st.error(f"整合銷售資料時出錯: {e}")
                # 添加空的銷售欄位
                enhanced_df['銷售數量'] = 0
                enhanced_df['銷售單價'] = 0
                enhanced_df['銷售小計'] = 0
        else:
            # 如果不添加銷售資料，仍然添加空的銷售欄位以維持表格結構一致
            enhanced_df['銷售數量'] = 0
            enhanced_df['銷售單價'] = 0
            enhanced_df['銷售小計'] = 0
            
        # Allow user to select display columns
        all_columns = enhanced_df.columns.tolist()
        default_columns = ['產品代號', '產品名稱', '數量', '銷售數量', '單位', '成本單價', '銷售單價', '成本總價', '銷售小計']
        
        # 根據是否顯示銷售資料添加其他默認欄位
        additional_columns = ['安全存量', '廠商簡稱', '大類名稱', '中類名稱']
        for col in additional_columns:
            if col in all_columns:
                default_columns.append(col)
        
        selected_columns = st.multiselect(
            "選擇顯示欄位:",
            options=all_columns,
            default=[col for col in default_columns if col in all_columns]
        )
        
        if not selected_columns:
            selected_columns = [col for col in default_columns if col in all_columns]
        
        # Sort options with added sales columns
        sort_options = {
            "產品代號": "產品代號",
            "產品名稱": "產品名稱",
            "庫存數量 (高到低)": "數量",
            "庫存數量 (低到高)": "數量_asc",
            "成本單價 (高到低)": "成本單價",
            "成本單價 (低到高)": "成本單價_asc",
            "成本總價 (高到低)": "成本總價",
            "成本總價 (低到高)": "成本總價_asc"
        }
        
        # 如果啟用銷售資料，添加相關排序選項
        if add_sales_data:
            sales_sort_options = {
                "銷售數量 (高到低)": "銷售數量",
                "銷售數量 (低到高)": "銷售數量_asc",
                "銷售單價 (高到低)": "銷售單價",
                "銷售單價 (低到高)": "銷售單價_asc",
                "銷售小計 (高到低)": "銷售小計",
                "銷售小計 (低到高)": "銷售小計_asc"
            }
            sort_options.update(sales_sort_options)
        
        sort_choice = st.selectbox("排序方式:", list(sort_options.keys()), index=0)
        sort_column = sort_options[sort_choice]
        
        # Handle ascending/descending
        if "_asc" in sort_column:
            sort_column = sort_column.replace("_asc", "")
            ascending = True
        else:
            ascending = False
        
        # Sort and display the table with column configuration
        if sort_column in enhanced_df.columns:
            sorted_df = enhanced_df.sort_values(by=sort_column, ascending=ascending)
            st.dataframe(
                sorted_df[selected_columns],
                use_container_width=True,
                column_config={
                    "產品代號": st.column_config.TextColumn("產品代號"),
                    "產品名稱": st.column_config.TextColumn("產品名稱"),
                    "數量": st.column_config.NumberColumn("庫存數量", format="%.0f"),
                    "銷售數量": st.column_config.NumberColumn("銷售數量", format="%.0f", help="來自銷貨單的銷售數量總和"),
                    "單位": st.column_config.TextColumn("單位"),
                    "成本單價": st.column_config.NumberColumn("成本單價", format="%.2f"),
                    "銷售單價": st.column_config.NumberColumn("銷售單價", format="%.2f", help="銷售小計除以銷售數量"),
                    "成本總價": st.column_config.NumberColumn("成本總價", format="%.2f"),
                    "銷售小計": st.column_config.NumberColumn("銷售小計", format="%.2f", help="來自銷貨單的銷售小計總和"),
                    "安全存量": st.column_config.NumberColumn("安全存量", format="%.0f"),
                    "廠商簡稱": st.column_config.TextColumn("廠商簡稱"),
                    "大類名稱": st.column_config.TextColumn("大類名稱"),
                    "中類名稱": st.column_config.TextColumn("中類名稱")
                },
                hide_index=True
            )
        else:
            st.dataframe(
                enhanced_df[selected_columns],
                use_container_width=True,
                column_config={
                    "產品代號": st.column_config.TextColumn("產品代號"),
                    "產品名稱": st.column_config.TextColumn("產品名稱"),
                    "數量": st.column_config.NumberColumn("庫存數量", format="%.0f"),
                    "銷售數量": st.column_config.NumberColumn("銷售數量", format="%.0f", help="來自銷貨單的銷售數量總和"),
                    "單位": st.column_config.TextColumn("單位"),
                    "成本單價": st.column_config.NumberColumn("成本單價", format="%.2f"),
                    "銷售單價": st.column_config.NumberColumn("銷售單價", format="%.2f", help="銷售小計除以銷售數量"),
                    "成本總價": st.column_config.NumberColumn("成本總價", format="%.2f"),
                    "銷售小計": st.column_config.NumberColumn("銷售小計", format="%.2f", help="來自銷貨單的銷售小計總和"),
                    "安全存量": st.column_config.NumberColumn("安全存量", format="%.0f"),
                    "廠商簡稱": st.column_config.TextColumn("廠商簡稱"),
                    "大類名稱": st.column_config.TextColumn("大類名稱"),
                    "中類名稱": st.column_config.TextColumn("中類名稱")
                },
                hide_index=True
            )

# Run the module when executed directly
if __name__ == "__main__":
    df, file_date = run_bc_products_analysis()
    if df is not None:
        display_bc_products_dashboard(df, file_date)
# 主應用程式入口 - Main Application Entry Point
import streamlit as st
import importlib
import os
import pandas as pd
import datetime
import shutil
from pathlib import Path

# Set page configuration
st.set_page_config(
    page_title="ERP系統",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create upload directories if they don't exist
os.makedirs("uploads/sales", exist_ok=True)
os.makedirs("uploads/bc_products", exist_ok=True)

# Initialize debug mode session state
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False

# Main title
st.title("企業資源計劃 (ERP) 系統")

# Add debug toggle in sidebar at the very bottom
with st.sidebar:
    st.markdown("---")
    # Use expander to hide technical controls
    with st.expander("開發者選項"):
        debug_mode = st.checkbox("啟用調試模式", value=st.session_state.debug_mode)
        st.session_state.debug_mode = debug_mode
        
        if debug_mode:
            # Add additional debugging tools if in debug mode
            if st.button("清除所有快取", key="clear_all_cache"):
                try:
                    import sales
                    import bc_products
                    sales.load_data.clear() if hasattr(sales.load_data, 'clear') else None
                    bc_products.load_data.clear() if hasattr(bc_products.load_data, 'clear') else None
                    st.success("所有快取已清除")
                    st.rerun()
                except Exception as e:
                    st.error(f"清除快取失敗: {e}")
            
            # Garbage collection trigger for memory optimization
            if st.button("執行內存優化", key="run_gc"):
                import gc
                gc.collect()
                st.success("已執行垃圾回收")
                
            # Show memory usage
            try:
                import psutil
                process = psutil.Process()
                memory_info = process.memory_info()
                st.info(f"內存使用: {memory_info.rss / (1024*1024):.1f} MB")
            except:
                st.info("無法讀取內存使用率")
    
    # Add version info
    st.markdown("""
    <div style="font-size:0.8em; opacity:0.7; text-align:center; margin-top:20px;">
    v1.1 性能優化版
    </div>
    """, unsafe_allow_html=True)

# Initialize session state for module selection
if 'selected_module' not in st.session_state:
    st.session_state.selected_module = "銷貨單毛利分析"

# Module selection in sidebar
st.sidebar.title("模組選擇")
selected_module = st.sidebar.radio(
    "請選擇要使用的模組:",
    ["銷貨單毛利分析", "BC產品全部資料", "銷貨單與BC產品整合", "檔案上傳管理", "更多模組即將推出..."],
    index=["銷貨單毛利分析", "BC產品全部資料", "銷貨單與BC產品整合", "檔案上傳管理", "更多模組即將推出..."].index(st.session_state.selected_module)
)

# Update session state when module changes
st.session_state.selected_module = selected_module

# Main content area based on module selection
if selected_module == "銷貨單毛利分析":
    # Import and run the sales module
    try:
        import sales
        importlib.reload(sales)  # Reload to get latest changes

        # Run the sales analysis
        df, period_display, analysis_type = sales.run_sales_analysis()
        sales.display_sales_dashboard(df, period_display)
    except Exception as e:
        st.error(f"無法載入銷貨單毛利分析模組: {e}")
elif selected_module == "BC產品全部資料":
    # Import and run the BC products module
    try:
        import bc_products
        importlib.reload(bc_products)  # Reload to get latest changes

        # Run the BC products analysis
        df, file_date = bc_products.run_bc_products_analysis()
        if df is not None:
            bc_products.display_bc_products_dashboard(df, file_date)
    except Exception as e:
        st.error(f"無法載入BC產品全部資料模組: {e}")
elif selected_module == "銷貨單與BC產品整合":
    # Import and run the integrated module
    try:
        import integrated_module
        importlib.reload(integrated_module)  # Reload to get latest changes

        # Run the integrated analysis
        sales_df, period_display, bc_df, file_date = integrated_module.run_integrated_analysis()
        integrated_module.display_integrated_dashboard(sales_df, period_display, bc_df, file_date)
    except Exception as e:
        st.error(f"無法載入銷貨單與BC產品整合模組: {e}")
elif selected_module == "檔案上傳管理":
    st.header("檔案上傳管理")
    
    # Initialize session state for upload file type
    if 'upload_file_type' not in st.session_state:
        st.session_state.upload_file_type = "銷貨單毛利分析表"
    if 'manage_file_type' not in st.session_state:
        st.session_state.manage_file_type = "銷貨單毛利分析表"
    if 'last_uploaded_file' not in st.session_state:
        st.session_state.last_uploaded_file = None
    
    # Create tabs for different upload types
    upload_tab, manage_tab = st.tabs(["上傳新檔案", "管理已上傳檔案"])
    
    with upload_tab:
        st.subheader("上傳檔案")
        
        # File type selection with saved state
        file_type = st.radio(
            "請選擇上傳的檔案類型:",
            ["銷貨單毛利分析表", "BC產品全部資料"],
            index=0 if st.session_state.upload_file_type == "銷貨單毛利分析表" else 1,
            key="upload_file_type_radio"
        )
        # Update session state
        st.session_state.upload_file_type = file_type
        
        uploaded_file = st.file_uploader(
            "選擇Excel檔案 (.xlsx)",
            type=["xlsx"],
            help="請上傳符合系統格式的Excel檔案",
            key="file_uploader"
        )
        
        # Process uploaded file
        if uploaded_file is not None:
            # Check file format briefly (can add more validation later)
            try:
                df = pd.read_excel(uploaded_file)
                st.success(f"成功載入檔案: {uploaded_file.name} (包含 {len(df)} 行資料)")
                
                # Show a preview of the data
                with st.expander("預覽檔案內容"):
                    st.dataframe(df.head(10))
                
                # Generate proper filename with date
                now = datetime.datetime.now()
                today = now.strftime("%Y%m%d")
                timestamp = now.strftime("%H%M%S")
                
                if file_type == "銷貨單毛利分析表":
                    dst_dir = Path("sales data")
                    # Keep the original filename or modify it to include date
                    if not uploaded_file.name.startswith("銷貨單毛利分析表_"):
                        filename = f"銷貨單毛利分析表_{today}.xlsx"
                    else:
                        filename = uploaded_file.name
                else:  # BC產品全部資料
                    dst_dir = Path("bc  products")
                    # Keep the original filename or modify it to include date
                    if not uploaded_file.name.startswith("BC_產品全部SKU_"):
                        filename = f"BC_產品全部SKU_{today}.xlsx"
                    else:
                        filename = uploaded_file.name
                
                # Display the filename that will be used
                st.info(f"檔案將使用以下名稱保存: {filename}")
                
                # Save file button
                save_col, view_col = st.columns(2)
                with save_col:
                    if st.button("儲存檔案", key="save_file_btn"):
                        # Create directories if they don't exist
                        dst_dir.mkdir(exist_ok=True)
                        
                        # Save the file to the appropriate directory
                        dst_path = dst_dir / filename
                        with open(dst_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Also save a copy to uploads directory with timestamp for uniqueness
                        if file_type == "銷貨單毛利分析表":
                            uploads_dir = Path("uploads/sales")
                            upload_copy_path = uploads_dir / filename
                            module_to_go = "銷貨單毛利分析"
                        else:
                            uploads_dir = Path("uploads/bc_products")
                            upload_copy_path = uploads_dir / filename
                            module_to_go = "BC產品全部資料"
                        
                        # Ensure uploads directory exists
                        uploads_dir.mkdir(exist_ok=True, parents=True)
                        
                        with open(upload_copy_path, "wb") as f:
                            uploaded_file.seek(0)
                            f.write(uploaded_file.getbuffer())
                        
                        # Store the last uploaded file info in session state
                        st.session_state.last_uploaded_file = {
                            "filename": filename,
                            "type": file_type,
                            "module": module_to_go,
                            "path": str(dst_path),
                            "timestamp": timestamp
                        }
                        
                        st.success(f"檔案已儲存至 {dst_path}")
                        
                        # Show where to find the data in the app
                        st.info(f"您現在可以前往「{module_to_go}」模組查看此資料")
                
                with view_col:
                    # Add button to navigate to appropriate module
                    if st.button("儲存後前往查看", key="save_and_view_btn"):
                        # Create directories if they don't exist
                        dst_dir.mkdir(exist_ok=True)
                        
                        # Save the file to the appropriate directory
                        dst_path = dst_dir / filename
                        with open(dst_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        
                        # Also save a copy to uploads directory for records
                        if file_type == "銷貨單毛利分析表":
                            uploads_dir = Path("uploads/sales")
                            upload_copy_path = uploads_dir / filename
                            # Set session state to navigate to sales module
                            st.session_state.selected_module = "銷貨單毛利分析"
                        else:
                            uploads_dir = Path("uploads/bc_products")
                            upload_copy_path = uploads_dir / filename
                            # Set session state to navigate to BC products module
                            st.session_state.selected_module = "BC產品全部資料"
                        
                        # Ensure uploads directory exists
                        uploads_dir.mkdir(exist_ok=True, parents=True)
                        
                        with open(upload_copy_path, "wb") as f:
                            uploaded_file.seek(0)
                            f.write(uploaded_file.getbuffer())
                        
                        st.success(f"檔案已儲存，正在前往模組...")
                        st.rerun()  # Rerun to navigate to the selected module
            
            except Exception as e:
                st.error(f"檔案處理錯誤: {e}")
    
    with manage_tab:
        st.subheader("管理已上傳檔案")
        
        # File type selection for management with saved state
        manage_file_type = st.radio(
            "請選擇要管理的檔案類型:",
            ["銷貨單毛利分析表", "BC產品全部資料"],
            index=0 if st.session_state.manage_file_type == "銷貨單毛利分析表" else 1,
            key="manage_file_type_radio"
        )
        
        # Update session state
        st.session_state.manage_file_type = manage_file_type
        
        # Display existing files and allow deletion
        if manage_file_type == "銷貨單毛利分析表":
            file_dir = "sales data"
            uploads_dir = "uploads/sales"
            module_name = "銷貨單毛利分析"
        else:
            file_dir = "bc  products"
            uploads_dir = "uploads/bc_products"
            module_name = "BC產品全部資料"
        
        # Get file lists with modification times for sorting
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
        
        active_files = get_sorted_files(file_dir)
        upload_history = get_sorted_files(uploads_dir)
        
        # Add refresh button
        if st.button("重新整理檔案清單", key="refresh_files"):
            st.rerun()
        
        # Button to navigate to module
        if st.button(f"前往「{module_name}」模組查看資料", key="go_to_module"):
            if manage_file_type == "銷貨單毛利分析表":
                st.session_state.selected_module = "銷貨單毛利分析"
            else:
                st.session_state.selected_module = "BC產品全部資料"
            st.rerun()
        
        # Show active files with last modified time
        st.subheader("目前使用中檔案")
        if active_files:
            for i, file in enumerate(active_files):
                file_path = os.path.join(file_dir, file)
                mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                mod_time_str = mod_time.strftime("%Y-%m-%d %H:%M:%S")
                
                col1, col2, col3 = st.columns([3, 2, 1])
                with col1:
                    st.text(file)
                with col2:
                    st.text(f"修改時間: {mod_time_str}")
                with col3:
                    if st.button("刪除", key=f"del_{file}"):
                        try:
                            os.remove(file_path)
                            st.success(f"已刪除 {file}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"刪除失敗: {e}")
        else:
            st.info(f"沒有{manage_file_type}檔案")
        
        # Show upload history with last modified time
        st.subheader("上傳歷史")
        if upload_history:
            for i, file in enumerate(upload_history):
                file_path = os.path.join(uploads_dir, file)
                mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                mod_time_str = mod_time.strftime("%Y-%m-%d %H:%M:%S")
                
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                with col1:
                    st.text(file)
                with col2:
                    st.text(f"上傳時間: {mod_time_str}")
                with col3:
                    if st.button("啟用", key=f"restore_{file}"):
                        try:
                            # Copy from uploads to active directory
                            shutil.copy(os.path.join(uploads_dir, file), 
                                       os.path.join(file_dir, file))
                            st.success(f"已啟用 {file}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"啟用失敗: {e}")
                with col4:
                    if st.button("刪除", key=f"perm_del_{file}"):
                        try:
                            os.remove(os.path.join(uploads_dir, file))
                            st.success(f"已永久刪除 {file}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"刪除失敗: {e}")
        else:
            st.info(f"沒有{manage_file_type}上傳歷史")
            
        # If there's a last uploaded file, show a shortcut
        if st.session_state.last_uploaded_file:
            last_file = st.session_state.last_uploaded_file
            if last_file["type"] == manage_file_type:
                st.markdown("---")
                st.subheader("最近上傳的檔案")
                st.success(f"檔案名稱: {last_file['filename']}")
                st.info(f"儲存位置: {last_file['path']}")
                
                if st.button(f"前往「{last_file['module']}」模組查看最近上傳的檔案", key="view_last_uploaded"):
                    st.session_state.selected_module = last_file["module"]
                    st.rerun()
        else:
            st.info(f"沒有{manage_file_type}上傳歷史")

elif selected_module == "更多模組即將推出...":
    st.info("更多功能模組正在開發中，敬請期待！")
    
    # Placeholder for future modules
    st.subheader("即將推出的模組:")
    upcoming_modules = [
        "庫存管理",
        "採購訂單",
        "客戶關係管理 (CRM)",
        "人力資源管理",
        "財務報表"
    ]
    
    for module in upcoming_modules:
        st.markdown(f"- {module}")
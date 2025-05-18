# Modified display_sales_dashboard function with session_state for BC inventory comparison
def display_sales_dashboard(df, period_display):
    # Initialize session state for BC inventory comparison
    if 'bc_inventory_matched' not in st.session_state:
        st.session_state.bc_inventory_matched = False
    if 'bc_inventory_data' not in st.session_state:
        st.session_state.bc_inventory_data = None
    if 'match_stats' not in st.session_state:
        st.session_state.match_stats = None
    if 'product_summary_with_inventory' not in st.session_state:
        st.session_state.product_summary_with_inventory = None
    
    # Summary metrics in a row
    col1, col2, col3, col4 = st.columns(4)

    # Total sales
    total_sales = df['總計金額'].sum()
    col1.metric("總銷售額", f"{total_sales:,.0f} NTD")

    # Total profit
    total_profit = df['毛利'].sum()
    col2.metric("總毛利", f"{total_profit:,.0f} NTD")

    # Average profit margin
    avg_profit_margin = (total_profit / total_sales * 100) if total_sales and total_sales > 0 else 0
    col3.metric("平均毛利率", f"{avg_profit_margin:.2f}%")

    # Total orders
    total_orders = df['銷貨單號'].nunique()
    col4.metric("訂單數量", f"{total_orders}")

    # Create two columns for charts
    chart1, chart2 = st.columns(2)

    with chart1:
        st.subheader("每日銷售趨勢")
        if '銷貨日期_dt' in df.columns:
            # Filter out NaT values
            valid_dates = df.dropna(subset=['銷貨日期_dt'])

            if not valid_dates.empty:
                # Group by date and sum the sales
                daily_sales = valid_dates.groupby(valid_dates['銷貨日期_dt'].dt.date)['總計金額'].sum().reset_index()
                daily_sales.columns = ['Date', 'Sales']

                # Plot with Plotly
                fig = px.line(daily_sales, x='Date', y='Sales',
                              title='Daily Sales Trend',
                              labels={'Sales': 'Sales (NTD)', 'Date': 'Date'})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("無法顯示日銷售趨勢：沒有有效的日期數據")
        else:
            st.write("無法顯示日銷售趨勢：日期欄位無法解析")

    with chart2:
        st.subheader("top 10客戶")
        # Group by customer and sum the sales
        customer_sales = df.groupby('客戶名稱')['總計金額'].sum().reset_index()
        customer_sales = customer_sales.sort_values('總計金額', ascending=False).head(10)

        # Plot with Plotly
        fig = px.bar(customer_sales, x='客戶名稱', y='總計金額',
                     title='Top 10 Customers by Sales',
                     labels={'總計金額': 'Sales (NTD)', '客戶名稱': 'Customer'})
        st.plotly_chart(fig, use_container_width=True)

    # Product analysis
    st.subheader("產品分析")
    col1, col2 = st.columns(2)

    with col1:
        # Top selling products
        product_sales = df.groupby('產品名稱')['總計金額'].sum().reset_index()
        product_sales = product_sales.sort_values('總計金額', ascending=False).head(10)

        fig = px.bar(product_sales, x='總計金額', y='產品名稱', orientation='h',
                     title='Top 10 Products by Sales',
                     labels={'總計金額': 'Sales (NTD)', '產品名稱': 'Product'})
        st.plotly_chart(fig, use_container_width=True)

    with col2:
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

        # Filter out rows with zero or negative total sales
        product_margin = product_margin[product_margin['總計金額'] > 0]

        # Get top 10 by profit margin
        product_margin = product_margin.sort_values('毛利率', ascending=False).head(10)

        fig = px.bar(product_margin, x='毛利率', y='產品名稱', orientation='h',
                     title='Top 10 Products by Profit Margin (%)',
                     labels={'毛利率': 'Profit Margin (%)', '產品名稱': 'Product'})
        st.plotly_chart(fig, use_container_width=True)

    # Raw data section (expandable)
    with st.expander("查看原始數據"):
        st.dataframe(df)

    # Product summary table
    st.subheader("產品彙總表")
    
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

    # Now do the aggregation on filtered data
    product_summary = df_products_filtered.groupby(['產品代號']).agg({
        '產品名稱': 'first',  # Take the first product name for each product code
        '數量': 'sum',  # Sum quantities
        '單位': 'first',  # Take the first unit
        '單價': 'mean' if '單價' in df_products_filtered.columns else None,  # Average price
        '小計': 'sum',  # Sum subtotals
        '成本總值': 'sum'  # Sum cost values
    }).reset_index()

    # Remove None-valued aggregations
    product_summary = product_summary.dropna(axis=1, how='all')

    # Sort by 小計 in descending order (highest to lowest)
    product_summary = product_summary.sort_values(by='小計', ascending=False)

    # Calculate 單價（數量）= 小計 / 數量
    product_summary['單價（數量）'] = product_summary.apply(
        lambda row: row['小計'] / row['數量'] if row['數量'] > 0 else 0, 
        axis=1
    )

    # 保存產品彙總表的原始副本（在添加BC庫存數據之前）
    if st.session_state.product_summary_with_inventory is None:
        original_product_summary = product_summary.copy()
    else:
        # 使用保存的帶有庫存數據的產品汇总表
        product_summary = st.session_state.product_summary_with_inventory.copy()
        
    # 產品銷售比對BC庫存資料區塊
    st.markdown("---")
    st.markdown("### 💡 產品銷售比對BC庫存資料")
    
    # 根據會話狀態顯示不同的UI
    if st.session_state.bc_inventory_matched:
        # 已經完成比對，顯示比對結果統計
        stats = st.session_state.match_stats
        st.success(f"比對完成！共有 {stats['match_count']} 項產品在BC庫存中找到匹配記錄（總計 {stats['total_count']} 項產品）")
        
        # 使用列布局顯示各種統計信息
        col1, col2, col3 = st.columns(3)
        col1.metric("庫存充足產品數", f"{stats['stock_sufficient']}", help="庫存數量大於或等於銷售數量的產品")
        col2.metric("庫存不足產品數", f"{stats['stock_insufficient']}", help="庫存數量小於銷售數量的產品")
        col3.metric("無庫存產品數", f"{stats['total_count'] - stats['match_count']}", help="在BC庫存中沒有找到匹配記錄的產品")
        
        st.info(f"使用的BC庫存資料檔案：{stats['file_name']} ({stats['file_date']})")
        
        # 添加清除比對結果的按鈕
        if st.button("清除庫存比對結果", key="clear_inventory_match"):
            st.session_state.bc_inventory_matched = False
            st.session_state.bc_inventory_data = None
            st.session_state.match_stats = None
            st.session_state.product_summary_with_inventory = None
            st.experimental_rerun()
    else:
        # 顯示比對按鈕
        comparison_button = st.button("🔄 開始比對產品銷售與BC庫存資料", 
                                     type="primary", 
                                     use_container_width=True,
                                     help="點擊此按鈕將產品彙總表與BC產品庫存資料進行匹配",
                                     key="compare_bc_inventory_button")
        
        # 如果用戶點擊了比對按鈕
        if comparison_button:
            # 設置選擇文件的標記
            if 'file_selection_active' not in st.session_state:
                st.session_state.file_selection_active = True
            
            # BC庫存文件選擇器
            bc_products_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bc  products")
            excel_files = [f for f in os.listdir(bc_products_dir) if f.endswith('.xlsx')]
            
            if not excel_files:
                st.error("找不到BC產品資料檔案")
            else:
                # 按日期排序，選擇最新的文件作為默認選項
                excel_files.sort()
                default_file = excel_files[-1]
                
                # 使用session_state儲存當前選擇的文件
                if 'selected_bc_file' not in st.session_state:
                    st.session_state.selected_bc_file = default_file
                
                # 選擇檔案
                selected_file = st.selectbox(
                    "選擇BC產品庫存資料檔案:", 
                    excel_files,
                    index=excel_files.index(default_file),
                    key="bc_file_selector"
                )
                
                # 保存選擇的文件到session_state
                st.session_state.selected_bc_file = selected_file
                
                # 添加提交按鈕
                submit_button = st.button("確定選擇", type="primary", key="confirm_bc_file_selection")
                
                # 如果點擊確定選擇按鈕
                if submit_button:
                    # 加載BC產品資料
                    file_path = os.path.join(bc_products_dir, selected_file)
                    try:
                        # 使用bc_products模組中的load_data函數
                        import bc_products
                        bc_df = bc_products.load_data(file_path)
                        
                        if bc_df.empty:
                            st.error(f"無法載入BC產品資料: {selected_file}")
                        else:
                            # 提取文件日期用於顯示
                            file_date = selected_file.split('_')[-1].replace('.xlsx', '')
                            file_date_formatted = f"{file_date[:4]}/{file_date[4:6]}/{file_date[6:]}"
                            
                            # 確保BC資料中的產品代號是字符串類型
                            bc_df['產品代號'] = bc_df['產品代號'].astype(str)
                            
                            # 確保產品匯總表的產品代號是字符串類型
                            original_product_summary['產品代號'] = original_product_summary['產品代號'].astype(str)
                            
                            # 合併產品彙總表與BC庫存資料
                            merged_df = original_product_summary.merge(
                                bc_df[['產品代號', '數量']], 
                                on='產品代號', 
                                how='left',
                                suffixes=('', '_庫存')
                            )
                            
                            # 填充缺失的庫存數量為0
                            merged_df['數量_庫存'] = merged_df['數量_庫存'].fillna(0).astype(int)
                            
                            # 添加庫存差異列
                            merged_df['庫存差異'] = merged_df['數量_庫存'] - merged_df['數量']
                            
                            # 將處理後的DataFrame保存到session_state中
                            st.session_state.product_summary_with_inventory = merged_df
                            st.session_state.bc_inventory_data = bc_df[['產品代號', '數量']]
                            
                            # 計算統計信息
                            match_count = (merged_df['數量_庫存'] > 0).sum()
                            total_count = len(merged_df)
                            stock_sufficient = ((merged_df['數量_庫存'] >= merged_df['數量']) & (merged_df['數量_庫存'] > 0)).sum()
                            stock_insufficient = ((merged_df['數量_庫存'] < merged_df['數量']) & (merged_df['數量_庫存'] > 0)).sum()
                            
                            # 保存統計信息到session_state中
                            st.session_state.match_stats = {
                                'match_count': match_count,
                                'total_count': total_count,
                                'stock_sufficient': stock_sufficient,
                                'stock_insufficient': stock_insufficient,
                                'file_name': selected_file,
                                'file_date': file_date_formatted
                            }
                            
                            # 標記比對已完成
                            st.session_state.bc_inventory_matched = True
                            
                            # 重新運行以顯示更新後的界面
                            st.experimental_rerun()
                            
                    except Exception as e:
                        st.error(f"比對過程中發生錯誤: {e}")
    
    # 準備顯示欄位列表
    if st.session_state.bc_inventory_matched and '數量_庫存' in product_summary.columns:
        # 如果已經比對並且有庫存資料，顯示更多欄位
        display_columns = ['產品代號', '產品名稱', '數量', '數量_庫存', '庫存差異', '單位', '單價', '單價（數量）', '小計', '成本總值']
    else:
        # 默認顯示欄位
        display_columns = ['產品代號', '產品名稱', '數量', '單位', '單價', '單價（數量）', '小計', '成本總值']
    
    # 確保所有顯示的欄位都存在
    display_columns = [col for col in display_columns if col in product_summary.columns]
    
    # 設置列配置
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
    
    # 如果有庫存數量欄位，添加到column_config
    if '數量_庫存' in product_summary.columns:
        column_config["數量"] = st.column_config.NumberColumn(
            "銷售數量",
            format="%.0f",
            help="銷售的產品數量"
        )
        
        column_config["數量_庫存"] = st.column_config.NumberColumn(
            "庫存數量",
            format="%.0f",
            help="BC產品庫存數量"
        )
    
    # 如果有庫存差異欄位，添加到column_config
    if '庫存差異' in product_summary.columns:
        column_config["庫存差異"] = st.column_config.NumberColumn(
            "庫存差異",
            format="%.0f",
            help="庫存數量減去銷售數量的差異（正值表示庫存充足，負值表示庫存不足）"
        )
    
    # 顯示產品彙總表
    st.dataframe(
        product_summary[display_columns],
        use_container_width=True,
        column_config=column_config,
        hide_index=True
    )
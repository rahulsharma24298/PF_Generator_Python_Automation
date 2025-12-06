import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# Page configuration
st.set_page_config(page_title="Excel File Mapper", layout="wide")
st.title("Excel File Mapping Tool")
st.markdown("""
This tool helps you map data between two Excel files:
1. **PF_Data.csv** - Contains strategy parameters
2. **ResultSet.xlsx** - Contains instrument data

After mapping, it auto-creates a FinalPF.csv with all PF_Data.csv columns, using mapping results for mapped columns and PF_Data's first row for all others.
""")

if 'pf_data' not in st.session_state:
    st.session_state.pf_data = None
if 'resultset_data' not in st.session_state:
    st.session_state.resultset_data = None
if 'mapping_complete' not in st.session_state:
    st.session_state.mapping_complete = False
if 'download_count' not in st.session_state:
    st.session_state.download_count = 1

# File upload section
st.header("Step 1: Upload Files")
col1, col2 = st.columns(2)
with col1:
    st.subheader("PF_Data File")
    pf_file = st.file_uploader("Upload PF_Data.csv", type=['csv'], key="pf_upload")
    if pf_file:
        st.session_state.pf_data = pd.read_csv(pf_file)
        st.success("PF_Data file uploaded successfully!")
        st.write(f"Shape: {st.session_state.pf_data.shape}")
        st.dataframe(st.session_state.pf_data.head(3))
with col2:
    st.subheader("ResultSet File")
    resultset_file = st.file_uploader("Upload ResultSet.xlsx", type=['xlsx'], key="resultset_upload")
    if resultset_file:
        st.session_state.resultset_data = pd.read_excel(resultset_file)
        st.success("ResultSet file uploaded successfully!")
        st.write(f"Shape: {st.session_state.resultset_data.shape}")
        st.dataframe(st.session_state.resultset_data.head(3))

if st.session_state.pf_data is not None and st.session_state.resultset_data is not None:
    st.header("Step 2: Parameter Mapping")

    rs = st.session_state.resultset_data.copy()

    # Convert ExpiryDate to human readable format using epoch initial date as 1 January 1980
    if 'ExpiryDate' in rs.columns:
        epoch_start = datetime(1980, 1, 1)
        try:
            if pd.api.types.is_numeric_dtype(rs['ExpiryDate']):
                rs['ExpiryDate_DT'] = epoch_start + pd.to_timedelta(rs['ExpiryDate'], unit='s')
            else:
                rs['ExpiryDate_DT'] = pd.to_datetime(rs['ExpiryDate'])
            rs['ExpiryDate_Readable'] = rs['ExpiryDate_DT'].dt.strftime('%d/%m/%y')
            rs = rs.sort_values('ExpiryDate_DT')
        except Exception as e:
            st.error(f"Error converting ExpiryDate: {e}")
            rs['ExpiryDate_Readable'] = rs['ExpiryDate'].astype(str)

    exchanges = rs['Exch'].unique().tolist() if 'Exch' in rs.columns else []
    segments = rs['Segment'].unique().tolist() if 'Segment' in rs.columns else []
    symbols = rs['Symbol'].unique().tolist() if 'Symbol' in rs.columns else []
    expiries = rs['ExpiryDate_Readable'].unique().tolist() if 'ExpiryDate_Readable' in rs.columns else []
    inst_types = rs['InstType'].unique().tolist() if 'InstType' in rs.columns else []
    option_types = rs['OptionType'].unique().tolist() if 'OptionType' in rs.columns else []
    strike_prices = sorted(rs['StrikePrice'].unique().tolist()) if 'StrikePrice' in rs.columns else []

    st.subheader("Available Instruments in ResultSet")
    if st.checkbox("Show available instruments"):
        st.dataframe(
            rs[['Exch', 'Segment', 'Symbol', 'ExpiryDate_Readable', 'InstType', 'OptionType', 'StrikePrice', 'Token', 'Name']]
        )

    st.subheader("Strike Gap Parameter")
    gap = st.number_input("Strike Gap", min_value=0, value=500, step=50, help="Value to increase strike prices by")

    st.subheader("ATM_CE Mapping")
    col1, col2, col3 = st.columns(3)
    with col1:
        atm_exch = st.selectbox("Exchange", exchanges, key="atm_exch")
        atm_segment = st.selectbox("Segment", segments, key="atm_segment")
        atm_symbol = st.selectbox("Symbol", symbols, key="atm_symbol")
    with col2:
        atm_expiry = st.selectbox("Expiry Date", expiries, key="atm_expiry")
        atm_inst_type = st.selectbox("Instrument Type", inst_types, key="atm_inst_type")
        atm_option_type = st.selectbox("Option Type", option_types, key="atm_option_type")
    with col3:
        st.write("Strike Range")
        default_min = 0
        default_max = 0
        filtered = rs[(rs['Symbol'] == atm_symbol) & (rs['ExpiryDate_Readable'] == atm_expiry) & (rs['OptionType'] == atm_option_type)]
        if not filtered.empty:
            default_min = filtered['StrikePrice'].min()
            default_max = filtered['StrikePrice'].max()
        atm_strike_min = st.number_input("Min Strike", value=int(default_min), key="atm_min")
        atm_strike_max = st.number_input("Max Strike", value=int(default_max), key="atm_max")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("−", key="dec_min"):
                st.session_state.atm_min -= gap
        with col_b:
            if st.button("+", key="inc_min"):
                st.session_state.atm_min += gap
        col_c, col_d = st.columns(2)
        with col_c:
            if st.button("−", key="dec_max"):
                st.session_state.atm_max -= gap
        with col_d:
            if st.button("+", key="inc_max"):
                st.session_state.atm_max += gap

    def find_atm_token(exch, segment, symbol, expiry_readable, inst_type, option_type, strike_min, strike_max):
        filtered = rs.copy()
        if exch: filtered = filtered[filtered['Exch'] == exch]
        if segment: filtered = filtered[filtered['Segment'] == segment]
        if symbol: filtered = filtered[filtered['Symbol'] == symbol]
        if expiry_readable and 'ExpiryDate_Readable' in filtered.columns:
            filtered = filtered[filtered['ExpiryDate_Readable'] == expiry_readable]
        if inst_type: filtered = filtered[filtered['InstType'] == inst_type]
        if option_type: filtered = filtered[filtered['OptionType'] == option_type]
        if 'StrikePrice' in filtered.columns:
            filtered = filtered[(filtered['StrikePrice'] >= strike_min) & (filtered['StrikePrice'] <= strike_max)]
        st.write(f"Matching ATM instruments: {len(filtered)}")
        if len(filtered) > 0:
            st.dataframe(filtered[['Token', 'StrikePrice', 'Name']])
        if len(filtered) == 1 and 'Token' in filtered.columns:
            return filtered['Token'].iloc[0]
        elif len(filtered) > 1 and 'Token' in filtered.columns:
            st.write("Multiple instruments match your criteria. Please select one:")
            selected_token = st.selectbox("Select ATM Token", options=filtered['Token'].tolist(), key="select_atm")
            return selected_token
        else:
            return None

    if st.button("Find ATM_CE Token"):
        with st.spinner("Finding ATM_CE token..."):
            atm_token = find_atm_token(
                atm_exch, atm_segment, atm_symbol, atm_expiry,
                atm_inst_type, atm_option_type, st.session_state.atm_min, st.session_state.atm_max
            )
            if atm_token:
                st.session_state.atm_token = atm_token
                st.success(f"ATM_CE Token found: {atm_token}")
                atm_instrument = rs[rs['Token'] == atm_token].iloc[0]
                st.session_state.atm_strike = atm_instrument['StrikePrice'] if 'StrikePrice' in atm_instrument else 0
                st.session_state.atm_name = atm_instrument['Name'] if 'Name' in atm_instrument else "ATM_CE"
                st.session_state.atm_exchange_val = atm_instrument['Exch'] if 'Exch' in atm_instrument else "NSE"
                st.session_state.atm_segment_val = atm_instrument['Segment'] if 'Segment' in atm_instrument else "F&O"
                st.session_state.atm_expiry_val = atm_instrument['ExpiryDate'] if 'ExpiryDate' in atm_instrument else 0
            else:
                st.error("Could not find matching ATM token. Please adjust your selection criteria.")

    if hasattr(st.session_state, 'atm_token') and st.session_state.atm_token:
        st.subheader("NONATM_CE Mapping")
        col1, col2, col3 = st.columns(3)
        with col1:
            nonatm_exch = st.selectbox("Exchange", exchanges, key="nonatm_exch", index=exchanges.index(atm_exch) if atm_exch in exchanges else 0)
            nonatm_segment = st.selectbox("Segment", segments, key="nonatm_segment", index=segments.index(atm_segment) if atm_segment in segments else 0)
            nonatm_symbol = st.selectbox("Symbol", symbols, key="nonatm_symbol", index=symbols.index(atm_symbol) if atm_symbol in symbols else 0)
        with col2:
            nonatm_expiry = st.selectbox("Expiry Date", expiries, key="nonatm_expiry", index=expiries.index(atm_expiry) if atm_expiry in expiries else 0)
            nonatm_inst_type = st.selectbox("Instrument Type", inst_types, key="nonatm_inst_type", index=inst_types.index(atm_inst_type) if atm_inst_type in inst_types else 0)
            nonatm_option_type = st.selectbox("Option Type", option_types, key="nonatm_option_type", index=option_types.index(atm_option_type) if atm_option_type in option_types else 0)
        with col3:
            st.write("Strike Range")
            nonatm_strike_min = st.number_input("Min Strike", value=int(st.session_state.atm_strike - 10*gap), key="nonatm_min")
            nonatm_strike_max = st.number_input("Max Strike", value=int(st.session_state.atm_strike + 10*gap), key="nonatm_max")
            col_e, col_f = st.columns(2)
            with col_e:
                if st.button("−", key="nonatm_dec_min"):
                    st.session_state.nonatm_min -= gap
            with col_f:
                if st.button("+", key="nonatm_inc_min"):
                    st.session_state.nonatm_min += gap
            col_g, col_h = st.columns(2)
            with col_g:
                if st.button("−", key="nonatm_dec_max"):
                    st.session_state.nonatm_max -= gap
            with col_h:
                if st.button("+", key="nonatm_inc_max"):
                    st.session_state.nonatm_max += gap

        def find_nonatm_tokens(exch, segment, symbol, expiry_readable, inst_type, option_type, strike_min, strike_max):
            filtered = rs.copy()
            if exch: filtered = filtered[filtered['Exch'] == exch]
            if segment: filtered = filtered[filtered['Segment'] == segment]
            if symbol: filtered = filtered[filtered['Symbol'] == symbol]
            if expiry_readable and 'ExpiryDate_Readable' in filtered.columns: filtered = filtered[filtered['ExpiryDate_Readable'] == expiry_readable]
            if inst_type: filtered = filtered[filtered['InstType'] == inst_type]
            if option_type: filtered = filtered[filtered['OptionType'] == option_type]
            if 'StrikePrice' in filtered.columns: filtered = filtered[(filtered['StrikePrice'] >= strike_min) & (filtered['StrikePrice'] <= strike_max)]
            filtered = filtered.sort_values('StrikePrice')
            st.write(f"Matching NONATM instruments: {len(filtered)}")
            if len(filtered) > 0:
                st.dataframe(filtered[['Token', 'StrikePrice', 'Name']])
            return filtered

        if st.button("Find NONATM_CE Tokens"):
            with st.spinner("Finding NONATM_CE tokens..."):
                nonatm_tokens_df = find_nonatm_tokens(
                    nonatm_exch, nonatm_segment, nonatm_symbol, nonatm_expiry,
                    nonatm_inst_type, nonatm_option_type, st.session_state.nonatm_min, st.session_state.nonatm_max
                )
                if len(nonatm_tokens_df) > 0:
                    st.session_state.nonatm_tokens_df = nonatm_tokens_df
                    st.session_state.mapping_complete = True
                    st.success(f"Found {len(nonatm_tokens_df)} NONATM_CE tokens!")
                else:
                    st.error("Could not find matching NONATM tokens. Please adjust your selection criteria.")

    # Step 3: Generate and combine mapping with PF_Data.csv columns
    if st.session_state.mapping_complete and hasattr(st.session_state, 'nonatm_tokens_df'):
        st.header("Step 3: Generate FinalPF.csv with All PF Columns")

        # build output_file-like mapping from tokens
        output_data = []
        atm_token = st.session_state.atm_token
        atm_name = st.session_state.atm_name
        atm_exchange = st.session_state.atm_exchange_val
        atm_segment_val = st.session_state.atm_segment_val
        atm_expiry_val = st.session_state.atm_expiry_val
        nonatm_tokens_df = st.session_state.nonatm_tokens_df

        for i, (_, row) in enumerate(nonatm_tokens_df.iterrows()):
            nonatm_token = row['Token']
            nonatm_name = row['Name'] if 'Name' in row else f"NONATM_CE_{i+1}"
            nonatm_exchange = row['Exch'] if 'Exch' in row else "NSE"
            nonatm_segment = row['Segment'] if 'Segment' in row else "F&O"
            nonatm_expiry = row['ExpiryDate'] if 'ExpiryDate' in row else atm_expiry_val
            output_data.append({
                'PF': i+1,
                'ATM_CE': atm_token,
                'NONATM_CE': nonatm_token,
                'Description': f"{atm_name}|{nonatm_name}",
                'Exchange': f"{atm_exchange}|{nonatm_exchange}",
                'Segment': f"{atm_segment_val}|{nonatm_segment}",
                'EXPIRY': f"{atm_expiry_val}|{nonatm_expiry}"
            })
        output_df = pd.DataFrame(output_data)

        # Combine with PF_Data.csv columns
        pf_data = st.session_state.pf_data.copy()
        pf_cols = pf_data.columns.tolist()
        output_cols = output_df.columns.tolist()
        default_row = pf_data.iloc[0].to_dict()

        final_rows = []
        for _, output_row in output_df.iterrows():
            final_row = {}
            for col in pf_cols:
                if col in output_cols:
                    final_row[col] = output_row[col]
                else:
                    final_row[col] = default_row.get(col, "")
            final_rows.append(final_row)

        finalpf_df = pd.DataFrame(final_rows)
        st.subheader("FinalPF.csv Preview (First 10 rows)")
        st.dataframe(finalpf_df.head(10))

        # Download button
        csv = finalpf_df.to_csv(index=False)
        st.download_button(
            label=f"Download FinalPF.csv",
            data=csv,
            file_name="FinalPF.csv",
            mime="text/csv"
        )
        st.success("FinalPF.csv created successfully with PF_Data.csv columns and mapped values.")
else:
    st.info("Please upload both files to proceed with mapping.")

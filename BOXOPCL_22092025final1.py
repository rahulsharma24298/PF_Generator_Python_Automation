import streamlit as st
import pandas as pd
from datetime import datetime
import re

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
    pf_file = st.file_uploader("Upload PF_Data.csv", type=['csv'], key="pf_upload")
    if pf_file:
        st.session_state.pf_data = pd.read_csv(pf_file)
        st.success("PF_Data file uploaded successfully!")
        st.write(f"Shape: {st.session_state.pf_data.shape}")
        st.dataframe(st.session_state.pf_data.head(3))
with col2:
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

    st.subheader("ATM_CE Mapping")

    # Inputs: 1st row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        atm_exch = st.selectbox("Exchange", exchanges, key="atm_exch")
    with col2:
        atm_segment = st.selectbox("Segment", segments, key="atm_segment")
    with col3:
        atm_symbol = st.selectbox("Symbol", symbols, key="atm_symbol")
    with col4:
        atm_expiry = st.selectbox("Expiry Date", expiries, key="atm_expiry")
    # Inputs: 2nd row
    col5, col6, col7 = st.columns(3)
    with col5:
        atm_inst_type = st.selectbox("Instrument Type", inst_types, key="atm_inst_type")
    with col6:
        atm_option_type = st.selectbox("Option Type", option_types, key="atm_option_type")
    with col7:
        filtered_for_strikes = rs[
            (rs['Exch'] == atm_exch) &
            (rs['Segment'] == atm_segment) &
            (rs['Symbol'] == atm_symbol) &
            (rs['ExpiryDate_Readable'] == atm_expiry) &
            (rs['InstType'] == atm_inst_type) &
            (rs['OptionType'] == atm_option_type)
        ]
        strike_options = sorted(filtered_for_strikes['StrikePrice'].unique()) if not filtered_for_strikes.empty else []
        if not strike_options:
            st.warning("No strikes available for selected criteria.")
            atm_strike = None
        else:
            atm_strike = st.selectbox("Strike Price", strike_options, key="atm_strike")

    def find_exact_atm_token(exch, segment, symbol, expiry_readable, inst_type, option_type, strike):
        if strike is None:
            return None, pd.DataFrame()
        filt = rs[
            (rs['Exch'] == exch) &
            (rs['Segment'] == segment) &
            (rs['Symbol'] == symbol) &
            (rs['ExpiryDate_Readable'] == expiry_readable) &
            (rs['InstType'] == inst_type) &
            (rs['OptionType'] == option_type) &
            (rs['StrikePrice'] == strike)
        ]
        if 'Name' in filt.columns:
            filt = filt.sort_values('Name')
        elif 'Description' in filt.columns:
            filt = filt.sort_values('Description')
        else:
            filt = filt.sort_index()
        return (filt['Token'].iloc[0] if not filt.empty else None), filt

    if st.button("Find ATM_CE Token"):
        with st.spinner("Finding ATM_CE token..."):
            atm_token, atm_preview_df = find_exact_atm_token(
                atm_exch, atm_segment, atm_symbol, atm_expiry,
                atm_inst_type, atm_option_type, atm_strike
            )
            if atm_token:
                st.session_state.atm_token = atm_token
                st.success(f"ATM_CE Token found: {atm_token}")
                st.subheader("Matching ATM Instrument:")
                st.dataframe(atm_preview_df)
                atm_instrument = atm_preview_df.iloc[0]
                st.session_state.atm_strike_val = atm_instrument['StrikePrice'] if 'StrikePrice' in atm_instrument else 0
                st.session_state.atm_name = atm_instrument['Name'] if 'Name' in atm_instrument else "ATM_CE"
                st.session_state.atm_exchange_val = atm_instrument['Exch'] if 'Exch' in atm_instrument else "NSE"
                st.session_state.atm_segment_val = atm_instrument['Segment'] if 'Segment' in atm_instrument else "F&O"
                st.session_state.atm_expiry_val = atm_instrument['ExpiryDate'] if 'ExpiryDate' in atm_instrument else 0
                st.session_state.atm_symbol_val = atm_symbol
                st.session_state.atm_inst_type_val = atm_inst_type
                st.session_state.atm_option_type_val = atm_option_type
            else:
                st.error("No matching ATM CE token found for the exact Strike Price.")

    if hasattr(st.session_state, 'atm_token') and st.session_state.atm_token:
        st.subheader("NONATM_CE Mapping")
        col1, col2, col3 = st.columns(3)
        with col1:
            nonatm_exch = st.selectbox("Exchange", exchanges, key="nonatm_exch",
                                       index=exchanges.index(st.session_state.atm_exchange_val) if st.session_state.atm_exchange_val in exchanges else 0)
            nonatm_segment = st.selectbox("Segment", segments, key="nonatm_segment",
                                         index=segments.index(st.session_state.atm_segment_val) if st.session_state.atm_segment_val in segments else 0)
            nonatm_symbol = st.selectbox("Symbol", symbols, key="nonatm_symbol",
                                        index=symbols.index(st.session_state.atm_symbol_val) if 'atm_symbol_val' in st.session_state and st.session_state.atm_symbol_val in symbols else 0)
        with col2:
            nonatm_expiry = st.selectbox("Expiry Date", expiries, key="nonatm_expiry",
                                        index=expiries.index(st.session_state.atm_expiry_val) if st.session_state.atm_expiry_val in expiries else 0)
            nonatm_inst_type = st.selectbox("Instrument Type", inst_types, key="nonatm_inst_type",
                                           index=inst_types.index(st.session_state.atm_inst_type_val) if 'atm_inst_type_val' in st.session_state and st.session_state.atm_inst_type_val in inst_types else 0)
            nonatm_option_type = st.selectbox("Option Type", option_types, key="nonatm_option_type",
                                             index=option_types.index(st.session_state.atm_option_type_val) if 'atm_option_type_val' in st.session_state and st.session_state.atm_option_type_val in option_types else 0)
        with col3:
            st.write("Strike Range")
            nonatm_strike_min = st.number_input("Min Strike", value=int(st.session_state.atm_strike_val - 10000) if 'atm_strike_val' in st.session_state else 0,
                                                key="nonatm_min")
            nonatm_strike_max = st.number_input("Max Strike", value=int(st.session_state.atm_strike_val + 10000) if 'atm_strike_val' in st.session_state else 0,
                                                key="nonatm_max")

    def find_nonatm_tokens(exch, segment, symbol, expiry_readable, inst_type, option_type, strike_min, strike_max):
        filtered = rs.copy()
        if exch:
            filtered = filtered[filtered['Exch'] == exch]
        if segment:
            filtered = filtered[filtered['Segment'] == segment]
        if symbol:
            filtered = filtered[filtered['Symbol'] == symbol]
        if expiry_readable and 'ExpiryDate_Readable' in filtered.columns:
            filtered = filtered[filtered['ExpiryDate_Readable'] == expiry_readable]
        if inst_type:
            filtered = filtered[filtered['InstType'] == inst_type]
        if option_type:
            filtered = filtered[filtered['OptionType'] == option_type]
        if 'StrikePrice' in filtered.columns:
            filtered = filtered[(filtered['StrikePrice'] >= strike_min) & (filtered['StrikePrice'] <= strike_max)]
        if 'Name' in filtered.columns:
            filtered = filtered.sort_values('Name')
        elif 'Description' in filtered.columns:
            filtered = filtered.sort_values('Description')
        else:
            filtered = filtered.sort_index()
        # NO preview or write here
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

    # Step 3: FinalPF.csv with gap filtering and REVERSE PF feature
    if st.session_state.mapping_complete and hasattr(st.session_state, 'nonatm_tokens_df'):
        st.header("Step 3: Generate FinalPF.csv and Download")

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

        strike_gap = st.number_input(
            "Strike Gap (enter in Rupees)", min_value=0, value=100, step=50,
            help="If 100, remove rows where Description ends with '50CE'. If 50, remove rows ending with '00CE'. 0 keeps all rows."
        )

        def filter_by_custom_gap(df, gap):
            if gap == 0:
                return df.copy()
            filtered_rows = []
            for idx, row in df.iterrows():
                description = row['Description'].split('|')[-1]
                match = re.search(r'(\d+)(\d{2})CE$', description)
                if match:
                    last_two_digits = int(match.group(2))
                    if gap == 100:
                        if last_two_digits != 50:
                            filtered_rows.append(row)
                    elif gap == 50:
                        if last_two_digits != 0:
                            filtered_rows.append(row)
                    else:
                        filtered_rows.append(row)
                else:
                    filtered_rows.append(row)
            return pd.DataFrame(filtered_rows)

        filtered_finalpf_df = filter_by_custom_gap(finalpf_df, strike_gap).sort_values('Description')

        # --- NEW: Add Reverse PF functionality ---
        if 'OPCL' not in filtered_finalpf_df.columns:
            st.warning("Column 'OPCL' not found in preview. No reverse PF functionality will be shown.")
            reverse_df = None
            st.download_button(
                label="Download FinalPF.csv (gap applied)",
                data=filtered_finalpf_df.to_csv(index=False),
                file_name="FinalPF.csv",
                mime="text/csv"
            )
        else:
            add_reverse = st.button('Add Reverse PF')
            if add_reverse:
                reversed_rows = []
                for _, row in filtered_finalpf_df.iterrows():
                    row_copy = row.copy()
                    if row_copy['OPCL'] == 'OPEN':
                        row_copy['OPCL'] = 'CLOSE'
                    elif row_copy['OPCL'] == 'CLOSE':
                        row_copy['OPCL'] = 'OPEN'
                    else:
                        pass
                    reversed_rows.append(row_copy)
                reverse_df = pd.DataFrame(reversed_rows)
                combined_df = pd.concat([filtered_finalpf_df, reverse_df], ignore_index=True)
                st.subheader("FinalPF with Reverse PF")
                st.dataframe(combined_df)
                csv_rev = combined_df.to_csv(index=False)
                st.download_button(
                    label='Download FinalPF_with_Reverse.csv',
                    data=csv_rev,
                    file_name='FinalPF_with_Reverse.csv',
                    mime='text/csv'
                )
            else:
                st.download_button(
                    label="Download FinalPF.csv (gap applied)",
                    data=filtered_finalpf_df.to_csv(index=False),
                    file_name="FinalPF.csv",
                    mime="text/csv"
                )
        # --- END OF Reverse PF step ---

else:
    st.info("Please upload both files to proceed with mapping.")

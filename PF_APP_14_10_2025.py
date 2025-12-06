import streamlit as st
import pandas as pd
from datetime import datetime
import re

st.set_page_config(page_title="Excel File Mapper", layout="wide")
st.title("Excel File Mapping Tool")
st.markdown("""
**This tool helps you map data between two Excel files:**

- **PF_Data.csv** - Contains strategy parameters
- **ResultSet.xlsx** - Contains instrument data

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
if 'finalpf_df' not in st.session_state:
    st.session_state.finalpf_df = None

# ------ Step 1: Upload Files ------
st.header("Step 1: Upload Input Files")

col1, col2 = st.columns(2)
with col1:
    pf_file = st.file_uploader("Upload PF_Data.csv", type=['csv'], key="pf_upload")
    if pf_file:
        st.session_state.pf_data = pd.read_csv(pf_file)
        st.success("PF_Data file uploaded successfully!")
        st.write(f"Rows: {st.session_state.pf_data.shape[0]}, Columns: {st.session_state.pf_data.shape[1]}")
        st.dataframe(st.session_state.pf_data.head(3), height=150)
with col2:
    resultset_file = st.file_uploader("Upload ResultSet.xlsx", type=['xlsx'], key="resultset_upload")
    if resultset_file:
        st.session_state.resultset_data = pd.read_excel(resultset_file)
        st.success("ResultSet file uploaded successfully!")
        st.write(f"Rows: {st.session_state.resultset_data.shape[0]}, Columns: {st.session_state.resultset_data.shape[1]}")
        st.dataframe(st.session_state.resultset_data.head(3), height=150)

if st.session_state.pf_data is not None and st.session_state.resultset_data is not None:

    rs = st.session_state.resultset_data.copy()

    # Convert ExpiryDate to human readable format
    if 'ExpiryDate' in rs.columns:
        epoch_start = datetime(1980, 1, 1)
        try:
            if pd.api.types.is_numeric_dtype(rs['ExpiryDate']):
                rs['ExpiryDate_DT'] = epoch_start + pd.to_timedelta(rs['ExpiryDate'], unit='s')
            else:
                rs['ExpiryDate_DT'] = pd.to_datetime(rs['ExpiryDate'])
            rs['ExpiryDate_Readable'] = rs['ExpiryDate_DT'].dt.strftime('%d/%m/%Y')
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

    # ------ Step 2: ATM CE token selection ------
    st.header("Step 2: Specify Multiple ATM_CE Strike Prices")

    atm_cols = st.columns(6)
    with atm_cols[0]:
        atm_exch = st.selectbox("Exchange", exchanges, key="multi_atm_exch")
    with atm_cols[1]:
        atm_segment = st.selectbox("Segment", segments, key="multi_atm_segment")
    with atm_cols[2]:
        atm_symbol = st.selectbox("Symbol", symbols, key="multi_atm_symbol")
    with atm_cols[3]:
        atm_expiry = st.selectbox("Expiry Date", expiries, key="multi_atm_expiry")
    with atm_cols[4]:
        atm_inst_type = st.selectbox("Instrument Type", inst_types, key="multi_atm_inst_type")
    with atm_cols[5]:
        atm_option_type = st.selectbox("Option Type", option_types, key="multi_atm_option_type")

    st.markdown("### Enter one or more ATM CE Strike Prices (rounded whole numbers):")
    if 'strike_prices' not in st.session_state:
        st.session_state.strike_prices = [0]

    # Dynamic input boxes for strikes with add/remove buttons
    num_strikes = len(st.session_state.strike_prices)
    for i in range(num_strikes):
        cols = st.columns([3, 1])
        st.session_state.strike_prices[i] = cols[0].number_input(
            f"Strike {i + 1}",
            min_value=0,
            value=st.session_state.strike_prices[i],
            key=f"strike_input_{i}"
        )
        if num_strikes > 1:
            if cols[1].button('Remove', key=f'remove_strike_{i}'):
                st.session_state.strike_prices.pop(i)
                st.rerun()  # replaces experimental_rerun

    if st.button("Add Strike Price"):
        st.session_state.strike_prices.append(0)
        st.rerun()  # replaces experimental_rerun

    def find_multiple_atm_tokens(exch, segment, symbol, expiry_readable, inst_type, option_type, strikes):
        tokens = []
        for strike in strikes:
            filt = rs[
                (rs['Exch'] == exch) &
                (rs['Segment'] == segment) &
                (rs['Symbol'] == symbol) &
                (rs['ExpiryDate_Readable'] == expiry_readable) &
                (rs['InstType'] == inst_type) &
                (rs['OptionType'] == option_type) &
                (rs['StrikePrice'] == strike)
            ]
            token = filt['Token'].iloc[0] if not filt.empty else None
            tokens.append({'StrikePrice': strike, 'Token': token})
        return tokens

    if st.button("Find ATM_CE Tokens for Entered Strikes"):
        with st.spinner("Looking up ATM_CE tokens..."):
            results = find_multiple_atm_tokens(
                atm_exch, atm_segment, atm_symbol, atm_expiry,
                atm_inst_type, atm_option_type, st.session_state.strike_prices
            )
            all_found = True
            for res in results:
                strike = res['StrikePrice']
                token = res['Token']
                if token:
                    st.success(f"Found Token for Strike {strike}: {token}")
                else:
                    st.warning(f"No Token found for Strike {strike}")
                    all_found = False
            if all_found:
                st.session_state.atm_tokens_multi = {r['StrikePrice']: r['Token'] for r in results if r['Token']}
            else:
                st.session_state.atm_tokens_multi = {r['StrikePrice']: r['Token'] for r in results if r['Token']}

    # ------ Step 3: NONATM_CE filtering and CSV Generation ------
    if 'atm_tokens_multi' in st.session_state and st.session_state.atm_tokens_multi:
        st.header("Step 3: Configure NONATM_CE Strike Range and Generate Portfolio File")

        settings_cols = st.columns(4)
        with settings_cols[0]:
            strike_range = st.number_input(
                "Strike Range (+/- Rupees) for NONATM_CE tokens", min_value=0, value=50000, step=50,
                help="Defines the range around each ATM CE strike to find NONATM CE tokens."
            )
        with settings_cols[1]:
            strike_gap = st.number_input(
                "Strike Gap (Rupees)", min_value=0, value=0, step=50,
                help="Filter final rows by strike gap. 0 disables."
            )
        with settings_cols[2]:
            add_reverse_pf = st.checkbox("Add Reverse PF for final output")

        nonatm_tokens_per_atm = {}
        for atm_strike, atm_token in st.session_state.atm_tokens_multi.items():
            low_strike = max(0, atm_strike - strike_range)
            high_strike = atm_strike + strike_range

            filtered_nonatm = rs[
                (rs['Exch'] == atm_exch) &
                (rs['Segment'] == atm_segment) &
                (rs['Symbol'] == atm_symbol) &
                (rs['ExpiryDate_Readable'] == atm_expiry) &
                (rs['InstType'] == atm_inst_type) &
                (rs['OptionType'] == atm_option_type) &
                (rs['StrikePrice'] >= low_strike) &
                (rs['StrikePrice'] <= high_strike)
            ].copy()

            st.write(f"ATM CE Strike {atm_strike}: {len(filtered_nonatm)} NONATM_CE tokens found in range [{low_strike} - {high_strike}]")

            nonatm_tokens_per_atm[atm_strike] = filtered_nonatm

        generate_btn = st.button("Generate Combined FinalPF")

        # -------- CHANGE: Format StrikePrice for Output --------
        def format_strike_price(strike):
            # Accept int, float, or string
            try:
                strike = int(strike)
                return str(strike // 100)
            except Exception:
                return str(strike)

        # Change: This builds readable option description with divided strike price
        def build_option_description(row):
            symbol = row.get('Symbol', '')
            expiry = row.get('ExpiryDate_Readable', '') if 'ExpiryDate_Readable' in row else row.get('ExpiryDate', '')
            strike = row.get('StrikePrice', '')
            opt_type = row.get('OptionType', '')

            # Dividing StrikePrice by 100 for output
            strike_formatted = format_strike_price(strike)
            # Remove trailing '.0' if present
            if strike_formatted.endswith('.0'):
                strike_formatted = strike_formatted[:-2]

            return f"{symbol} {expiry} {strike_formatted} {opt_type}".strip()

        if generate_btn:
            output_data = []
            pf_data = st.session_state.pf_data.copy()
            pf_cols = pf_data.columns.tolist()
            default_row = pf_data.iloc[0].to_dict()

            for atm_strike, nonatm_df in nonatm_tokens_per_atm.items():
                atm_token = st.session_state.atm_tokens_multi.get(atm_strike)
                if atm_token is None or nonatm_df.empty:
                    continue

                atm_row = rs[
                    (rs['Exch'] == atm_exch) &
                    (rs['Segment'] == atm_segment) &
                    (rs['Symbol'] == atm_symbol) &
                    (rs['ExpiryDate_Readable'] == atm_expiry) &
                    (rs['InstType'] == atm_inst_type) &
                    (rs['OptionType'] == atm_option_type) &
                    (rs['StrikePrice'] == atm_strike)
                ]
                if not atm_row.empty:
                    atm_row = atm_row.iloc[0]
                else:
                    atm_row = pd.Series()

                # --- Change: Now builds both sides of Description with formatted strikes
                atm_description = build_option_description(atm_row if isinstance(atm_row, pd.Series) else pd.Series())

                for i, (_, row) in enumerate(nonatm_df.iterrows()):
                    nonatm_token = row['Token']
                    if nonatm_token == atm_token:
                        continue
                    nonatm_description = build_option_description(row)
                    nonatm_name = row['Name'] if 'Name' in row else f"NONATM_CE_{i + 1}"
                    nonatm_exchange = row['Exch'] if 'Exch' in row else "NSE"
                    nonatm_segment = row['Segment'] if 'Segment' in row else "F&O"
                    nonatm_expiry = row['ExpiryDate'] if 'ExpiryDate' in row else atm_expiry

                    opcl_val = 'OPEN'
                    if 'OPCL' in pf_cols:
                        opcl_val = default_row.get('OPCL', 'OPEN')

                    output_data.append({
                        'PF': f"{atm_strike}_{i + 1}",
                        'ATM_CE': atm_token,
                        'NONATM_CE': nonatm_token,
                        'Description': f"{atm_description}|{nonatm_description}",
                        'Exchange': f"{atm_row.get('Exch', 'NSE')}|{nonatm_exchange}",
                        'Segment': f"{atm_row.get('Segment', 'F&O')}|{nonatm_segment}",
                        'EXPIRY': f"{atm_row.get('ExpiryDate', atm_expiry)}|{nonatm_expiry}",
                        'OPCL': opcl_val
                    })

            if not output_data:
                st.error("No NONATM_CE tokens found for the given ATM CE ranges after filtering.")
                st.session_state.finalpf_df = None
            else:
                combined_output_df = pd.DataFrame(output_data)

                final_rows = []
                for _, output_row in combined_output_df.iterrows():
                    final_row = {}
                    for col in pf_cols:
                        if col in combined_output_df.columns:
                            final_row[col] = output_row[col]
                        else:
                            final_row[col] = default_row.get(col, "")
                    final_rows.append(final_row)
                finalpf_df = pd.DataFrame(final_rows)

                def filter_by_custom_gap(df, gap):
                    if gap == 0:
                        return df.copy()
                    filtered_rows = []
                    for _, row in df.iterrows():
                        description = row.get('Description', '').split('|')[-1]
                        match = re.search(r'(\d+)(\d{2}) CE$', description)
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

                filtered_finalpf_df = filter_by_custom_gap(finalpf_df, strike_gap)

                # FINAL SORT BY DESCRIPTION (A-Z increasing)
                filtered_finalpf_df = filtered_finalpf_df.sort_values('Description', ascending=True).reset_index(drop=True)

                if add_reverse_pf and 'OPCL' in filtered_finalpf_df.columns:
                    reversed_rows = []
                    for _, row in filtered_finalpf_df.iterrows():
                        row_copy = row.copy()
                        if row_copy['OPCL'] == 'OPEN':
                            row_copy['OPCL'] = 'CLOSE'
                        elif row_copy['OPCL'] == 'CLOSE':
                            row_copy['OPCL'] = 'OPEN'
                        reversed_rows.append(row_copy)
                    reverse_df = pd.DataFrame(reversed_rows)
                    combined_df = pd.concat([filtered_finalpf_df, reverse_df], ignore_index=True)
                    st.session_state.finalpf_df = combined_df.sort_values('Description', ascending=True).reset_index(drop=True)
                else:
                    st.session_state.finalpf_df = filtered_finalpf_df

        if st.session_state.finalpf_df is not None:
            st.header("Final Portfolio Mapping Output")
            st.dataframe(st.session_state.finalpf_df, height=300)

            # LAST SORT before CSV download!
            sorted_final_df = st.session_state.finalpf_df.sort_values('Description', ascending=True).reset_index(drop=True)
            csv_data = sorted_final_df.to_csv(index=False)
            download_name = 'FinalPF_with_Reverse.csv' if (add_reverse_pf and 'OPCL' in st.session_state.finalpf_df.columns) else 'FinalPF.csv'

            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name=download_name,
                mime='text/csv'
            )

else:
    st.info("Please upload both PF_Data.csv and ResultSet.xlsx files to proceed.")

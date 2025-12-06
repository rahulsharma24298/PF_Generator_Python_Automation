import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re
import xml.etree.ElementTree as ET

st.set_page_config(page_title="Multi-Strategy PF Generator", layout="wide")
st.title("PF Generator: Multi-Strategy Workspace")

strategy = st.sidebar.selectbox("Select Strategy", ["CONREV", "BOX"], index=0)
st.sidebar.markdown("Choose which logic to run. Output file will have strategy name prefix.")

# Helper for expiry conversion
def convert_expiry_dates(rs):
    epoch_start = datetime(1980, 1, 1)
    if 'ExpiryDate' in rs.columns:
        try:
            rs['ExpiryDate_DT'] = rs['ExpiryDate'].apply(lambda x: epoch_start + timedelta(seconds=x))
            rs['ExpiryDate_Readable'] = rs['ExpiryDate_DT'].dt.strftime('%d/%m/%Y')
            rs.sort_values('ExpiryDate_DT', inplace=True)
        except Exception as e:
            st.error(f"Error converting ExpiryDate: {e}")
            rs['ExpiryDate_Readable'] = rs['ExpiryDate'].astype(str)
    return rs

if strategy == "CONREV":
    st.header("CONREV Strategy File Generation")

    if 'conrev_pf_data_df' not in st.session_state:
        st.session_state.conrev_pf_data_df = None
    if 'conrev_resultset_df' not in st.session_state:
        st.session_state.conrev_resultset_df = None
    if 'conrev_ltp_df' not in st.session_state:
        st.session_state.conrev_ltp_df = None

    col1, col2, col3 = st.columns(3)
    with col1:
        pf_upload = st.file_uploader("Upload pf_data.csv", type=['csv'], key='conrev_pf_data_uploader')
        if pf_upload:
            st.session_state.conrev_pf_data_df = pd.read_csv(pf_upload)
            st.success(f"pf_data.csv uploaded ({len(st.session_state.conrev_pf_data_df)} rows)")
    with col2:
        resultset_upload = st.file_uploader("Upload resultset.xlsx", type=['xlsx'], key='conrev_resultset_uploader')
        if resultset_upload:
            rs = pd.read_excel(resultset_upload)
            rs = convert_expiry_dates(rs)
            st.session_state.conrev_resultset_df = rs
            st.success(f"resultset.xlsx uploaded ({len(rs)} rows)")
    with col3:
        ltp_upload = st.file_uploader("Upload LTP_File.xml", type=['xml'], key='conrev_ltp_uploader')
        if ltp_upload:
            try:
                ltp_tree = ET.parse(ltp_upload)
                ltp_root = ltp_tree.getroot()
                ltp_items = []
                for md in ltp_root.findall('.//MarketData'):
                    symbol = md.attrib['Symbol']
                    token = int(md.attrib['Token'])
                    ltp = float(md.attrib.get('LTP', '0')) * 100
                    ltp_items.append({'Symbol': symbol, 'Token': token, 'LTP': ltp})
                ltp_df = pd.DataFrame(ltp_items).drop_duplicates()
                st.session_state.conrev_ltp_df = ltp_df
                st.success("LTP_File.xml uploaded and parsed.")
            except Exception as e:
                st.error(f"Error loading/parsing LTP_File.xml: {e}")

    if (st.session_state.conrev_pf_data_df is not None and
        st.session_state.conrev_resultset_df is not None and
        st.session_state.conrev_ltp_df is not None):

        rs = st.session_state.conrev_resultset_df.copy()
        ltp_df = st.session_state.conrev_ltp_df

        expiries = sorted(rs['ExpiryDate_Readable'].dropna().unique())
        selected_expiry = st.selectbox("Select Expiry Date", expiries, key="conrev_expiry")
        strikes_up_down = st.number_input("Strikes Up-Down (number above/below ATM)", min_value=0, max_value=10, value=2, key="conrev_strikes_ud")

        futstk_symbols = rs[(rs['ExpiryDate_Readable'] == selected_expiry) & (rs['InstType'] == 'FUTSTK')]['Symbol'].unique()
        st.write(f"Number of FUTSTK symbols for expiry {selected_expiry}: {len(futstk_symbols)}")

        if st.button(f"Generate CONREV_OPTFILE.csv"):
            output_rows = []
            for symbol_row in ltp_df.itertuples():
                symbol = symbol_row.Symbol
                fut_token = symbol_row.Token
                fut_ltp = symbol_row.LTP
                if symbol not in futstk_symbols:
                    continue
                fut_rows = rs[(rs['Symbol'] == symbol) & (rs['ExpiryDate_Readable'] == selected_expiry) & (rs['InstType'] == 'FUTSTK')]
                if fut_rows.empty:
                    continue
                ce_opts = rs[(rs['Symbol'] == symbol) & (rs['ExpiryDate_Readable'] == selected_expiry) &
                             (rs['InstType'] == 'OPTSTK') & (rs['OptionType'] == 'CE')].sort_values('StrikePrice')
                if ce_opts.empty:
                    continue
                strikes = ce_opts['StrikePrice'].tolist()
                atm_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - fut_ltp))
                idx_start = max(atm_idx - strikes_up_down, 0)
                idx_end = min(atm_idx + strikes_up_down + 1, len(strikes))
                indices = list(range(idx_start, idx_end))
                selected_strikes = [strikes[i] for i in indices]
                for strike in selected_strikes:
                    opt_rows = ce_opts[ce_opts['StrikePrice'] == strike]
                    for opt_row in opt_rows.itertuples():
                        opt_token = opt_row.Token
                        fut_res = rs[(rs['Token'] == fut_token) & (rs['InstType'] == 'FUTSTK')]
                        opt_res = rs[(rs['Token'] == opt_token) & (rs['InstType'] == 'OPTSTK')]
                        exch_fut = fut_res['Exch'].iloc[0] if not fut_res.empty else ''
                        exch_opt = opt_res['Exch'].iloc[0] if not opt_res.empty else ''
                        seg_fut = fut_res['Segment'].iloc[0] if not fut_res.empty else ''
                        seg_opt = opt_res['Segment'].iloc[0] if not opt_res.empty else ''
                        expiry_fut = fut_res['ExpiryDate'].iloc[0] if not fut_res.empty else ''
                        expiry_opt = opt_res['ExpiryDate'].iloc[0] if not opt_res.empty else ''
                        desc_fut = f"{symbol} {selected_expiry}"
                        desc_opt = f"{symbol} {selected_expiry} {strike} CE"
                        output_rows.append({
                            'Exchange': f"{exch_fut}|{exch_opt}",
                            'Segment': f"{seg_fut}|{seg_opt}",
                            'Description': f"{desc_fut}|{desc_opt}",
                            'CLIENTCODE': '',  # Use pf_data first row below
                            'EXPIRY': f"{expiry_fut}|{expiry_opt}",
                            'FUT': fut_token,
                            'OPT': opt_token
                        })
            pf_cols = st.session_state.conrev_pf_data_df.columns.tolist()
            pf_first_row = st.session_state.conrev_pf_data_df.iloc[0].to_dict()
            merged_rows = []
            for row in output_rows:
                merged_row = {}
                for col in pf_cols:
                    if col in row and col != 'CLIENTCODE':
                        merged_row[col] = row[col]
                    elif col == 'CLIENTCODE':
                        merged_row[col] = pf_first_row.get('CLIENTCODE', '')
                    else:
                        merged_row[col] = pf_first_row.get(col, '')
                merged_rows.append(merged_row)
            final_crv_df = pd.DataFrame(merged_rows, columns=pf_cols)
            st.subheader("Preview of CONREV_OPTFILE.csv (5 rows)")
            st.dataframe(final_crv_df.head(5))
            filename = f"{strategy}_OPTFILE.csv"
            csv = final_crv_df.to_csv(index=False)
            st.download_button(f"Download {filename}", data=csv, file_name=filename, mime='text/csv')

elif strategy == "BOX":
    st.header("BOX Strategy File Generation")

    if 'box_pf_data' not in st.session_state:
        st.session_state.box_pf_data = None
    if 'box_resultset' not in st.session_state:
        st.session_state.box_resultset = None
    if 'box_mapping_complete' not in st.session_state:
        st.session_state.box_mapping_complete = False

    col1, col2 = st.columns(2)
    with col1:
        pf_file = st.file_uploader("Upload PF_Data.csv", type=['csv'], key="box_pf_upload")
        if pf_file:
            st.session_state.box_pf_data = pd.read_csv(pf_file)
            st.success("PF_Data uploaded")
            st.dataframe(st.session_state.box_pf_data.head(3))
    with col2:
        resultset_file = st.file_uploader("Upload ResultSet.xlsx", type=['xlsx'], key="box_resultset_upload")
        if resultset_file:
            rs = pd.read_excel(resultset_file)
            epoch_start = datetime(1980, 1, 1)
            rs['ExpiryDate_DT'] = rs['ExpiryDate'].apply(lambda x: epoch_start + timedelta(seconds=x))
            rs['ExpiryDate_Readable'] = rs['ExpiryDate_DT'].dt.strftime('%d/%m/%y')
            rs = rs.sort_values('ExpiryDate_DT')
            st.session_state.box_resultset = rs
            st.success("ResultSet uploaded")
            st.dataframe(rs.head(3))

    if st.session_state.box_pf_data is not None and st.session_state.box_resultset is not None:
        rs = st.session_state.box_resultset.copy()

        exchanges = rs['Exch'].unique().tolist()
        segments = rs['Segment'].unique().tolist()
        symbols = rs['Symbol'].unique().tolist()
        expiries = rs['ExpiryDate_Readable'].unique().tolist()
        inst_types = rs['InstType'].unique().tolist()
        option_types = rs['OptionType'].unique().tolist()

        st.header("Step 2: Parameter Mapping")

        st.subheader("Available Instruments in ResultSet")
        if st.checkbox("Show available instruments"):
            st.dataframe(rs[['Exch', 'Segment', 'Symbol', 'ExpiryDate_Readable', 'InstType', 'OptionType', 'StrikePrice', 'Token', 'Name']])

        st.subheader("ATM_CE Mapping")
        col1, col2, col3 = st.columns(3)
        with col1:
            atm_exch = st.selectbox("Exchange", exchanges, key="box_atm_exch")
            atm_segment = st.selectbox("Segment", segments, key="box_atm_segment")
            atm_symbol = st.selectbox("Symbol", symbols, key="box_atm_symbol")
        with col2:
            atm_expiry = st.selectbox("Expiry Date", expiries, key="box_atm_expiry")
            atm_inst_type = st.selectbox("Instrument Type", inst_types, key="box_atm_inst_type")
            atm_option_type = st.selectbox("Option Type", option_types, key="box_atm_option_type")
        with col3:
            filtered = rs[(rs['Symbol'] == atm_symbol) & (rs['ExpiryDate_Readable'] == atm_expiry) & (rs['OptionType'] == atm_option_type)]
            default_min = int(filtered['StrikePrice'].min()) if not filtered.empty else 0
            default_max = int(filtered['StrikePrice'].max()) if not filtered.empty else 0
            atm_min = st.number_input("Min Strike", value=default_min, key="box_atm_min")
            atm_max = st.number_input("Max Strike", value=default_max, key="box_atm_max")

        def find_atm_token(exch, segment, symbol, expiry_readable, inst_type, option_type, strike_min, strike_max):
            filtered = rs.copy()
            if exch: filtered = filtered[filtered['Exch'] == exch]
            if segment: filtered = filtered[filtered['Segment'] == segment]
            if symbol: filtered = filtered[filtered['Symbol'] == symbol]
            if expiry_readable and 'ExpiryDate_Readable' in filtered.columns:
                filtered = filtered[filtered['ExpiryDate_Readable'] == expiry_readable]
            if inst_type: filtered = filtered[filtered['InstType'] == inst_type]
            if option_type: filtered = filtered[filtered['OptionType'] == option_type]
            filtered = filtered[(filtered['StrikePrice'] >= strike_min) & (filtered['StrikePrice'] <= strike_max)]
            st.write(f"Matching ATM instruments: {len(filtered)}")
            if len(filtered) > 0:
                st.dataframe(filtered[['Token', 'StrikePrice', 'Name']])
            if len(filtered) == 1 and 'Token' in filtered.columns:
                return filtered['Token'].iloc[0]
            elif len(filtered) > 1 and 'Token' in filtered.columns:
                st.write("Select one ATM Token")
                selected = st.selectbox("ATM Token Select", filtered['Token'].tolist())
                return selected
            return None

        if st.button("Find ATM_CE Token"):
            with st.spinner("Finding ATM_CE token..."):
                token = find_atm_token(atm_exch, atm_segment, atm_symbol, atm_expiry, atm_inst_type, atm_option_type, atm_min, atm_max)
                if token:
                    st.session_state.box_atm_token = token
                    st.success(f"Found ATM Token: {token}")
                    atm_inst = rs[rs['Token'] == token].iloc[0]
                    st.session_state.box_atm_strike = atm_inst['StrikePrice']
                    st.session_state.box_atm_name = atm_inst['Name']
                    st.session_state.box_atm_exchange_val = atm_inst['Exch']
                    st.session_state.box_atm_segment_val = atm_inst['Segment']
                    st.session_state.box_atm_expiry_val = atm_inst['ExpiryDate']

        if hasattr(st.session_state, 'box_atm_token'):
            st.subheader("NONATM_CE Mapping")
            col1, col2, col3 = st.columns(3)
            with col1:
                # Safe index fallback to avoid ValueError
                atm_name_symbol = st.session_state.box_atm_name.split()[0] if st.session_state.box_atm_name else ""
                default_sym_idx = 0
                try:
                    default_sym_idx = symbols.index(atm_name_symbol)
                except ValueError:
                    default_sym_idx = 0
                nonatm_exch = st.selectbox("Exchange", exchanges, key="nonatm_exch", index=exchanges.index(st.session_state.box_atm_exchange_val) if st.session_state.box_atm_exchange_val in exchanges else 0)
                nonatm_segment = st.selectbox("Segment", segments, key="nonatm_segment", index=segments.index(st.session_state.box_atm_segment_val) if st.session_state.box_atm_segment_val in segments else 0)
                nonatm_symbol = st.selectbox("Symbol", symbols, key="nonatm_symbol", index=default_sym_idx)
            with col2:
                nonatm_expiry = st.selectbox("Expiry Date", expiries, key="nonatm_expiry", index=expiries.index(st.session_state.box_atm_expiry_val) if st.session_state.box_atm_expiry_val in expiries else 0)
                nonatm_inst_type = st.selectbox("Instrument Type", inst_types, key="nonatm_inst_type", index=inst_types.index(atm_inst_type) if atm_inst_type in inst_types else 0)
                nonatm_option_type = st.selectbox("Option Type", option_types, key="nonatm_option_type", index=option_types.index(atm_option_type) if atm_option_type in option_types else 0)
            with col3:
                nonatm_min = st.number_input("Min Strike", value=st.session_state.box_atm_strike - 10000, key="nonatm_min")
                nonatm_max = st.number_input("Max Strike", value=st.session_state.box_atm_strike + 10000, key="nonatm_max")

            def find_nonatm_tokens(exch, segment, symbol, expiry_readable, inst_type, option_type, strike_min, strike_max):
                filt = rs.copy()
                if exch: filt = filt[filt['Exch'] == exch]
                if segment: filt = filt[filt['Segment'] == segment]
                if symbol: filt = filt[filt['Symbol'] == symbol]
                if expiry_readable and 'ExpiryDate_Readable' in filt.columns:
                    filt = filt[filt['ExpiryDate_Readable'] == expiry_readable]
                if inst_type: filt = filt[filt['InstType'] == inst_type]
                if option_type: filt = filt[filt['OptionType'] == option_type]
                filt = filt[(filt['StrikePrice'] >= strike_min) & (filt['StrikePrice'] <= strike_max)]
                filt = filt.sort_values('StrikePrice')
                st.write(f"Matching NONATM instruments: {len(filt)}")
                if len(filt) > 0:
                    st.dataframe(filt[['Token', 'StrikePrice', 'Name']])
                return filt

            if st.button("Find NONATM_CE Tokens"):
                with st.spinner("Finding NONATM_CE tokens..."):
                    nonatm_tokens_df = find_nonatm_tokens(nonatm_exch, nonatm_segment, nonatm_symbol, nonatm_expiry, nonatm_inst_type, nonatm_option_type, nonatm_min, nonatm_max)
                    if len(nonatm_tokens_df) > 0:
                        st.session_state.box_nonatm_tokens_df = nonatm_tokens_df
                        st.session_state.box_mapping_complete = True
                        st.success(f"Found {len(nonatm_tokens_df)} NONATM_CE tokens!")
                    else:
                        st.error("No matching NONATM tokens found.")

        if st.session_state.box_mapping_complete and 'box_nonatm_tokens_df' in st.session_state:
            st.header("Step 3: Generate FinalPF.csv with All PF Columns")
            output_data = []
            atm_token = st.session_state.box_atm_token
            atm_name = st.session_state.box_atm_name
            atm_exchange = st.session_state.box_atm_exchange_val
            atm_segment_val = st.session_state.box_atm_segment_val
            atm_expiry_val = st.session_state.box_atm_expiry_val
            nonatm_tokens_df = st.session_state.box_nonatm_tokens_df

            for i, (_, row) in enumerate(nonatm_tokens_df.iterrows()):
                nonatm_token = row['Token']
                nonatm_name = row.get('Name', f"NONATM_CE_{i+1}")
                nonatm_exchange = row.get('Exch', "NSE")
                nonatm_segment = row.get('Segment', "F&O")
                nonatm_expiry = row.get('ExpiryDate', atm_expiry_val)
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

            pf_data = st.session_state.box_pf_data.copy()
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
            st.subheader("FinalPF.csv Preview (All rows - Before Gap)")
            st.dataframe(finalpf_df.sort_values('Description'))

            strike_gap = st.number_input("Strike Gap (enter in Rupees)", min_value=0, value=100, step=50,
                                        help="If 100, remove rows where Description ends with '50CE'. If 50, remove rows ending with '00CE'. 0 keeps all rows.")

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

            st.subheader(f"FinalPF.csv Preview (All rows - After Gap {strike_gap})")
            st.dataframe(filtered_finalpf_df)

            csv = filtered_finalpf_df.to_csv(index=False)
            st.download_button(
                label="Download FinalPF.csv (gap applied)",
                data=csv,
                file_name="FinalPF.csv",
                mime="text/csv"
            )

else:
    st.info("Please upload both files to proceed with mapping.")

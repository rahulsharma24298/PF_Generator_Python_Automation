import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta


st.set_page_config(page_title="PF Generator", layout="wide")
st.title("PF Generator: Exact Structure and Merging for final_CRV.csv")


# --- Session state ---
if 'pf_data_df' not in st.session_state:
    st.session_state.pf_data_df = None
if 'resultset_df' not in st.session_state:
    st.session_state.resultset_df = None
if 'ltp_df' not in st.session_state:
    st.session_state.ltp_df = None


# --- File uploads ---
st.header("Step 1: Upload Files")
col1, col2, col3 = st.columns(3)


with col1:
    pf_upload = st.file_uploader("Upload pf_data.csv", type=['csv'], key='pf_data_uploader')
    if pf_upload:
        try:
            st.session_state.pf_data_df = pd.read_csv(pf_upload)
            st.success(f"pf_data.csv uploaded ({len(st.session_state.pf_data_df)} rows)")
        except Exception as e:
            st.error(f"Error loading pf_data.csv: {e}")


with col2:
    resultset_upload = st.file_uploader("Upload resultset.xlsx", type=['xlsx'], key='resultset_uploader')
    if resultset_upload:
        try:
            rs = pd.read_excel(resultset_upload)
            epoch_start = datetime(1980, 1, 1)
            if 'ExpiryDate' in rs.columns:
                rs['ExpiryDate_DT'] = rs['ExpiryDate'].apply(lambda x: epoch_start + timedelta(seconds=x))
                rs['ExpiryDate_Readable'] = rs['ExpiryDate_DT'].dt.strftime('%d/%m/%Y')
                rs.sort_values('ExpiryDate_DT', inplace=True)
            st.session_state.resultset_df = rs
            st.success(f"resultset.xlsx uploaded ({len(rs)} rows)")
        except Exception as e:
            st.error(f"Error loading resultset.xlsx: {e}")


with col3:
    ltp_upload = st.file_uploader("Upload LTP_File.xml", type=['xml'], key='ltp_uploader')
    if ltp_upload:
        try:
            ltp_tree = ET.parse(ltp_upload)
            ltp_root = ltp_tree.getroot()
            ltp_items = []
            for md in ltp_root.findall('.//MarketData'):
                symbol = md.attrib['Symbol']
                token = int(md.attrib['Token'])
                # Read HIGH attribute instead of LTP, fallback to 0 if missing, multiply by 100 as before
                high_value = float(md.attrib.get('HIGH', '0')) * 100
                ltp_items.append({'Symbol': symbol, 'Token': token, 'LTP': high_value})
            ltp_df = pd.DataFrame(ltp_items).drop_duplicates()
            st.session_state.ltp_df = ltp_df
            st.success("LTP_File.xml uploaded and parsed.")
        except Exception as e:
            st.error(f"Error loading/parsing LTP_File.xml: {e}")


# --- Processing and output logic ---
if (st.session_state.pf_data_df is not None and
    st.session_state.resultset_df is not None and
    st.session_state.ltp_df is not None):


    rs = st.session_state.resultset_df.copy()
    ltp_df = st.session_state.ltp_df


    expiries = sorted(rs['ExpiryDate_Readable'].dropna().unique())
    selected_expiry = st.selectbox("Select Expiry Date", expiries)


    strikes_up_down = st.number_input("Strikes Up-Down (number above/below ATM)", min_value=0, max_value=10, value=2)


    futstk_symbols = rs[(rs['ExpiryDate_Readable'] == selected_expiry) & (rs['InstType'] == 'FUTSTK')]['Symbol'].unique()
    st.write(f"Number of FUTSTK symbols for expiry {selected_expiry}: {len(futstk_symbols)}")


    if st.button("Generate final_CRV.csv"):
        output_rows = []
        for symbol_row in ltp_df.itertuples():
            symbol = symbol_row.Symbol
            fut_token = symbol_row.Token
            fut_ltp = symbol_row.LTP
            if symbol not in futstk_symbols:
                continue


            # --- Find future token row
            fut_rows = rs[
                (rs['Symbol'] == symbol) &
                (rs['ExpiryDate_Readable'] == selected_expiry) &
                (rs['InstType'] == 'FUTSTK')
            ]
            if fut_rows.empty:
                continue


            ce_opts = rs[
                (rs['Symbol'] == symbol) &
                (rs['ExpiryDate_Readable'] == selected_expiry) &
                (rs['InstType'] == 'OPTSTK') &
                (rs['OptionType'] == 'CE')
            ].sort_values('StrikePrice')


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
                    # --- Find resultset rows for both FUT and OPT tokens for column fill
                    opt_token = opt_row.Token


                    fut_res = rs[(rs['Token'] == fut_token) & (rs['InstType'] == 'FUTSTK')]
                    opt_res = rs[(rs['Token'] == opt_token) & (rs['InstType'] == 'OPTSTK')]


                    exch_fut = fut_res['Exch'].iloc[0] if not fut_res.empty else ''
                    exch_opt = opt_res['Exch'].iloc[0] if not opt_res.empty else ''
                    seg_fut = fut_res['Segment'].iloc[0] if not fut_res.empty else ''
                    seg_opt = opt_res['Segment'].iloc[0] if not opt_res.empty else ''
                    expiry_fut = fut_res['ExpiryDate'].iloc[0] if not fut_res.empty else ''
                    expiry_opt = opt_res['ExpiryDate'].iloc[0] if not opt_res.empty else ''
                    # Expiry as unix for output, not readable

                    # Divide strike by 100 to convert paisa to rupees in Description
                    strike_in_rupees = strike / 100
                    desc_fut = f"{symbol} {selected_expiry}"
                    desc_opt = f"{symbol} {selected_expiry} {strike_in_rupees:.0f} CE"


                    output_rows.append({
                        'Exchange': f"{exch_fut}|{exch_opt}",
                        'Segment': f"{seg_fut}|{seg_opt}",
                        'Description': f"{desc_fut}|{desc_opt}",
                        'CLIENTCODE': '',  # Placed from pf_data's first row below
                        'EXPIRY': f"{expiry_fut}|{expiry_opt}",
                        'FUT': fut_token,
                        'OPT': opt_token
                    })


        pf_cols = st.session_state.pf_data_df.columns.tolist()
        pf_first_row = st.session_state.pf_data_df.iloc[0].to_dict()


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
        st.subheader("Preview final_CRV.csv (5 rows)")
        st.dataframe(final_crv_df.head(5))
        csv = final_crv_df.to_csv(index=False)
        st.download_button("Download final_CRV.csv", data=csv, file_name='final_CRV.csv', mime='text/csv')


else:
    st.info("Please upload pf_data.csv, resultset.xlsx, and LTP_File.xml to proceed.")

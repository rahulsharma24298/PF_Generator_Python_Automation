# PF_Generator_Python_Automation
This project contains all PF Generator modules for the BOX and CONREV strategies. Based on specified strike and expiry ranges, it generates PF files in Excel format for use in trading applications.

Steps
# Excel File Mapping Tool

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)

**This project contains the Excel File Mapping Tool for generating trading portfolio files (PF files) from strategy parameters and instrument data.** It automates the mapping of ATM CE and NONATM CE tokens based on strike ranges, expiry dates, and filtering criteria, producing a `FinalPF.csv` ready for trading applications.

## ✨ Features

- **Dual File Upload**: Supports `PF_Data.csv` (strategy parameters) and `ResultSet.xlsx` (instrument data)
- **Flexible ATM CE Selection**:
  - Manual strike price entry (multiple strikes supported)
  - Range-based selection with customizable strike gaps (0, 50, 100)
- **Automated NONATM CE Mapping**: Configurable strike range (±₹) around each ATM CE
- **Advanced Filtering**: Strike gap filtering and reverse PF generation (OPEN/CLOSE)
- **Professional Output**: Generates `FinalPF.csv` with all PF_Data columns + mapping results
- **Expiry Handling**: Automatic conversion of epoch timestamps to readable dates

## 📋 Prerequisites

- **Python 3.8+**
- **Streamlit**: `pip install streamlit`
- **Pandas**: `pip install pandas`
- **OpenPyXL**: `pip install openpyxl` (for Excel support)

## 🚀 Quick Start

### 1. Clone or Download
git clone <your-repo-url>
cd excel-file-mapper

Steps

### 2. Install Dependencies
pip install -r requirements.txt

Steps

### 3. Run the Application
streamlit run app.py

Steps
*Browser opens automatically at `http://localhost:8501`*

### 4. Prepare Input Files
📁 input-files/
├── PF_Data.csv # Strategy parameters (required columns: PF, ATM_CE, NONATM_CE, etc.)
└── ResultSet.xlsx # Instrument master data (required columns: Token, Exch, Symbol, etc.)

Steps

### 5. Usage Workflow
1. **Upload** both input files
2. **Select ATM CE** (Manual strikes OR Range mode)
3. **Configure** NONATM CE strike range and filters
4. **Generate** FinalPF.csv
5. **Download** the output file

## 📁 Project Structure

excel-file-mapper/
├── app.py # Main Streamlit application
├── requirements.txt # Python dependencies
├── README.md # This file
├── input-files/ # Sample input files
│ ├── PF_Data.csv
│ └── ResultSet.xlsx
└── outputs/ # Generated files (FinalPF.csv)

Steps

## 🔧 Configuration Options

| Feature | Description | Default |
|---------|-------------|---------|
| **ATM Mode** | Manual strikes or Range selection | Manual |
| **Strike Range** | NONATM CE search range (±₹) | ±50,000 |
| **Strike Gap** | Filter strikes ending with 00/50 | 0 (disabled) |
| **Reverse PF** | Generate OPEN/CLOSE pairs | Optional |

## 🛠️ Input File Requirements

### PF_Data.csv
PF,ATM_CE,NONATM_CE,Description,Exchange,Segment,EXPIRY,OPCL,...

Steps

### ResultSet.xlsx
Token,Exch,Segment,Symbol,ExpiryDate,InstType,OptionType,StrikePrice,Name,...

Steps

**Note**: ExpiryDate supports both epoch timestamps and readable dates.

## 💾 Sample Output (FinalPF.csv)

PF,ATM_CE,NONATM_CE,Description,Exchange,Segment,EXPIRY,OPCL,...
100_1,12345,12346,"NIFTY 07/12/2025 20000 CE|NIFTY 07/12/2025 20500 CE","NSE|NSE","F&O|F&O","07/12/2025|07/12/2025",OPEN,...

Steps

## 🔄 Deployment Options

### Local Development
streamlit run app.py --server.port 8501 --server.address 0.0.0.0

Steps

### Streamlit Cloud (Free)
1. Push to GitHub
2. Connect repo at [share.streamlit.io](https://share.streamlit.io)
3. Deploy in 1 click

### Docker
Dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

Steps

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| Excel upload fails | Install `openpyxl`: `pip install openpyxl` |
| No tokens found | Verify strike prices exist in ResultSet.xlsx |
| Expiry format error | Tool auto-converts epoch timestamps |

## 📈 Future Enhancements

- [ ] Multi-symbol support
- [ ] Bulk ATM processing
- [ ] Custom column mapping
- [ ] API integration
- [ ] Batch processing mode

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📄 License

MIT License - Free to use and modify for trading applications.

## 🙏 Acknowledgments

Built for capital markets trading professionals. Optimized for performance and usability.

---

**⭐ Star this repo if it saves you time!**

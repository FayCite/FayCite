# FayCite
**Academic Citation Assistant**

Automatically analyze research papers and insert citations with supporting quotes from your PDF library. Supports APA, MLA, Chicago, and IEEE citation styles.

## Features
- AI-powered citation analysis
- Multi-style citation support (APA, MLA, Chicago, IEEE)
- Zotero bibliography integration
- Grammarly-style document viewer
- Word document export

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Set up Azure OpenAI environment variables
3. Run: `streamlit run app.py`

## Installation

### Prerequisites
- Python 3.11 or higher
- Azure OpenAI API access

### Quick Start
```bash
# Clone the repository
git clone https://github.com/FayCite/FayCite.git
cd FayCite

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_ENDPOINT="your-endpoint"

# Run the application
streamlit run app.py
```

## Usage

1. **Upload Documents**: Upload your Word documents or text files for citation analysis
2. **PDF Library**: Add your research PDFs to build your citation library
3. **Citation Analysis**: FayCite will automatically analyze your document and suggest relevant citations
4. **Citation Formatting**: Choose from APA, MLA, Chicago, or IEEE citation styles
5. **Export**: Download your document with properly formatted citations

## File Structure

- `app.py` - Main Streamlit application
- `citation_processor.py` - AI-powered citation processing engine
- `pdf_library.py` - PDF management and metadata extraction
- `document_parser.py` - Multi-format document parsing
- `citation_formatter.py` - Citation formatting for multiple styles
- `bibliography_parser.py` - Zotero bibliography integration
- `apa_formatter.py` - APA-specific formatting utilities

## Configuration

Create a `.streamlit/config.toml` file for custom configuration:

```toml
[server]
port = 8501
address = "localhost"

[theme]
primaryColor = "#1f77b4"
backgroundColor = "#ffffff"
secondaryBackgroundColor = "#f0f2f6"
textColor = "#262730"
```

## Environment Variables

The following environment variables are required:

- `AZURE_OPENAI_API_KEY` - Your Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT` - Your Azure OpenAI endpoint URL

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue on the GitHub repository or contact the development team.
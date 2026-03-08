<!-- README.md for bibliometrix-python -->

# bibliometrix-python

## A Python tool for comprehensive science mapping analysis

[![bibliometrix: An R-tool for comprehensive science mapping
analysis.](https://www.bibliometrix.org/JOI-badge.svg)](https://doi.org/10.1016/j.joi.2017.08.007)

<p align="center">
<img src="https://www.bibliometrix.org/logo_new.png" width="400"/>
</p>

## Overview

**bibliometrix-python** is a Python implementation of the renowned **bibliometrix** R package, providing a comprehensive set of tools for quantitative research in bibliometrics and scientometrics.

This project reimplements the core functionality of [bibliometrix](https://github.com/massimoaria/bibliometrix) (developed by Massimo Aria and Corrado Cuccurullo) using Python and the Shiny for Python framework, making these powerful bibliometric tools accessible to the Python scientific community.

Bibliometrics applies quantitative analysis and statistics to scientific publications and their citation patterns. It has become essential across all scientific fields for evaluating growth, maturity, leading authors, conceptual and intellectual maps, and emerging trends within research communities.

**bibliometrix-python** supports scholars in three key phases of analysis:

- **Data importing and conversion** from major bibliographic databases (Web of Science, Scopus, PubMed, Dimensions, Lens, Cochrane)

- **Bibliometric analysis** of publication datasets, including descriptive statistics, author productivity, and source impact

- **Building and visualizing networks** for co-citation, coupling, collaboration, and co-word analysis

## biblioshiny: Python Edition

**bibliometrix-python** includes an interactive web application built with **Shiny for Python**, providing an intuitive interface for comprehensive bibliometric analysis.

The web application enables scholars to easily access bibliometric analysis features through an interactive workflow:

### Data Management

- **Import and convert** data from multiple bibliographic databases:
  - Web of Science (plaintext, BibTeX, EndNote) - ✅ Fully supported
  - Scopus (CSV, BibTeX) - 🚧 In progress
  - PubMed (plaintext export) - 🚧 In progress
  - Dimensions (Excel, CSV) - 🚧 In progress
  - Lens.org (CSV) - 🚧 In progress
  - Cochrane CDSR (plaintext) - 🚧 In progress

- **Filter data** by various criteria including publication years, languages, document types, citation counts, and Bradford's Law zones

- **Sample datasets** for testing and learning

### Analytics and Visualization

- **Three-level metrics** for comprehensive analysis:

  - **Sources**: journal performance, impact metrics, Bradford's Law, sources' local impact, production over time

  - **Authors**: productivity analysis, Lotka's Law, collaboration patterns, h-index, local impact, affiliations analysis

  - **Documents**: citation analysis, most relevant papers, references spectroscopy

- **Countries Analysis**: scientific production by country, collaboration networks, corresponding authors' countries

### Knowledge Structure Analysis

- **Conceptual Structure**: analyzing topics and themes through co-word analysis, thematic mapping, and thematic evolution

- **Intellectual Structure**: examining citation networks through co-citation analysis, historiograph, and document coupling

- **Social Structure**: exploring collaboration patterns through co-authorship networks at author, institution, and country levels

### Content Analysis Features

- **Word Analysis**: frequent words, word clouds, treemaps, word frequency over time

- **Trend Topics**: identify emerging and declining research topics

- **Three-Field Plot**: Sankey diagrams for exploring relationships between authors, keywords, and journals

### Advanced Features

- **AI-Powered Assistant**: Integrated Google Gemini AI chatbot for contextual help and insights - 🧪 BETA

- **Interactive Reports**: Generate comprehensive Excel reports combining multiple analyses

- **Export Capabilities**: Download plots as high-resolution images and tables as Excel files

### How to use biblioshiny

To launch the application, simply run:

```bash
shiny run app.py
```

Or using Python:

```bash
python -m shiny run app.py
```

The application will start and provide a local URL (typically `http://127.0.0.1:8000`) to access the web interface.

## How to cite

If you use this package for your research, please cite the original R package:

Aria, M. & Cuccurullo, C. (2017) **bibliometrix: An R-tool for comprehensive science mapping analysis**, *Journal of Informetrics*, 11(4), pp 959-975, Elsevier, DOI: 10.1016/j.joi.2017.08.007

## Community

**Original bibliometrix (R version):**
- Official website: https://www.bibliometrix.org
- CRAN page: https://cran.r-project.org/package=bibliometrix
- GitHub repository: https://github.com/massimoaria/bibliometrix

**Python implementation:**
- GitHub repository: https://github.com/PRAISELab-PicusLab/bibliometrix-python
- Issue tracker: https://github.com/PRAISELab-PicusLab/bibliometrix-python/issues

## Installation

### Prerequisites

- Python 3.9 or higher
- pip package manager

### Install from source

Clone the repository:

```bash
git clone https://github.com/PRAISELab-PicusLab/bibliometrix-python.git
cd bibliometrix-python
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Run the application

```bash
shiny run app.py
```

Or specify custom host and port:

```bash
shiny run app.py --port 8000 --host 0.0.0.0
```

## Project Structure

```plaintext
bibliometrix-python/
│
├── app.py                  # Main application entry point
├── requirements.txt        # Python dependencies
├── README.md              
│
├── functions/             # Analysis functions
│   ├── get_annualproduction.py
│   ├── get_averagecitations.py
│   ├── get_bradfordlaw.py
│   ├── get_relevantauthors.py
│   ├── get_relevantsources.py
│   └── ... (35+ analysis modules)
│
├── www/                   # Web application components
│   ├── services/          # Core bibliometric services
│   │   ├── parsers.py
│   │   ├── format_functions.py
│   │   ├── networkplot.py
│   │   ├── thematicmap.py
│   │   └── utils.py
│   └── static/            # Static assets (CSS, JS)
│       └── biblioshiny.css
│
└── sources/               # Sample datasets and test files
    ├── Web_of_Science/
    ├── Scopus/
    ├── PubMed/
    ├── Dimensions/
    ├── Lens/
    └── Cochrane/
```

## Key Features

### Data Import and Processing

bibliometrix-python supports importing bibliographic data from major scientific databases:

- **Web of Science**: plaintext (.txt), BibTeX (.bib), EndNote (.ciw) - ✅ Fully supported
- **Scopus**: CSV (.csv), BibTeX (.bib) - 🚧 In progress
- **PubMed**: plaintext export - 🚧 In progress
- **Dimensions**: Excel (.xlsx), CSV (.csv) - 🚧 In progress
- **Lens.org**: CSV (.csv) - 🚧 In progress
- **Cochrane**: plaintext (.txt) - 🚧 In progress

### Comprehensive Bibliometric Analysis

The application provides extensive analysis capabilities organized by analytical level:

#### Overview Analysis
- Main information and descriptive statistics
- Annual scientific production
- Average citations per year
- Document type distribution
- Keywords analysis

#### Sources Analysis
- Most relevant sources (journals)
- Most locally cited sources
- Bradford's Law
- Sources' local impact
- Sources' production over time

#### Authors Analysis
- Most relevant authors
- Most locally cited authors
- Authors' production over time
- Lotka's Law
- Authors' local impact
- Affiliations analysis
- Author collaboration patterns

#### Documents Analysis
- Most globally cited documents
- Most locally cited documents
- Most locally cited references
- References spectroscopy
- Frequent words analysis
- Word clouds and treemaps
- Words' frequency over time
- Trend topics

#### Network Analysis
- Co-occurrence networks
- Co-citation networks
- Collaboration networks
- Country collaboration maps
- Thematic maps
- Thematic evolution
- Clustering analysis
- Factorial analysis
- Historiograph

### Interactive Visualizations

All analyses include interactive visualizations built with Plotly and other modern Python libraries:

- Bar charts, line plots, and scatter plots
- Network diagrams
- Sankey diagrams (Three-Field Plot)
- Heatmaps
- Word clouds
- Treemaps
- Thematic maps

### Export and Reporting

- Export plots as high-resolution PNG images (customizable DPI)
- Download tables as Excel files
- Generate comprehensive reports combining multiple analyses
- Add analyses to report collection for batch download

## AI Assistant Integration (BETA)

The application includes an AI-powered chatbot using Google Gemini API to help users:

- Understand bibliometric concepts
- Interpret analysis results
- Get contextual help
- Receive recommendations for further analysis

**Note:** This feature is currently in BETA testing.

To use the AI assistant, configure your Gemini API key in the Settings panel.

## Acknowledgments

This project is a Python reimplementation of the original **bibliometrix** R package developed by:

**Massimo Aria** and **Corrado Cuccurullo**  
*University of Naples Federico II, Italy*

We are grateful for their pioneering work in making bibliometric analysis accessible to researchers worldwide.

For the original R implementation and comprehensive documentation, please visit:
- Website: https://www.bibliometrix.org
- GitHub: https://github.com/massimoaria/bibliometrix

### Main References (Original bibliometrix)

Aria, M. & Cuccurullo, C. (2017). **bibliometrix: An R-tool for comprehensive science mapping analysis**, *Journal of Informetrics*, 11(4), pp 959-975, Elsevier, DOI: 10.1016/j.joi.2017.08.007

Aria, M., Le, T., Cuccurullo, C., Belfiore, A., & Choe, J. (2024). **openalexR: An R-Tool for Collecting Bibliometric Data from OpenAlex**. *The R Journal*, DOI: 10.32614/RJ-2023-089

Aria, M., Cuccurullo, C., D'Aniello, L., Misuraca, M., & Spano, M. (2022). **Thematic Analysis as a New Culturomic Tool: The Social Media Coverage on COVID-19 Pandemic in Italy**. *Sustainability*, 14(6), 3643

For a complete list of references and applications, visit: https://www.bibliometrix.org

## 🤝 Contributing

We welcome contributions to improve the application! To contribute, simply open a pull request or report issues on our [issue tracker](https://github.com/PRAISELab-PicusLab/bibliometrix-python/issues). We look forward to your improvements!

## 👨‍💻 Team

This project was developed by:

**Mariano Barone** · **Gian Marco Orlando** · **Giuseppe Riccio** · **Antonio Romano** · **Diego Russo** · **Vincenzo Moscato**

*Department of Electrical Engineering and Information Technology*  
*University of Naples Federico II, Italy*

**Research Lab:** The [PRAISE](https://github.com/PRAISELab) (PRedictive AnalytIcs for underUnderstanding big multimEdia data) research group is part of the PICUS Lab at the Department of Electrical Engineering and Information Technologies (DIETI), University of Naples Federico II, Italy.

## 📄 License

This application is distributed under the GNU General Public License as specified in the [LICENSE](LICENSE) file.

When used in a publication, please cite the original bibliometrix R package (see [How to cite](#how-to-cite) section).

## ⚠️ Development Notes

**Note:** This is an independent Python implementation and may not be fully compatible with the R version. Some features are still under development.

For detailed development status and known issues, please check the [issue tracker](https://github.com/PRAISELab-PicusLab/bibliometrix-python/issues).

---

<p align="center">
Made with ❤️ by PRAISELab Team at University of Naples Federico II
</p>

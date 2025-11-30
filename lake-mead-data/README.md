# Lake Mead Water Level Analyzer

This tool scrapes Lake Mead water level data from the USGS National Water Information System and generates visualizations with trend analysis.

## Features

- **Data Collection**: Fetches daily water elevation data from USGS API (site 09421000 - Lake Mead at Hoover Dam)
- **Trend Analysis**:
  - Year-over-Year (YoY) comparison
  - Month-over-Month (MoM) changes
  - Detection of 3+ consecutive months of declining water levels
- **Visualizations**:
  - Historical water level chart
  - YoY change bar chart
  - MoM change for last 24 months
- **Data Caching**: Saves data locally for offline analysis

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### Fetch Real Data from USGS

Simply run the script:

```bash
python lake_mead_analyzer.py
```

The script will:
1. Attempt to fetch the latest data from USGS
2. Fall back to cached data if API is unavailable
3. Display an error if no data is accessible
4. Display trend analysis in the terminal
5. Generate visualization charts
6. Save charts to the `output/` directory

### Use Sample Data

To skip the API call and use sample data for testing:

```bash
python lake_mead_analyzer.py --sample
```

This is useful for:
- Testing the visualization and analysis features
- Running in environments without internet access
- Demonstrations and development

## Data Source

- **Source**: U.S. Geological Survey (USGS) National Water Information System
- **Site**: 09421000 (Lake Mead at Hoover Dam, AZ-NV)
- **Parameter**: Reservoir elevation (feet)
- **API**: [USGS Water Services](https://waterservices.usgs.gov/)

## Output

- **Terminal**: Detailed trend analysis including current levels, YoY/MoM changes, and declining trend alerts
- **Charts**: PNG file with three visualizations saved to `output/` directory
- **Data**: CSV file cached locally for reuse

## Example Output

The script identifies:
- Current water elevation
- Month-over-month change with percentage
- Year-over-year change with percentage
- Warning if water has declined for 3+ consecutive months
- 12-month summary statistics

## Data Updates

Data is fetched from USGS in real-time. The USGS updates Lake Mead data daily.

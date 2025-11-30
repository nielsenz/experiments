#!/usr/bin/env python3
"""
Lake Mead Water Level Data Analyzer
Scrapes monthly water level data, generates visualizations, and analyzes trends.
"""

import requests
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
import json
import sys
import numpy as np
from pathlib import Path

# Configuration
USGS_SITE_ID = "09421000"  # Lake Mead at Hoover Dam
PARAMETER_CODE = "00054"   # Reservoir elevation, feet
START_DATE = "1990-01-01"  # Historical data start
OUTPUT_DIR = Path(__file__).parent / "output"
DATA_FILE = Path(__file__).parent / "lake_mead_data.csv"


class LakeMeadAnalyzer:
    """Analyzes Lake Mead water level data."""

    def __init__(self):
        self.data = None
        OUTPUT_DIR.mkdir(exist_ok=True)

    def fetch_data(self):
        """Fetch water level data from USGS API."""
        print("Fetching Lake Mead water level data from USGS...")

        # USGS Daily Values Service
        url = "https://waterservices.usgs.gov/nwis/dv/"

        params = {
            'sites': USGS_SITE_ID,
            'format': 'json',
            'parameterCd': PARAMETER_CODE,
            'startDT': START_DATE,
            'siteStatus': 'all'
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Extract time series data
            time_series = data['value']['timeSeries'][0]['values'][0]['value']

            # Convert to DataFrame
            records = []
            for record in time_series:
                records.append({
                    'date': pd.to_datetime(record['dateTime']),
                    'elevation': float(record['value'])
                })

            self.data = pd.DataFrame(records)
            self.data.set_index('date', inplace=True)

            # Save to CSV for future use
            self.data.to_csv(DATA_FILE)
            print(f"✓ Fetched {len(self.data)} daily records")
            print(f"✓ Data range: {self.data.index.min().date()} to {self.data.index.max().date()}")

            return True

        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching data from USGS API: {e}")
            return False
        except (KeyError, IndexError) as e:
            print(f"✗ Error parsing API response: {e}")
            return False

    def load_cached_data(self):
        """Load previously cached data."""
        if DATA_FILE.exists():
            print(f"Loading cached data from {DATA_FILE}...")
            self.data = pd.read_csv(DATA_FILE, parse_dates=['date'], index_col='date')
            print(f"✓ Loaded {len(self.data)} records")
            return True
        else:
            print("✗ No cached data found")
            return False

    def generate_sample_data(self):
        """Generate sample data based on historical Lake Mead trends for demonstration."""
        print("Generating sample data for demonstration...")

        # Create date range from 2000 to present
        date_range = pd.date_range(start='2000-01-01', end=datetime.now(), freq='D')

        # Simulate Lake Mead elevation with realistic trends
        # Historical high: ~1225 ft (1983), Historical low: ~1040 ft (2022)
        # Starting elevation in 2000: ~1200 ft

        n_days = len(date_range)

        # Base trend: general decline from 1200 to 1050 with recovery after 2022
        base_trend = np.linspace(1200, 1050, int(n_days * 0.95))
        recovery = np.linspace(1050, 1065, n_days - len(base_trend))
        trend = np.concatenate([base_trend, recovery])

        # Add seasonal variation (higher in spring, lower in late summer)
        seasonal = 15 * np.sin(np.arange(n_days) * 2 * np.pi / 365.25 - np.pi/2)

        # Add some random noise
        np.random.seed(42)
        noise = np.random.normal(0, 2, n_days)

        # Combine components
        elevation = trend + seasonal + noise

        # Create DataFrame
        self.data = pd.DataFrame({
            'elevation': elevation
        }, index=date_range)
        self.data.index.name = 'date'

        # Save to CSV
        self.data.to_csv(DATA_FILE)
        print(f"✓ Generated {len(self.data)} days of sample data")
        print(f"✓ Data range: {self.data.index.min().date()} to {self.data.index.max().date()}")
        print("  Note: This is SAMPLE DATA for demonstration. For real data, ensure internet access to USGS API.")

        return True

    def get_monthly_data(self):
        """Aggregate daily data to monthly (end of month values)."""
        if self.data is None or self.data.empty:
            return None

        # Resample to monthly, taking the last value of each month
        monthly = self.data.resample('ME').last()
        return monthly

    def analyze_trends(self):
        """Analyze Year-over-Year, Month-over-Month, and declining trends."""
        monthly = self.get_monthly_data()

        if monthly is None or len(monthly) < 2:
            print("✗ Insufficient data for trend analysis")
            return

        print("\n" + "="*70)
        print("LAKE MEAD WATER LEVEL ANALYSIS")
        print("="*70)

        # Current level
        current = monthly.iloc[-1]
        current_date = monthly.index[-1]
        print(f"\nCurrent Level (as of {current_date.strftime('%B %Y')}):")
        print(f"  Elevation: {current['elevation']:.2f} feet")

        # Month-over-Month (MoM) change
        if len(monthly) >= 2:
            previous_month = monthly.iloc[-2]
            mom_change = current['elevation'] - previous_month['elevation']
            mom_percent = (mom_change / previous_month['elevation']) * 100

            print(f"\nMonth-over-Month Change:")
            print(f"  Previous: {previous_month['elevation']:.2f} feet ({monthly.index[-2].strftime('%B %Y')})")
            print(f"  Change: {mom_change:+.2f} feet ({mom_percent:+.2f}%)")
            print(f"  Status: {'📉 DECLINING' if mom_change < 0 else '📈 RISING' if mom_change > 0 else '➡️  STABLE'}")

        # Year-over-Year (YoY) change
        one_year_ago_date = current_date - pd.DateOffset(years=1)
        # Find closest month to one year ago
        year_ago_data = monthly[monthly.index <= one_year_ago_date]

        if len(year_ago_data) > 0:
            year_ago = year_ago_data.iloc[-1]
            yoy_change = current['elevation'] - year_ago['elevation']
            yoy_percent = (yoy_change / year_ago['elevation']) * 100

            print(f"\nYear-over-Year Change:")
            print(f"  One year ago: {year_ago['elevation']:.2f} feet ({year_ago_data.index[-1].strftime('%B %Y')})")
            print(f"  Change: {yoy_change:+.2f} feet ({yoy_percent:+.2f}%)")
            print(f"  Status: {'📉 DECLINING' if yoy_change < 0 else '📈 RISING' if yoy_change > 0 else '➡️  STABLE'}")

        # Detect consecutive declining months (3+)
        print("\n" + "-"*70)
        print("TREND DETECTION (3+ Consecutive Months)")
        print("-"*70)

        # Calculate month-to-month differences
        monthly_diff = monthly['elevation'].diff()

        # Find consecutive declining months
        declining_streak = 0
        max_streak = 0
        streak_end_date = None
        current_streak_active = False

        for i in range(len(monthly_diff) - 1, -1, -1):
            if pd.notna(monthly_diff.iloc[i]) and monthly_diff.iloc[i] < 0:
                declining_streak += 1
                if i == len(monthly_diff) - 1:
                    current_streak_active = True
            else:
                if declining_streak > max_streak:
                    max_streak = declining_streak
                    if not current_streak_active:
                        streak_end_date = monthly.index[i]
                declining_streak = 0
                current_streak_active = False

        # Check final streak
        if declining_streak > max_streak:
            max_streak = declining_streak

        # Current declining streak
        current_declining = 0
        for i in range(len(monthly_diff) - 1, -1, -1):
            if pd.notna(monthly_diff.iloc[i]) and monthly_diff.iloc[i] < 0:
                current_declining += 1
            else:
                break

        if current_declining >= 3:
            print(f"\n🚨 WARNING: Water level has been declining for {current_declining} consecutive months!")
            print(f"   Start of decline: {monthly.index[-current_declining].strftime('%B %Y')}")
            print(f"   Total decline: {monthly['elevation'].iloc[-current_declining:].iloc[0] - current['elevation']:.2f} feet")
        elif current_declining > 0:
            print(f"\n⚠️  Water level declining for {current_declining} month(s)")
        else:
            print(f"\n✓ No current declining trend (water level stable or rising)")

        # Historical declining trends
        if max_streak >= 3:
            print(f"\nHistorical note: Longest declining streak was {max_streak} months")

        # Last 12 months summary
        last_12_months = monthly.iloc[-12:]
        if len(last_12_months) == 12:
            declining_months = (last_12_months['elevation'].diff() < 0).sum()
            rising_months = (last_12_months['elevation'].diff() > 0).sum()
            print(f"\nLast 12 Months Summary:")
            print(f"  Declining months: {declining_months}")
            print(f"  Rising months: {rising_months}")
            print(f"  Net change: {last_12_months['elevation'].iloc[-1] - last_12_months['elevation'].iloc[0]:+.2f} feet")

        print("\n" + "="*70)

    def create_visualizations(self):
        """Generate visualization charts."""
        if self.data is None or self.data.empty:
            print("✗ No data available for visualization")
            return

        monthly = self.get_monthly_data()

        print("\nGenerating visualizations...")

        # Create figure with multiple subplots
        fig, axes = plt.subplots(3, 1, figsize=(14, 12))
        fig.suptitle('Lake Mead Water Level Analysis', fontsize=16, fontweight='bold')

        # 1. Historical water levels
        ax1 = axes[0]
        ax1.plot(monthly.index, monthly['elevation'], linewidth=2, color='#2E86AB')
        ax1.fill_between(monthly.index, monthly['elevation'], alpha=0.3, color='#2E86AB')
        ax1.set_title('Historical Water Levels (Monthly)', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Elevation (feet)')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax1.xaxis.set_major_locator(mdates.YearLocator(2))

        # Add horizontal line for critical levels
        critical_level = 1050  # Example critical level
        ax1.axhline(y=critical_level, color='red', linestyle='--', alpha=0.7, label=f'Critical Level ({critical_level} ft)')
        ax1.legend()

        # 2. Year-over-Year change
        ax2 = axes[1]
        yoy_change = monthly['elevation'].diff(periods=12)  # 12 months = 1 year
        colors = ['red' if x < 0 else 'green' for x in yoy_change]
        ax2.bar(monthly.index, yoy_change, color=colors, alpha=0.6, width=20)
        ax2.set_title('Year-over-Year Change (feet)', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Date')
        ax2.set_ylabel('YoY Change (feet)')
        ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax2.grid(True, alpha=0.3, axis='y')
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax2.xaxis.set_major_locator(mdates.YearLocator(2))

        # 3. Month-over-Month change (last 24 months)
        ax3 = axes[2]
        last_24_months = monthly.iloc[-24:]
        mom_change = last_24_months['elevation'].diff()
        colors = ['red' if x < 0 else 'green' for x in mom_change]
        ax3.bar(last_24_months.index, mom_change, color=colors, alpha=0.6)
        ax3.set_title('Month-over-Month Change - Last 24 Months (feet)', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Date')
        ax3.set_ylabel('MoM Change (feet)')
        ax3.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
        ax3.grid(True, alpha=0.3, axis='y')
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha='right')

        plt.tight_layout()

        # Save figure
        output_file = OUTPUT_DIR / f"lake_mead_analysis_{datetime.now().strftime('%Y%m%d')}.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"✓ Saved visualization to: {output_file}")
        plt.close()

    def run(self, use_sample_data=False):
        """Main execution method."""
        print("Lake Mead Water Level Analyzer")
        print("="*70)

        # Try to fetch fresh data, fall back to cached if unavailable
        if use_sample_data:
            print("\nUsing sample data mode...")
            if not self.generate_sample_data():
                return False
        elif not self.fetch_data():
            print("\nAttempting to load cached data...")
            if not self.load_cached_data():
                print("\nNo cached data found. Generating sample data for demonstration...")
                if not self.generate_sample_data():
                    print("\n✗ Unable to generate sample data.")
                    return False

        # Perform analysis
        self.analyze_trends()

        # Create visualizations
        self.create_visualizations()

        return True


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Lake Mead Water Level Analyzer')
    parser.add_argument('--sample', action='store_true',
                        help='Use sample data instead of fetching from USGS')
    args = parser.parse_args()

    analyzer = LakeMeadAnalyzer()
    success = analyzer.run(use_sample_data=args.sample)

    if success:
        print("\n✓ Analysis complete!")
    else:
        print("\n✗ Analysis failed")
        sys.exit(1)


if __name__ == "__main__":
    main()

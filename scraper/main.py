"""
Scraper CLI – Leaguepedia + gol.gg
Usage: python -m scraper.main --full
"""
import argparse
from etl.normalize import run_etl

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--years', default='2011-2025')
    args = parser.parse_args()
    print(f"[scraper] Starting ETL years={args.years} full={args.full}")
    run_etl()
    print("[scraper] Done.")

if __name__ == '__main__':
    main()

#!/usr/bin/env python3

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

import pandas as pd
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

UF_CODES = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR",
    "15": "PA", "16": "AP", "17": "TO",
    "21": "MA", "22": "PI", "23": "CE", "24": "RN",
    "25": "PB", "26": "PE", "27": "AL", "28": "SE",
    "29": "BA", "31": "MG", "32": "ES", "33": "RJ",
    "35": "SP", "41": "PR", "42": "SC", "43": "RS",
    "50": "MS", "51": "MT", "52": "GO", "53": "DF"
}

VALID_UFS = set(UF_CODES.values())

SIM_COLUMNS = [
    "TIPOBITO", "DTOBITO", "IDADE",
    "SEXO", "CODMUNRES", "CAUSABAS"
]

# Directory containing this script
SCRIPT_DIR = Path(__file__).resolve().parent

# Project root (one directory above scripts/)
PROJECT_DIR = SCRIPT_DIR.parent

# Data directories
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = DATA_DIR / "processed_data"

# ============================================================
# SIM DATA PROCESSING
# ============================================================

def detect_csv_format(filepath):
    """Detect CSV encoding and delimiter."""

    encodings = ["utf-8-sig", "cp1252", "latin1"]

    for encoding in encodings:
        try:
            with open(filepath, encoding=encoding) as file:
                sample = file.read(50000)

            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Could not determine CSV encoding.")

    try:
        delimiter = csv.Sniffer().sniff(
            sample, delimiters=";,\t|"
        ).delimiter
    except csv.Error:
        delimiter = ";"

    return encoding, delimiter


def clean_code(value, width=None):
    """Clean coded fields while preserving leading zeroes."""

    if pd.isna(value):
        return ""

    value = str(value).strip()

    if value.endswith(".0"):
        value = value[:-2]

    value = re.sub(r"\s+", "", value)

    if width and value.isdigit():
        value = value.zfill(width)

    return value.upper()


def decode_age(value):
    """Decode SIM's three-character age field.
    Decode SIM IDADE.

    1 = minutes
    2 = hours
    3 = months
    4 = years
    5 = older than 100 years
    9 = unknown
    """

    if pd.isna(value):
        return None

    value = str(value).strip()

    if len(value) != 3 or not value.isdigit():
        return None

    unit = value[0]
    quantity = int(value[1:])

    if unit in ("1", "2", "3"):
        # Minutes, hours, or months: completed age is zero.
        return 0

    if unit == "4":
        # Years. Group everyone aged 90+ together.
        return min(quantity, 90)

    if unit == "5":
        # Over 100 years.
        return 90

    return None


def decode_sex(value):
    """Standardize sex as M or F."""

    value = str(value).strip().upper()

    if value in ("M", "1"):
        return "M"

    if value in ("F", "2"):
        return "F"

    return None


def decode_cause(value):
    """
    Extract the ICD-10 three-character category.

    Included:
        V01-V99
        W00-W99
        X00-X99
        Y00-Y34
    """

    if pd.isna(value):
        return None

    code = re.sub(
        r"[^A-Z0-9]", "", str(value).strip().upper()
    )

    if len(code) < 3:
        return None

    category = code[:3]

    if not category[1:].isdigit():
        return None

    letter = category[0]
    number = int(category[1:])

    if letter == "V" and 1 <= number <= 99:
        return category

    if letter in ("W", "X") and 0 <= number <= 99:
        return category

    if letter == "Y" and 0 <= number <= 34:
        return category

    return None



def decode_state(value):
    """Extract state from the SIM municipality-of-residence code."""

    code = clean_code(value)

    code = re.sub(r"\D", "", code)

    if len(code) not in (6, 7):
        return None

    return UF_CODES.get(code[:2])



def process_sim(filepath, chunksize=500_000):
    """
    Read SIM in chunks, filter records and aggregate deaths.

    Returns:
        deaths: grouped death counts
        report: processing counters
    """

    encoding, delimiter = detect_csv_format(filepath)

    print(f"SIM encoding: {encoding}")
    print(f"CSV delimiter: {repr(delimiter)}")

    # Check column names before processing.
    header = pd.read_csv(
        filepath,
        sep=delimiter,
        encoding=encoding,
        nrows=0
    ).columns.tolist()

    lookup = {
        str(col).strip().upper(): col
        for col in header
    }

    missing = set(SIM_COLUMNS) - set(lookup)

    if missing:
        raise ValueError(
            f"Missing SIM columns: {missing}"
        )

    usecols = [lookup[col] for col in SIM_COLUMNS]

    report = Counter()
    partial_results = []

    reader = pd.read_csv(
        filepath,
        sep=delimiter,
        encoding=encoding,
        dtype=str,
        usecols=usecols,
        chunksize=chunksize,
        keep_default_na=False
    )

    for chunk_number, chunk in enumerate(reader, start=1):

        report["rows_read"] += len(chunk)

        # Non-fetal deaths.
        mask = chunk["TIPOBITO"].str.strip().eq("2")
        report["non_fetal"] += int(mask.sum())

        chunk = chunk.loc[mask].copy()

        # Deaths occurring in 2024.
        dates = (
            chunk["DTOBITO"]
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(8)
        )

        dates = pd.to_datetime(
            dates,
            format="%d%m%Y",
            errors="coerce"
        )

        mask = dates.dt.year.eq(2024)

        report["year_2024"] += int(mask.sum())
        report["invalid_or_other_year"] += int((~mask).sum())

        chunk = chunk.loc[mask].copy()

        # Age.
        chunk["age"] = chunk["IDADE"].map(decode_age)

        mask = chunk["age"].notna()

        report["valid_age"] += int(mask.sum())
        report["invalid_age"] += int((~mask).sum())

        chunk = chunk.loc[mask].copy()
        chunk["age"] = chunk["age"].astype(int)

        # Sex.
        chunk["sex"] = chunk["SEXO"].map(decode_sex)

        mask = chunk["sex"].notna()

        report["valid_sex"] += int(mask.sum())
        report["invalid_sex"] += int((~mask).sum())

        chunk = chunk.loc[mask].copy()

        # State.
        chunk["uf"] = chunk["CODMUNRES"].map(decode_state)

        mask = chunk["uf"].notna()

        report["valid_state"] += int(mask.sum())
        report["invalid_state"] += int((~mask).sum())

        chunk = chunk.loc[mask].copy()

        # Underlying cause.
        chunk["cause"] = chunk["CAUSABAS"].map(decode_cause)

        mask = chunk["cause"].notna()

        report["valid_cause"] += int(mask.sum())
        report["invalid_cause"] += int((~mask).sum())

        chunk = chunk.loc[mask].copy()

        # Aggregate within the chunk.
        if not chunk.empty:

            grouped = (
                chunk.groupby(
                    ["age", "sex", "uf", "cause"]
                )
                .size()
                .reset_index(name="deaths")
            )

            partial_results.append(grouped)

        if chunk_number % 5 == 0:
            print(
                f"Processed {chunk_number} chunks: "
                f"{report['rows_read']:,} records"
            )

        if not partial_results:

            print("\nDIAGNOSTICS")
            print("-" * 40)

            for key, value in report.items():
                print(f"{key}: {value:,}")

            raise ValueError(
                "No valid mortality records found. "
                "Check the filtering diagnostics above."
            )

    # Combine chunk-level aggregations.
    deaths = pd.concat(
        partial_results,
        ignore_index=True
    )

    deaths = (
        deaths.groupby(
            ["age", "sex", "uf", "cause"],
            as_index=False
        )["deaths"]
        .sum()
    )

    report["final_deaths"] = int(deaths["deaths"].sum())

    return deaths, report


# ============================================================
# IBGE POPULATION PROCESSING
# ============================================================

def normalize_column(value):
    return re.sub(
        r"\s+", "", str(value).strip()
    ).upper()


def find_population_header(filepath, sheet=0):

    preview = pd.read_excel(
        filepath,
        sheet_name=sheet,
        header=None,
        nrows=30
    )

    for i, row in preview.iterrows():

        values = {
            normalize_column(v)
            for v in row.tolist()
        }

        if {"IDADE", "SEXO", "SIGLA"}.issubset(values):
            return i

    raise ValueError(
        "Could not find IDADE, SEXO and SIGLA "
        "in the population spreadsheet."
    )


def decode_population_age(value):

    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        age = int(value)
        return 100 if age >= 100 else age

    text = str(value).strip().lower()

    if "+" in text or "mais" in text:
        return 100

    numbers = re.findall(r"\d+", text)

    if not numbers:
        return None

    age = int(numbers[0])

    return 100 if age >= 100 else age


def decode_population_sex(value):
    """Convert IBGE sex labels into M/F."""
    if pd.isna(value):
        return None

    sex = str(value).strip().casefold()

    if sex == "homens":
        return "M"

    if sex == "mulheres":
        return "F"

    # Exclude combined-sex records.
    return None


def decode_population_number(value):

    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    # Brazilian thousands separator.
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", text):
        text = text.replace(".", "")

    elif "," in text and "." not in text:
        text = text.replace(",", ".")

    try:
        return float(text)
    except ValueError:
        return None


def process_population(filepath, sheet=0):

    header = find_population_header(
        filepath, sheet
    )

    df = pd.read_excel(
        filepath,
        sheet_name=sheet,
        header=header
    )

    columns = {
        normalize_column(col): col
        for col in df.columns
    }

    required = ["IDADE", "SEXO", "SIGLA", "2024"]

    missing = [
        col for col in required
        if col not in columns
    ]

    if missing:
        raise ValueError(
            f"Missing population columns: {missing}. "
            f"Available: {list(columns)}"
        )

    df = df[
        [columns[col] for col in required]
    ].copy()

    df.columns = [
        "age_raw", "sex_raw", "uf_raw", "population_raw"
    ]

    df["age"] = df["age_raw"].map(decode_population_age)
    df["sex"] = df["sex_raw"].map(decode_population_sex)

    df["uf"] = (
        df["uf_raw"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df["population"] = (
        df["population_raw"]
        .map(decode_population_number)
    )

    # Retain only the 27 states, male/female and valid ages.
    df = df[
        df["age"].notna()
        & df["sex"].notna()
        & df["uf"].isin(VALID_UFS)
        & df["population"].notna()
    ].copy()

    df["age"] = df["age"].astype(int)

    # Combine all ages >=100 into one group.
    population = (
        df.groupby(
            ["age", "sex", "uf"],
            as_index=False
        )["population"]
        .sum()
    )

    missing_ufs = VALID_UFS - set(population["uf"])

    if missing_ufs:
        raise ValueError(
            f"Population data missing states: {missing_ufs}"
        )

    return population


# ============================================================
# MERGING AND MORTALITY RATES
# ============================================================

def calculate_rates(deaths, population, output_dir):

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # Total external-cause mortality.
    total_deaths = (
        deaths.groupby(
            ["age", "sex", "uf"],
            as_index=False
        )["deaths"]
        .sum()
    )

    total = population.merge(
        total_deaths,
        on=["age", "sex", "uf"],
        how="left",
        validate="one_to_one"
    )

    total["deaths"] = (
        total["deaths"]
        .fillna(0)
        .astype(int)
    )

    total["mortality_rate"] = (
        total["deaths"] / total["population"]
    )

    total["rate_per_100k"] = (
        total["mortality_rate"] * 100_000
    )

    # Cause-specific mortality.
    by_cause = deaths.merge(
        population,
        on=["age", "sex", "uf"],
        how="left",
        validate="many_to_one",
        indicator=True
    )

    unmatched = by_cause["_merge"] != "both"

    if unmatched.any():
        raise ValueError(
            "Some SIM groups have no IBGE population denominator:\n"
            + by_cause.loc[
                unmatched, ["age", "sex", "uf"]
            ].drop_duplicates().to_string(index=False)
        )

    by_cause = by_cause.drop(columns="_merge")

    by_cause["mortality_rate"] = (
        by_cause["deaths"] / by_cause["population"]
    )

    by_cause["rate_per_100k"] = (
        by_cause["mortality_rate"] * 100_000
    )

    # Consistent column order.
    total = total[
        [
            "age", "sex", "uf",
            "deaths", "population",
            "mortality_rate", "rate_per_100k"
        ]
    ]

    by_cause = by_cause[
        [
            "age", "sex", "uf", "cause",
            "deaths", "population",
            "mortality_rate", "rate_per_100k"
        ]
    ]

    total = total.sort_values(
        ["uf", "sex", "age"]
    )

    by_cause = by_cause.sort_values(
        ["uf", "sex", "age", "cause"]
    )

    total.to_csv(
        output_dir / "mortality_total.csv",
        index=False,
        encoding="utf-8",
        float_format="%.12g"
    )

    by_cause.to_csv(
        output_dir / "mortality_by_cause.csv",
        index=False,
        encoding="utf-8",
        float_format="%.12g"
    )

    return total, by_cause


# ============================================================
# REPORT
# ============================================================

def write_report(
    output_dir, report, population, total, by_cause
):

    lines = [
        "SIM 2024 / IBGE 2024 PROCESSING REPORT",
        "=" * 45,
        "",
        "SIM FILTERING",
        ""
    ]

    for key, value in report.items():
        lines.append(f"{key}: {value:,}")

    lines += [
        "",
        "POPULATION",
        "",
        f"Rows: {len(population):,}",
        f"States: {population['uf'].nunique()}",
        f"Population: {population['population'].sum():,.0f}",
        "",
        "FINAL OUTPUTS",
        "",
        f"Total table rows: {len(total):,}",
        f"Cause table rows: {len(by_cause):,}",
        f"ICD-10 categories: {by_cause['cause'].nunique()}",
        f"Total deaths: {total['deaths'].sum():,}",
        "",
        "NOTES",
        "",
        "- Age is in completed years; 100 represents 100+.",
        "- Sex: M = male; F = female.",
        "- State is based on municipality of residence.",
        "- Cause is based on CAUSABAS (underlying cause).",
        "- Causes included: V01-V99, W00-W99, X00-X99, Y00-Y34.",
        "- Rates are deaths divided by the 2024 population.",
        "- These rates describe 2024, not future mortality forecasts.",
        "- Cause table contains observed causes only."
    ]

    (output_dir / "processing_report.txt").write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Process SIM 2024 and IBGE population data."
    )

    parser.add_argument(
        "--sim",
        type=Path,
        default=DATA_DIR / "Mortalidade_Geral_2024.csv"
    )

    parser.add_argument(
        "--population",
        type=Path,
        default=DATA_DIR / "projecoes_2024_tab1_idade_simples.xlsx"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR
    )

    parser.add_argument(
        "--chunksize",
        type=int,
        default=500_000
    )

    args = parser.parse_args()

    sim_path = Path(args.sim)
    population_path = Path(args.population)
    output_dir = Path(args.output)

    if not sim_path.exists():
        parser.error(f"SIM file not found: {sim_path}")

    if not population_path.exists():
        parser.error(
            f"Population file not found: {population_path}"
        )

    print("\nSTEP 1: Processing SIM mortality data")

    deaths, report = process_sim(
        sim_path,
        chunksize=args.chunksize
    )

    print("\nSTEP 2: Processing IBGE population data")

    population = process_population(
        population_path
    )

    print("\nSTEP 3: Calculating mortality rates")

    total, by_cause = calculate_rates(
        deaths,
        population,
        output_dir
    )

    print("\nSTEP 4: Generating processing report")

    write_report(
        output_dir,
        report,
        population,
        total,
        by_cause
    )

    print("\nPROCESSING COMPLETE!")
    print(f"Deaths included: {by_cause['deaths'].sum():,}")
    print(f"Cause-specific rows: {len(by_cause):,}")
    print(f"Total rows: {len(total):,}")
    print(f"Output directory: {output_dir.resolve()}")


if __name__ == "__main__":
    main()

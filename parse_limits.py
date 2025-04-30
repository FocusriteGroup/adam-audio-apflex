import argparse
import pandas as pd
import matplotlib.pyplot as plt

def calculate_absolute_limits(limits_path, reference_path, upper_output_path, lower_output_path):
    # Load the limits and reference data
    limits_df = pd.read_csv(limits_path)
    # print limts data
    #print(limits_df)

    reference_df = pd.read_csv(reference_path)  # Skip metadata rows

    # print first row of reference data
    print(reference_df.head(1))
    #copy the first row of the and store to a variable  



    # print first 6 rows of reference data
    print(reference_df.head(6))


if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Calculate absolute limits based on reference and relative limits.")
    parser.add_argument("limits", help="Path to the limits.csv file")
    parser.add_argument("reference", help="Path to the reference CSV file (1Ch or 2Ch)")
    parser.add_argument("upper_output", help="Path to save the output CSV file with upper absolute limits")
    parser.add_argument("lower_output", help="Path to save the output CSV file with lower absolute limits")
    args = parser.parse_args()

    # Run the calculation
    calculate_absolute_limits(args.limits, args.reference, args.upper_output, args.lower_output)
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import keyboard

def calculate_absolute_limits(limits_path, reference_path, upper_output_path, lower_output_path):
    # Load the limits and reference data
    limits_df = pd.read_csv(limits_path)
    # print limts data
    print(limits_df)
    
    reference_df = pd.read_csv(reference_path,skiprows=4)  # Skip metadata rows
    reference_header = pd.read_csv(reference_path, nrows=3)  # Read the first 3 rows for header info
    # Print the header of the reference file
    print(reference_header)

    print(reference_header.head(1))

    print(reference_header.iloc[0, 2])

    # Rename columns for easier access
    limits_df.columns = ["Lower_Freq", "Upper_Freq", "Upper_Limit", "Lower_Limit"]

    if "Ch2" in reference_df.columns or len(reference_df.columns) == 4:
        # Two-channel file
        reference_df.columns = ["Frequency", "Ch1", "Frequency2", "Ch2"]
        is_two_channel = True
    elif "Ch1" in reference_df.columns or len(reference_df.columns) == 2:
        # Single-channel file
        reference_df.columns = ["Frequency", "Ch1"]
        is_two_channel = False
    else:
        raise ValueError("Unexpected reference file format. Ensure the file has valid columns.")

    # Prepare results for upper and lower limits
    upper_results = []
    lower_results = []

    # Iterate through each frequency in the reference data
    for index, row in reference_df.iterrows():

        freq = row["Frequency"]
        #print(f"Processing frequency: {freq} Hz")
        #keyboard.wait('s')
        ch1_value = row["Ch1"]
        ch2_value = row["Ch2"] if is_two_channel else ch1_value  # Duplicate Ch1 for Ch2 if single-channel

        # Find the corresponding limit range
        limit_row = limits_df[(limits_df["Lower_Freq"] <= freq) & (limits_df["Upper_Freq"] > freq)]

        if not limit_row.empty:
            upper_limit = limit_row["Upper_Limit"].values[0]
            lower_limit = limit_row["Lower_Limit"].values[0]

            # Calculate absolute limits for Ch1 and Ch2
            ch1_upper = ch1_value + upper_limit
            ch1_lower = ch1_value + lower_limit
            ch2_upper = ch2_value + upper_limit
            ch2_lower = ch2_value + lower_limit

            upper_results.append([freq, ch1_upper, freq, ch2_upper])
            lower_results.append([freq, ch1_lower, freq, ch2_lower])
        else:
            # No matching limit range found
            pass
            #upper_results.append([freq, None, freq, None])
            #lower_results.append([freq, None, freq, None])

    # Create DataFrames for upper and lower limits
    upper_df = pd.DataFrame(upper_results, columns=["Frequency_Ch1", "Ch1", "Frequency_Ch2", "Ch2"])
    lower_df = pd.DataFrame(lower_results, columns=["Frequency_Ch1", "Ch1", "Frequency_Ch2", "Ch2"])

    # Save the results to separate CSV files
    upper_df.to_csv(upper_output_path, index=False)
    lower_df.to_csv(lower_output_path, index=False)
    print(f"Upper limits saved to {upper_output_path}")
    print(f"Lower limits saved to {lower_output_path}")

    # Plot the reference and absolute limits
    plot_reference_and_limits(reference_df, upper_df, lower_df, is_two_channel)

def plot_reference_and_limits(reference_df, upper_df, lower_df, is_two_channel):
    plt.figure(figsize=(12, 8))

    # Plot for Channel 1
    plt.plot(reference_df["Frequency"], reference_df["Ch1"], label="Reference Ch1", color="blue")
    plt.plot(upper_df["Frequency_Ch1"], upper_df["Ch1"], label="Ch1 Upper Limit", linestyle="--", color="green")
    plt.plot(lower_df["Frequency_Ch1"], lower_df["Ch1"], label="Ch1 Lower Limit", linestyle="--", color="red")

    if is_two_channel:
        # Plot for Channel 2
        plt.plot(reference_df["Frequency"], reference_df["Ch2"], label="Reference Ch2", color="orange")
        plt.plot(upper_df["Frequency_Ch2"], upper_df["Ch2"], label="Ch2 Upper Limit", linestyle="--", color="purple")
        plt.plot(lower_df["Frequency_Ch2"], lower_df["Ch2"], label="Ch2 Lower Limit", linestyle="--", color="brown")

    # Add labels, legend, and grid
    plt.xscale("log")  # Set x-axis to logarithmic scale
    plt.xlabel("Frequency (Hz)")
    plt.ylabel("Level (dB)")
    plt.title("Reference and Absolute Limits")
    plt.legend()
    plt.grid(True, which="both", linestyle="--", linewidth=0.5)  # Grid for both major and minor ticks
    plt.tight_layout()

    # Show the plot
    plt.show()

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
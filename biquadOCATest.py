from oca_tools.oca_utilities import OCP1ToolWrapper
from biquad_tools.biquad_designer import Biquad_Filter

# 1. Create the biquad filter
biquad = Biquad_Filter(
    filter_type="low_shelf",      # Choose: "bell", "high_shelf", "low_shelf"
    gain=6.0,                # Gain in dB
    peak_freq=1000.0,        # Frequency in Hz
    Q=1.0,                   # Quality factor
    sample_rate=48000
)

# 2. Extract the coefficients in [b0, b1, b2, a1, a2] format
coeffs_dict = biquad.coefficients
coeffs = [
    coeffs_dict["b0"],
    coeffs_dict["b1"],
    coeffs_dict["b2"],
    coeffs_dict["a1"],
    coeffs_dict["a2"]
]

print("🔧 Biquad Coefficients:")
print(coeffs)

# 3. Connect to the OCA device via the CLI wrapper
wrapper = OCP1ToolWrapper(
    cli_path="aes70-cli",         # Assumes it's next to oca_utilities.py
    target_ip="192.168.10.20",        # ✅ Your actual device IP
    port=50001                        # ✅ Your actual device port
)

# 4. Send the coefficients to band 0 (or change index)
response = wrapper.set_biquad(index=0, coefficients=coeffs)

print("📡 Device Response:")
print(response)
biquad.plot_transfer_function()

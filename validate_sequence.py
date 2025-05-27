import clr

# Load the APx API DLLs
clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API2.dll")
clr.AddReference(r"C:\\Program Files\\Audio Precision\\APx500 9.0\\API\\AudioPrecision.API.dll")

from AudioPrecision.API import APx500_Application

def main():
    # Attach to a running instance or create a new one
    try:
        apx = APx500_Application.GetInstance()
    except:
        apx = APx500_Application()

    # Bring GUI to front (optional)
    apx.Visible = True

    # Wake-up check
    try:
        print(f"[INFO] Connected to project: {apx.ProjectFileName}")
    except Exception as e:
        print(f"[ERROR] Failed to connect to APx: {e}")
        return

    # Ensure sequence mode is enabled
    apx.SequenceMode = True

    # Check if sequence has any steps
    if apx.Sequence.Count == 0:
        print("[ERROR] Sequence is empty. Nothing to run.")
        return

    # Run the sequence
    try:
        apx.Sequence.Run()
        print("[INFO] Sequence started.")
    except Exception as run_error:
        print(f"[ERROR] Failed to run sequence: {run_error}")

if __name__ == "__main__":
    main()

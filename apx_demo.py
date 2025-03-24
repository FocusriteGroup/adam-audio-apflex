import win32com.client

def main():
    # Create an instance of the Audio Precision API
    apx = win32com.client.Dispatch("APx500.Application")

    # Open a project file (replace with your actual project file path)
    project_path = "APSandbox.approjx"
    apx.OpenProject(project_path)

    # Start a measurement (replace with your actual measurement name)
    measurement_name = "Acoustic Response"
    apx.Measurements[measurement_name].Start()

    # Wait for the measurement to complete
    apx.Measurements[measurement_name].WaitForCompletion()

    # Retrieve measurement results (replace with your actual result name)
    result_name = "YourResultName"
    result = apx.Measurements[measurement_name].Results[result_name].Value

    # Print the result
    print(f"Measurement result: {result}")

    # Close the project
    apx.CloseProject()

if __name__ == "__main__":
    main()
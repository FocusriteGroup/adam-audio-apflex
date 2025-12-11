from services.workstation_logger import WorkstationLogger

WORKSTATION_ID = "TEST_WS"
SERVICE_HOST = "192.168.10.115"  
SERVICE_PORT = 65432

log_data = {
    "task": "test_log",
    "target": "dummy_target",
    "result": "Logger test successful"
}

WorkstationLogger.send_log_to_service(
    workstation_id=WORKSTATION_ID,
    log_data=log_data,
    service_host=SERVICE_HOST,
    service_port=SERVICE_PORT
)
print("Logger test sent!")
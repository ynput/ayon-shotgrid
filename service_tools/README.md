## Service tools
Helper tools to develop shotgrid services or parts of the services.

### How to run
At this moment there is available PowerShell script and Makefile. All commands expect that there is created virtual environment in `./venv`. These scripts depend on the existence of a `./.env`, use `example_env` as template. The contents of the file should be:
```
AYON_SERVER_URL={AYON server url}
AYON_API_KEY={AYON server api key (ideally service user)}
```

### Commands
- `createenv` - install requirements needed for running processed (requires Git)
- `leecher` - start leecher
- `processor` - start processor
- `transmitter` - start transmitter
- `services` - start all services

### Leecher 
Shotgrid leecher postpone shotgrid events into AYON event database. Is separated from processor to be able restart or have different shotgrid processors for different purposes loading events from single place. Using AYON server as middle-ware helps to know which event was already processed or is processing. In theory one event should not be processed multiple times. 

### Processor
Processor of shotgrid events. Is not loading events from shotgrid but from AYON database. Can get only one shotgrid event at once and if there is other running processor processing events under same identifier it won't continue to process next events until that is finished. That is due to race condition issues that may happen. Processor requires to have running **leecher**.

### Transmitter
Transmit AYON events to shotgrid.

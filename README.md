# Usage
Create python virtual enviroment, if not already created
```
python -m venv bddAqEnv
```

Activate python venv
```
.\bddAqEnv\Scripts\activate.bat 
```

Install dependencies, if not already installed

```
pip install -r requirements.txt
```

Connect BDD board using UART and run the app using commandline
```
__main__.py -p COM11 -1 0 -2 1 -1p 2000 -2p 4 -1f 1 -2f 100 -1d 50 -2d 50 -fs 7000 -o data.csv 
```

**REQUIRED command line parameters**
- `-p` `--port` COM port to use
- `-1` `--ch1_en` Channel 1 enable (0 or 1)
- `-2` `--ch2_en` Channel 2 enable (0 or 1)
- `-1p` `--ch1_polarity` Channel 1 polarity change interval - **seconds**
- `-2p` `--ch2_polarity` Channel 2 polarity change interval - **seconds**
- `-1f` `--ch1_pwmFreq` Channel 1 PWM frequency (0 disables PWM) - **Hz**
- `-1f` `--ch1_pwmFreq` Channel 2 PWM frequency (0 disables PWM) - **Hz**
- `-1d` `--ch1_pwmDuty` Channel 1 PWM duty (0 disables channel, 100 disables PWM) - **%**
- `-2d` `--ch2_pwmDuty` Channel 2 PWM duty (0 disables channel, 100 disables PWM) - **%**
- `-fs` `--sampleFreq` Measurement sampling frequency, should be at least 2*PWM frequency - **Hz**

**OPTIONAL command line parameters**
- `-o` `--output` Name of CSV file to which measured data will be written. If not specified, logging is disabled.

## Logging

App is logging data to specified file in CSV format with this header
```
"Timestamp", "CH1 Current (A)", "CH1 Voltage (V)", "CH1 Total charge (C)", "CH2 Current (A)", "CH2 Voltage (V)", "CH2 Total charge (C)"
```

## GUI
App has a simple gui available at http://localhost:8050  
Datas are refreshed every second. Values shown are an averaged values from last 1 second. Delta indicators show difference against long term average of last 10 seconds.

## Specialitky

When channel is left floating (no load connected, or high impedance), it should be disabled using `-1` or `-2` parameter. If floating channel is not disabled, measurements will be saturated with noise.

Maximum sampling frequency is 7 kHz, maximum PWM frequency is 562.5 kHz, maximum polarity change interval should be 65535 seconds. Duty cycle has resolution of 0.78 %

Maximum measured voltage is +-60V, with 10% offset error - real range is therefore approximately +-54V. Voltage is measured at the output so it will follow polarity change interval.
Maximum measured current is by default 10 A.
Resolution of both measurements is 16 bit, that is 1.8 mV for voltage and 0.15 mA for current. However noise is a significant factor, therefore reported values will have accuracy of +- 5%, if properly calibrated.

Offsets are calibrated automatically at every boot, values are mapped by predefined mapping transfer functions based on prototype device.
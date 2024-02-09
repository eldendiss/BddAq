import serial
import csv
import struct
import plotly.graph_objects as go

import sys, argparse
import threading
from datetime import datetime
from timscale import calculate_timer_params
from dash import Dash,dcc,html,callback,Input,Output, State
#use timscale.py


polynomial = 0x1021
init_crc = 0xFFFF

ch1Ibuffer = []
ch1Ubuffer = []
ch2Ibuffer = []
ch2Ubuffer = []
bufferLen = 1000

ch1ILongTerm = []
ch1ULongTerm = []
ch2ILongTerm = []
ch2ULongTerm = []
longTermLen = 1000

ch1charge = 0
ch2charge = 0

refU1 = 0
refU2 = 0
refI1 = 0
refI2 = 0

# File to save data
data_file = "received_data.csv"

# Control file
control_file = "control.txt"

def crc16_ccitt(data, poly=0x1021, init_val=0xFFFF):
    crc = init_val
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ poly
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc

def is_packet_valid(packet):
    # Extract the data and the CRC from the packet
    data, received_crc = packet[:-2], packet[-2:]
    calculated_crc = crc16_ccitt(data, polynomial, init_crc)

    # Combine the received CRC bytes and compare
    received_crc_value = (received_crc[0] << 8) | received_crc[1]
    return received_crc_value == calculated_crc

def read_packet(ser):
    try:
        if ser.in_waiting > 3000:  # Check if buffer is near its capacity
            # Handle potential buffer overflow here
            pass
    
        packet = ser.read(11)  # Read exactly 11 bytes for one packet
    
        if len(packet) == 11 and packet.endswith(b'\n'):
            return packet
        return None
    except Exception as e:
        return None

def combine_bytes(high_byte, low_byte):
    return (high_byte << 8) | low_byte

def convert_current(adc_value):
    if adc_value == 0:
        return 0
    val = (adc_value + 83.785) / 6163.6
    
    #round to 2 decimal places
    return round(val, 2)

def convert_voltage(adc_value):
    
    if adc_value < 32768:
        val = (adc_value + 67.8011) / 587.1251
    if adc_value > 32768:
        val =  (adc_value - 65476) / 587.2795
    if adc_value == 32768:
        val =  0
    return round(val, 2)
    
    

def create_packet(ch1_en, ch1_polarity, ch1_pwmFreq, ch1_pwmDuty, ch2_en, ch2_polarity, ch2_pwmFreq, ch2_pwmDuty, sampleFreq):
    global bufferLen, longTermLen
    # Create a packet with the given parameters
    fmt = '<BIIBBIIBHH'

    #calculate time in microseconds from sample frequency
    # Pack the values into a binary string
    arr, psc = calculate_timer_params(sampleFreq,72000000)
    bufferLen = sampleFreq
    longTermLen = 10*sampleFreq
    
    packet = struct.pack(fmt, ch1_en, ch1_polarity, ch1_pwmFreq, ch1_pwmDuty,
                                ch2_en, ch2_polarity, ch2_pwmFreq, ch2_pwmDuty, arr, psc)

    # Ensure the length is 24 bytes
    assert len(packet) == 24, "Packet length is not 24 bytes!"

    return packet

def readAndSaveData(ser, csvfile,start_time, args, kill):
    global ch1charge, ch2charge
    
    if csvfile is not None:
        csvwriter = csv.writer(csvfile)
        #write current args to file
        csvwriter.writerow(["Port", "CH1 Enable", "CH1 Polarity (s)", "CH1 PWM Frequency (Hz)", "CH1 PWM Duty (%)", "CH2 Enable", "CH2 Polarity (s)", "CH2 PWM Frequency (Hz)", "CH2 PWM Duty (%)", "Sample Frequency (Hz)"])
        csvwriter.writerow([args.port, args.ch1_en, args.ch1_polarity, args.ch1_pwmFreq, args.ch1_pwmDuty, args.ch2_en, args.ch2_polarity, args.ch2_pwmFreq, args.ch2_pwmDuty, args.sampleFreq])
        csvwriter.writerow(["Timestamp", "CH1 Current (A)", "CH1 Voltage (V)", "CH1 Total charge (C)", "CH2 Current (A)", "CH2 Voltage (V)", "CH2 Total charge (C)"])

    try:
        while True:
            if(kill):
                return
            packet = read_packet(ser)
            if packet and is_packet_valid(packet[:-1]):  # Exclude newline from CRC check
                ch1_current = convert_current(combine_bytes(packet[0], packet[1]))
                ch1_voltage = convert_voltage(combine_bytes(packet[2], packet[3]))
                ch2_current = convert_current(combine_bytes(packet[4], packet[5]))
                ch2_voltage = convert_voltage(combine_bytes(packet[6], packet[7]))

                elapsed_time = int((datetime.now() - start_time).total_seconds() * 1e6)

                ch1charge += round((1/args.sampleFreq)*ch1_current,2)
                ch2charge += round((1/args.sampleFreq)*ch2_current,2)
                if csvfile is not None:
                    csvwriter.writerow([elapsed_time, ch1_current, ch1_voltage, ch1charge, ch2_current, ch2_voltage, ch2charge])
                    csvfile.flush()
                
                ch1Ibuffer.append(ch1_current)
                ch1Ubuffer.append(ch1_voltage)
                ch2Ibuffer.append(ch2_current)
                ch2Ubuffer.append(ch2_voltage)
                if len(ch1Ibuffer) > bufferLen:
                    ch1ILongTerm.append(sum(ch1Ibuffer)/len(ch1Ibuffer))
                    if len(ch1ILongTerm) > longTermLen:
                        ch1ILongTerm.pop(0)
                    ch1Ibuffer.pop(0)
                if len(ch1Ubuffer) > bufferLen:
                    ch1ULongTerm.append(sum(ch1Ubuffer)/len(ch1Ubuffer))
                    if len(ch1ULongTerm) > longTermLen:
                        ch1ULongTerm.pop(0)
                    ch1Ubuffer.pop(0)
                if len(ch2Ibuffer) > bufferLen:
                    ch2ILongTerm.append(sum(ch2Ibuffer)/len(ch2Ibuffer))
                    if len(ch2ILongTerm) > longTermLen:
                        ch2ILongTerm.pop(0)
                    ch2Ibuffer.pop(0)
                if len(ch2Ubuffer) > bufferLen:
                    ch2ULongTerm.append(sum(ch2Ubuffer)/len(ch2Ubuffer))
                    if len(ch2ULongTerm) > longTermLen:
                        ch2ULongTerm.pop(0)
                    ch2Ubuffer.pop(0)
    except KeyboardInterrupt:
        return
 
@callback(Output('ch1I', 'figure'),
          Input('interval-component', 'n_intervals'))   
def updateCh1I(n):
    global refI1
    
    ch1I = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = 0,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "CH1 Current (A)"},
        delta = {'reference': refI1},
        gauge = {'axis': {'range': [None, 10]},
                 'steps' : [
                    {"range": [0, 8], "color": "#04756F"},
                    {"range": [8, 9], "color": "#FF8C00"},
                    {"range": [9, 10], "color": "#D90000"}],
                 'bar': {'color': "#FF8C00"}}))
    ch1I.update_layout(paper_bgcolor = "#2E0927", font = {"color": "#FF8C00"})
    if len(ch1Ibuffer) > 0:
                ch1I.update_traces(value=sum(ch1Ibuffer)/len(ch1Ibuffer))
                
    return ch1I

@callback(Output('ch1U', 'figure'),
          Input('interval-component', 'n_intervals'))   
def updateCh1U(n):
    global refU1
    ch1U = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = 0,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "CH1 Voltage (V)"},
        delta = {'reference': refU1},
        gauge = {'axis': {'range': [None, 60]},
                 'steps' : [
                    {"range": [0, 50], "color": "#04756F"},
                    {"range": [50, 55], "color": "#FF8C00"},
                    {"range": [55, 60], "color": "#D90000"}],
                 'bar': {'color': "#FF8C00"}}))
    ch1U.update_layout(paper_bgcolor = "#2E0927", font = {"color": "#FF8C00"})
    if len(ch1Ubuffer) > 0:
                ch1U.update_traces(value=sum(ch1Ubuffer)/len(ch1Ubuffer))
                
    return ch1U
             
@callback(Output('ch2I', 'figure'),
          Input('interval-component', 'n_intervals'))                   
def updateCh2I(n):
    global refI2
    ch2I = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = 0,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "CH2 Current (A)"},
        delta = {'reference': refI2},
        gauge = {'axis': {'range': [None, 10]},
                 'steps' : [
                    {"range": [0, 8], "color": "#04756F"},
                    {"range": [8, 9], "color": "#FF8C00"},
                    {"range": [9, 10], "color": "#D90000"}],
                 'bar': {'color': "#FF8C00"}}))
    ch2I.update_layout(paper_bgcolor = "#2E0927", font = {"color": "#FF8C00"})
    if len(ch2Ibuffer) > 0:
                ch2I.update_traces(value=sum(ch2Ibuffer)/len(ch2Ibuffer))
    
    return ch2I

@callback(Output('ch2U', 'figure'),
          Input('interval-component', 'n_intervals'))   
def updateCh2U(n):
    global refU2
    ch2U = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = 0,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "CH2 Voltage (V)"},
        delta = {'reference': refU2},
        gauge = {'axis': {'range': [None, 60]},
                 'steps' : [
                    {"range": [0, 50], "color": "#04756F"},
                    {"range": [50, 55], "color": "#FF2D00"},
                    {"range": [55, 60], "color": "#D90000"}],
                 'bar': {'color': "#FF8C00"}}))
    ch2U.update_layout(paper_bgcolor = "#2E0927", font = {"color": "#FF8C00"})
    if len(ch2Ubuffer) > 0:
                ch2U.update_traces(value=sum(ch2Ubuffer)/len(ch2Ubuffer))
                
    return ch2U
         
@callback(Output('ch1C', 'children'),
          Input('interval-component', 'n_intervals'))          
def updateCh1Charge(n):
    formatted_charge = "{:.2f}".format(ch1charge)
    var = html.H3(f"{formatted_charge} C")
    return var

@callback(Output('ch2C', 'children'),
          Input('interval-component', 'n_intervals'))   
def updateCh1Charge(n):
    formatted_charge = "{:.2f}".format(ch2charge)
    var = html.H3(f"{formatted_charge} C")
    return var

@callback(  Output('ch1I','reference'),  
            Input('set_ref1', 'n_clicks'),
            State('ch1I', 'figure'),
            prevent_initial_call=True
)
def set_ref1I(n_clicks, value):
    global refI1
    if len(ch1ILongTerm) >= 0:
        refI1 = sum(ch1ILongTerm)/len(ch1ILongTerm)
    return refI1

@callback(  Output('ch1U','reference'),
            Input('set_ref1', 'n_clicks'),
            State('ch1U', 'figure'),
            prevent_initial_call=True
)
def set_ref1U(n_clicks, value):
    global refU1
    if len(ch1ULongTerm) >= 0:
        refU1 = sum(ch1ULongTerm)/len(ch1ULongTerm)
    return refU1
    

@callback(  Output('ch2I','reference'),
            Input('set_ref2', 'n_clicks'),
            State('ch2I', 'figure'),
            prevent_initial_call=True
)
def set_ref2I(n_clicks, value):
    global refI2
    if len(ch2ILongTerm) >= 0:
        refI2 = sum(ch2ILongTerm)/len(ch2ILongTerm)
    return refI2

@callback(  Output('ch2U','reference'),
            Input('set_ref2', 'n_clicks'),
            State('ch2U', 'figure'),
            prevent_initial_call=True
)
def set_ref2U(n_clicks, value):
    global refU2
    if len(ch2ULongTerm) >= 0:
        refU2 = sum(ch2ULongTerm)/len(ch2ULongTerm)
    return refU2

def main(argv):
    kill = False
    #get port number, ch1_en, ch1_polarity, ch1_pwmFreq, ch1_pwmDuty, ch2_en, ch2_polarity, ch2_pwmFreq, ch2_pwmDuty, sampleFreq
    try:
        parser = argparse.ArgumentParser(description='Process packet parameters.')
        parser.add_argument('-p', '--port', help='Port number', required=True)
        parser.add_argument('-1', '--ch1_en', help='Channel 1 Enable', type=int, required=False, default=0)
        parser.add_argument('-2', '--ch2_en', help='Channel 2 Enable', type=int, required=False, default=0)
        parser.add_argument('-1p', '--ch1_polarity', help='Channel 1 Polarity', type=int, required=False, default=0)
        parser.add_argument('-2p', '--ch2_polarity', help='Channel 2 Polarity', type=int, required=False, default=0)
        parser.add_argument('-1f', '--ch1_pwmFreq', help='Channel 1 PWM Frequency', type=int, required=False, default=0)
        parser.add_argument('-2f', '--ch2_pwmFreq', help='Channel 2 PWM Frequency', type=int, required=False, default=0)
        parser.add_argument('-1d', '--ch1_pwmDuty', help='Channel 1 PWM Duty', type=int, required=False, default=0)
        parser.add_argument('-2d', '--ch2_pwmDuty', help='Channel 2 PWM Duty', type=int, required=False, default=0)
        parser.add_argument('-fs', '--sampleFreq', help='Sampling Frequency', type=int, required=False, default=0)
        parser.add_argument('-o', '--output', help='CSV output file', required=False, default=None)

        args = parser.parse_args()
    except argparse.ArgumentError:
        print('Usage: main.py -p <port> -1 <ch1_en> -2 <ch2_en> -1p <ch1_polarity> -2p <ch2_polarity> -1f <ch1_pwmFreq> -2f <ch2_pwmFreq> -1d <ch1_pwmDuty> -2d <ch2_pwmDuty> -fs <sampleFrequency> -o <outputFile>')
        sys.exit(2)
        
    #initialize windows
    
    try:
        ser = serial.Serial(args.port, baudrate=921600)  # Adjust the port and baudrate accordingly
        ser.timeout = 0 
        #ser.open()
        #get cmd parameters
        #send start packet
        packet = create_packet(args.ch1_en, args.ch1_polarity, args.ch1_pwmFreq, args.ch1_pwmDuty, args.ch2_en, args.ch2_polarity, args.ch2_pwmFreq, args.ch2_pwmDuty, args.sampleFreq)
        #send packet
        ser.write(packet)
        ser.flush()
        
        # Synchronize with the start of a packet
        while True:
        # Read one byte at a time until you find the newline character
            byte = ser.read(1)
            if byte == b'\n':
                break  # Newline found, synchronization complete
            
        start_time = datetime.now()  # Record the start time
    except Exception as e:
        print(f"Error opening serial port: {e}")
        exit()
    
    app = Dash("bddaq")
    app.css.append_css({"external_url": "/assets/style.css"})
    app.server.static_folder = 'assets'
    app.layout = html.Div([
    html.Div([
        dcc.Graph(id='ch1I'),
        dcc.Graph(id='ch1U'),
        html.H4(children='CH1 Total Charge (C)',style={'color': '#FF8C00', 'font-family': 'sans-serif', 'text-align': 'center'}),
        html.H3(id='ch1C',style={'color': '#FF8C00', 'font-family': 'sans-serif', 'text-align': 'center'}),
        html.Button('Set reference', id='set_ref1', n_clicks=0, style={'text-align': 'center', 'display': 'block', 'margin': 'auto', 'width': '50%'}),
    ], style={'display': 'inline-block', 'width': '50%'}),  # First row with two graphs side by side
    html.Div([
        dcc.Graph(id='ch2I'),
        dcc.Graph(id='ch2U'),
        html.H4(children='CH2 Total Charge (C)',style={'color': '#FF8C00', 'font-family': 'sans-serif', 'text-align': 'center'}),
        html.H3(id='ch2C',style={'color': '#FF8C00', 'font-family': 'sans-serif', 'text-align': 'center'}),
        html.Button('Set reference', id='set_ref2', n_clicks=0, style={'text-align': 'center', 'display': 'block', 'margin': 'auto', 'width': '50%'}),
    ], style={'display': 'inline-block', 'width': '50%'}),  # Second row with two graphs side by side
    dcc.Interval(
        id='interval-component',
        interval=1*1000, # in milliseconds
        n_intervals=0
    )
    ])
    
    #if file exists, rename it
    if args.output:
        try:
            with open(args.output, 'r') as f:
                pass
            import os
            args.output = f"{args.output.split('.')[0]}_{datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.csv"
        except FileNotFoundError:
            pass
    
    
    # Continuously read data
    if args.output:
        csvfile = open(args.output, 'w', newline='')
    else:
        csvfile = None

    # Create a thread for reading data from the serial port
    serial_thread = threading.Thread(target=readAndSaveData, args=(ser, csvfile,start_time, args, kill))
    serial_thread.start()
    
    
    app.run(debug=True, use_reloader=False)
    # catch keyboard interrupt
    try:
        while True:
            pass
    except KeyboardInterrupt:
        print("Stopped by User")
        # write stop packet (24 0 bytes)
        ser.write(bytearray(24))        
        ser.close()
        if csvfile is not None:
            csvfile.close()
        #destroy serial thread
        kill = True
        import os
        os._exit(0)
            
if __name__ == "__main__":
    main(sys.argv[1:])
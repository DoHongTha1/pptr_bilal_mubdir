import socket
import matplotlib.pyplot as plt
import time
import threading
import queue
import sys
import select  # For non-blocking input


# Settings
collectionRate = 0.1
liveUpdateRate = collectionRate/2


# Network details
NODEMCU_IP = "192.168.4.1"
UDP_PORT = 4210
BUFFER_SIZE = 1024  


# Initialize UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(1.0)  

# CSV file
csv_filename = "sensor_data_udp.csv"

# Data storage
timestamps = []
sensor_data = {f"Sensor {i+1}": [] for i in range(12)}

# Flag to stop the loop
running = True

# Queue for thread-safe data transfer
data_queue = queue.Queue()

sensor_labels = [
    "Tachometer (Hz)", "Torque 1 (mN.m)", "Torque 2 (mN.m)", "Thrust (g)", 
    "Shunt Voltage (mV)", "Supply Voltage (V)", "Speed (RPM)", "Motor Voltage (V)", 
    "Motor Current (mA)", "Motor Electrical Power (mW)", "Motor Mechanical Power (mW)", "Motor Efficiency (%)"
]

# Function to collect sensor data
def collect_data():
    global running
    start_time = time.time()

    with open(csv_filename, "w") as f:
        f.write("Timestamp(ms),Tachometer(Hz),Torque 1(mN.m),Torque 2(mN.m),Thrust(g),Shunt Voltage(mV),Supply Voltage(V),Speed(RPM), Motor Voltage(V),Motor Current(mA),Motor Electrical Power(mW),Motor Mechanical Power(mW),Motor Efficiency(%)\n")

    while running:
        try:
            sock.sendto(b"CM3", (NODEMCU_IP, UDP_PORT))
            data, _ = sock.recvfrom(BUFFER_SIZE)
            values = data.decode().strip().split(",")
            values = [float(v) for v in values]
            rpm = values[0]*60.00
            shuntVoltage_mV = values[4]/1000.00
            values[4] = shuntVoltage_mV
            loadVoltage_V  = (values[5]/1.00) + (shuntVoltage_mV/1000.00)
            current_mA = shuntVoltage_mV/0.01
            power_mW = current_mA*loadVoltage_V
            values.append(rpm)
            values.append(loadVoltage_V)
            values.append(current_mA)
            values.append(power_mW)
            values.append(((values[1]+values[2])/2)*2*3.141*values[0])
            values.append(power_mW*100)
            
            if len(values) == 12:
                current_time = round((time.time() - start_time) * 1000) / 1000  # Convert ms to sec
                data_point = (current_time, [float(v) for v in values])
                data_queue.put(data_point)  # for live graph

                with open(csv_filename, "a") as f:  # Append mode
                    f.write(f"{current_time}," + ",".join([str(v) for v in values]) + "\n")

        except socket.timeout:
            5
        time.sleep(collectionRate)

# Start data collection thread
data_thread = threading.Thread(target=collect_data, daemon=True)
data_thread.start()

# Initialize sensor_data only once
sensor_data = {label: [] for label in sensor_labels}  # Initialize only once, not inside the loop

# **Main Thread: Plotting**
plt.ion()
fig, axes = plt.subplots(4, 3, figsize=(10, 10), sharex=True)

last_update = time.time()  # Track last update time

try:
    while running:
        # Process all queue data
        while not data_queue.empty():
            current_time, values = data_queue.get()
            timestamps.append(current_time)
            
            # Append values to sensor_data, ensuring the correct index
            for i, value in enumerate(values):
                if i < len(sensor_labels):  # Ensure index is within bounds
                    sensor_data[sensor_labels[i]].append(value)  # Append new data to existing lists

        # Update the plot every `liveUpdateRate` seconds (reduce UI lag)
        if time.time() - last_update > liveUpdateRate:
            for i, (sensor, values) in enumerate(sensor_data.items()):
                if timestamps:
                    row, col = divmod(i, 3)
                    axes[row, col].cla()  # Clear the axes
                    axes[row, col].plot(timestamps, values, label=sensor)
                    axes[row, col].set_ylabel(sensor)
                    # axes[row, col].legend([sensor])

            plt.xlabel("Time (seconds)")
            fig.canvas.draw()
            fig.canvas.flush_events()
            last_update = time.time()  # Reset update time

        # **Non-blocking user input to stop**
        if select.select([sys.stdin], [], [], 0.1)[0]:  # Check for input
            user_input = sys.stdin.readline().strip()

            if user_input.lower() == "exit":  # Stop if "exit" is typed
                running = False
            else:
                sock.sendto(user_input.encode(), (NODEMCU_IP, UDP_PORT))  # Send user input to NodeMCU
                print(f"Sent: {user_input}")

except KeyboardInterrupt:
    print("Stopping...")

# Ensure data collection thread stops
data_thread.join()

# Final plot
plt.ioff()
plt.figure(figsize=(10, 10))
for i, (sensor, values) in enumerate(sensor_data.items()):
    plt.subplot(4, 3, i + 1)
    plt.plot(timestamps, values, label=sensor)
    plt.ylabel(sensor)
    plt.legend()

plt.xlabel("Time (seconds)")
plt.show()

print("Data collection stopped. Final graph displayed.")
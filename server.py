from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse
import asyncio
import re
import time
import threading
from datetime import datetime
import uvicorn
import json
from collections import deque

app = FastAPI(title="ESP32 Button Sequence Monitor")

# Variables to track vibration status and current event
should_vibrate = False
current_event = 'no_event'
vibration_timeout = None
button_sequence = []  # Track button press sequence (Only Button 2, 3, and 4)
active_websocket = None  # Track the active WebSocket connection (single client)
message_queue = deque(maxlen=50)  # Single message queue with max 50 messages
message_retention_period = 3600  # How long to keep messages in seconds (1 hour)

# Function to broadcast message to the client or queue it if disconnected
async def send_message(message):
    # Skip queueing for reset events
    if message.get('triggerVibration') == False and message.get('currentEvent') == 'no_event':
        print("Reset event detected - not adding to queue as requested")
        
        # Only send if client is connected, otherwise discard
        if active_websocket:
            try:
                await active_websocket.send_json(message)
                print(f"Reset message sent to connected client")
            except Exception as e:
                print(f"Error sending reset message: {e}")
        else:
            print("Reset event ignored (no connected client)")
        return
        
    # Normal processing for other messages
    # Store the message with timestamp
    current_time = datetime.now().isoformat()
    message_queue.append({
        'timestamp': current_time,
        'message': message
    })
    
    # Log message queue status
    print(f"Added message to queue: {json.dumps(message)}")
    print(f"Queue size is now: {len(message_queue)}")
    
    # If client is connected, send the message
    if active_websocket:
        try:
            await active_websocket.send_json(message)
            print(f"Message sent to connected client: {json.dumps(message)}")
        except Exception as e:
            print(f"Error sending message: {e}")
            print("Message remains in queue for later delivery")
    else:
        print(f"No client connected - message queued for later delivery")

# Function to reset vibration after timeout
def reset_vibration(timeout_seconds):
    global should_vibrate, current_event
    time.sleep(timeout_seconds)
    should_vibrate = False
    current_event = 'no_event'
    print("Vibration reset to false after timeout.")
    
    # Create a new event loop for the thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run the broadcast in this new loop
    loop.run_until_complete(send_message({'triggerVibration': False, 'currentEvent': 'no_event'}))
    loop.close()

# Clean up old messages
def cleanup_old_messages():
    global message_queue
    current_time = datetime.now()
    
    # Create a new queue to hold non-expired messages
    valid_messages = deque(maxlen=message_queue.maxlen)
    
    for msg in message_queue:
        message_time = datetime.fromisoformat(msg['timestamp'])
        time_diff = (current_time - message_time).total_seconds()
        
        # Keep message if it's still within retention period
        if time_diff <= message_retention_period:
            valid_messages.append(msg)
    
    # Replace the queue with only valid messages
    old_size = len(message_queue)
    message_queue = valid_messages
    new_size = len(message_queue)
    
    if old_size != new_size:
        print(f"Cleaned up message queue: removed {old_size - new_size} old messages")
    
    # Schedule next cleanup
    threading.Timer(300, cleanup_old_messages).start()  # Every 5 minutes

# Basic home route
@app.get("/")
async def home():
    return {"message": "ESP32 Button Sequence Monitor Server is Running!"}

# WebSocket endpoint - same path as your Fitbit app expects
@app.websocket("/signal")
async def websocket_endpoint(websocket: WebSocket):
    global active_websocket, message_queue
    
    await websocket.accept()
    
    # Store as the active websocket
    active_websocket = websocket
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{timestamp}] ✅ Client connected")
    
    # Send current state immediately upon connection
    await websocket.send_json({
        'triggerVibration': should_vibrate,
        'currentEvent': current_event
    })
    print(f"Sent current state: vibration={should_vibrate}, event={current_event}")
    
    # Check if there are queued messages
    queued_message_count = len(message_queue)
    print(f"Checking queue status: {queued_message_count} messages pending")
    
    if queued_message_count > 0:
        print(f"Found {queued_message_count} queued messages to deliver:")
        
        # Create a copy of the queue for processing
        messages_to_send = list(message_queue)
        message_queue.clear()  # Clear the queue
        print(f"Queue cleared. Processing {len(messages_to_send)} messages")
        
        # Process each queued message
        for i, message_data in enumerate(messages_to_send):
            try:
                # Check if message is still relevant based on timestamp
                message_time = datetime.fromisoformat(message_data['timestamp'])
                current_time = datetime.now()
                time_diff = (current_time - message_time).total_seconds()
                
                # Only send if not too old
                if time_diff <= message_retention_period:
                    message_content = message_data['message']
                    print(f"Delivering message {i+1}/{len(messages_to_send)}: {json.dumps(message_content)}")
                    
                    await websocket.send_json(message_content)
                    await asyncio.sleep(1)  # 1 second delay between messages
                    
                    print(f"Successfully delivered message from {message_data['timestamp']}")
                else:
                    print(f"Skipping message from {message_data['timestamp']} - too old (age: {time_diff}s)")
            except Exception as e:
                print(f"Error sending queued message: {e}")
                # Put the message back in the queue if there was an error sending it
                message_queue.append(message_data)
                print(f"Message re-queued due to error")
    else:
        print("No queued messages to deliver")
    
    try:
        # Keep the connection open
        while True:
            # Wait for any messages from client (not expected in your case)
            data = await websocket.receive_text()
            print(f"Message received from client: {data}")
            
    except WebSocketDisconnect:
        # Handle disconnection
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{timestamp}] ❌ Client disconnected")
        active_websocket = None
    
    except Exception as e:
        print(f"Error in WebSocket handler: {e}")
        active_websocket = None
        print(f"WebSocket connection closed due to error: {e}")

# Signal endpoint - POST to update status
@app.post("/signal")
async def post_signal(request: Request):
    global should_vibrate, current_event, button_sequence, vibration_timeout
    
    try:
        data = await request.json()
        print(f"Received data: {data}")
        
        if not data:
            return JSONResponse(
                status_code=400,
                content={'success': False, 'message': 'No JSON data received'}
            )
        
        # Check if we're receiving button press data from ESP32
        if data.get('device') == "ESP32":
            # Check each button message
            button_messages = {
                "button1": data.get('message1'),
                "button2": data.get('message2'),
                "button3": data.get('message3'),
                "button4": data.get('message4')
            }
            
            # Process button presses
            for button, status in button_messages.items():
                if status and "Pressed" in status:
                    button_num = int(button[-1])  # Extract button number
                    
                    if button_num == 1:
                        print("*** Door Bell is Rung! ***")
                        
                        # Set vibration for doorbell
                        should_vibrate = True
                        current_event = 'main_button_pressed'
                        
                        # Clear any existing timeout thread
                        if vibration_timeout and vibration_timeout.is_alive():
                            vibration_timeout.cancel()
                        
                        # Set new timeout thread
                        vibration_timeout = threading.Timer(5.0, reset_vibration, [5])
                        vibration_timeout.daemon = True
                        vibration_timeout.start()
                        
                        # Send to client or queue with proper format
                        await send_message({
                            'triggerVibration': should_vibrate, 
                            'currentEvent': current_event
                        })
                    else:
                        # Add the button press to the sequence
                        button_sequence.append(button_num)
                        print(f"{button.capitalize()} Pressed! Current sequence: {button_sequence}")
            
            # Ensure only the last 3 button presses are stored
            if len(button_sequence) > 3:
                button_sequence.pop(0)  # Keep only the last 3 button presses
                print(f"Sequence window shifted. Current sequence: {button_sequence}")
            
            # If exactly 3 button presses are stored, check the sequence
            if len(button_sequence) == 3:
                print(f"Complete sequence detected: {button_sequence}")
                
                sequence_matched = True
                passcode_number = 0
                visitor_name = "Unknown"
                
                # Check predefined sequences and set appropriate event
                if button_sequence == [2, 3, 4]:
                    print("*** Sequence [2,3,4] recognized - Rohit is here! ***")
                    passcode_number = 1
                    current_event = f"correct_input_{passcode_number}"
                    visitor_name = "Rohit"
                elif button_sequence == [2, 2, 2]:
                    print("*** Sequence [2,2,2] recognized - Francis is here! ***")
                    passcode_number = 2
                    current_event = f"correct_input_{passcode_number}"
                    visitor_name = "Francis"
                elif button_sequence == [3, 3, 3]:
                    print("*** Sequence [3,3,3] recognized - Michael is here! ***")
                    passcode_number = 3
                    current_event = f"correct_input_{passcode_number}"
                    visitor_name = "Michael"
                else:
                    print(f"❌ Error! Unknown sequence {button_sequence} ❌")
                    current_event = "incorrect_input"
                    sequence_matched = False
                
                # Set vibration based on sequence match
                should_vibrate = sequence_matched
                
                # Clear any existing timeout thread
                if vibration_timeout and vibration_timeout.is_alive():
                    vibration_timeout.cancel()
                
                if sequence_matched:
                    # Set new timeout thread
                    vibration_timeout = threading.Timer(5.0, reset_vibration, [5])
                    vibration_timeout.daemon = True
                    vibration_timeout.start()
                    
                    # Send to client or queue with proper format
                    await send_message({
                        'triggerVibration': should_vibrate,
                        'currentEvent': current_event,
                        'passcode': str(passcode_number),
                        'visitorName': visitor_name
                    })
                    
                    print(f"Visitor notification sent: {visitor_name} (passcode: {passcode_number})")
                else:
                    # For incorrect sequence
                    vibration_timeout = threading.Timer(5.0, reset_vibration, [5])
                    vibration_timeout.daemon = True
                    vibration_timeout.start()
                    
                    # Send to client or queue with proper format
                    await send_message({
                        'triggerVibration': should_vibrate, 
                        'currentEvent': current_event
                    })
                    
                    print("Incorrect sequence notification sent")
                
                # Reset sequence after checking
                button_sequence = []
                print("Sequence reset for next visitor")
            
            return {
                'success': True,
                'triggerVibration': should_vibrate,
                'currentEvent': current_event,
                'currentSequence': button_sequence
            }
            
        # For direct event specifiers (rarely used but supported)
        elif data.get('event'):
            event_type = data.get('event')
            print(f"Direct event request received: {event_type}")
            
            if event_type == 'main_button_pressed':
                should_vibrate = True
                current_event = 'main_button_pressed'
                
                # Clear any existing timeout thread
                if vibration_timeout and vibration_timeout.is_alive():
                    vibration_timeout.cancel()
                
                # Set new timeout thread
                vibration_timeout = threading.Timer(5.0, reset_vibration, [5])
                vibration_timeout.daemon = True
                vibration_timeout.start()
                
                # Send to client or queue with proper format
                await send_message({
                    'triggerVibration': should_vibrate, 
                    'currentEvent': current_event
                })
                
                return {'triggerVibration': should_vibrate}
            
            # For explicitly setting a visitor event without button sequence
            correct_input_regex = r'^correct_input_(\d+)$'
            match = re.match(correct_input_regex, event_type)
            
            if match:
                passcode_number = match.group(1)
                print(f"Direct visitor passcode received: {passcode_number}")
                
                # Map passcode to visitor name
                visitor_names = {
                    "1": "Rohit",
                    "2": "Francis", 
                    "3": "Michael",
                    "221": "Sam",
                    "222": "Jon",
                    "223": "Mike"
                }
                visitor_name = visitor_names.get(passcode_number, "Unknown")
                
                should_vibrate = True
                current_event = f"correct_input_{passcode_number}"
                
                # Clear any existing timeout thread
                if vibration_timeout and vibration_timeout.is_alive():
                    vibration_timeout.cancel()
                
                # Set new timeout thread
                vibration_timeout = threading.Timer(5.0, reset_vibration, [5])
                vibration_timeout.daemon = True
                vibration_timeout.start()
                
                # Send to client or queue with proper format
                await send_message({
                    'triggerVibration': should_vibrate,
                    'currentEvent': current_event,
                    'passcode': passcode_number,
                    'visitorName': visitor_name
                })
                
                return {
                    'triggerVibration': should_vibrate,
                    'passcode': passcode_number,
                    'visitorName': visitor_name
                }
            
            # If no recognized event was found
            print(f"Unrecognized event type: {event_type}")
            return JSONResponse(
                status_code=400,
                content={'success': False, 'message': f'Unrecognized event type: {event_type}'}
            )
        
        # If neither device nor event was found in the request
        else:
            print("Invalid request format - missing device or event")
            return JSONResponse(
                status_code=400,
                content={'success': False, 'message': 'Invalid request format - missing device or event'}
            )
    
    except Exception as e:
        print(f"Error handling POST request: {e}")
        return JSONResponse(
            status_code=500,
            content={'success': False, 'message': f'Internal Server Error: {str(e)}'}
        )

# Signal endpoint - GET to check current status
@app.get("/signal")
async def get_signal():
    try:
        return {
            'triggerVibration': should_vibrate,
            'currentEvent': current_event
        }
    except Exception as e:
        print(f"Error handling GET request: {e}")
        return JSONResponse(
            status_code=500,
            content={'success': False, 'message': 'Internal Server Error'}
        )

# Get message queue info
@app.get("/queue-status")
async def get_queue_status():
    try:
        queue_messages = []
        for i, msg in enumerate(message_queue):
            queue_messages.append({
                "index": i,
                "timestamp": msg['timestamp'],
                "message": msg['message']
            })
            
        return {
            "clientConnected": active_websocket is not None,
            "queuedMessages": len(message_queue),
            "oldestMessageTime": message_queue[0]['timestamp'] if message_queue else None,
            "newestMessageTime": message_queue[-1]['timestamp'] if message_queue else None,
            "messages": queue_messages
        }
    except Exception as e:
        print(f"Error handling queue status request: {e}")
        return JSONResponse(
            status_code=500,
            content={'success': False, 'message': f'Internal Server Error: {str(e)}'}
        )

# Run the server
if __name__ == "__main__":
    print("\n=== ESP32 Button Sequence Monitor Server ===")
    print("Starting FastAPI server with WebSocket support and message queuing...")
    print("This server handles both HTTP endpoints and WebSocket connections on port 3000")
    
    # Start message cleanup scheduler
    cleanup_old_messages()
    
    # Configure Uvicorn with websocket ping/pong interval (50 seconds)
    uvicorn.run(
        "server:app",  # Make sure this file is named server.py
        host="0.0.0.0",
        port=3000,
        log_level="info",
        ws_ping_interval=50,  # Send ping every 50 seconds
        ws_ping_timeout=30    # Wait 30 seconds for pong response
    )
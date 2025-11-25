const express = require("express");
const path = require("path");
const app = express();
const PORT = 8080;

const bodyParser = require("body-parser");
const jsonParser = bodyParser.json();

app.use(express.json());
app.use(express.urlencoded({extended:true}));
app.use(express.static(path.join(__dirname,"public")));

app.get('/',(req,res)=>{
    res.status(200);
    res.send("This is the root url.");
});

app.post('/signal',(req,res)=>{
  let should_vibrate, current_event, button_sequence, vibration_timeout
    
    try{
        data = req.json()
        print(f"Received data: {data}")
        
        if (!data){
                res.status(400);
                res.send(['success=false', 'message=No JSON data received']);
        }
        
        // Check if we're receiving button press data from ESP32
        if (req.getHeader('device') === "ESP32"){
            // Check each button message
            button_messages = [
                "button1": req.getHeader('message1'),
                "button2": req.getHeader('message2'),
                "button3": req.getHeader('message3'),
                "button4": req.getHeader('message4')
            ];
            /*
            // Process button presses
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
            
            // Ensure only the last 3 button presses are stored
            if len(button_sequence) > 3:
                button_sequence.pop(0)  # Keep only the last 3 button presses
                print(f"Sequence window shifted. Current sequence: {button_sequence}")
            
            // If exactly 3 button presses are stored, check the sequence
            if len(button_sequence) == 3:
                print(f"Complete sequence detected: {button_sequence}")
                
                sequence_matched = True
                passcode_number = 0
                visitor_name = "Unknown"
                
                // Check predefined sequences and set appropriate event
                if (button_sequence == [2, 3, 4]){
                    print("*** Sequence [2,3,4] recognized - Rohit is here! ***")
                    passcode_number = 1
                    current_event = f"correct_input_{passcode_number}"
                    visitor_name = "Rohit"
                }elif (button_sequence == [2, 2, 2]){
                    print("*** Sequence [2,2,2] recognized - Francis is here! ***")
                    passcode_number = 2
                    current_event = f"correct_input_{passcode_number}"
                    visitor_name = "Francis"
                }elif (button_sequence == [3, 3, 3]){
                    print("*** Sequence [3,3,3] recognized - Michael is here! ***")
                    passcode_number = 3
                    current_event = f"correct_input_{passcode_number}"
                    visitor_name = "Michael"
                }else{
                    print(f"❌ Error! Unknown sequence {button_sequence} ❌")
                    current_event = "incorrect_input"
                    sequence_matched = False
                }
                // Set vibration based on sequence match
                should_vibrate = sequence_matched;
                
                // Clear any existing timeout thread
                if (vibration_timeout and vibration_timeout.is_alive())
                    vibration_timeout.cancel();
                
                if (sequence_matched){
                    // Set new timeout thread
                    vibration_timeout = threading.Timer(5.0, reset_vibration, [5])
                    vibration_timeout.daemon = True
                    vibration_timeout.start()
                    
                    // Send to client or queue with proper format
                    await send_message({
                        'triggerVibration': should_vibrate,
                        'currentEvent': current_event,
                        'passcode': str(passcode_number),
                        'visitorName': visitor_name
                    })
                    
                    print(f"Visitor notification sent: {visitor_name} (passcode: {passcode_number})")
                }else{
                    // For incorrect sequence
                    vibration_timeout = threading.Timer(5.0, reset_vibration, [5])
                    vibration_timeout.daemon = True
                    vibration_timeout.start()
                    
                    // Send to client or queue with proper format
                    await send_message({
                        'triggerVibration': should_vibrate, 
                        'currentEvent': current_event
                    })
                    
                    print("Incorrect sequence notification sent");
                }
                // Reset sequence after checking
                button_sequence = []
                print("Sequence reset for next visitor")
            
            return {
                'success': True,
                'triggerVibration': should_vibrate,
                'currentEvent': current_event,
                'currentSequence': button_sequence
            }
            */
        // For direct event specifiers (rarely used but supported)
        } else if (req.getHeader('event')){
            event_type = req.getHeader('event')
            print('Direct event request received: '+event_type);
            
            if (event_type === 'main_button_pressed'){
                /*should_vibrate = true
                current_event = 'main_button_pressed'
                
                // Clear any existing timeout thread
                if vibration_timeout and vibration_timeout.is_alive():
                    vibration_timeout.cancel()
                
                // Set new timeout thread
                vibration_timeout = threading.Timer(5.0, reset_vibration, [5])
                vibration_timeout.daemon = True
                vibration_timeout.start()
                
                // Send to client or queue with proper format
                await send_message({
                    'triggerVibration': should_vibrate, 
                    'currentEvent': current_event
                })
                */
                vibration_timeout = 5.0;
                res.send(['triggerVibration=should_vibrate','duration='+vibration_timeout]);
            }
            /*
            // For explicitly setting a visitor event without button sequence
            correct_input_regex = r'^correct_input_(\d+)$'
            match = re.match(correct_input_regex, event_type)
            
            if (match){
                passcode_number = match.group(1)
                print(f"Direct visitor passcode received: {passcode_number}")
                
                // Map passcode to visitor name
                visitor_names = {
                    "1": "Rohit",
                    "2": "Francis", 
                    "3": "Michael",
                    "221": "Sam",
                    "222": "Jon",
                    "223": "Mike"
                }
                visitor_name = visitor_names.get(passcode_number, "Unknown")
                
                should_vibrate = true;
                current_event = `correct_input_{passcode_number}`;
                
                // Clear any existing timeout thread
                if (vibration_timeout && vibration_timeout.is_alive())
                    vibration_timeout.cancel();
                
                // Set new timeout thread
                vibration_timeout = threading.Timer(5.0, reset_vibration, [5])
                vibration_timeout.daemon = true;
                vibration_timeout.start();
                
                // Send to client or queue with proper format
                await send_message({
                    'triggerVibration': should_vibrate,
                    'currentEvent': current_event,
                    'passcode': passcode_number,
                    'visitorName': visitor_name
                })
                
                res.send([
                    'triggerVibration=should_vibrate',
                    'passcode=passcode_number',
                    'visitorName=visitor_name'
                ]);
            }else{
              // If no recognized event was found
              print(`Unrecognized event type: {event_type}`);
              res.status(400);
              res.send(['success=false', `message=Unrecognized event type: {event_type}`]);
            }*/
        // If neither device nor event was found in the request
        } else {
          print("Invalid request format - missing device or event");
          res.status(400);
          res.send('success=false','message=Invalid request format - missing device or event']);
        }
    catch(Exception as e){
      print(`Error handling POST request: {e}`);
      res.status(500);
      res.send(['success=false',`message=Internal Server Error: {str(e)}`]);
    }
});

app.get('/signal',(req,res)=>{
  res.status(200);
  res.send(['triggerVibration=should_vibrate',
            'currentEvent=current_event']);
});

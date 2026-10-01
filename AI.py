import numpy as np
import cv2
import imutils

# Load the trained cascade model
gun_cascade = cv2.CascadeClassifier(r"C:\Users\ap735\OneDrive\Desktop\pr\Aditya\Cascade.xml")

if gun_cascade.empty():
    print("Error: Cascade file not found or invalid!")
    exit()

camera = cv2.VideoCapture(0)
gun_exist = False

while True:
    ret, frame = camera.read()
    if not ret:
        print("Failed to grab frame")
        break

    frame = imutils.resize(frame, width=500)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Reset gun_exist flag for each frame
    gun_exist = False

    # Detect gun in the frame
    gun = gun_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

    if len(gun) > 0:
        gun_exist = True

    # Draw rectangles around detected guns
    for (x, y, w, h) in gun:
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

    # Show the security feed
    cv2.imshow("Security Feed", frame)
    
    # Exit condition
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break

    # Print message if gun is detected
    if gun_exist:
        print("Gun detected!")

camera.release()
cv2.destroyAllWindows()
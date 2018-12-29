import numpy as np
import cv2
from matplotlib import pyplot as plt
from picamera.array import PiRGBArray
from picamera import PiCamera
import io
import time
import yaml
import requests

servurl = 'https://parkingpalserv.azurewebsites.net/Data/UpdateData'

# Read input img and grab reference file
#img = cv2.imread('EmptyLot.png', 1)
ref = r"refnew.yml"

# Set up window for final image
cv2.namedWindow('final', cv2.WINDOW_NORMAL)
cv2.resizeWindow('final', 1200,500)

# Open reference file, loop to grab spots and create contours and rectangles for each
with open(ref, 'r') as stream:
    lot_data = yaml.load(stream)
spot_contours = []
spot_bounding_rectangles = []
spot_mask = []
for spot in lot_data:
    points = np.array(spot['points'])
    rect = cv2.boundingRect(points)
    spot_contours.append(points)
    spot_bounding_rectangles.append(rect)
    mask = cv2.drawContours(np.zeros((rect[3], rect[2]),dtype=np.uint8),
        [points.copy()],contourIdx=-1,color=255,thickness=-1,lineType=cv2.LINE_8)
    mask = mask==255
    spot_mask.append(mask)

# Status array of bool and Buffer array for if spot is changing status
spot_status = [False]*len(lot_data)
spot_buffer = [None]*len(lot_data)

# Set up Camera
with PiCamera() as cam:
    cam.resolution = (1920, 1080)
    time.sleep(2)
    # Loop for updating parking spaces
    while(True):
        # Capture image from video for processing
        stream2 = io.BytesIO()
        cam.capture(stream2, format="png")
        data = np.fromstring(stream2.getvalue(), dtype=np.uint8)
        img = cv2.imdecode(data, 1)
    
        spots = 0
        occupied = 0
        handicapped = 0
        handicappedt = 0

        # Apply Gaussian Blur and color change to HLS then Grayscale
        blurredImg = cv2.GaussianBlur(img.copy(),(5,5),3)
        hls = cv2.cvtColor(blurredImg,cv2.COLOR_BGR2HLS)
        grayscale = cv2.cvtColor(hls,cv2.COLOR_BGR2GRAY)
        img_copy = img.copy()
    
        # Loop through spots in the lot and check/update status
        for idx, spot in enumerate(lot_data):
            points = np.array(spot['points'])
            rect = spot_bounding_rectangles[idx]
            # Crop image to the size of the space
            cropImg = grayscale[rect[1]:(rect[1]+rect[3]),rect[0]:(rect[0]+rect[2])]
            
            # # For Testing
            # cv2.imshow('cropImg', cropImg)

            # Get status by checking the standard deviation and arithmetic mean
            status = np.std(cropImg) < 32 and np.mean(cropImg) < 102

            # # For Testing
            # print(idx+1, status)
            # print(np.std(cropImg))
            # print(np.mean(cropImg))
            # print(np.min(cropImg))
            # while(True):
            #     k = cv2.waitKey(3)
            #     if k == ord('x'):
            #         break
            #     elif k == ord('e'):
            #         exit()

            # If status doesn't match saved status, mark 1 in buffer
            if status != spot_status[idx] and spot_buffer[idx] == None:
                spot_buffer[idx] = 1
            # If status is still different and buffer is 1
            elif status != spot_status[idx] and spot_buffer[idx] != None:
                spot_status[idx] = status
                spot_buffer[idx] = None
            # If status is same and buffer has value
            elif status == spot_status[idx] and spot_buffer[idx] != None:
                spot_buffer[idx] = None
            #print('Spot:', idx, '-', spot_status[idx])

        # Overlay
        for idx, spot in enumerate(lot_data):
            points = np.array(spot['points'])
            if spot_status[idx]:
                if idx >= 12 and idx <= 16:
                    color = (255,0,0)
                    handicapped += 1
                else:
                    color = (0,255,0)
                    spots += 1
            else:
                color = (0,0,255)
                if idx >= 12 and idx <= 16:
                    handicappedt += 1
                else:
                    occupied += 1
            cv2.drawContours(img_copy,[points],contourIdx=-1,color=color,
                thickness=2,lineType=cv2.LINE_8)

        # Display final image with spaces outlined as occupied or open
        cv2.imshow('final', img_copy)

        # Output Space info and send to server
        print('Total Spots:', spots+occupied+handicapped+handicappedt)
        print('Open:', spots)
        print('Open Handicapped', handicapped)
        print('Occupied:', occupied)
        print('Occupied Handicapped: ', handicappedt)
        print()

        payload = [('total', spots+occupied+handicapped+handicappedt), ('open', spots), ('handicapped', handicapped), ('occupied', occupied), ('handicappedo', handicappedt)]
        r = requests.post(servurl, data=payload)

        # Set to 0 for testing
        k = cv2.waitKey(3000)
        if k == ord('q'):
            break
        
cv2.destroyAllWindows()

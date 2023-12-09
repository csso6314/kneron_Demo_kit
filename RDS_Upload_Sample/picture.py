import cv2
import pygame
import numpy as np
import cv2
import os
import time
import shutil
import pygame

# initialize variables
cpu_serial = "0X02"
DeviceID = "0x7680"
#folder = 'Pictures/Dinasour/'
folder = 'Pictures/Helmet/'
#project_name = "ProjectD"	# append project name when calling filename_append_project_name()

username = 'admin'     # RDS account
password = '12345678'     # RDS password
#host = 'carview.cvprqxu67qc8.us-east-1.rds.amazonaws.com'    # RDS address version1
# 0921 RDS version2
#host = 'db-carview-v2.cvprqxu67qc8.us-east-1.rds.amazonaws.com'    # RDS address version2
#host = 'db-instai.cvprqxu67qc8.us-east-1.rds.amazonaws.com'
host = 'instai-web-rds.cvprqxu67qc8.us-east-1.rds.amazonaws.com'
port = '3306'         # RDS port
#database = 'carview'   # RDS name
database = 'myDB'     # version2
save_path = './to-be-uploaded'
file_destination = './uploaded'
if not os.path.isdir(file_destination):
    os.mkdir(file_destination)

if not os.path.isdir('./to-be-uploaded'):
    os.mkdir('./to-be-uploaded')  

def Capture(display,name,pos,size): # (pygame Surface, String, tuple, tuple)
    image = pygame.Surface(size)  # Create image surface
    image.blit(display,(0,0),(pos,size))  # Blit portion of the display to the image
    pygame.image.save(image,name)  # Save the image to the disk**

pygame.init()
pygame.display.set_caption("OpenCV camera stream on Pygame")
surface = pygame.display.set_mode([1280,720])
#0 Is the built in camera
cap = cv2.VideoCapture(0)
#Gets fps of your camera
fps = cap.get(cv2.CAP_PROP_FPS)
print("fps:", fps)
#If your camera can achieve 60 fps
#Else just have this be 1-30 fps
cap.set(cv2.CAP_PROP_FPS, 60)

while True:
    surface.fill([0,0,0])

    success, frame = cap.read()
    if not success:
        break

    #for some reasons the frames appeared inverted
    frame = np.fliplr(frame)
    frame = np.rot90(frame)

    # The video uses BGR colors and PyGame needs RGB
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    surf = pygame.surfarray.make_surface(frame)

    for event in pygame.event.get():
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_presses = pygame.mouse.get_pressed()
            x0, y0 = pygame.mouse.get_pos()

        if event.type == pygame.MOUSEBUTTONUP:
            x1, y1 = pygame.mouse.get_pos()
            if x0-x1>300:                                     #滑左多遠
                cap.release()                                  #釋放鏡頭
                cv2.destroyAllWindows()                        #關閉所有視窗
            elif mouse_presses[0]:
                localtime = time.localtime()
                result = time.strftime("%Y%m%d%H%M%S", localtime)
                os.chdir(save_path)
                #ontime=save_path+'/'+result
                if not os.path.isdir(result):
                    os.makedirs(result)
                    pictures_count=1
                os.chdir(result)
                #cv2.imwrite(cpu_serial + '_' + DeviceID + '_' + result +'_' + str(pictures_count) +' .jpg',surf)
                Capture(surf,cpu_serial + '_' + DeviceID + '_' + result +'_' + str(pictures_count) +' .jpg',(0,0),(640,640)) #相機調整
                print('save:',cpu_serial + '_' + DeviceID + '_' + result +'_' + str(pictures_count) +' .jpg')
                pictures_count = pictures_count + 1
                os.chdir('..')
                os.chdir('..')


        

    # Show the PyGame surface!
    surface.blit(surf, (0,0))
    pygame.display.flip()